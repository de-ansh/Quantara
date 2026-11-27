"""Balance check and rebalancing plan against the user's target mix."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import price_service, stock_lookup
from app.services.portfolio_balance import (
    Target,
    asset_class,
    balance_flags,
    rebalance_plan,
    trim_to,
)

MODERATE = Target.load(None, "Moderate")  # 70 / 20 / 5 / 5


def h(ticker, value, sector="Example sector", kind="stock", name=None, currency="INR", pnl=0.0):
    return SimpleNamespace(kind=kind, ticker=ticker, name=name or ticker, sector=sector, currency=currency,
                           market_value=value, unrealized_pnl=pnl)


def test_asset_class_matches_whole_words_only():
    assert asset_class(h("X.NS", 1, name="Bondway Engineering Ltd")) == "equity"
    assert asset_class(h("1", 1, kind="fund", sector="Debt Scheme - Corporate Bond Fund")) == "debt"
    assert asset_class(h("2", 1, kind="fund", sector="Debt Scheme - Liquid Fund")) == "cash"
    assert asset_class(h("G.NS", 1, sector="ETF", name="Example Gold ETF")) == "gold"


def test_target_defaults_from_the_risk_profile_until_saved():
    assert (MODERATE.equity, MODERATE.is_default) == (70.0, True)
    assert Target.load(None, None).equity == 70.0  # no profile: moderate
    saved = Target.load({"equity": 60, "debt": 30, "cash": 5, "gold": 5, "max_stock": 15, "max_sector": 30}, "Moderate")
    assert (saved.equity, saved.max_stock, saved.is_default) == (60.0, 15.0, False)


def test_a_short_horizon_makes_the_default_one_step_more_cautious():
    short = Target.load(None, "Aggressive", horizon_months=12)
    assert (short.equity, short.is_default) == (70.0, True)  # the Moderate mix
    assert "within 12 months" in (short.basis or "")
    assert Target.load(None, "Conservative", 6).equity == 50.0  # already the most cautious
    assert Target.load(None, "Aggressive", 60).equity == 85.0
    saved = {"equity": 90, "debt": 10, "cash": 0, "gold": 0, "max_stock": 20, "max_sector": 35}
    assert Target.load(saved, "Aggressive", 12).equity == 90.0  # a saved target is never changed


def test_trim_brings_the_holding_to_the_cap_of_what_remains():
    sold = trim_to(500, 1000, 20)  # 50% of 1000
    assert round((500 - sold) / (1000 - sold), 6) == 0.2
    assert trim_to(100, 1000, 20) == 0


def test_flags_a_big_company_and_sector_but_not_a_big_fund_or_etf():
    holdings = [
        h("BIG.NS", 500, sector="Banks"), h("B2.NS", 100, sector="Banks"), h("C.NS", 100, sector="Energy"),
        h("ETF.NS", 150, sector="ETF"), h("123", 150, kind="fund", sector="Equity Scheme - Flexi Cap Fund"),
    ]
    flags, mix = balance_flags(holdings, {}, {}, Target(100, 0, 0, 0))
    assert [(f.kind, f.ticker) for f in flags] == [("stock", "BIG.NS"), ("sector", None)]
    assert flags[0].title == "BIG.NS is 50% of this portfolio" and flags[0].amount == 375.0
    assert flags[1].title == "Banks is 60% of this portfolio"
    assert mix == {"INR": {"equity": 100}}


def test_limits_come_from_the_target():
    holdings = [h("A.NS", 300, sector="S1"), h("B.NS", 700, kind="fund", sector="Equity Scheme")]
    assert not balance_flags(holdings, {}, {}, Target(100, 0, 0, 0, max_stock=40))[0]
    assert [f.kind for f in balance_flags(holdings, {}, {}, Target(100, 0, 0, 0, max_stock=25))[0]] == ["stock"]


def test_mix_flag_names_the_biggest_drift_from_target():
    holdings = [h(f"E{i}.NS", 150, sector=f"S{i}") for i in range(6)]
    holdings.append(h("9", 100, kind="fund", sector="Debt Scheme - Gilt Fund"))
    flags, mix = balance_flags(holdings, {}, {}, MODERATE)
    assert mix["INR"] == {"equity": 90, "debt": 10}
    [flag] = [f for f in flags if f.kind == "mix"]
    assert flag.title == "Equity is 90%; your target is 70%"
    assert "debt 10% vs 20%" in flag.detail
    assert not [f for f in balance_flags(holdings, {}, {}, Target(90, 10, 0, 0))[0] if f.kind == "mix"]


def test_avoid_ratings_and_stocks_held_elsewhere_are_flagged_per_currency():
    holdings = [h(f"S{i}", 100, sector=f"Sector {i}") for i in range(6)] + [h("US1", 50, currency="USD", sector="Tech")]
    flags, mix = balance_flags(holdings, {"S1": "Avoid", "S2": "Hold"}, {"S3": ["Other"]}, Target(100, 0, 0, 0))
    assert [(f.kind, f.ticker) for f in flags if f.currency == "INR"] == [("verdict", "S1"), ("elsewhere", "S3")]
    assert any(f.title == "S3 is also in Other" for f in flags)
    assert [f.kind for f in flags if f.currency == "USD"] == ["stock", "sector"]  # one stock is 100% of the dollars
    assert set(mix) == {"INR", "USD"}


def test_plan_sells_avoid_then_losses_then_smallest_gains_and_adds_to_what_is_short():
    holdings = [
        h("WIN.NS", 300, pnl=150), h("SMALL.NS", 300, pnl=10), h("LOSS.NS", 200, pnl=-50), h("BAD.NS", 100, pnl=40),
        h("7", 100, kind="fund", sector="Debt Scheme - Gilt Fund"),
    ]  # 900 equity of 1000; target 50/50 means 400 equity out
    plan = rebalance_plan(holdings, Target(50, 50, 0, 0, max_stock=100), {"BAD.NS": "Avoid"})
    sells = [(t.ticker, t.amount, t.reason) for t in plan if t.action == "sell"]
    assert sells == [
        ("BAD.NS", 100, "rated Avoid"),
        ("LOSS.NS", 200, "at a loss, so no tax and it offsets gains"),
        ("SMALL.NS", 100, "smallest gain in this class"),
    ]
    assert [t.gain for t in plan if t.action == "sell"] == [40, -50, 3]
    assert [(t.asset_class, t.amount) for t in plan if t.action == "add"] == [("debt", 400)]


def test_new_money_goes_in_first_so_small_drifts_need_no_selling():
    holdings = [h("A.NS", 740, pnl=100), h("7", 160, kind="fund", sector="Debt Scheme - Gilt Fund"),
                h("8", 50, kind="fund", sector="Debt Scheme - Liquid Fund"), h("G.NS", 50, sector="ETF", name="Gold ETF")]
    # 74 / 16 / 5 / 5 against 70 / 20 / 5 / 5: within the drift, so nothing is sold
    assert rebalance_plan(holdings, MODERATE, {}) == []
    # Total 1,100: equity wants 770 (has 740), debt 220 (160), cash and gold 55 each (50)
    plan = rebalance_plan(holdings, MODERATE, {}, new_money=100)
    assert [(t.action, t.asset_class, t.amount) for t in plan] == [
        ("add", "equity", 30), ("add", "debt", 60), ("add", "cash", 5), ("add", "gold", 5)]


def test_a_company_over_its_limit_is_sold_before_losses():
    holdings = [h("HUGE.NS", 600, pnl=300), h("LOSS.NS", 400, pnl=-100)]
    plan = rebalance_plan(holdings, Target(60, 40, 0, 0, max_stock=40), {})
    assert [(t.ticker, t.reason) for t in plan if t.action == "sell"] == [("HUGE.NS", "over your company limit")]


@pytest.mark.asyncio
async def test_target_mix_defaults_saves_validates_and_resets(client: AsyncClient):
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    first = (await client.get("/api/v1/portfolio/target-mix", headers=headers)).json()
    assert first["is_default"] is True and first["equity"] + first["debt"] + first["cash"] + first["gold"] == 100

    mine = {"equity": 60, "debt": 30, "cash": 5, "gold": 5, "max_stock": 15, "max_sector": 30}
    saved = await client.put("/api/v1/portfolio/target-mix", headers=headers, json=mine)
    assert saved.status_code == 200 and saved.json()["is_default"] is False
    assert (await client.get("/api/v1/portfolio/target-mix", headers=headers)).json() == {**mine, "is_default": False, "basis": None}

    bad = await client.put("/api/v1/portfolio/target-mix", headers=headers, json={**mine, "equity": 70})
    assert bad.status_code == 422 and "add up to 100" in bad.text

    reset = (await client.delete("/api/v1/portfolio/target-mix", headers=headers)).json()
    assert reset["is_default"] is True
    assert (await client.get("/api/v1/portfolio/target-mix")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_balance_endpoint_flags_concentration_and_plans_against_the_target(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {})
    monkeypatch.setattr(stock_lookup, "last_close", lambda t: None)
    now = utcnow()
    db_session.add_all([
        Stock(ticker="AAA.NS", name="Example A", sector="Banks", price=100.0, price_updated_at=now),
        Stock(ticker="BBB.NS", name="Example B", sector="Energy", price=100.0, price_updated_at=now),
    ])
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def pos(t, shares):
        return {"ticker": t, "weight": 0.5, "shares": shares, "cost_basis": 90}

    main = await client.post("/api/v1/portfolio/", headers=headers, json={"name": "Main", "positions": [pos("AAA.NS", 9), pos("BBB.NS", 1)]})
    await client.post("/api/v1/portfolio/", headers=headers, json={"name": "Side", "positions": [pos("AAA.NS", 1), pos("BBB.NS", 1)]})
    await client.put("/api/v1/portfolio/target-mix", headers=headers,
                     json={"equity": 50, "debt": 50, "cash": 0, "gold": 0, "max_stock": 20, "max_sector": 35})
    url = f"/api/v1/portfolio/{main.json()['id']}/balance"
    body = (await client.get(url, headers=headers)).json()
    kinds = [(f["kind"], f["ticker"]) for f in body["flags"]]
    assert ("stock", "AAA.NS") in kinds and ("mix", None) in kinds and ("elsewhere", "BBB.NS") in kinds
    assert body["mix"] == {"INR": {"equity": 100}}
    assert body["target"]["equity"] == 50 and body["target"]["is_default"] is False
    assert [(t["action"], t["ticker"], t["amount"]) for t in body["plan"]] == [("sell", "AAA.NS", 500), ("add", None, 500)]

    # 1,000 of new money covers the debt gap without selling: 2,000 total, 1,000 each
    funded = (await client.get(url + "?new_money=1000", headers=headers)).json()
    assert [(t["action"], t["asset_class"], t["amount"]) for t in funded["plan"]] == [("add", "debt", 1000)]

    assert (await client.get(url + "?new_money=-5", headers=headers)).status_code == 422

    # All portfolios as one: AAA counts once at 10 shares (1,000 of 1,200), and the plan says where it's held
    together = (await client.get("/api/v1/portfolio/balance", headers=headers)).json()
    assert together["portfolio_id"] is None
    assert [f["title"] for f in together["flags"] if f["kind"] == "stock"] == ["Example A is 83% of all your portfolios"]
    assert not [f for f in together["flags"] if f["kind"] == "elsewhere"]
    [sell] = [t for t in together["plan"] if t["action"] == "sell"]
    assert (sell["ticker"], sell["amount"], sorted(sell["held_in"])) == ("AAA.NS", 600, ["Main", "Side"])
    assert (await client.get("/api/v1/portfolio/999999/balance", headers=headers)).status_code == 404

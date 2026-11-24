"""Balance check: concentration, sector tilt, asset mix against the risk profile, Avoid ratings, doubly held stocks."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import price_service, stock_lookup
from app.services.portfolio_balance import balance_flags, trim_to


def h(ticker, value, sector="Example sector", kind="stock", name=None, currency="INR"):
    return SimpleNamespace(kind=kind, ticker=ticker, name=name or ticker, sector=sector, currency=currency, market_value=value)


def test_trim_brings_the_holding_to_the_cap_of_what_remains():
    sold = trim_to(500, 1000, 20)  # 50% of 1000
    assert round((500 - sold) / (1000 - sold), 6) == 0.2
    assert trim_to(100, 1000, 20) == 0


def test_flags_a_big_company_and_sector_but_not_a_big_fund_or_etf():
    holdings = [
        h("BIG.NS", 500, sector="Banks"), h("B2.NS", 100, sector="Banks"), h("C.NS", 100, sector="Energy"),
        h("ETF.NS", 150, sector="ETF"), h("123", 150, kind="fund", sector="Equity Scheme - Flexi Cap Fund"),
    ]
    flags, mix = balance_flags(holdings, {}, {}, None)
    assert [(f.kind, f.ticker) for f in flags] == [("stock", "BIG.NS"), ("sector", None)]
    assert flags[0].title == "BIG.NS is 50% of this portfolio" and flags[0].amount == 375.0
    assert flags[1].title == "Banks is 60% of this portfolio"
    assert mix == {"INR": {"equity": 100.0}}


def test_equity_above_the_profile_ceiling_and_cash_like_holdings_count_apart():
    holdings = [
        h("A.NS", 150), h("B.NS", 150), h("C.NS", 150), h("D.NS", 150), h("E.NS", 150),
        h("CASH.NS", 150, sector="ETF", name="Example Liquid ETF"), h("9", 100, kind="fund", sector="Debt Scheme - Gilt Fund"),
    ]
    flags, mix = balance_flags(holdings, {}, {}, "Conservative")
    assert mix["INR"] == {"equity": 75.0, "cash": 15.0, "debt": 10.0}
    [flag] = [f for f in flags if f.kind == "mix"]
    assert flag.title == "Equity is 75% of this portfolio" and flag.amount == 150.0  # 750 -> 600 of 1000
    assert not [f for f in balance_flags(holdings, {}, {}, "Aggressive")[0] if f.kind == "mix"]


def test_avoid_ratings_and_stocks_held_elsewhere_are_flagged_per_currency():
    holdings = [h(f"S{i}", 100, sector=f"Sector {i}") for i in range(6)] + [h("US1", 50, currency="USD", sector="Tech")]
    flags, mix = balance_flags(holdings, {"S1": "Avoid", "S2": "Hold"}, {"S3": ["Other"]}, None)
    assert [(f.kind, f.ticker) for f in flags if f.currency == "INR"] == [("verdict", "S1"), ("elsewhere", "S3")]
    assert any(f.title == "S3 is also in Other" for f in flags)
    assert [f.kind for f in flags if f.currency == "USD"] == ["stock", "sector"]  # one stock is 100% of the dollars
    assert set(mix) == {"INR", "USD"}


@pytest.mark.asyncio
async def test_balance_endpoint_flags_concentration_and_other_portfolios(client: AsyncClient, db_session, monkeypatch):
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
    body = (await client.get(f"/api/v1/portfolio/{main.json()['id']}/balance", headers=headers)).json()
    kinds = [(f["kind"], f["ticker"]) for f in body["flags"]]
    assert ("stock", "AAA.NS") in kinds and ("elsewhere", "AAA.NS") in kinds and ("elsewhere", "BBB.NS") in kinds
    assert body["mix"] == {"INR": {"equity": 100.0}}

    missing = await client.get("/api/v1/portfolio/999999/balance", headers=headers)
    assert missing.status_code == 404

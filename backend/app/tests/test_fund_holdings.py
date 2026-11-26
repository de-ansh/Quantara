"""Look-through: what each held fund owns (from Groww), counted in the mix and in company exposure."""

import json
from datetime import date, timedelta
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.clock import utcnow
from app.models.listed_security import ListedSecurity
from app.models.mutual_fund import FundHolding, MutualFund
from app.models.portfolio import Portfolio, PortfolioFund, PortfolioPosition
from app.models.stock import Stock
from app.models.user import User
from app.services import fund_holdings, price_service, stock_lookup
from app.services.fund_holdings import (
    fetch_scheme,
    norm_company,
    parse_scheme,
    refresh_fund_holdings,
)
from app.services.portfolio_balance import (
    FundLine,
    Target,
    balance_flags,
    exposures,
    rebalance_plan,
    split,
)


def groww(code: int, lines: list[tuple[str, str, float]], regular: str | None = None) -> dict:
    return {"scheme_code": str(code), "regular_search_id": regular, "holdings": [
        {"company_name": n, "nature_name": k, "sector_name": "Example", "corpus_per": w,
         "portfolio_date": "2030-01-30T18:30:00.000Z"} for n, k, w in lines]}


def test_company_names_compare_without_suffixes():
    assert norm_company("Example Bank Ltd.") == norm_company("EXAMPLE BANK LIMITED") == "example bank"
    assert norm_company("A & B Industries") == "a b industries"


def test_parse_reads_kinds_weights_and_the_indian_portfolio_date():
    as_of, rows = parse_scheme(groww(1, [("Example Bank Ltd", "EQUITY", 60), ("GOI 2034", "DEBT", 30),
                                         ("TREPS", "CASH", 9.5), ("Example REIT", "REALEST", 0.5), ("Nothing", "EQUITY", 0)]))
    assert as_of == date(2030, 1, 31)
    assert [(r["name"], r["kind"], r["weight"]) for r in rows] == [
        ("Example Bank Ltd", "equity", 60.0), ("GOI 2034", "debt", 30.0), ("TREPS", "cash", 9.5), ("Example REIT", "other", 0.5)]


@pytest.mark.asyncio
async def test_finding_a_regular_plan_through_its_direct_plan_page(monkeypatch):
    monkeypatch.setattr(fund_holdings, "PAUSE_SECONDS", 0)
    pages = {
        "example-flexi-direct": groww(111, [], regular="example-flexi-regular"),
        "example-flexi-regular": groww(222, [("Example Bank Ltd", "EQUITY", 100)]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in request.url.path and "st_p_query" in request.url.path:
            return httpx.Response(200, json={"data": {"content": [
                {"entity_type": "Scheme", "search_id": "example-flexi-direct", "title": "Example Flexi Cap Fund"}]}})
        slug = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=pages[slug]) if slug in pages else httpx.Response(404)

    fund = SimpleNamespace(scheme_code=222, name="Example Flexi Cap Fund - Regular Plan - Growth", groww_id=None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await fetch_scheme(client, fund)
        assert found and found[0] == "example-flexi-regular"
        assert await fetch_scheme(client, SimpleNamespace(scheme_code=999, name="Example Flexi", groww_id=None)) is None


@pytest.mark.asyncio
async def test_refresh_stores_held_funds_matches_tickers_and_waits_a_week(db_session, monkeypatch):
    user = (await db_session.execute(select(User))).scalars().first()
    db_session.add_all([
        MutualFund(scheme_code=300001, name="Example Fund - Direct Plan - Growth", nav=10, nav_date=date(2030, 1, 31)),
        MutualFund(scheme_code=300002, name="Unheld Fund", nav=10, nav_date=date(2030, 1, 31)),
        ListedSecurity(ticker="EXBANK.NS", name="EXAMPLE BANK LIMITED", exchange="NSE"),
        ListedSecurity(ticker="EXBANK.BO", name="Example Bank Limited", exchange="BSE"),
    ])
    await db_session.flush()
    pf = Portfolio(user_id=user.id, name="Funds")
    pf.funds.append(PortfolioFund(scheme_code=300001, units=10, cost_basis=8))
    db_session.add(pf)
    await db_session.commit()
    asked: list[int] = []

    async def fake_fetch(client, fund):
        asked.append(fund.scheme_code)
        return "example-fund", groww(fund.scheme_code, [("Example Bank Ltd", "EQUITY", 70), ("Example Bank Ltd", "DEBT", 30)])

    monkeypatch.setattr(fund_holdings, "fetch_scheme", fake_fetch)
    now = utcnow()
    assert await refresh_fund_holdings(db_session, now) == 1
    rows = (await db_session.execute(select(FundHolding).order_by(FundHolding.weight.desc()))).scalars().all()
    assert [(r.ticker, r.kind, r.weight) for r in rows] == [("EXBANK.NS", "equity", 70), (None, "debt", 30)]  # bonds aren't the stock
    fund = await db_session.get(MutualFund, 300001)
    assert (fund.groww_id, fund.holdings_as_of) == ("example-fund", date(2030, 1, 31))
    assert await refresh_fund_holdings(db_session, now + timedelta(days=3)) == 0
    assert await refresh_fund_holdings(db_session, now + timedelta(days=8)) == 1
    assert asked == [300001, 300001]  # never the unheld fund


def h(ticker, value, kind="stock", name=None, sector="Example", pnl=0.0):
    return SimpleNamespace(kind=kind, ticker=ticker, name=name or ticker, sector=sector, currency="INR",
                           market_value=value, unrealized_pnl=pnl)


LOOK = {"9001": [FundLine("Example Bank Ltd", "EXBANK.NS", "equity", 50), FundLine("Other Co Ltd", None, "equity", 20),
                 FundLine("GOI 2034", None, "debt", 30)]}


def test_a_fund_counts_by_what_it_owns():
    fund = h("9001", 1000, kind="fund", name="Example Hybrid Fund")
    assert split(fund, LOOK) == {"equity": 700.0, "debt": 300.0}
    assert split(fund, {}) == {"equity": 1000.0}  # no holdings yet: by its name


def test_exposure_adds_direct_and_fund_stakes_and_flags_the_total():
    holdings = [h("EXBANK.NS", 100, name="Example Bank"), h("A.NS", 400, sector="A"), h("B.NS", 500, sector="B"),
                h("9001", 1000, kind="fund", name="Example Hybrid Fund")]
    top = exposures(holdings, LOOK)
    bank = next(e for e in top if e.ticker == "EXBANK.NS")
    assert (bank.direct, bank.via_funds, bank.funds) == (100, 500, ["Example Hybrid Fund"])
    assert any(e.name == "Other Co Ltd" and e.ticker is None and e.via_funds == 200 for e in top)

    flags, mix = balance_flags(holdings, {}, {}, Target(85, 15, 0, 0, max_stock=25, max_sector=100), look=LOOK)
    assert mix["INR"] == {"equity": 85, "debt": 15}
    [bank_flag] = [f for f in flags if f.kind == "stock" and f.ticker == "EXBANK.NS"]
    assert bank_flag.title == "Example Bank is 30% of this portfolio, counting your funds"
    assert "₹100 directly and ₹500 through 1 fund (Example Hybrid Fund)" in bank_flag.detail
    assert bank_flag.amount == 100  # only direct shares can be sold, and all of them still leaves it over
    # Without look-through the bank is 5% and nothing is flagged
    assert not [f for f in balance_flags(holdings, {}, {}, Target(85, 15, 0, 0, max_stock=25, max_sector=100))[0]
                if f.ticker == "EXBANK.NS"]


def test_the_plan_sees_a_funds_debt_and_sells_from_main_classes():
    holdings = [h("A.NS", 500, pnl=50), h("9001", 500, kind="fund", name="Example Hybrid Fund", pnl=200)]
    # 500 + 350 equity, 150 debt: against 70/30 equity is 85% (15 over), so 150 of equity goes to debt
    plan = rebalance_plan(holdings, Target(70, 30, 0, 0, max_stock=100), {}, look=LOOK)
    assert [(t.action, t.ticker or t.asset_class, t.amount) for t in plan] == [("sell", "A.NS", 150), ("add", "debt", 150)]


@pytest.mark.asyncio
async def test_balance_endpoint_returns_exposures_and_which_funds_are_counted(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {})
    monkeypatch.setattr(stock_lookup, "last_close", lambda t: None)
    user = (await db_session.execute(select(User).where(User.email == "test@quantara.com"))).scalar_one()
    db_session.add_all([
        Stock(ticker="EXBANK.NS", name="Example Bank", sector="Banks", price=100.0, price_updated_at=utcnow()),
        MutualFund(scheme_code=400001, name="Example Hybrid Fund - Direct Plan - Growth", nav=10,
                   nav_date=date(2030, 1, 31), holdings_as_of=date(2030, 1, 31)),
        MutualFund(scheme_code=400002, name="Example New Fund - Direct Plan - Growth", nav=10, nav_date=date(2030, 1, 31)),
    ])
    await db_session.flush()
    db_session.add_all([FundHolding(scheme_code=400001, name="Example Bank Ltd", ticker="EXBANK.NS", kind="equity", weight=60),
                        FundHolding(scheme_code=400001, name="GOI 2034", kind="debt", weight=40)])
    pf = Portfolio(user_id=user.id, name="Mixed")
    pf.positions.append(PortfolioPosition(ticker="EXBANK.NS", weight=0.5, shares=10, cost_basis=90))
    pf.funds.extend([PortfolioFund(scheme_code=400001, units=100, cost_basis=9), PortfolioFund(scheme_code=400002, units=10, cost_basis=9)])
    db_session.add(pf)
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    body = (await client.get(f"/api/v1/portfolio/{pf.id}/balance", headers=headers)).json()
    bank = body["exposures"][0]
    assert (bank["ticker"], bank["direct"], bank["via_funds"], bank["pct"]) == ("EXBANK.NS", 1000.0, 600.0, 76.19)
    assert body["funds_looked_through"] == ["Example Hybrid Fund - Direct Plan - Growth"]
    assert body["funds_not_looked_through"] == ["Example New Fund - Direct Plan - Growth"]
    assert body["holdings_as_of"] == "2030-01-31"
    assert body["mix"]["INR"]["debt"] == 19  # 400 of the fund's 1,000 is bonds, of 2,100 in all
    json.dumps(body)

    # The stock page: the same company through funds, matched on the symbol whichever exchange the page shows
    mine = (await client.get("/api/v1/portfolio/exposure/exbank.bo", headers=headers)).json()
    assert (mine["via_funds"], mine["holdings_as_of"]) == (600.0, "2030-01-31")
    assert mine["funds"] == [{"name": "Example Hybrid Fund - Direct Plan - Growth", "amount": 600.0, "weight": 60.0}]
    none = (await client.get("/api/v1/portfolio/exposure/OTHER.NS", headers=headers)).json()
    assert (none["via_funds"], none["funds"], none["holdings_as_of"]) == (0, [], None)
    assert (await client.get("/api/v1/portfolio/exposure/EXBANK.NS")).status_code in (401, 403)

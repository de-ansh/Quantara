"""Tests for AMFI NAV loading, matching broker fund rows to schemes, and funds in portfolios."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.models.listed_security import ListedSecurity
from app.models.mutual_fund import MutualFund
from app.services import mutual_funds
from app.services.mutual_funds import fund_key, parse_nav_all, parse_scheme_master, refresh_funds

# AMFI's layout: a header, category lines, fund-house lines, then rows; older rows leave plan and option blank
NAV_ALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Flexi Cap Fund)

Example Mutual Fund

200001;INF000X01011;-;Example Flexi Cap Fund;Direct Plan;Growth Option;50.5;19-Nov-2026
200002;INF000X01029;INF000X01037;Example Flexi Cap Fund;Direct Plan;IDCW Option;20.25;19-Nov-2026
200003;INF000X01045;-;Example Flexi Cap Fund;Regular Plan;Growth;45.0;19-Nov-2026

Open Ended Schemes(Equity Scheme - Mid Cap Fund)

200010;INF000X01102;-;Example Midcap Fund;;;80.0;19-Nov-2026
200011;INF000X01110;-;Example Midcap Fund;;;70.0;19-Nov-2026
200012;INF000X01128;-;Example Midcap Fund;;;N.A.;19-Nov-2026
200020;INF000X01201;-;Example Nifty ETF;;;250.0;19-Nov-2026
"""
MASTER = """AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,Scheme Minimum Amount,Launch Date, Closure Date,ISIN
Example AMC,200010,Example Midcap Fund,Open Ended,Equity Scheme - Mid Cap Fund,Example Midcap Fund-Direct Plan-Growth Option,500,01-Jan-2014,,INF000X01102
Example AMC,200011,Example Midcap Fund,Open Ended,Equity Scheme - Mid Cap Fund,Example Midcap Fund-Regular Plan-Growth Option,500,01-Jan-2014,,INF000X01110
"""


async def _headers(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def amfi(monkeypatch):
    """Serve the sample files instead of AMFI; returns the list of URLs asked for."""
    asked: list[str] = []

    async def fake_download(url: str) -> str | None:
        asked.append(url)
        return NAV_ALL if url == mutual_funds.NAV_ALL else MASTER

    monkeypatch.setattr(mutual_funds, "_download", fake_download)
    return asked


def test_parse_nav_all_reads_rows_and_categories():
    funds = parse_nav_all(NAV_ALL)
    assert set(funds) == {200001, 200002, 200003, 200010, 200011, 200020}  # the N.A. row is dropped
    direct = funds[200001]
    assert direct.name == "Example Flexi Cap Fund - Direct Plan - Growth Option"
    assert direct.category == "Equity Scheme - Flexi Cap Fund"
    assert (direct.nav, direct.nav_date, direct.isin, direct.isin_reinvest) == (50.5, date(2026, 11, 19), "INF000X01011", None)
    assert funds[200002].isin_reinvest == "INF000X01037"
    assert funds[200010].name == "Example Midcap Fund" and funds[200010].category == "Equity Scheme - Mid Cap Fund"


def test_parse_scheme_master():
    assert parse_scheme_master(MASTER) == {
        200010: "Example Midcap Fund-Direct Plan-Growth Option",
        200011: "Example Midcap Fund-Regular Plan-Growth Option",
    }


def test_fund_key_lines_up_broker_and_amfi_names():
    # Groww writes "<scheme> Direct Growth"; AMFI spells out plan and option, sometimes twice
    assert fund_key("Parag Parikh Flexi Cap Fund Direct Growth") == fund_key("Parag Parikh Flexi Cap Fund - Direct Plan - Growth")
    assert fund_key("Example Large Cap Fund Direct Growth") == fund_key("Example Large Cap Fund - Direct Plan Growth Plan - Growth Option")
    assert fund_key("Example Mid Cap Fund Direct Growth") == fund_key("Example Midcap Fund-Direct Plan-Growth Option")
    assert fund_key("Example Fund Direct Growth")[1:] == ("direct", "growth")
    assert fund_key("Example Fund - Regular Plan - IDCW Payout")[1:] == ("regular", "other")
    # Zerodha Coin writes only the scheme name; read from a broker row, that means Direct Growth
    assert fund_key("Parag Parikh Flexi Cap Fund", unstated="direct") == fund_key("Parag Parikh Flexi Cap Fund - Direct Plan - Growth")
    assert fund_key("Example Fund Regular", unstated="direct")[1:] == ("regular", "growth")
    assert fund_key("Example Fund IDCW", unstated="direct")[1:] == ("direct", "other")
    assert fund_key("Example Fund")[1:] == ("regular", "other")  # AMFI's own old single-plan names: unchanged


@pytest.mark.asyncio
async def test_refresh_loads_navs_then_keeps_the_previous_one(db_session, amfi, monkeypatch):
    assert await refresh_funds(db_session) == 6
    midcap = await db_session.get(MutualFund, 200010)
    assert midcap.name == "Example Midcap Fund-Direct Plan-Growth Option"  # the master's full name
    assert midcap.prev_nav is None
    assert await refresh_funds(db_session) == 0  # fresh: no second download
    assert len(amfi) == 2

    # Next day's file: yesterday's NAV becomes the previous one
    monkey_nav = NAV_ALL.replace("80.0;19-Nov-2026", "82.0;20-Nov-2026")

    async def next_day(url: str) -> str | None:
        return monkey_nav if url == mutual_funds.NAV_ALL else MASTER

    monkeypatch.setattr(mutual_funds, "_download", next_day)
    await refresh_funds(db_session, max_age=timedelta(0))
    await db_session.refresh(midcap)
    assert (midcap.nav, midcap.prev_nav, midcap.nav_date) == (82.0, 80.0, date(2026, 11, 20))


@pytest.mark.asyncio
async def test_match_and_save_funds_then_value_them(client: AsyncClient, db_session, amfi):
    db_session.add(ListedSecurity(ticker="EXNIFTY.NS", name="Example Nifty ETF", exchange="NSE", isin="INF000X01201", is_etf=True))
    await db_session.commit()
    headers = await _headers(client)

    matched = (await client.post("/api/v1/portfolio/funds/match", headers=headers, json={"funds": [
        {"name": "Example Flexi Cap Fund Direct Growth"},   # Groww: name only
        {"isin": "INF000X01110", "name": "whatever"},       # Coin: ISIN wins
        {"isin": "INF000X01201"},                           # a listed ETF stays a stock
        {"name": "Nothing Like This Fund Direct Growth"},
        {"name": "Example Flexi Cap Fund"},                 # Coin: bare name, so the direct growth plan
    ]})).json()["matches"]
    assert [m and m["scheme_code"] for m in matched] == [200001, 200011, None, None, 200001]  # the table loaded on first use

    created = await client.post("/api/v1/portfolio/", headers=headers, json={
        "name": "Funds", "funds": [
            {"scheme_code": 200001, "units": 100, "cost_basis": 40},
            {"scheme_code": 200011, "units": 10},
        ],
    })
    assert created.status_code == 201
    body = created.json()
    assert body["positions"] == []
    assert body["funds"][0] == {"scheme_code": 200001, "units": 100.0, "cost_basis": 40.0,
                                "name": "Example Flexi Cap Fund - Direct Plan - Growth Option"}

    perf = (await client.get(f"/api/v1/portfolio/{body['id']}/performance", headers=headers)).json()
    flexi = next(h for h in perf["holdings"] if h["ticker"] == "200001")
    assert flexi["kind"] == "fund" and flexi["currency"] == "INR" and flexi["price"] == 50.5
    assert flexi["market_value"] == 5050.0 and flexi["unrealized_pnl"] == 1050.0
    inr = perf["totals"][0]
    assert inr["market_value"] == 5050.0 + 700.0
    assert set(inr["sector_allocation"]) == {"Equity Scheme - Flexi Cap Fund", "Equity Scheme - Mid Cap Fund"}

    # Replacing the funds; a scheme AMFI doesn't have is refused
    pid = body["id"]
    bad = await client.put(f"/api/v1/portfolio/{pid}", headers=headers, json={"funds": [{"scheme_code": 999999, "units": 1}]})
    assert bad.status_code == 422
    updated = await client.put(f"/api/v1/portfolio/{pid}", headers=headers, json={"funds": [{"scheme_code": 200003, "units": 5}]})
    assert [f["scheme_code"] for f in updated.json()["funds"]] == [200003]

    deleted = await client.delete(f"/api/v1/portfolio/{pid}", headers=headers)
    assert deleted.status_code == 204

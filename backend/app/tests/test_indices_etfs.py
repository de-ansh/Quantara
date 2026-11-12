"""Indices list and constituents, and the ETF list, from NSE feeds."""

import pytest

from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import nse_market
from app.services.nse_market import (
    etf_category,
    index_file_candidates,
    parse_etfs,
    parse_index_list,
)

NIFTY50 = {"key": "INDICES ELIGIBLE IN DERIVATIVES", "index": "NIFTY 50", "last": 25240.6, "percentChange": -0.06,
           "pe": "20.59", "pb": "3.1", "dy": "1.35", "yearHigh": 26373.2, "yearLow": 22179.9, "perChange30d": 12.87,
           "perChange365d": -2.45, "advances": "20", "declines": "30"}
CSV = "Company Name,Industry,Symbol,Series,ISIN Code\nTata Consultancy Services Ltd.,IT,TCS,EQ,X\nInfosys Ltd.,IT,INFY,EQ,Y\n"


def test_index_list_parses_nse_strings():
    [idx] = parse_index_list([NIFTY50, {"key": "X"}])
    assert idx == {"name": "NIFTY 50", "category": "Indices Eligible In Derivatives", "last": 25240.6, "change_pct": -0.06,
                   "pe": 20.59, "pb": 3.1, "dividend_yield": 1.35, "year_high": 26373.2, "year_low": 22179.9,
                   "return_30d": 12.87, "return_1y": -2.45, "advances": 20, "declines": 30}


def test_index_file_names_follow_both_nse_patterns():
    assert index_file_candidates("NIFTY 50") == ["ind_nifty50list.csv", "ind_nifty50_list.csv"]
    assert index_file_candidates("NIFTY INDIA DEFENCE")[1] == "ind_niftyindiadefence_list.csv"


@pytest.mark.parametrize("underlying,category", [
    ("Domestic price of Silver- based on LBMA Silver daily spot fixing price", "Silver"),
    ("Domestic Price of Gold", "Gold"),
    ("NASDAQ 100 Index", "International"),
    ("Nifty 1D Rate Index", "Debt"),
    ("CRISIL IBX Gilt Index - April 2033", "Debt"),
    ("Nifty Bank Index", "Banking & financial"),
    ("Nifty IT Index", "Sector & theme"),
    ("Nifty200 Momentum 30 Index", "Factor & strategy"),
    ("Nifty 50 Index", "Broad market"),
])
def test_etf_categories(underlying, category):
    assert etf_category(underlying) == category


def test_etf_category_falls_back_to_the_symbol():
    assert etf_category("Index", "LIQUIDBEES") == "Debt"
    assert etf_category("Index", "GOLDBEES") == "Gold"
    assert etf_category("Government Securities", "GILT5YBEES") == "Debt"


def test_etfs_compute_premium_and_sort_by_traded_value():
    rows = [
        {"symbol": "SMALL", "assets": "Nifty 50 Index", "ltP": "100", "nav": "100", "trdVal": "1000", "per": "0.1"},
        {"symbol": "SILVERBEES", "assets": "Domestic price of Silver", "ltP": "171.78", "nav": "176.6596",
         "trdVal": "4185174352.23", "per": "-2.86", "wkhi": "360", "wklo": "143.65", "perChange30d": -15.24, "perChange365d": 19.45},
    ]
    etfs = parse_etfs(rows)
    assert [e["symbol"] for e in etfs] == ["SILVERBEES", "SMALL"]
    assert etfs[0]["premium_pct"] == -2.76 and etfs[0]["category"] == "Silver" and etfs[1]["premium_pct"] == 0.0


@pytest.mark.asyncio
async def test_index_endpoint_joins_constituents_with_our_data(client, db_session, monkeypatch):
    db_session.add(Stock(ticker="TCS.NS", name="TCS", sector="IT", price=3100, previous_close=3000, market_cap=1.1e13,
                         pe_ratio=24, return_1y_pct=-20, price_updated_at=utcnow()))
    await db_session.commit()

    async def nse(path, ttl=0):
        return {"data": [NIFTY50]} if path == "api/allIndices" else None

    async def index_file(filename):
        return CSV if filename == "ind_nifty50list.csv" else None

    monkeypatch.setattr(nse_market, "nse_json", nse)
    monkeypatch.setattr(nse_market, "_index_file", index_file)
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/market/indices/nifty%2050", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["index"]["pe"] == 20.59
    assert [m["ticker"] for m in body["members"]] == ["TCS.NS", "INFY.NS"]  # largest first; untracked last
    assert body["members"][0]["change_pct"] == 3.33 and body["members"][1]["price"] is None

    assert (await client.get("/api/v1/market/indices/NIFTY%20NOPE", headers=headers)).status_code == 404
    listed = await client.get("/api/v1/market/indices", headers=headers)
    assert [i["name"] for i in listed.json()] == ["NIFTY 50"]
    assert (await client.get("/api/v1/market/etfs", headers=headers)).json() is None  # feed down: None, not []

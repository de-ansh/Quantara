"""The listed-securities directory: parsing the exchange lists and searching beyond tracked stocks."""

import pytest

from app.models.listed_security import ListedSecurity
from app.models.stock import Stock
from app.services import stock_directory
from app.services.stock_directory import parse_bse, parse_nse, parse_nse_etfs, parse_us

NSE = """SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE
TCS,Tata Consultancy Services Limited,EQ,25-AUG-2004,1,1,INE467B01029,1
TMPV,Tata Motors Passenger Vehicles Limited,EQ,14-OCT-2025,2,1,INE155A01022,2
"""
BSE = """TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,FinInstrmNm
2026-11-06,2026-11-06,CM,BSE,STK,532540,INE467B01029,TCS,A,TATA CONSULTANCY SERVICES LTD.
2026-11-06,2026-11-06,CM,BSE,STK,500002,INE117A01099,BSEONLY,A,BSE ONLY LIMITED
2026-11-06,2026-11-06,CM,BSE,MF,900001,INF000000001,SOMEMF,A,SOME FUND
2026-11-06,2026-11-06,CM,BSE,STK,543000,INF204KB14I2,NIFTYBEES,F,Nippon India Mutual Fund
2026-11-06,2026-11-06,CM,BSE,STK,543001,INF769K01AA1,ESG,F,Mirae Asset Mutual Fund
2026-11-06,2026-11-06,CM,BSE,STK,543002,IN9117A01099,BSEONLYPP,A,BSE ONLY LIMITED
"""
NSE_ETF = """Symbol,Underlying Asset,SecurityName,DateofListing,MarketLot,ISINNumber,FaceValue,ETF Underlying,Underlying Key
NIFTYBEES,Nifty 50,NIPINDETFNIFTYBEES,08-Jan-02,1,INF204KB14I2,1,EQUITY,Nifty 50
ITETF,Mirae Asset Nifty IT ETF,MIRAEITETF,20-Jul-23,1,INF769K01KH1,10,EQUITY,Nifty IT
"""
US = """Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares
Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N
Y|BRK.B|Berkshire Hathaway Inc. New Common Stock|N| |N|100|N||BRK.B|BRK.B|N
Y|BRK.A|Berkshire Hathaway Inc. Common Stock|N| |N|1|N||BRK.A|BRK.A|N
Y|GOOGN|Alphabet Inc. - Depositary Shares representing a 1/20th Interest in a Share of Series B Mandatory Convertible Preferred Stock|Q|Q|N|100|N|N||GOOGN|N
Y|TRNZ|Trinity Capital Inc. 7.875% Notes due 2029|Q|G|N|100|N|N||TRNZ|N
Y|ZEOWW|Zeo Energy Corporation - Warrants|Q|S|N|100|N|N||ZEOWW|N
Y|PFBC|Preferred Bank - Common Stock|Q|Q|N|100|N|N||PFBC|N
Y|SPY|SPDR S&P 500 ETF Trust|P| |Y|100|N||SPY|SPY|N
Y|ZXZZT|NASDAQ TEST STOCK|Q|G|N|100|Y|N||ZXZZT|N
Y|ABC$A|Preferred Series A|N| |N|100|N||ABC$A|ABC$A|N
File Creation Time: 1107202600:00|||||||||||
"""


def test_parsers_map_to_yahoo_tickers_and_dedupe_bse_by_isin():
    nse = parse_nse(NSE) + parse_nse_etfs(NSE_ETF)
    assert [r["ticker"] for r in nse] == ["TCS.NS", "TMPV.NS", "NIFTYBEES.NS", "ITETF.NS"]
    assert nse[2]["name"] == "NIFTYBEES – Nifty 50 ETF" and nse[2]["is_etf"]
    assert nse[3]["name"] == "ITETF – Mirae Asset Nifty IT ETF"  # no "ETF ETF"
    bse = {r["ticker"]: r for r in parse_bse(BSE, {r["isin"] for r in nse})}
    # TCS and NIFTYBEES are on NSE (same ISIN), MF isn't a stock; a fund-house-only name leads with its symbol
    assert set(bse) == {"BSEONLY.BO", "ESG.BO", "BSEONLYPP.BO"}
    assert bse["BSEONLYPP.BO"]["name"] == "BSE ONLY LIMITED (Partly Paid)"
    assert bse["ESG.BO"]["name"] == "ESG – Mirae Asset Mutual Fund" and bse["ESG.BO"]["is_etf"]
    us = {r["ticker"]: r for r in parse_us(US)}
    # test issue, $-preferred, depositary preferred, notes, warrants and footer dropped; a bank named Preferred kept
    assert set(us) == {"AAPL", "BRK-B", "BRK-A", "SPY", "PFBC"}
    assert us["AAPL"]["exchange"] == "NASDAQ" and us["SPY"]["is_etf"]
    assert us["AAPL"]["name"] == "Apple Inc." and us["PFBC"]["name"] == "Preferred Bank"
    assert us["BRK-A"]["name"] == "Berkshire Hathaway Inc. Class A" != us["BRK-B"]["name"]


async def _headers(client):
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_search_reaches_untracked_listings_and_track_starts_tracking(client, db_session):
    db_session.add(Stock(ticker="TCS.NS", name="Tata Consultancy Services Ltd"))
    db_session.add(Stock(ticker="TATAMOTORS.NS", name="Tata Motors Ltd"))  # delisted: no exchange lists it
    db_session.add_all([
        ListedSecurity(ticker="TCS.NS", name="Tata Consultancy Services Limited", exchange="NSE"),
        ListedSecurity(ticker="TMPV.NS", name="Tata Motors Passenger Vehicles Limited", exchange="NSE"),
        ListedSecurity(ticker="TATAPOWER.NS", name="The Tata Power Company Limited", exchange="NSE"),
        ListedSecurity(ticker="TATA", name="Unrelated US Co", exchange="NYSE"),
    ])
    await db_session.commit()
    headers = await _headers(client)

    page = (await client.get("/api/v1/stocks/search?query=tata", headers=headers)).json()
    tickers = [s["ticker"] for s in page["stocks"]]
    assert tickers[0] == "TCS.NS" and page["stocks"][0]["tracked"]  # tracked first, listed once
    assert tickers[1] == "TATA"  # exact symbol beats name matches
    assert set(tickers) == {"TCS.NS", "TATA", "TMPV.NS", "TATAPOWER.NS"} and page["total_count"] == 4
    assert not page["stocks"][1]["tracked"]

    browse = (await client.get("/api/v1/stocks/search", headers=headers)).json()
    assert browse["total_count"] == 4 and browse["stocks"][0]["ticker"] == "TCS.NS"  # no query: everything listed

    india = (await client.get("/api/v1/stocks/search?query=tata&market=in", headers=headers)).json()
    assert "TATA" not in [s["ticker"] for s in india["stocks"]]
    # Data filters only make sense on tracked stocks
    assert (await client.get("/api/v1/stocks/search?query=tata&pe_max=30", headers=headers)).json()["total_count"] == 0

    page2 = (await client.get("/api/v1/stocks/search?query=tata&limit=2&offset=2", headers=headers)).json()
    assert [s["ticker"] for s in page2["stocks"]] == tickers[2:]

    tracked = (await client.get("/api/v1/stocks/search?query=TMPV.NS&track=true", headers=headers)).json()
    assert tracked["stocks"][0]["tracked"] and tracked["stocks"][0]["price"] != "N/A"
    stock = await db_session.get(Stock, "TMPV.NS")
    await db_session.refresh(stock)
    assert stock.name == "Tata Motors Passenger Vehicles Limited"


@pytest.mark.asyncio
async def test_verdict_needs_scores_then_maps_final_score(client, db_session):
    from app.services.recommendation_engine import RecommendationEngine, RecommendationScore

    db_session.add(Stock(ticker="GOOD", name="Good Co", sector="Technology"))
    await db_session.commit()
    headers = await _headers(client)
    unrated = (await client.get("/api/v1/recommendations/GOOD/verdict", headers=headers)).json()
    assert unrated["verdict"] == "Unrated" and unrated["missing"] == ["research report", "risk score"]

    stock = await db_session.get(Stock, "GOOD")
    stock.research_score, stock.risk_score = 90.0, 50.0  # strong research, inside a Moderate band
    await db_session.commit()
    rated = (await client.get("/api/v1/recommendations/GOOD/verdict", headers=headers)).json()
    assert rated["verdict"] == "Buy" and rated["final_score"] >= 70 and len(rated["reasons"]) == 3
    assert rated["reasons"][0].startswith("Strong research quality")

    engine = RecommendationEngine()
    assert engine.verdict(RecommendationScore(50, 50, 50, 50, 69.9))[0] == "Hold"
    assert engine.verdict(RecommendationScore(20, 30, 40, 50, 49.9))[0] == "Avoid"


@pytest.mark.asyncio
async def test_refresh_loads_every_list_and_names_bare_ticker_stocks(db_session, monkeypatch):
    pages = {stock_directory.NSE_EQUITY_LIST: NSE, stock_directory.NSE_ETF_LIST: NSE_ETF, stock_directory.US_LIST: US}

    async def fake_get(client, url):
        return pages[url]

    async def fake_bhavcopy(client, today):
        return BSE

    monkeypatch.setattr(stock_directory, "_get", fake_get)
    monkeypatch.setattr(stock_directory, "_latest_bhavcopy", fake_bhavcopy)
    db_session.add(Stock(ticker="AAPL", name="AAPL"))  # tracked from a watchlist before it had a name
    await db_session.commit()

    assert await stock_directory.refresh_directory(db_session) == {"NSE": 4, "BSE": 3, "US": 5}
    stock = await db_session.get(Stock, "AAPL")
    await db_session.refresh(stock)
    assert stock.name == "Apple Inc."

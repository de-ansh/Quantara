"""Tests for the scheduled price refresh."""

import pandas as pd
import pytest
from sqlalchemy import select

from app.api.v1.research import to_search_item
from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import price_service


@pytest.mark.asyncio
async def test_refresh_updates_quotes_and_keeps_missing(db_session, monkeypatch):
    db_session.add_all([
        Stock(ticker="AAPL", name="Apple", price=100.0),
        Stock(ticker="GONE", name="Delisted", price=5.0),
    ])
    await db_session.commit()

    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {"AAPL": (110.0, 100.0)})
    assert await price_service.refresh_prices(db_session) == 1

    aapl = (await db_session.execute(select(Stock).where(Stock.ticker == "AAPL"))).scalar_one()
    gone = (await db_session.execute(select(Stock).where(Stock.ticker == "GONE"))).scalar_one()
    assert (aapl.price, aapl.previous_close) == (110.0, 100.0)
    assert aapl.price_updated_at is not None
    assert gone.price == 5.0 and gone.price_updated_at is None  # no quote: untouched

    item = to_search_item(aapl)
    assert item.change_pct == 10.0
    assert item.price == "$110.00"


@pytest.mark.asyncio
async def test_refresh_survives_download_failure(db_session, monkeypatch):
    db_session.add(Stock(ticker="AAPL", name="Apple", price=100.0))
    await db_session.commit()

    def _boom(tickers):
        raise ConnectionError("yahoo down")

    monkeypatch.setattr(price_service, "fetch_quotes", _boom)
    assert await price_service.refresh_prices(db_session) == 0
    aapl = (await db_session.execute(select(Stock))).scalar_one()
    assert aapl.price == 100.0


def test_fetch_quotes_parses_batched_download(monkeypatch):
    idx = pd.date_range("2026-10-19", periods=3)
    frame = pd.DataFrame({"AAPL": [1.0, 2.0, 3.0], "NODATA": [None, None, None]}, index=idx)
    monkeypatch.setattr(price_service.yf, "download", lambda *a, **k: {"Close": frame})

    assert price_service.fetch_quotes(["AAPL", "NODATA", "MISSING"]) == {"AAPL": (3.0, 2.0)}


@pytest.mark.asyncio
async def test_refresh_fundamentals_maps_sector_and_keeps_known_values(db_session, monkeypatch):

    db_session.add_all([
        Stock(ticker="TMCV.NS", name="TMCV.NS", pe_ratio=16.0),
        Stock(ticker="AAPL", name="Apple", fundamentals_updated_at=utcnow()),  # fresh
    ])
    await db_session.commit()
    calls: list[str] = []

    def _fake(ticker):
        calls.append(ticker)
        return {"name": "Tata Motors Limited", "sector": "Consumer Discretionary",
                "market_cap": 1.46e12, "pe_ratio": None, "beta": 0.84}

    monkeypatch.setattr(price_service, "fetch_fundamentals", _fake)
    assert await price_service.refresh_fundamentals(db_session) == 1
    assert calls == ["TMCV.NS"]  # fresh rows are skipped

    tm = (await db_session.execute(select(Stock).where(Stock.ticker == "TMCV.NS"))).scalar_one()
    assert (tm.name, tm.market_cap, tm.beta) == ("Tata Motors Limited", 1.46e12, 0.84)
    assert tm.pe_ratio == 16.0  # missing P/E never erases a known one
    assert tm.fundamentals_updated_at is not None


def test_fetch_fundamentals_maps_yahoo_sector(monkeypatch):
    class _T:
        info = {"longName": "Tata Motors Limited", "sector": "Consumer Cyclical", "marketCap": 1.0}

    monkeypatch.setattr(price_service.yf, "Ticker", lambda t: _T())
    assert price_service.fetch_fundamentals("TMCV.NS")["sector"] == "Consumer Discretionary"


@pytest.mark.asyncio
async def test_unrated_stocks_get_a_real_risk_score(db_session, monkeypatch):
    db_session.add_all([Stock(ticker="AAPL", name="Apple"), Stock(ticker="NOHIST", name="No history")])
    await db_session.commit()
    assert to_search_item(await db_session.get(Stock, "AAPL")).risk is None
    assert to_search_item(await db_session.get(Stock, "AAPL")).signal == "Unrated"

    from app.providers.yahoo import YahooFinanceProvider

    real = YahooFinanceProvider.get_historical_data

    async def history(self, ticker, **kw):
        return pd.DataFrame() if ticker == "NOHIST" else await real(self, ticker, **kw)

    monkeypatch.setattr(YahooFinanceProvider, "get_historical_data", history)
    assert await price_service.score_unrated_stocks(db_session) == 1

    aapl = await db_session.get(Stock, "AAPL")
    nohist = await db_session.get(Stock, "NOHIST")
    assert aapl.risk_score is not None and 0 <= aapl.risk_score <= 100
    assert nohist.risk_score is None  # defaults alone never become a score

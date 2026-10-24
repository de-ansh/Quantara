"""Tests for Stock Search and Research API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.research import search_stocks
from app.models.stock import Stock


@pytest.mark.asyncio
async def test_search_stocks_with_query():
    """Test stock search with ticker and name query."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    nvda = Stock(
        ticker="NVDA",
        name="NVIDIA Corporation",
        price=120.5,
        market_cap=3e12,
        risk_score=72.0,
        research_score=85.0,
        alpha_projection="+14.2%",
        status="bullish",
    )
    mock_result.scalars.return_value.all.return_value = [nvda]
    mock_result.scalar_one.return_value = 1
    mock_db.execute.return_value = mock_result

    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp = await search_stocks(
        current_user=current_user,
        db=mock_db,
        query="NVD",
    )

    assert resp.total_count == 1
    assert len(resp.stocks) == 1
    item = resp.stocks[0]
    assert item.ticker == "NVDA"
    assert item.name == "NVIDIA Corporation"
    assert item.price == "$120.50"
    assert item.risk == 72.0
    assert item.signal == "High"


@pytest.mark.asyncio
async def test_search_stocks_empty_results():
    """Test stock search when query has no matching stocks."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one.return_value = 0
    mock_db.execute.return_value = mock_result

    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp = await search_stocks(
        current_user=current_user,
        db=mock_db,
        query="XYZUNKNOWN",
    )

    assert resp.total_count == 0
    assert len(resp.stocks) == 0


@pytest.mark.asyncio
async def test_search_stocks_with_criteria_filters():
    """Test stock search with P/E, beta, and risk range criteria."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    aapl = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        price=225.0,
        market_cap=3.4e12,
        risk_score=48.0,
        research_score=92.0,
        pe_ratio=32.0,
        beta=1.1,
    )
    mock_result.scalars.return_value.all.return_value = [aapl]
    mock_result.scalar_one.return_value = 1
    mock_db.execute.return_value = mock_result

    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp = await search_stocks(
        current_user=current_user,
        db=mock_db,
        query="Apple",
        pe_max=35.0,
        beta_max=1.5,
        risk_max=60.0,
    )

    assert resp.total_count == 1
    item = resp.stocks[0]
    assert item.ticker == "AAPL"
    assert item.signal == "Strong"


def test_price_and_market_cap_formatting_uses_listing_currency():
    from app.api.v1.research import format_market_cap, format_price

    assert format_price(189.42, "AAPL") == "$189.42"
    assert format_price(1215.4, "RELIANCE.NS") == "₹1,215.40"
    assert format_price(None, "AAPL") == "N/A"
    assert format_market_cap(2.94e12, "AAPL") == "$2.94T"
    assert format_market_cap(558.2e9, "INFY.BO") == "₹558.20B"
    assert format_market_cap(None, "AAPL") == "N/A"


@pytest.mark.asyncio
async def test_search_pagination(client, db_session):
    from app.models.stock import Stock

    db_session.add_all([Stock(ticker=t, name=t) for t in ["CCC", "AAA", "DDD", "BBB"]])
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    page = (await client.get("/api/v1/stocks/search?limit=2&offset=1", headers=headers)).json()
    assert [s["ticker"] for s in page["stocks"]] == ["BBB", "CCC"]
    assert page["total_count"] == 4
    assert (await client.get("/api/v1/stocks/search?limit=500", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_price_history_endpoint(client, monkeypatch):
    from app.api.v1 import research

    calls = []

    def _fake(ticker, range_):
        calls.append((ticker, range_))
        return [research.PricePoint(date="2026-01-01", close=100.0),
                research.PricePoint(date="2026-02-01", close=125.0)]

    monkeypatch.setattr(research, "_download_history", _fake)
    monkeypatch.setattr(research, "_history_cache", {})
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = (await client.get("/api/v1/stocks/aapl/history?range=6M", headers=headers)).json()
    assert resp["ticker"] == "AAPL" and resp["change_pct"] == 25.0 and len(resp["points"]) == 2
    await client.get("/api/v1/stocks/AAPL/history?range=6M", headers=headers)
    assert calls == [("AAPL", "6M")]  # second call served from cache

    assert (await client.get("/api/v1/stocks/AAPL/history?range=2D", headers=headers)).status_code == 422
    monkeypatch.setattr(research, "_download_history", lambda t, r: [])
    assert (await client.get("/api/v1/stocks/NOPE/history", headers=headers)).status_code == 404

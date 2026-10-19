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
        price="$120.50",
        market_cap="$3.0T",
        risk_score=72.0,
        research_score=85.0,
        alpha_projection="+14.2%",
        status="bullish",
    )
    mock_result.scalars.return_value.all.return_value = [nvda]
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
        price="$225.00",
        market_cap="$3.4T",
        risk_score=48.0,
        research_score=92.0,
        pe_ratio=32.0,
        beta=1.1,
    )
    mock_result.scalars.return_value.all.return_value = [aapl]
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

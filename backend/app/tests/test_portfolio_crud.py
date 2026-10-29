"""Tests for Portfolio and Position CRUD API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PositionBase,
    create_portfolio,
    delete_portfolio,
    get_portfolio,
    list_portfolios,
    update_portfolio,
)
from app.core.clock import utcnow
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.stock import Stock


@pytest.fixture
def mock_current_user():
    return {
        "id": "1",
        "email": "portfolio_mgr@quantara.com",
        "risk_level": "Aggressive",
        "volatility_tolerance": 75.0,
    }


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def sample_portfolio(mock_current_user):
    now = utcnow()
    p = Portfolio(
        id=10,
        user_id=int(mock_current_user["id"]),
        name="Growth Tech",
        description="High growth tech allocation",
        initial_investment=150000.0,
        created_at=now,
        updated_at=now,
    )
    PortfolioPosition(
        id=101,
        portfolio_id=10,
        ticker="AAPL",
        shares=100.0,
        cost_basis=180.0,
        weight=0.6,
        portfolio=p,
    )
    PortfolioPosition(
        id=102,
        portfolio_id=10,
        ticker="MSFT",
        shares=50.0,
        cost_basis=400.0,
        weight=0.4,
        portfolio=p,
    )
    return p


@pytest.mark.asyncio
async def test_list_portfolios_empty(mock_current_user, mock_db):
    """Test listing portfolios when user has none."""
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_db.execute.return_value = mock_result

    resp = await list_portfolios(current_user=mock_current_user, db=mock_db)

    assert resp.total_count == 0
    assert resp.portfolios == []
    assert mock_db.execute.called


@pytest.mark.asyncio
async def test_list_portfolios_with_data(mock_current_user, sample_portfolio, mock_db):
    """Test listing portfolios returning user's active portfolios."""
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [sample_portfolio]
    mock_db.execute.return_value = mock_result

    resp = await list_portfolios(current_user=mock_current_user, db=mock_db)

    assert resp.total_count == 1
    assert len(resp.portfolios) == 1
    p_data = resp.portfolios[0]
    assert p_data.id == 10
    assert p_data.name == "Growth Tech"
    assert len(p_data.positions) == 2
    assert p_data.positions[0].ticker == "AAPL"
    assert p_data.positions[0].weight == 0.6


@pytest.mark.asyncio
async def test_create_portfolio(mock_current_user, mock_db, monkeypatch):
    """Test creating a new portfolio; untracked tickers are verified, then tracked."""
    from app.services import stock_lookup

    monkeypatch.setattr(stock_lookup, "last_close", lambda t: 120.0)
    stock_mock_aapl = MagicMock()
    stock_mock_aapl.scalar_one_or_none.return_value = Stock(ticker="AAPL", name="Apple Inc.")

    stock_mock_nvda = MagicMock()
    stock_mock_nvda.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [stock_mock_aapl, stock_mock_nvda]

    payload = PortfolioCreate(
        name="Alpha Core",
        description="Core equity basket",
        initial_investment=200000.0,
        positions=[
            PositionBase(ticker="AAPL", weight=0.5, shares=200.0, cost_basis=175.0),
            PositionBase(ticker="NVDA", weight=0.5, shares=100.0, cost_basis=120.0),
        ],
    )

    resp = await create_portfolio(request=payload, current_user=mock_current_user, db=mock_db)

    assert resp.name == "Alpha Core"
    assert resp.user_id == 1
    assert resp.initial_investment == 200000.0
    assert len(resp.positions) == 2
    assert resp.positions[0].ticker == "AAPL"
    assert resp.positions[1].ticker == "NVDA"

    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.refresh.called


@pytest.mark.asyncio
async def test_get_portfolio_found(mock_current_user, sample_portfolio, mock_db):
    """Test retrieving existing portfolio by ID."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_portfolio
    mock_db.execute.return_value = mock_result

    resp = await get_portfolio(
        portfolio_id=10, current_user=mock_current_user, db=mock_db
    )

    assert resp.id == 10
    assert resp.name == "Growth Tech"
    assert len(resp.positions) == 2


@pytest.mark.asyncio
async def test_get_portfolio_not_found(mock_current_user, mock_db):
    """Test 404 raised when portfolio does not exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_portfolio(
            portfolio_id=999, current_user=mock_current_user, db=mock_db
        )

    assert exc_info.value.status_code == 404
    assert "Portfolio not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_portfolio_metadata(mock_current_user, sample_portfolio, mock_db):
    """Test updating portfolio name and initial investment."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_portfolio
    mock_db.execute.return_value = mock_result

    payload = PortfolioUpdate(
        name="Renamed Growth Tech",
        initial_investment=180000.0,
    )

    resp = await update_portfolio(
        portfolio_id=10, request=payload, current_user=mock_current_user, db=mock_db
    )

    assert resp.name == "Renamed Growth Tech"
    assert resp.initial_investment == 180000.0
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_update_portfolio_positions(mock_current_user, sample_portfolio, mock_db):
    """Test updating positions rebalances the portfolio."""
    # 1st execute: select(Portfolio)
    mock_port_result = MagicMock()
    mock_port_result.scalar_one_or_none.return_value = sample_portfolio

    # 2nd execute: select(PortfolioPosition) for deletion
    mock_pos_result = MagicMock()
    mock_pos_result.scalars().all.return_value = list(sample_portfolio.positions)

    # select(Stock) for the new position
    stock_mock = MagicMock()
    stock_mock.scalar_one_or_none.return_value = Stock(ticker="GOOGL", name="Alphabet")

    # Tickers are verified before old positions are removed
    mock_db.execute.side_effect = [mock_port_result, stock_mock, mock_pos_result]

    payload = PortfolioUpdate(
        positions=[
            PositionBase(ticker="GOOGL", weight=1.0, shares=50.0, cost_basis=160.0),
        ]
    )

    resp = await update_portfolio(
        portfolio_id=10, request=payload, current_user=mock_current_user, db=mock_db
    )

    assert len(resp.positions) == 1
    assert resp.positions[0].ticker == "GOOGL"
    assert resp.positions[0].weight == 1.0
    assert mock_db.delete.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_update_portfolio_not_found(mock_current_user, mock_db):
    """Test 404 raised when updating non-existent portfolio."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    payload = PortfolioUpdate(name="Non-existent")

    with pytest.raises(HTTPException) as exc_info:
        await update_portfolio(
            portfolio_id=999, request=payload, current_user=mock_current_user, db=mock_db
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_portfolio_success(mock_current_user, sample_portfolio, mock_db):
    """Test deleting portfolio."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_portfolio
    mock_db.execute.return_value = mock_result

    result = await delete_portfolio(
        portfolio_id=10, current_user=mock_current_user, db=mock_db
    )

    assert result is None
    assert mock_db.delete.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_delete_portfolio_not_found(mock_current_user, mock_db):
    """Test deleting non-existent portfolio returns 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await delete_portfolio(
            portfolio_id=999, current_user=mock_current_user, db=mock_db
        )

    assert exc_info.value.status_code == 404

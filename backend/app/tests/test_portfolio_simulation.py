"""Tests for Portfolio Simulation and MPT Covariance Analytics."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from app.api.v1 import risk
from app.api.v1.portfolio import PortfolioStock, SimulationRequest, simulate_portfolio
from app.models.stock import Stock
from app.services.portfolio_analytics import PortfolioAnalyticsEngine


@pytest.fixture
def no_price_history(monkeypatch):
    """Simulate a Yahoo outage so the endpoint uses its asset-class fallbacks."""

    async def _none(tickers):
        return None

    monkeypatch.setattr(risk, "_get_daily_returns", _none)


def _db_returning(*stocks):
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(stocks)
    mock_db.execute.return_value = result
    return mock_db


@pytest.fixture
def mock_current_user():
    return {
        "id": "1",
        "email": "portfolio_mgr@quantara.com",
        "risk_level": "Moderate",
        "volatility_tolerance": 60.0,
    }


# =====================================================================
# Unit Tests for PortfolioAnalyticsEngine
# =====================================================================


def test_asset_classification():
    """Test asset classification across cash, bonds, commodities, and equities."""
    assert PortfolioAnalyticsEngine.classify_asset("BIL")[0] == "cash"
    assert PortfolioAnalyticsEngine.classify_asset("TLT")[0] == "fixed_income"
    assert PortfolioAnalyticsEngine.classify_asset("GLD")[0] == "commodity"
    assert PortfolioAnalyticsEngine.classify_asset("AAPL", "Technology")[0] == "equity"


def test_pairwise_correlations():
    """Test correlation rules for cash, flight-to-safety bonds, and sector equities."""
    # Identity
    assert PortfolioAnalyticsEngine.estimate_pairwise_correlation("AAPL", "AAPL") == 1.0

    # Cash has zero correlation
    assert PortfolioAnalyticsEngine.estimate_pairwise_correlation("AAPL", "BIL") == 0.0
    assert PortfolioAnalyticsEngine.estimate_pairwise_correlation("BIL", "TLT") == 0.0

    # Equities vs Bonds (negative correlation)
    corr_eq_bond = PortfolioAnalyticsEngine.estimate_pairwise_correlation("AAPL", "TLT")
    assert corr_eq_bond < 0.0

    # Same sector equities vs different sector equities
    corr_same_sec = PortfolioAnalyticsEngine.estimate_pairwise_correlation(
        "AAPL", "MSFT", sector_a="Technology", sector_b="Technology"
    )
    corr_diff_sec = PortfolioAnalyticsEngine.estimate_pairwise_correlation(
        "AAPL", "JNJ", sector_a="Technology", sector_b="Healthcare"
    )
    assert corr_same_sec > corr_diff_sec


def test_single_stock_portfolio():
    """Test single stock has zero diversification benefit and matches stock volatility."""
    result = PortfolioAnalyticsEngine.calculate_portfolio_metrics(
        tickers=["NVDA"],
        weights=[1.0],
        volatilities=[0.35],
        expected_returns=[0.18],
    )
    assert result.portfolio_volatility == pytest.approx(0.35, abs=1e-3)
    assert result.portfolio_return == pytest.approx(0.18, abs=1e-3)
    assert result.diversification_benefit_pct == 0.0
    assert len(result.covariance_matrix) == 1
    assert result.covariance_matrix[0][0] == pytest.approx(0.35**2, abs=1e-3)


def test_stock_bond_diversification():
    """Test multi-asset portfolio achieves diversification reduction via covariance."""
    # 60/40 Equity + Bond portfolio
    result = PortfolioAnalyticsEngine.calculate_portfolio_metrics(
        tickers=["AAPL", "TLT"],
        weights=[0.6, 0.4],
        volatilities=[0.22, 0.08],
        expected_returns=[0.12, 0.04],
        sectors={"AAPL": "Technology", "TLT": "Fixed Income"},
    )

    weighted_avg_vol = 0.6 * 0.22 + 0.4 * 0.08  # 0.164
    assert result.portfolio_volatility < weighted_avg_vol
    assert result.diversification_benefit_pct > 0.0
    assert "AAPL" in result.correlation_matrix
    assert "TLT" in result.correlation_matrix["AAPL"]
    assert result.correlation_matrix["AAPL"]["TLT"] < 0.0


def test_weight_normalization():
    """Test raw non-normalized weights are normalized without error."""
    result = PortfolioAnalyticsEngine.calculate_portfolio_metrics(
        tickers=["AAPL", "MSFT"],
        weights=[60.0, 40.0],  # sum = 100.0
        volatilities=[0.20, 0.20],
        expected_returns=[0.10, 0.10],
    )
    assert result.normalized_weights == [0.6, 0.4]
    assert result.portfolio_return == pytest.approx(0.10, abs=1e-3)


# =====================================================================
# Integration Tests for /portfolio/simulate Endpoint
# =====================================================================


@pytest.mark.asyncio
async def test_simulate_portfolio_with_default_metrics(mock_current_user, no_price_history):
    """Test simulate endpoint computes MPT covariance and valid trajectories."""
    mock_db = _db_returning()

    payload = SimulationRequest(
        stocks=[
            PortfolioStock(ticker="AAPL", weight=0.6),
            PortfolioStock(ticker="TLT", weight=0.25),
            PortfolioStock(ticker="GLD", weight=0.10),
            PortfolioStock(ticker="BIL", weight=0.05),
        ],
        initial_investment=1000000.0,
        time_horizon_months=120,
    )

    res = await simulate_portfolio(request=payload, current_user=mock_current_user, db=mock_db)

    # Validate output schema
    assert res.expected_return > 0
    assert res.expected_volatility > 0
    assert res.sharpe_ratio > 0
    assert res.max_drawdown < 0
    assert res.diversification_benefit_pct > 0

    # Check correlation & covariance matrices
    assert len(res.covariance_matrix) == 4
    assert "AAPL" in res.correlation_matrix
    assert res.correlation_matrix["AAPL"]["AAPL"] == 1.0
    assert res.correlation_matrix["AAPL"]["BIL"] == 0.0

    assert res.estimated_tickers == ["AAPL", "TLT", "GLD", "BIL"]

    # Validate projected trajectory
    assert len(res.trajectory) == 121  # month 0 to 120
    assert res.trajectory[0].median == 1000000.0
    assert res.trajectory[0].upper_95 == 1000000.0
    assert res.trajectory[0].lower_5 == 1000000.0

    # Verify bounds ordering at horizon
    final_point = res.trajectory[-1]
    assert final_point.lower_5 <= final_point.median <= final_point.upper_95


@pytest.mark.asyncio
async def test_simulate_portfolio_with_db_stocks(mock_current_user, no_price_history):
    """Without price history, DB sector and beta still drive the estimates."""
    mock_db = _db_returning(
        Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", beta=1.1),
        Stock(ticker="MSFT", name="Microsoft Corp.", sector="Technology", beta=1.05),
    )

    payload = SimulationRequest(
        stocks=[
            PortfolioStock(ticker="AAPL", weight=0.5),
            PortfolioStock(ticker="MSFT", weight=0.5),
        ],
        initial_investment=500000.0,
        time_horizon_months=60,
    )

    res = await simulate_portfolio(request=payload, current_user=mock_current_user, db=mock_db)

    assert res.expected_return > 0
    assert res.expected_volatility > 0
    assert res.correlation_matrix["AAPL"]["MSFT"] == 0.72  # intra-sector technology
    assert res.expected_return == pytest.approx((0.025 + 1.075 * 0.055) * 100, abs=0.01)
    assert len(res.trajectory) == 61


@pytest.mark.asyncio
async def test_simulate_portfolio_uses_real_price_history(mock_current_user, monkeypatch):
    """Volatility, beta, correlation and drawdown are computed from daily returns."""
    rng = np.random.default_rng(7)
    market = rng.normal(0.0004, 0.01, 250)
    returns = pd.DataFrame(
        {
            "^GSPC": market,
            "AAA": 2.0 * market + rng.normal(0, 0.005, 250),  # beta ~2
            "BBB": rng.normal(0.0003, 0.012, 250),  # uncorrelated with the market
        }
    )

    async def _returns(tickers):
        return returns

    monkeypatch.setattr(risk, "_get_daily_returns", _returns)

    payload = SimulationRequest(
        stocks=[PortfolioStock(ticker="AAA", weight=0.5), PortfolioStock(ticker="BBB", weight=0.5)],
        initial_investment=1000.0,
        time_horizon_months=12,
    )
    res = await simulate_portfolio(
        request=payload, current_user=mock_current_user, db=_db_returning()
    )

    assert res.estimated_tickers == []
    assert res.asset_volatilities["AAA"] == pytest.approx(
        returns["AAA"].std() * np.sqrt(252), abs=1e-3
    )
    assert res.correlation_matrix["AAA"]["BBB"] == pytest.approx(
        returns["AAA"].corr(returns["BBB"]), abs=1e-3
    )
    growth = (1 + returns[["AAA", "BBB"]].mean(axis=1)).cumprod()
    assert res.max_drawdown == pytest.approx((growth / growth.cummax() - 1).min() * 100, abs=0.01)
    # CAPM: AAA's beta of ~2 must pull the blended return well above the risk-free rate
    assert res.expected_return > (0.025 + 1.0 * 0.055) * 100


@pytest.mark.asyncio
async def test_simulate_rejects_weights_not_summing_to_one(mock_current_user, no_price_history):
    payload = SimulationRequest(
        stocks=[PortfolioStock(ticker="AAPL", weight=0.5), PortfolioStock(ticker="MSFT", weight=0.3)],
        initial_investment=1000.0,
        time_horizon_months=12,
    )
    with pytest.raises(HTTPException) as exc:
        await simulate_portfolio(request=payload, current_user=mock_current_user, db=_db_returning())
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_simulate_portfolio_volatility_modes(mock_current_user):
    """Test volatility_mode adjusts volatility and expected return projections."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    stocks = [
        PortfolioStock(ticker="AAPL", weight=0.6),
        PortfolioStock(ticker="TLT", weight=0.4),
    ]

    base_res = await simulate_portfolio(
        request=SimulationRequest(
            stocks=stocks,
            initial_investment=100000.0,
            time_horizon_months=12,
            volatility_mode="base",
        ),
        current_user=mock_current_user,
        db=mock_db,
    )

    cons_res = await simulate_portfolio(
        request=SimulationRequest(
            stocks=stocks,
            initial_investment=100000.0,
            time_horizon_months=12,
            volatility_mode="conservative",
        ),
        current_user=mock_current_user,
        db=mock_db,
    )

    aggr_res = await simulate_portfolio(
        request=SimulationRequest(
            stocks=stocks,
            initial_investment=100000.0,
            time_horizon_months=12,
            volatility_mode="aggressive",
        ),
        current_user=mock_current_user,
        db=mock_db,
    )

    # Conservative should have higher volatility and lower return than Base
    assert cons_res.expected_volatility > base_res.expected_volatility
    assert cons_res.expected_return < base_res.expected_return

    # Aggressive should have lower perceived volatility and higher return than Base
    assert aggr_res.expected_volatility < base_res.expected_volatility
    assert aggr_res.expected_return > base_res.expected_return


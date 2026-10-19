"""Tests for Portfolio Simulation and MPT Covariance Analytics."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.portfolio import PortfolioStock, SimulationRequest, simulate_portfolio
from app.models.stock import Stock
from app.services.portfolio_analytics import PortfolioAnalyticsEngine


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
async def test_simulate_portfolio_with_default_metrics(mock_current_user):
    """Test simulate endpoint computes MPT covariance and valid trajectories."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

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

    # Validate Monte Carlo trajectory
    assert len(res.trajectory) == 121  # month 0 to 120
    assert res.trajectory[0].median == 1000000.0
    assert res.trajectory[0].upper_95 == 1000000.0
    assert res.trajectory[0].lower_5 == 1000000.0

    # Verify bounds ordering at horizon
    final_point = res.trajectory[-1]
    assert final_point.lower_5 <= final_point.median <= final_point.upper_95


@pytest.mark.asyncio
async def test_simulate_portfolio_with_db_stocks(mock_current_user):
    """Test simulate endpoint utilizes database stock parameters when available."""
    mock_db = AsyncMock()

    db_stock_aapl = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        risk_score=44.0,  # vol = 44 / 200 = 0.22
        research_score=80.0,
        beta=1.1,
    )
    db_stock_msft = Stock(
        ticker="MSFT",
        name="Microsoft Corp.",
        sector="Technology",
        risk_score=40.0,  # vol = 40 / 200 = 0.20
        research_score=85.0,
        beta=1.05,
    )

    mock_res_aapl = MagicMock()
    mock_res_aapl.scalar_one_or_none.return_value = db_stock_aapl

    mock_res_msft = MagicMock()
    mock_res_msft.scalar_one_or_none.return_value = db_stock_msft

    mock_db.execute.side_effect = [mock_res_aapl, mock_res_msft]

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
    assert len(res.trajectory) == 61

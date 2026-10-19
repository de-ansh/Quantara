"""Tests for risk engine."""

import pytest

from app.services.risk_engine import RiskEngine, RiskLevel


class TestRiskEngine:
    """Test suite for risk engine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = RiskEngine()

    def test_calculate_volatility_score(self):
        """Test volatility score calculation."""
        # Low volatility
        score = self.engine.calculate_volatility_score(0.10)
        assert 0 <= score <= 100
        assert score < 50  # 10% volatility should be low risk

        # High volatility
        score = self.engine.calculate_volatility_score(0.50)
        assert score > 50  # 50% volatility should be high risk

    def test_calculate_beta_score(self):
        """Test beta score calculation."""
        # Market beta
        score = self.engine.calculate_beta_score(1.0)
        assert score == pytest.approx(50, rel=0.1)

        # Low beta
        score = self.engine.calculate_beta_score(0.5)
        assert score < 50

        # High beta
        score = self.engine.calculate_beta_score(1.5)
        assert score > 50

    def test_calculate_leverage_score(self):
        """Test leverage score calculation."""
        # No debt
        score = self.engine.calculate_leverage_score(0.0)
        assert score == 0

        # Moderate debt
        score = self.engine.calculate_leverage_score(1.0)
        assert 30 <= score <= 40

        # High debt
        score = self.engine.calculate_leverage_score(3.0)
        assert score >= 90

    def test_classify_risk_level(self):
        """Test risk level classification."""
        assert self.engine.classify_risk_level(20) == RiskLevel.CONSERVATIVE
        assert self.engine.classify_risk_level(50) == RiskLevel.MODERATE
        assert self.engine.classify_risk_level(80) == RiskLevel.AGGRESSIVE

    def test_analyze_stock_risk(self):
        """Test complete stock risk analysis."""
        analysis = self.engine.analyze_stock_risk(
            ticker="AAPL",
            historical_volatility=0.25,
            beta=1.2,
            debt_to_equity=0.5,
            earnings_volatility=0.15,
            consecutive_profitable_quarters=8,
            sector="Technology",
            pe_ratio=25.0,
            price_to_book=3.5,
        )

        assert analysis.ticker == "AAPL"
        assert 0 <= analysis.overall_risk_score <= 100
        assert analysis.risk_level in [
            RiskLevel.CONSERVATIVE,
            RiskLevel.MODERATE,
            RiskLevel.AGGRESSIVE,
        ]
        assert analysis.explanation
        assert analysis.components.volatility_score >= 0
        assert analysis.components.beta_score >= 0


@pytest.mark.asyncio
async def test_get_stock_correlations():
    """Test get_stock_correlations endpoint returns sector peers and macro hedges."""
    from unittest.mock import AsyncMock, MagicMock
    from app.api.v1.risk import get_stock_correlations
    from app.models.stock import Stock

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        beta=1.2,
    )
    mock_db.execute.return_value = mock_res

    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp = await get_stock_correlations(ticker="AAPL", current_user=current_user, db=mock_db)

    assert resp.ticker == "AAPL"
    assert resp.sector == "Technology"
    assert 0 < resp.benchmark_correlation <= 1.0
    assert len(resp.peers) > 0

    # Ensure AAPL is not in peers (no self-reference in peer list)
    peer_tickers = [p.ticker for p in resp.peers]
    assert "AAPL" not in peer_tickers

    # Intra-sector tech stocks should have high correlation
    msft_peer = next((p for p in resp.peers if p.ticker == "MSFT"), None)
    assert msft_peer is not None
    assert msft_peer.relationship == "Direct Sector Peer"
    assert msft_peer.correlation >= 0.65

    # Bond / TLT hedge should have negative correlation
    tlt_peer = next((p for p in resp.peers if p.ticker == "TLT"), None)
    assert tlt_peer is not None
    assert tlt_peer.correlation < 0.0
    assert "Hedge" in tlt_peer.relationship


def test_generate_drawdown_series_with_dataframe():
    """Test drawdown calculation with actual price DataFrame."""
    import pandas as pd
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    # 20 days of simulated prices with a peak and drop
    prices = [100.0, 105.0, 110.0, 115.0, 120.0, 114.0, 102.0, 96.0, 90.0, 95.0,
              100.0, 105.0, 102.0, 98.0, 104.0, 108.0, 112.0, 115.0, 118.0, 120.0]
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({"Close": prices}, index=dates)

    max_dd, points = engine.generate_drawdown_series(
        df=df,
        historical_volatility=0.25,
        overall_risk_score=55.0,
    )

    # 120 -> 90 is a -25% drawdown
    assert max_dd == pytest.approx(-0.25, rel=0.05)
    assert len(points) >= 14  # historical sampled points + 4 projection steps

    # Check connection point: last historical point has both historical and projected
    historical_points = [p for p in points if p["historical"] is not None]
    projected_points = [p for p in points if p["projected"] is not None]

    assert len(historical_points) > 0
    assert len(projected_points) == 5  # 1 connection point + 4 projection steps
    # Connection point equality
    assert historical_points[-1]["historical"] == projected_points[0]["projected"]

    # Recovery level bounds
    for p in points:
        if p["historical"] is not None:
            assert 0.0 <= p["historical"] <= 100.0
        if p["projected"] is not None:
            assert 0.0 <= p["projected"] <= 100.0


def test_generate_drawdown_series_fallback():
    """Test deterministic drawdown generation when price data is unavailable."""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    max_dd, points = engine.generate_drawdown_series(
        df=None,
        historical_volatility=0.30,
        overall_risk_score=70.0,
        max_drawdown=-0.35,
    )

    assert max_dd == -0.35
    assert len(points) == 16  # 12 historical + 4 projected

    for p in points:
        assert p["time"]
        assert p["drawdown_pct"] is not None
        assert p["drawdown_pct"] <= 0.0


@pytest.mark.asyncio
async def test_get_stock_risk_analysis_endpoint():
    """Test get_stock_risk_analysis endpoint returns drawdown series and risk components."""
    from unittest.mock import AsyncMock
    from app.api.v1.risk import get_stock_risk_analysis

    mock_db = AsyncMock()
    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp = await get_stock_risk_analysis(ticker="NVDA", current_user=current_user, db=mock_db)

    assert resp.ticker == "NVDA"
    assert 0.0 <= resp.overall_risk_score <= 100.0
    assert resp.risk_level in ["Conservative", "Moderate", "Aggressive"]
    assert resp.max_drawdown <= 0.0
    assert len(resp.drawdown_series) > 0
    assert resp.components.volatility_score >= 0.0



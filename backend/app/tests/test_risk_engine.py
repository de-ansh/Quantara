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


def _correlation_db(stock, peers):
    """Mock DB: first execute returns the active stock, second the peer universe."""
    from unittest.mock import AsyncMock, MagicMock

    db = AsyncMock()
    active, universe = MagicMock(), MagicMock()
    active.scalar_one_or_none.return_value = stock
    universe.scalars.return_value.all.return_value = peers
    db.execute.side_effect = [active, universe]
    return db


@pytest.mark.asyncio
async def test_get_stock_correlations(monkeypatch):
    """Correlations and betas are computed from real daily returns of DB peers and hedges."""
    import numpy as np
    import pandas as pd

    from app.api.v1 import risk
    from app.models.stock import Stock

    rng = np.random.default_rng(0)
    market = rng.normal(0, 0.01, 250)
    idx = pd.date_range("2025-01-01", periods=250, freq="B")
    prices = {
        "AAPL": market + rng.normal(0, 0.004, 250),
        "^GSPC": market,
        "MSFT": market + rng.normal(0, 0.004, 250),
        "JNJ": rng.normal(0, 0.01, 250),
        "TLT": -market + rng.normal(0, 0.004, 250),
        "GLD": rng.normal(0, 0.01, 250),
        "BIL": rng.normal(0, 0.0001, 250),
    }
    closes = pd.DataFrame({k: 100 * np.cumprod(1 + v) for k, v in prices.items()}, index=idx)
    downloads = []

    def fake_download(tickers, **kwargs):
        downloads.append(tickers)
        return pd.concat({"Close": closes[tickers]}, axis=1)

    monkeypatch.setattr(risk.yf, "download", fake_download)
    monkeypatch.setattr(risk, "_returns_cache", {})

    db = _correlation_db(
        Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", beta=1.2),
        [
            Stock(ticker="JNJ", name="Johnson & Johnson", sector="Healthcare", beta=0.6),
            Stock(ticker="MSFT", name="Microsoft Corp.", sector="Technology", beta=1.1),
        ],
    )
    resp = await risk.get_stock_correlations(ticker="AAPL", current_user={}, db=db)

    assert resp.ticker == "AAPL"
    assert resp.benchmark_correlation > 0.8
    peers = {p.ticker: p for p in resp.peers}
    assert "AAPL" not in peers
    # Same-sector peers are listed first
    assert resp.peers[0].ticker == "MSFT"
    assert peers["MSFT"].relationship == "Direct Sector Peer"
    assert peers["MSFT"].correlation > 0.8
    assert abs(peers["MSFT"].beta - 1.0) < 0.15
    assert abs(peers["JNJ"].correlation) < 0.3
    assert peers["TLT"].correlation < -0.8
    assert "Hedge" in peers["TLT"].relationship

    # Second request within the TTL is served from cache
    await risk.get_stock_correlations(
        ticker="AAPL",
        current_user={},
        db=_correlation_db(
            Stock(ticker="AAPL", sector="Technology", beta=1.2),
            [Stock(ticker="JNJ", sector="Healthcare"), Stock(ticker="MSFT", sector="Technology")],
        ),
    )
    assert len(downloads) == 1


@pytest.mark.asyncio
async def test_get_stock_correlations_falls_back_when_yahoo_fails(monkeypatch):
    """Without price history, correlations fall back to the sector-based estimate."""
    from app.api.v1 import risk
    from app.models.stock import Stock

    def boom(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(risk.yf, "download", boom)
    monkeypatch.setattr(risk, "_returns_cache", {})

    db = _correlation_db(
        Stock(ticker="AAPL", sector="Technology", beta=1.2),
        [Stock(ticker="MSFT", name="Microsoft Corp.", sector="Technology", beta=1.1)],
    )
    resp = await risk.get_stock_correlations(ticker="AAPL", current_user={}, db=db)

    peers = {p.ticker: p for p in resp.peers}
    assert peers["MSFT"].correlation >= 0.65
    assert peers["MSFT"].beta == 1.1
    assert peers["TLT"].correlation < 0.0
    assert 0 < resp.benchmark_correlation <= 1.0
    # Failures are not cached
    assert risk._returns_cache == {}


def test_generate_drawdown_series_with_dataframe():
    """Test drawdown calculation with actual price DataFrame."""
    import pandas as pd

    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    # 20 days of simulated prices with a peak and drop
    prices = [
        100.0,
        105.0,
        110.0,
        115.0,
        120.0,
        114.0,
        102.0,
        96.0,
        90.0,
        95.0,
        100.0,
        105.0,
        102.0,
        98.0,
        104.0,
        108.0,
        112.0,
        115.0,
        118.0,
        120.0,
    ]
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
    current_user = {"id": "1", "email": "analyst@quantara.com", "sec_user_agent": None}

    resp = await get_stock_risk_analysis(ticker="NVDA", current_user=current_user, db=mock_db)

    assert resp.ticker == "NVDA"
    assert 0.0 <= resp.overall_risk_score <= 100.0
    assert resp.risk_level in ["Conservative", "Moderate", "Aggressive"]
    assert resp.max_drawdown <= 0.0
    assert len(resp.drawdown_series) > 0
    assert resp.components.volatility_score >= 0.0
    assert len(resp.scenarios) == 6
    assert "market_beta" in resp.factor_sensitivities


def test_calculate_factor_sensitivities():
    """Test quantitative factor sensitivities calculation."""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()

    # Technology stock
    tech_sens = engine.calculate_factor_sensitivities(
        ticker="NVDA", beta=1.65, pe_ratio=45.0, debt_to_equity=0.3, sector="Technology"
    )
    assert tech_sens["market_beta"] == 1.65
    assert tech_sens["interest_rate_beta"] < -1.5  # High P/E growth stock duration penalty
    assert tech_sens["tech_momentum_beta"] > 1.5
    assert tech_sens["oil_beta"] < 0.0

    # Energy stock
    energy_sens = engine.calculate_factor_sensitivities(
        ticker="XOM", beta=0.85, pe_ratio=11.0, debt_to_equity=0.4, sector="Energy"
    )
    assert energy_sens["market_beta"] == 0.85
    assert energy_sens["oil_beta"] > 1.0  # Positive sensitivity to oil spikes


def test_run_scenario_stress_test():
    """Test multi-factor scenario stress testing."""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    scenarios = engine.run_scenario_stress_test(
        ticker="AAPL", beta=1.2, pe_ratio=28.0, debt_to_equity=0.8, sector="Technology"
    )

    assert len(scenarios) == 6
    scenario_ids = [s["id"] for s in scenarios]
    assert "fed_pivot_rate_spike" in scenario_ids
    assert "global_recession_bear" in scenario_ids
    assert "oil_supply_shock_120" in scenario_ids
    assert "ai_infra_expansion" in scenario_ids
    assert "credit_spread_widening" in scenario_ids
    assert "usd_liquidity_squeeze" in scenario_ids

    # Global recession should project severe negative return shock
    recession = next(s for s in scenarios if s["id"] == "global_recession_bear")
    assert recession["impact_pct"] < -15.0
    assert recession["status"] == "danger"
    assert "market_beta" in recession["factor_breakdown"]

    # AI expansion should project positive catalyst for tech
    ai_catalyst = next(s for s in scenarios if s["id"] == "ai_infra_expansion")
    assert ai_catalyst["impact_pct"] > 5.0
    assert ai_catalyst["status"] == "success"


@pytest.mark.asyncio
async def test_get_stock_scenarios_endpoint():
    """Test dedicated GET /stocks/{ticker}/scenarios endpoint."""
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1.risk import get_stock_scenarios
    from app.models.stock import Stock

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = Stock(
        ticker="MSFT",
        name="Microsoft Corp",
        sector="Technology",
        beta=1.25,
        pe_ratio=32.0,
    )
    mock_db.execute.return_value = mock_res
    current_user = {"id": "1", "email": "analyst@quantara.com"}

    scenarios = await get_stock_scenarios(ticker="MSFT", current_user=current_user, db=mock_db)

    assert len(scenarios) == 6
    for s in scenarios:
        assert s.name
        assert s.type
        assert s.status in ["danger", "warning", "success"]
        assert s.impact_pct is not None


@pytest.mark.asyncio
async def test_risk_endpoint_reports_assumed_inputs_when_data_unavailable(monkeypatch):
    """With no market data, defaults are disclosed and dependent factors are omitted."""
    from unittest.mock import AsyncMock

    from app.api.v1.risk import get_stock_risk_analysis
    from app.services.llm_orchestrator import LLMOrchestrator

    async def _offline(self, state):
        raise ConnectionError("offline")

    monkeypatch.setattr(LLMOrchestrator, "_retrieve_data", _offline)
    resp = await get_stock_risk_analysis(
        ticker="ZZZZ",
        current_user={"id": "1", "email": "a@b.com", "sec_user_agent": None},
        db=AsyncMock(),
    )

    assert resp.assumed_inputs == ["price_history", "beta", "pe_ratio", "debt_to_equity", "sector"]
    assert resp.factor_sensitivities == {}

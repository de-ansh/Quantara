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
        assert analysis.risk_level in [RiskLevel.CONSERVATIVE, RiskLevel.MODERATE, RiskLevel.AGGRESSIVE]
        assert analysis.explanation
        assert analysis.components.volatility_score >= 0
        assert analysis.components.beta_score >= 0

"""
Deterministic Risk Engine - Pure Python Implementation

This module implements a comprehensive risk scoring algorithm that is:
- Deterministic (no LLM dependencies)
- Independently testable
- Transparent and auditable

Risk Score Formula:
    (0.2 * volatility_score) +
    (0.15 * beta_score) +
    (0.2 * leverage_score) +
    (0.15 * earnings_stability_score) +
    (0.1 * sector_risk_score) +
    (0.2 * valuation_risk_score)

All scores normalized to 0-100 scale.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk level classifications."""
    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


@dataclass
class RiskComponents:
    """Individual risk component scores."""
    volatility_score: float
    beta_score: float
    leverage_score: float
    earnings_stability_score: float
    sector_risk_score: float
    valuation_risk_score: float


@dataclass
class RiskAnalysis:
    """Complete risk analysis result."""
    ticker: str
    overall_risk_score: float
    risk_level: RiskLevel
    components: RiskComponents
    risk_band: str
    explanation: str


class RiskEngine:
    """Deterministic risk scoring engine."""

    # Component weights
    WEIGHTS = {
        "volatility": 0.20,
        "beta": 0.15,
        "leverage": 0.20,
        "earnings_stability": 0.15,
        "sector": 0.10,
        "valuation": 0.20,
    }

    # Risk level thresholds
    CONSERVATIVE_THRESHOLD = 33.33
    MODERATE_THRESHOLD = 66.67

    # Sector risk mappings (example - should be data-driven)
    SECTOR_RISK_MAP = {
        "Technology": 65,
        "Healthcare": 55,
        "Financials": 60,
        "Energy": 70,
        "Utilities": 30,
        "Consumer Staples": 35,
        "Consumer Discretionary": 55,
        "Industrials": 50,
        "Materials": 60,
        "Real Estate": 50,
        "Communication Services": 55,
    }

    def calculate_volatility_score(
        self, 
        historical_volatility: float,
        volatility_percentile: Optional[float] = None
    ) -> float:
        """
        Calculate volatility risk score.
        
        Args:
            historical_volatility: Annualized volatility (e.g., 0.25 for 25%)
            volatility_percentile: Percentile rank vs market (0-100)
        
        Returns:
            Volatility score (0-100, higher = riskier)
        """
        # Convert volatility to percentage
        vol_pct = historical_volatility * 100
        
        # Normalize: 0% vol = 0 score, 100% vol = 100 score
        # Most stocks fall in 10-50% range
        base_score = min(vol_pct * 2, 100)
        
        # Adjust by percentile if available
        if volatility_percentile is not None:
            base_score = (base_score * 0.6) + (volatility_percentile * 0.4)
        
        return min(max(base_score, 0), 100)

    def calculate_beta_score(self, beta: float) -> float:
        """
        Calculate beta risk score.
        
        Args:
            beta: Stock beta vs market (e.g., 1.5)
        
        Returns:
            Beta score (0-100, higher = riskier)
        """
        # Beta of 1.0 = market risk (50 score)
        # Beta of 0.0 = no risk (0 score)
        # Beta of 2.0+ = very high risk (100 score)
        
        if beta < 0:
            # Negative beta is actually lower risk (inverse correlation)
            return max(0, 50 + (beta * 25))
        
        # Normalize: beta 0-2 maps to score 0-100
        score = beta * 50
        return min(max(score, 0), 100)

    def calculate_leverage_score(
        self,
        debt_to_equity: float,
        interest_coverage: Optional[float] = None
    ) -> float:
        """
        Calculate leverage risk score.
        
        Args:
            debt_to_equity: Debt-to-equity ratio
            interest_coverage: Interest coverage ratio (EBIT/Interest)
        
        Returns:
            Leverage score (0-100, higher = riskier)
        """
        # D/E ratio scoring
        # 0.0 = 0 score, 1.0 = 50 score, 3.0+ = 100 score
        de_score = min((debt_to_equity / 3.0) * 100, 100)
        
        # Interest coverage adjustment
        if interest_coverage is not None:
            if interest_coverage < 1.5:
                # Very risky - can't cover interest
                coverage_penalty = 30
            elif interest_coverage < 3.0:
                coverage_penalty = 15
            elif interest_coverage < 5.0:
                coverage_penalty = 5
            else:
                coverage_penalty = 0
            
            de_score = min(de_score + coverage_penalty, 100)
        
        return min(max(de_score, 0), 100)

    def calculate_earnings_stability_score(
        self,
        earnings_volatility: float,
        consecutive_profitable_quarters: int
    ) -> float:
        """
        Calculate earnings stability risk score.
        
        Args:
            earnings_volatility: Standard deviation of quarterly earnings
            consecutive_profitable_quarters: Number of consecutive profitable quarters
        
        Returns:
            Earnings stability score (0-100, higher = riskier)
        """
        # High volatility = high risk
        volatility_score = min(earnings_volatility * 100, 100)
        
        # More consecutive profitable quarters = lower risk
        if consecutive_profitable_quarters >= 12:
            stability_bonus = -30
        elif consecutive_profitable_quarters >= 8:
            stability_bonus = -20
        elif consecutive_profitable_quarters >= 4:
            stability_bonus = -10
        else:
            stability_bonus = 20  # Penalty for inconsistent profitability
        
        final_score = volatility_score + stability_bonus
        return min(max(final_score, 0), 100)

    def calculate_sector_risk_score(self, sector: str) -> float:
        """
        Calculate sector-based risk score.
        
        Args:
            sector: Sector name
        
        Returns:
            Sector risk score (0-100, higher = riskier)
        """
        return self.SECTOR_RISK_MAP.get(sector, 50)  # Default to moderate risk

    def calculate_valuation_risk_score(
        self,
        pe_ratio: Optional[float] = None,
        price_to_book: Optional[float] = None,
        price_to_sales: Optional[float] = None,
    ) -> float:
        """
        Calculate valuation risk score.
        
        Args:
            pe_ratio: Price-to-earnings ratio
            price_to_book: Price-to-book ratio
            price_to_sales: Price-to-sales ratio
        
        Returns:
            Valuation risk score (0-100, higher = riskier)
        """
        scores = []
        
        if pe_ratio is not None and pe_ratio > 0:
            # P/E scoring: 0-15 = low risk, 15-30 = moderate, 30+ = high
            pe_score = min((pe_ratio / 50) * 100, 100)
            scores.append(pe_score)
        
        if price_to_book is not None and price_to_book > 0:
            # P/B scoring: 0-2 = low risk, 2-5 = moderate, 5+ = high
            pb_score = min((price_to_book / 8) * 100, 100)
            scores.append(pb_score)
        
        if price_to_sales is not None and price_to_sales > 0:
            # P/S scoring: 0-2 = low risk, 2-5 = moderate, 5+ = high
            ps_score = min((price_to_sales / 8) * 100, 100)
            scores.append(ps_score)
        
        # Average available valuation metrics
        if scores:
            return sum(scores) / len(scores)
        
        return 50  # Default to moderate risk if no data

    def calculate_overall_risk(self, components: RiskComponents) -> float:
        """
        Calculate overall risk score from components.
        
        Args:
            components: Individual risk component scores
        
        Returns:
            Overall risk score (0-100)
        """
        overall = (
            self.WEIGHTS["volatility"] * components.volatility_score +
            self.WEIGHTS["beta"] * components.beta_score +
            self.WEIGHTS["leverage"] * components.leverage_score +
            self.WEIGHTS["earnings_stability"] * components.earnings_stability_score +
            self.WEIGHTS["sector"] * components.sector_risk_score +
            self.WEIGHTS["valuation"] * components.valuation_risk_score
        )
        
        return min(max(overall, 0), 100)

    def classify_risk_level(self, risk_score: float) -> RiskLevel:
        """
        Classify risk score into risk level.
        
        Args:
            risk_score: Overall risk score (0-100)
        
        Returns:
            Risk level classification
        """
        if risk_score <= self.CONSERVATIVE_THRESHOLD:
            return RiskLevel.CONSERVATIVE
        elif risk_score <= self.MODERATE_THRESHOLD:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.AGGRESSIVE

    def get_risk_band(self, risk_score: float) -> str:
        """
        Get risk band description.
        
        Args:
            risk_score: Overall risk score (0-100)
        
        Returns:
            Risk band string (e.g., "0-33")
        """
        if risk_score <= self.CONSERVATIVE_THRESHOLD:
            return "0-33"
        elif risk_score <= self.MODERATE_THRESHOLD:
            return "34-66"
        else:
            return "67-100"

    def generate_explanation(
        self,
        ticker: str,
        risk_score: float,
        risk_level: RiskLevel,
        components: RiskComponents
    ) -> str:
        """
        Generate human-readable risk explanation.
        
        Args:
            ticker: Stock ticker
            risk_score: Overall risk score
            risk_level: Risk level classification
            components: Risk components
        
        Returns:
            Explanation text
        """
        # Find highest risk components
        component_scores = {
            "Volatility": components.volatility_score,
            "Beta": components.beta_score,
            "Leverage": components.leverage_score,
            "Earnings Stability": components.earnings_stability_score,
            "Sector": components.sector_risk_score,
            "Valuation": components.valuation_risk_score,
        }
        
        sorted_components = sorted(
            component_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        top_risks = sorted_components[:2]
        
        explanation = (
            f"{ticker} has an overall risk score of {risk_score:.1f}, "
            f"classified as {risk_level.value}. "
            f"Primary risk factors are {top_risks[0][0]} ({top_risks[0][1]:.1f}) "
            f"and {top_risks[1][0]} ({top_risks[1][1]:.1f})."
        )
        
        return explanation

    def analyze_stock_risk(
        self,
        ticker: str,
        historical_volatility: float,
        beta: float,
        debt_to_equity: float,
        earnings_volatility: float,
        consecutive_profitable_quarters: int,
        sector: str,
        volatility_percentile: Optional[float] = None,
        interest_coverage: Optional[float] = None,
        pe_ratio: Optional[float] = None,
        price_to_book: Optional[float] = None,
        price_to_sales: Optional[float] = None,
    ) -> RiskAnalysis:
        """
        Perform complete risk analysis on a stock.
        
        Args:
            ticker: Stock ticker symbol
            historical_volatility: Annualized volatility
            beta: Stock beta vs market
            debt_to_equity: Debt-to-equity ratio
            earnings_volatility: Earnings volatility
            consecutive_profitable_quarters: Consecutive profitable quarters
            sector: Stock sector
            volatility_percentile: Optional volatility percentile
            interest_coverage: Optional interest coverage ratio
            pe_ratio: Optional P/E ratio
            price_to_book: Optional P/B ratio
            price_to_sales: Optional P/S ratio
        
        Returns:
            Complete risk analysis
        """
        logger.info(f"Analyzing risk for {ticker}")
        
        # Calculate individual components
        components = RiskComponents(
            volatility_score=self.calculate_volatility_score(
                historical_volatility, volatility_percentile
            ),
            beta_score=self.calculate_beta_score(beta),
            leverage_score=self.calculate_leverage_score(
                debt_to_equity, interest_coverage
            ),
            earnings_stability_score=self.calculate_earnings_stability_score(
                earnings_volatility, consecutive_profitable_quarters
            ),
            sector_risk_score=self.calculate_sector_risk_score(sector),
            valuation_risk_score=self.calculate_valuation_risk_score(
                pe_ratio, price_to_book, price_to_sales
            ),
        )
        
        # Calculate overall risk
        overall_risk = self.calculate_overall_risk(components)
        risk_level = self.classify_risk_level(overall_risk)
        risk_band = self.get_risk_band(overall_risk)
        explanation = self.generate_explanation(ticker, overall_risk, risk_level, components)
        
        logger.info(
            f"Risk analysis complete for {ticker}: "
            f"score={overall_risk:.1f}, level={risk_level.value}"
        )
        
        return RiskAnalysis(
            ticker=ticker,
            overall_risk_score=overall_risk,
            risk_level=risk_level,
            components=components,
            risk_band=risk_band,
            explanation=explanation,
        )

"""
Recommendation Engine

Implements the final recommendation scoring algorithm:
    Final Score = (0.4 * Research Score) +
                  (0.3 * Signal Score) +
                  (0.2 * Risk Alignment Score) +
                  (0.1 * Macro Fit Score)

Filters stocks by user risk band and ranks top N recommendations.
"""
from dataclasses import dataclass
from typing import List, Optional

from app.core.logging import get_logger
from app.services.risk_engine import RiskLevel

logger = get_logger(__name__)


@dataclass
class RecommendationScore:
    """Individual recommendation score components."""
    research_score: float
    signal_score: float
    risk_alignment_score: float
    macro_fit_score: float
    final_score: float


@dataclass
class StockRecommendation:
    """Complete stock recommendation."""
    ticker: str
    scores: RecommendationScore
    explanation: str
    reasoning_metadata: dict
    rank: int


class RecommendationEngine:
    """Recommendation scoring and ranking engine."""
    
    # Component weights
    WEIGHTS = {
        "research": 0.4,
        "signal": 0.3,
        "risk_alignment": 0.2,
        "macro_fit": 0.1,
    }
    
    def calculate_risk_alignment_score(
        self,
        stock_risk_score: float,
        user_risk_level: str,
        user_volatility_tolerance: float,
    ) -> float:
        """
        Calculate how well stock risk aligns with user profile.
        
        Args:
            stock_risk_score: Stock's risk score (0-100)
            user_risk_level: User's risk level (Conservative/Moderate/Aggressive)
            user_volatility_tolerance: User's volatility tolerance (0-100)
        
        Returns:
            Alignment score (0-100, higher = better alignment)
        """
        # Define user risk bands
        risk_bands = {
            "Conservative": (0, 33),
            "Moderate": (34, 66),
            "Aggressive": (67, 100),
        }
        
        min_risk, max_risk = risk_bands.get(user_risk_level, (0, 100))
        
        # Check if stock is in user's risk band
        if min_risk <= stock_risk_score <= max_risk:
            # Perfect alignment
            base_score = 100
        else:
            # Calculate distance from band
            if stock_risk_score < min_risk:
                distance = min_risk - stock_risk_score
            else:
                distance = stock_risk_score - max_risk
            
            # Penalize based on distance
            base_score = max(0, 100 - (distance * 2))
        
        # Adjust by volatility tolerance
        volatility_factor = user_volatility_tolerance / 100
        adjusted_score = base_score * (0.7 + (volatility_factor * 0.3))
        
        return min(max(adjusted_score, 0), 100)
    
    def calculate_macro_fit_score(
        self,
        sector: str,
        current_market_regime: str = "neutral",
    ) -> float:
        """
        Calculate macro environment fit score.
        
        Args:
            sector: Stock sector
            current_market_regime: Current market regime (bull/bear/neutral)
        
        Returns:
            Macro fit score (0-100)
        """
        # Simplified sector rotation logic
        # In production, this would use actual macro indicators
        
        sector_scores = {
            "bull": {
                "Technology": 80,
                "Consumer Discretionary": 75,
                "Financials": 70,
                "Industrials": 65,
                "Energy": 60,
                "Materials": 60,
                "Healthcare": 55,
                "Consumer Staples": 50,
                "Utilities": 45,
                "Real Estate": 50,
            },
            "bear": {
                "Utilities": 80,
                "Consumer Staples": 75,
                "Healthcare": 70,
                "Real Estate": 60,
                "Financials": 50,
                "Industrials": 45,
                "Materials": 45,
                "Energy": 50,
                "Technology": 40,
                "Consumer Discretionary": 35,
            },
            "neutral": {
                sector: 50 for sector in [
                    "Technology", "Healthcare", "Financials", "Energy",
                    "Utilities", "Consumer Staples", "Consumer Discretionary",
                    "Industrials", "Materials", "Real Estate"
                ]
            },
        }
        
        regime_scores = sector_scores.get(current_market_regime, sector_scores["neutral"])
        return regime_scores.get(sector, 50)
    
    def calculate_final_score(
        self,
        research_score: float,
        signal_score: float,
        risk_alignment_score: float,
        macro_fit_score: float,
    ) -> float:
        """
        Calculate final recommendation score.
        
        Args:
            research_score: Research quality score (0-100)
            signal_score: Signal strength score (0-100)
            risk_alignment_score: Risk alignment score (0-100)
            macro_fit_score: Macro fit score (0-100)
        
        Returns:
            Final score (0-100)
        """
        final = (
            self.WEIGHTS["research"] * research_score +
            self.WEIGHTS["signal"] * signal_score +
            self.WEIGHTS["risk_alignment"] * risk_alignment_score +
            self.WEIGHTS["macro_fit"] * macro_fit_score
        )
        
        return min(max(final, 0), 100)
    
    def generate_explanation(
        self,
        ticker: str,
        scores: RecommendationScore,
        sector: str,
        user_risk_level: str,
    ) -> str:
        """
        Generate human-readable recommendation explanation.
        
        Args:
            ticker: Stock ticker
            scores: Recommendation scores
            sector: Stock sector
            user_risk_level: User's risk level
        
        Returns:
            Explanation text
        """
        explanation = (
            f"{ticker} is recommended with a score of {scores.final_score:.1f}/100. "
            f"This recommendation is based on strong research quality ({scores.research_score:.1f}), "
            f"positive market signals ({scores.signal_score:.1f}), "
            f"good alignment with your {user_risk_level} risk profile ({scores.risk_alignment_score:.1f}), "
            f"and favorable macro conditions for {sector} ({scores.macro_fit_score:.1f})."
        )
        
        return explanation
    
    def filter_by_risk_band(
        self,
        stocks: List[dict],
        user_risk_level: str,
    ) -> List[dict]:
        """
        Filter stocks by user's risk band.
        
        Args:
            stocks: List of stock data dictionaries
            user_risk_level: User's risk level
        
        Returns:
            Filtered list of stocks
        """
        risk_bands = {
            "Conservative": (0, 33),
            "Moderate": (34, 66),
            "Aggressive": (67, 100),
        }
        
        min_risk, max_risk = risk_bands.get(user_risk_level, (0, 100))
        
        filtered = [
            stock for stock in stocks
            if min_risk <= stock.get("risk_score", 50) <= max_risk
        ]
        
        logger.info(
            f"Filtered {len(stocks)} stocks to {len(filtered)} "
            f"for {user_risk_level} risk level"
        )
        
        return filtered
    
    def rank_recommendations(
        self,
        stocks: List[dict],
        user_risk_level: str,
        user_volatility_tolerance: float,
        top_n: int = 10,
    ) -> List[StockRecommendation]:
        """
        Rank stocks and return top N recommendations.
        
        Args:
            stocks: List of stock data with scores
            user_risk_level: User's risk level
            user_volatility_tolerance: User's volatility tolerance
            top_n: Number of top recommendations to return
        
        Returns:
            List of ranked recommendations
        """
        logger.info(f"Ranking {len(stocks)} stocks for recommendations")
        
        recommendations = []
        
        for stock in stocks:
            # Calculate risk alignment
            risk_alignment = self.calculate_risk_alignment_score(
                stock.get("risk_score", 50),
                user_risk_level,
                user_volatility_tolerance,
            )
            
            # Calculate macro fit
            macro_fit = self.calculate_macro_fit_score(
                stock.get("sector", "Unknown")
            )
            
            # Calculate final score
            final_score = self.calculate_final_score(
                stock.get("research_score", 50),
                stock.get("signal_score", 50),
                risk_alignment,
                macro_fit,
            )
            
            scores = RecommendationScore(
                research_score=stock.get("research_score", 50),
                signal_score=stock.get("signal_score", 50),
                risk_alignment_score=risk_alignment,
                macro_fit_score=macro_fit,
                final_score=final_score,
            )
            
            explanation = self.generate_explanation(
                stock["ticker"],
                scores,
                stock.get("sector", "Unknown"),
                user_risk_level,
            )
            
            recommendations.append(
                StockRecommendation(
                    ticker=stock["ticker"],
                    scores=scores,
                    explanation=explanation,
                    reasoning_metadata={
                        "research_score": scores.research_score,
                        "signal_score": scores.signal_score,
                        "risk_alignment_score": scores.risk_alignment_score,
                        "macro_fit_score": scores.macro_fit_score,
                        "user_risk_level": user_risk_level,
                        "stock_sector": stock.get("sector"),
                    },
                    rank=0,  # Will be set after sorting
                )
            )
        
        # Sort by final score
        recommendations.sort(key=lambda x: x.scores.final_score, reverse=True)
        
        # Assign ranks
        for i, rec in enumerate(recommendations[:top_n], 1):
            rec.rank = i
        
        logger.info(f"Generated top {top_n} recommendations")
        
        return recommendations[:top_n]

"""Recommendations API endpoints."""
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import DBSession, CurrentUser
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter()
recommendation_engine = RecommendationEngine()


class RecommendationScoresResponse(BaseModel):
    """Recommendation scores response schema."""
    research_score: float
    signal_score: float
    risk_alignment_score: float
    macro_fit_score: float
    final_score: float


class RecommendationResponse(BaseModel):
    """Single recommendation response schema."""
    ticker: str
    rank: int
    scores: RecommendationScoresResponse
    explanation: str
    reasoning_metadata: dict


class RecommendationsListResponse(BaseModel):
    """List of recommendations response schema."""
    recommendations: List[RecommendationResponse]
    total_count: int
    user_risk_level: str


@router.get("/", response_model=RecommendationsListResponse)
async def get_recommendations(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 10,
) -> RecommendationsListResponse:
    """
    Get personalized stock recommendations.
    
    Args:
        current_user: Authenticated user
        db: Database session
        limit: Number of recommendations to return
    
    Returns:
        List of personalized recommendations
    """
    # TODO: Fetch user risk profile from database
    user_risk_level = "Moderate"
    user_volatility_tolerance = 60.0
    
    # TODO: Fetch stocks from database with scores
    # Mock stock data
    mock_stocks = [
        {
            "ticker": "AAPL",
            "sector": "Technology",
            "risk_score": 55.0,
            "research_score": 85.0,
            "signal_score": 75.0,
        },
        {
            "ticker": "MSFT",
            "sector": "Technology",
            "risk_score": 50.0,
            "research_score": 90.0,
            "signal_score": 80.0,
        },
        {
            "ticker": "JNJ",
            "sector": "Healthcare",
            "risk_score": 35.0,
            "research_score": 80.0,
            "signal_score": 65.0,
        },
    ]
    
    # Filter by risk band
    filtered_stocks = recommendation_engine.filter_by_risk_band(
        mock_stocks,
        user_risk_level,
    )
    
    # Rank recommendations
    recommendations = recommendation_engine.rank_recommendations(
        filtered_stocks,
        user_risk_level,
        user_volatility_tolerance,
        top_n=limit,
    )
    
    # Convert to response format
    response_recommendations = [
        RecommendationResponse(
            ticker=rec.ticker,
            rank=rec.rank,
            scores=RecommendationScoresResponse(
                research_score=rec.scores.research_score,
                signal_score=rec.scores.signal_score,
                risk_alignment_score=rec.scores.risk_alignment_score,
                macro_fit_score=rec.scores.macro_fit_score,
                final_score=rec.scores.final_score,
            ),
            explanation=rec.explanation,
            reasoning_metadata=rec.reasoning_metadata,
        )
        for rec in recommendations
    ]
    
    return RecommendationsListResponse(
        recommendations=response_recommendations,
        total_count=len(response_recommendations),
        user_risk_level=user_risk_level,
    )

from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DBSession
from app.models.recommendation import Recommendation
from app.models.signal import Signal
from app.models.stock import Stock
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

    recommendations: list[RecommendationResponse]
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
    # 1. Fetch user risk profile from current authenticated user
    user_risk_level = current_user.get("risk_level") or "Moderate"
    tolerance = current_user.get("volatility_tolerance")
    user_volatility_tolerance = float(tolerance) if tolerance is not None else 60.0

    # 2. Fetch active stocks from database
    stmt = select(Stock)
    result = await db.execute(stmt)
    stocks_db = result.scalars().all()

    if not stocks_db:
        return RecommendationsListResponse(
            recommendations=[],
            total_count=0,
            user_risk_level=user_risk_level,
        )

    # 3. Aggregate recent signal strength per ticker across all signals
    sig_stmt = select(Signal.ticker, func.avg(Signal.strength)).group_by(Signal.ticker)
    sig_result = await db.execute(sig_stmt)
    signal_averages: dict[str, float] = {t: float(avg) for t, avg in sig_result.all()}

    # Build candidate stock dictionaries
    candidate_stocks = [
        {
            "ticker": s.ticker,
            "sector": s.sector or "Technology",
            "risk_score": s.risk_score if s.risk_score is not None else 50.0,
            "research_score": s.research_score if s.research_score is not None else 50.0,
            "signal_score": float(signal_averages.get(s.ticker) or 50.0),
        }
        for s in stocks_db
    ]

    # 4. Filter by risk band
    filtered_stocks = recommendation_engine.filter_by_risk_band(
        candidate_stocks,
        user_risk_level,
    )

    # Fallback to candidates if risk band filtering yields empty set to prevent blank screen
    if not filtered_stocks:
        filtered_stocks = candidate_stocks

    # 5. Rank recommendations
    recommendations = recommendation_engine.rank_recommendations(
        filtered_stocks,
        user_risk_level,
        user_volatility_tolerance,
        top_n=limit,
    )

    # 6. Persist recommendations into database
    user_id_int = int(current_user["id"])
    active_stmt = select(Recommendation).where(
        Recommendation.user_id == user_id_int,
        Recommendation.is_active.is_(True),
    )
    prev_active = (await db.execute(active_stmt)).scalars().all()
    for prev in prev_active:
        prev.is_active = False

    now = datetime.utcnow()
    expires = now + timedelta(days=1)

    for rec in recommendations:
        db_rec = Recommendation(
            user_id=user_id_int,
            ticker=rec.ticker,
            final_score=rec.scores.final_score,
            research_score=rec.scores.research_score,
            signal_score=rec.scores.signal_score,
            risk_alignment_score=rec.scores.risk_alignment_score,
            macro_fit_score=rec.scores.macro_fit_score,
            explanation_text=rec.explanation,
            reasoning_metadata=rec.reasoning_metadata,
            created_at=now,
            expires_at=expires,
            is_active=True,
        )
        db.add(db_rec)

    await db.commit()

    # 7. Convert to response format
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

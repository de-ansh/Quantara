from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.clock import utcnow
from app.core.dependencies import CurrentUser, DBSession
from app.models.recommendation import Recommendation
from app.models.signal import Signal
from app.models.stock import Stock
from app.services.recommendation_engine import RecommendationEngine, signal_score

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

    # 3. Direction-aware signal score per ticker (50 when a stock has no signals)
    by_ticker: dict[str, list[tuple[float, dict | None]]] = {}
    for ticker, strength, data in (await db.execute(select(Signal.ticker, Signal.strength, Signal.data))).all():
        by_ticker.setdefault(ticker, []).append((strength, data))

    # Only stocks with computed risk and research scores can be ranked
    candidate_stocks = [
        {
            "ticker": s.ticker,
            "sector": s.sector or "Unknown",
            "risk_score": s.risk_score,
            "research_score": s.research_score,
            "signal_score": signal_score(by_ticker.get(s.ticker, [])),
        }
        for s in stocks_db
        if s.risk_score is not None and s.research_score is not None
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

    now = utcnow()
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


class VerdictResponse(BaseModel):
    """Plain-language call on one stock for the current user's risk profile."""

    ticker: str
    verdict: str  # Buy | Hold | Avoid | Unrated
    final_score: float | None
    reasons: list[str]
    missing: list[str]  # what has to be computed before a verdict is possible
    user_risk_level: str


@router.get("/{ticker}/verdict", response_model=VerdictResponse)
async def get_verdict(ticker: str, current_user: CurrentUser, db: DBSession) -> VerdictResponse:
    """Buy / Hold / Avoid for one stock, from the same score that ranks recommendations."""
    user_risk_level = current_user.get("risk_level") or "Moderate"
    tolerance = current_user.get("volatility_tolerance")
    stock = await db.get(Stock, ticker.upper())
    missing = []
    if stock is None or stock.research_score is None:
        missing.append("research report")
    if stock is None or stock.risk_score is None:
        missing.append("risk score")
    if missing:
        return VerdictResponse(ticker=ticker.upper(), verdict="Unrated", final_score=None, reasons=[],
                               missing=missing, user_risk_level=user_risk_level)

    from app.services.verdict_tracking import verdict_for

    v = await verdict_for(db, stock, user_risk_level, float(tolerance) if tolerance is not None else None)
    assert v is not None  # both scores were checked above
    return VerdictResponse(ticker=stock.ticker, verdict=v.verdict, final_score=round(v.final_score, 1),
                           reasons=v.reasons, missing=[], user_risk_level=user_risk_level)


class VerdictOutcome(BaseModel):
    verdict: str
    count: int
    avg_return_pct: float
    vs_all_rated_pct: float  # this verdict's average return minus every rated stock's
    share_that_rose_pct: float


class TrackRecordResponse(BaseModel):
    """How stocks given each verdict did afterwards; empty until the first horizon has passed."""

    risk_level: str
    horizon_days: int
    tracking_since: date | None
    first_results_on: date | None
    all_rated_avg_return_pct: float | None
    verdicts: list[VerdictOutcome]


@router.get("/track-record", response_model=TrackRecordResponse)
async def get_track_record(
    current_user: CurrentUser,
    db: DBSession,
    horizon_days: Annotated[int, Query()] = 30,
) -> TrackRecordResponse:
    """Returns `horizon_days` after each daily verdict for the user's risk profile."""
    from app.services.verdict_tracking import track_record

    if horizon_days not in (30, 90, 180):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "horizon_days must be 30, 90 or 180")
    record = await track_record(db, current_user.get("risk_level") or "Moderate", horizon_days)
    return TrackRecordResponse(**record)

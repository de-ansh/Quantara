"""Signals API endpoints."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DBSession

router = APIRouter()


class SignalResponse(BaseModel):
    """Signal response schema."""

    id: int
    ticker: str
    signal_type: str
    strength: float
    confidence: float
    timestamp: datetime
    metadata: dict


class SignalsListResponse(BaseModel):
    """List of signals response schema."""

    signals: list[SignalResponse]
    total_count: int


class SentimentCurvePoint(BaseModel):
    """Hourly sentiment data point."""

    time: str
    timestamp: datetime
    social: float
    news: float
    volume: int
    sentiment_label: str


class SentimentCurveResponse(BaseModel):
    """Sentiment curve response schema."""

    ticker: str | None = None
    period: str
    points: list[SentimentCurvePoint]
    current_social_score: float
    current_news_score: float
    sentiment_trend: str


@router.get("/", response_model=SignalsListResponse)
async def get_signals(
    current_user: CurrentUser,
    db: DBSession,
    ticker: str | None = None,
    signal_type: str | None = None,
    limit: int = 50,
) -> SignalsListResponse:
    """
    Get recent market signals.

    Args:
        current_user: Authenticated user
        db: Database session
        ticker: Optional ticker filter
        signal_type: Optional signal type filter
        limit: Number of signals to return

    Returns:
        List of signals
    """
    from sqlalchemy import desc, select

    from app.models.signal import Signal as DBSignal

    stmt = select(DBSignal)

    if ticker:
        stmt = stmt.where(DBSignal.ticker == ticker.upper())
    if signal_type:
        stmt = stmt.where(DBSignal.signal_type == signal_type)

    stmt = stmt.order_by(desc(DBSignal.timestamp)).limit(limit)
    result = await db.execute(stmt)
    db_signals = result.scalars().all()

    signals_response = [
        SignalResponse(
            id=sig.id,
            ticker=sig.ticker,
            signal_type=sig.signal_type,
            strength=sig.strength,
            confidence=sig.confidence,
            timestamp=sig.timestamp,
            metadata=sig.data or {},
        )
        for sig in db_signals
    ]

    return SignalsListResponse(
        signals=signals_response,
        total_count=len(signals_response),
    )


@router.get("/sentiment-curve", response_model=SentimentCurveResponse)
async def get_sentiment_curve(
    current_user: CurrentUser,
    db: DBSession,
    ticker: str | None = None,
    hours: int = 8,
) -> SentimentCurveResponse:
    """
    Get intraday time-bucketed social and news sentiment curve.

    Args:
        current_user: Authenticated user
        db: Database session
        ticker: Optional stock ticker filter
        hours: Number of hourly buckets (default: 8)

    Returns:
        SentimentCurveResponse with time-series points and aggregate trend
    """
    from datetime import datetime, timedelta

    from sqlalchemy import desc, select

    from app.models.signal import Signal as DBSignal
    from app.services.signal_engine import SignalEngine

    engine = SignalEngine()

    cutoff = datetime.utcnow() - timedelta(hours=max(hours, 24))
    stmt = select(DBSignal).where(
        DBSignal.timestamp >= cutoff,
        DBSignal.signal_type.in_(["sentiment_spike", "news_sentiment", "social_sentiment"])
    )
    if ticker:
        stmt = stmt.where(DBSignal.ticker == ticker.upper())

    stmt = stmt.order_by(desc(DBSignal.timestamp)).limit(200)
    result = await db.execute(stmt)
    db_signals = result.scalars().all()

    curve = engine.build_intraday_sentiment_curve(
        db_signals=list(db_signals),
        ticker=ticker,
        hours=hours,
    )

    return SentimentCurveResponse(
        ticker=curve.get("ticker"),
        period=curve.get("period", f"{hours}H"),
        points=[
            SentimentCurvePoint(
                time=p["time"],
                timestamp=datetime.fromisoformat(p["timestamp"]),
                social=p["social"],
                news=p["news"],
                volume=p["volume"],
                sentiment_label=p["sentiment_label"],
            )
            for p in curve.get("points", [])
        ],
        current_social_score=curve.get("current_social_score", 50.0),
        current_news_score=curve.get("current_news_score", 50.0),
        sentiment_trend=curve.get("sentiment_trend", "STABLE"),
    )

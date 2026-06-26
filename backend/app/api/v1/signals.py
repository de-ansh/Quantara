"""Signals API endpoints."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import DBSession, CurrentUser

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
    signals: List[SignalResponse]
    total_count: int


@router.get("/", response_model=SignalsListResponse)
async def get_signals(
    current_user: CurrentUser,
    db: DBSession,
    ticker: Optional[str] = None,
    signal_type: Optional[str] = None,
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
    from app.models.signal import Signal as DBSignal
    from sqlalchemy import select, desc
    
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
            metadata=sig.data or {}
        )
        for sig in db_signals
    ]
    
    return SignalsListResponse(
        signals=signals_response,
        total_count=len(signals_response),
    )

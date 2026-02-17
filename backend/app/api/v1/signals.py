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
    # TODO: Fetch from database with filters
    
    # Mock signals
    mock_signals = [
        SignalResponse(
            id=1,
            ticker="AAPL",
            signal_type="earnings_surprise",
            strength=85.0,
            confidence=95.0,
            timestamp=datetime.utcnow(),
            metadata={"surprise_pct": 15.5},
        ),
        SignalResponse(
            id=2,
            ticker="MSFT",
            signal_type="institutional_buying",
            strength=75.0,
            confidence=85.0,
            timestamp=datetime.utcnow(),
            metadata={"ownership_change_pct": 3.2},
        ),
    ]
    
    return SignalsListResponse(
        signals=mock_signals,
        total_count=len(mock_signals),
    )

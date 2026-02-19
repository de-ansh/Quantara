"""Signal model for tracking market signals and events."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, Integer, Index, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Signal(Base):
    """Signal model for market events and indicators."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    
    # Signal Information
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="earnings_surprise, institutional_buying, insider_buying, sentiment_spike"
    )
    strength: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Signal strength 0-100"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Confidence score 0-100"
    )
    
    # Additional Data
    data: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Additional signal-specific data"
    )
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_ticker_type_time", "ticker", "signal_type", "timestamp"),
        Index("idx_strength", "strength"),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal(ticker={self.ticker}, type={self.signal_type}, "
            f"strength={self.strength}, confidence={self.confidence})>"
        )

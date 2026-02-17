"""Recommendation model for personalized stock recommendations."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, Integer, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recommendation(Base):
    """Recommendation model with scoring and reasoning."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    
    # Scores
    final_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Final recommendation score 0-100"
    )
    research_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Research component score"
    )
    signal_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Signal component score"
    )
    risk_alignment_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Risk alignment with user profile"
    )
    macro_fit_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Macro environment fit score"
    )
    
    # Explanation
    explanation_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Human-readable explanation"
    )
    
    # Reasoning Metadata
    reasoning_metadata: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Detailed reasoning breakdown and factors"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="When this recommendation expires"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Whether recommendation is still valid"
    )

    __table_args__ = (
        Index("idx_user_active_score", "user_id", "is_active", "final_score"),
        Index("idx_ticker_score", "ticker", "final_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<Recommendation(id={self.id}, user_id={self.user_id}, ticker={self.ticker}, "
            f"score={self.final_score}, active={self.is_active})>"
        )

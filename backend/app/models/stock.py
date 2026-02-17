"""Stock model for storing stock information and scores."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Stock(Base):
    """Stock model with risk and research scores."""

    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Scores
    risk_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Risk score 0-100"
    )
    research_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Research quality score 0-100"
    )
    
    # Metadata
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_sector_risk", "sector", "risk_score"),
        Index("idx_research_score", "research_score"),
    )

    def __repr__(self) -> str:
        return f"<Stock(ticker={self.ticker}, sector={self.sector}, risk={self.risk_score})>"

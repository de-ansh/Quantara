"""Research report model for storing structured analysis."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, Integer, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResearchReport(Base):
    """Research report model with structured JSON data."""

    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    
    # Structured Data
    structured_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Structured research data validated by schema"
    )
    
    # Vector Embedding
    vector_embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Reference to vector DB embedding"
    )
    
    # Quality Metrics
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Confidence in analysis 0-100"
    )
    
    # Summary
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Human-readable summary"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="Report version number"
    )

    def __repr__(self) -> str:
        return (
            f"<ResearchReport(id={self.id}, ticker={self.ticker}, "
            f"confidence={self.confidence_score}, version={self.version})>"
        )

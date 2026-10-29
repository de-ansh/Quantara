"""Stock model for storing stock information and scores."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class Stock(Base):
    """Stock model with risk and research scores."""

    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Scores
    risk_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Risk score 0-100"
    )
    research_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Research quality score 0-100"
    )

    # Explorer fields
    pe_ratio: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Price-to-earnings ratio"
    )
    beta: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Beta vs market")
    market_cap: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Market cap in listing currency"
    )
    price: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Last price in listing currency"
    )
    previous_close: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Prior session close, for day change"
    )
    price_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="When price was last fetched from the market"
    )
    fundamentals_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="When market cap / P/E / beta were last fetched"
    )

    # Metadata
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_sector_risk", "sector", "risk_score"),
        Index("idx_research_score", "research_score"),
    )

    def __repr__(self) -> str:
        return f"<Stock(ticker={self.ticker}, sector={self.sector}, risk={self.risk_score})>"

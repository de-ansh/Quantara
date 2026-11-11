"""A company's reported quarterly results, from its NSE integrated filing (XBRL)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class QuarterlyResult(Base):
    __tablename__ = "quarterly_results"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    quarter_end: Mapped[date] = mapped_column(Date, primary_key=True)
    consolidated: Mapped[bool] = mapped_column(nullable=False)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Revenue from operations, rupees")
    profit: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Profit for the period, rupees")
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

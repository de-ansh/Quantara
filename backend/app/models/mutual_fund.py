"""Indian mutual fund schemes and their latest NAV, from AMFI's daily files."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class MutualFund(Base):
    """One scheme variant (e.g. Direct Plan, Growth); AMFI gives each its own code and NAV."""

    __tablename__ = "mutual_funds"

    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # with plan and option
    category: Mapped[str | None] = mapped_column(String(150), nullable=True)  # "Equity Scheme - Mid Cap Fund"
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)  # growth or payout
    isin_reinvest: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    prev_nav: Mapped[float | None] = mapped_column(Float, nullable=True)  # the NAV before nav_date's
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

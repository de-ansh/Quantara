"""Indian mutual fund schemes and their latest NAV, from AMFI's daily files."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
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
    # What the fund owns (from its public Groww page): where to fetch it, the portfolio's date, when last checked
    groww_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    holdings_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    holdings_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FundHolding(Base):
    """One line of a fund's latest monthly portfolio: a company, bond or cash, as a share of the fund."""

    __tablename__ = "fund_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("mutual_funds.scheme_code", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)  # listed Indian stock, when matched
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # equity | debt | cash | gold | other
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)  # % of the fund

"""Every listed security we can look up, from the exchanges' official lists (not tracked)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class ListedSecurity(Base):
    """Directory row; a stock enters `stocks` (and the price jobs) only once someone opens it."""

    __tablename__ = "listed_securities"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)  # Yahoo form: TCS.NS, ABB.BO, BRK-B
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    is_etf: Mapped[bool] = mapped_column(default=False, nullable=False)
    # End-of-day prices for Indian listings from BSE's bhavcopy (matched by ISIN); None for US rows
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

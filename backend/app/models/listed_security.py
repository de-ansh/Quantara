"""Every listed security we can look up, from the exchanges' official lists (not tracked or priced)."""

from datetime import datetime

from sqlalchemy import DateTime, String
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

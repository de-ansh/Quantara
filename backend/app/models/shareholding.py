"""Shareholding pattern per stock per quarter, from NSE shareholding filings.

Promoter % comes for every tracked stock from NSE's list; the institutional split is read from each
filing's XBRL when someone opens the stock, so those columns stay empty until then.
"""

from datetime import date

from sqlalchemy import BigInteger, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Shareholding(Base):
    __tablename__ = "shareholdings"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    quarter: Mapped[date] = mapped_column(Date, primary_key=True)  # quarter-end the filing is "as on"
    promoter_pct: Mapped[float] = mapped_column(Float, nullable=False)
    fii_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Foreign institutions (FPIs etc.)")
    dii_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Domestic institutions, incl. mutual funds")
    mf_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Mutual funds (part of DII)")
    retail_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Non-institutional public")
    shareholders: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

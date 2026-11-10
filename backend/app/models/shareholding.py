"""Promoter holding per stock per quarter, from NSE shareholding filings."""

from datetime import date

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Shareholding(Base):
    __tablename__ = "shareholdings"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    quarter: Mapped[date] = mapped_column(Date, primary_key=True)  # quarter-end the filing is "as on"
    promoter_pct: Mapped[float] = mapped_column(Float, nullable=False)

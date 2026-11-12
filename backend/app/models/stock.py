"""Stock model for storing stock information and scores."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, String, Text
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
    # Screening fundamentals from Yahoo, in percent except debt/equity (a ratio, 0.5 = 50%)
    roe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # From annual statements (refreshed weekly): ROCE on capital employed, 3-year compound growth
    roce_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_cagr_3y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_cagr_3y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    statements_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # NSE shareholding: promoter stake and its change from the previous quarter, in percentage points
    promoter_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    promoter_change_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    shareholding_quarter: Mapped[date | None] = mapped_column(Date, nullable=True)
    results_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Daily technical snapshot from a year of closes (screener filters); gaps are % from the level
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma50_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Price vs 50-day average, %")
    sma200_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Price vs 200-day average, %")
    from_high_52w_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Price vs 52-week high, % (<= 0)")
    from_low_52w_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Price vs 52-week low, % (>= 0)")
    turnover_1d: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Last session's traded value, listing currency")
    turnover_20d: Mapped[float | None] = mapped_column(Float, nullable=True, comment="20-session average traded value")
    technicals_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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

    # Earnings filing (transcript / results PDF) the user linked, used as research context
    filing_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filing_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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

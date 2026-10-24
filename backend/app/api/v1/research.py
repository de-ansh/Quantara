"""Research API endpoints."""


from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.services.research_engine import ResearchEngine

router = APIRouter()
research_engine = ResearchEngine()


class ResearchReportResponse(BaseModel):
    """Research report response schema."""

    ticker: str
    summary: str
    key_insights: list[str]
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
    confidence_score: float
    generated_at: datetime | None = None


class StockSearchItem(BaseModel):
    """Stock item schema for explorer list."""

    ticker: str
    name: str
    price: str
    cap: str
    risk: float
    signal: str
    alpha: str
    status: str
    change_pct: float | None = None
    price_updated_at: datetime | None = None
    sector: str | None = None
    pe: float | None = None
    beta: float | None = None


def _currency(ticker: str) -> str:
    return "₹" if ticker.upper().endswith((".NS", ".BO")) else "$"


def format_price(value: float | None, ticker: str) -> str:
    """Display price in the listing currency, e.g. $189.42 / ₹1,215.40."""
    return f"{_currency(ticker)}{value:,.2f}" if value is not None else "N/A"


def format_market_cap(value: float | None, ticker: str) -> str:
    """Display market cap with T/B/M suffix in the listing currency."""
    if value is None:
        return "N/A"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= divisor:
            return f"{_currency(ticker)}{value / divisor:.2f}{suffix}"
    return f"{_currency(ticker)}{value:,.0f}"


def to_search_item(stock: Any) -> StockSearchItem:
    """Explorer row for a Stock record."""
    sig_str = "Neutral"
    if stock.research_score is not None:
        if stock.research_score >= 88:
            sig_str = "Strong"
        elif stock.research_score >= 70:
            sig_str = "High"
        elif stock.research_score < 40:
            sig_str = "Weak"

    return StockSearchItem(
        ticker=stock.ticker,
        name=stock.name or stock.ticker,
        price=format_price(stock.price, stock.ticker),
        cap=format_market_cap(stock.market_cap, stock.ticker),
        risk=stock.risk_score or 50.0,
        signal=sig_str,
        alpha=stock.alpha_projection or "+0.0%",
        status=stock.status or "neutral",
        change_pct=(
            round((stock.price / stock.previous_close - 1) * 100, 2)
            if stock.price and stock.previous_close
            else None
        ),
        price_updated_at=stock.price_updated_at,
        sector=stock.sector,
        pe=stock.pe_ratio,
        beta=stock.beta,
    )


class StockSearchListResponse(BaseModel):
    """Stock search list response schema."""

    stocks: list[StockSearchItem]
    total_count: int


@router.get("/stocks/search", response_model=StockSearchListResponse)
async def search_stocks(
    current_user: CurrentUser,
    db: DBSession,
    query: str | None = None,
    market: str | None = None,
    pe_min: float | None = None,
    pe_max: float | None = None,
    beta_min: float | None = None,
    beta_max: float | None = None,
    risk_min: float | None = None,
    risk_max: float | None = None,
    signals: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StockSearchListResponse:
    """
    Search stocks with criteria filters and optional market region.

    Results are ordered by ticker; `total_count` is the number of matches before paging.
    """
    from sqlalchemy import and_, func, or_, select

    from app.models.signal import Signal
    from app.models.stock import Stock

    stmt = select(Stock)

    # Market region filter (US vs India)
    if market:
        m = market.strip().lower()
        if m in ("in", "india", "nse", "bse"):
            stmt = stmt.where(or_(Stock.ticker.ilike("%.NS"), Stock.ticker.ilike("%.BO")))
        elif m in ("us", "usa", "nyse", "nasdaq"):
            stmt = stmt.where(and_(~Stock.ticker.ilike("%.NS"), ~Stock.ticker.ilike("%.BO")))

    # 1. Join with signals if signal filters applied
    if signals:
        signal_list = [s.strip().lower() for s in signals.split(",") if s.strip()]
        if signal_list:
            mapped_types = []
            for s in signal_list:
                if "inflow" in s or "institutional" in s:
                    mapped_types.append("institutional_buying")
                elif "insider" in s:
                    mapped_types.append("insider_buying")
                elif "options" in s or "vol" in s or "sentiment" in s:
                    mapped_types.append("sentiment_spike")

            if mapped_types:
                sig_stmt = select(Signal.ticker).where(Signal.signal_type.in_(mapped_types))
                sig_res = await db.execute(sig_stmt)
                matching_tickers = set(sig_res.scalars().all())
                stmt = stmt.where(Stock.ticker.in_(matching_tickers))

    if query:
        stmt = stmt.where(or_(Stock.ticker.ilike(f"%{query}%"), Stock.name.ilike(f"%{query}%")))
    if pe_min is not None:
        stmt = stmt.where(Stock.pe_ratio >= pe_min)
    if pe_max is not None:
        stmt = stmt.where(Stock.pe_ratio <= pe_max)
    if beta_min is not None:
        stmt = stmt.where(Stock.beta >= beta_min)
    if beta_max is not None:
        stmt = stmt.where(Stock.beta <= beta_max)
    if risk_min is not None:
        stmt = stmt.where(Stock.risk_score >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Stock.risk_score <= risk_max)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(stmt.order_by(Stock.ticker).limit(limit).offset(offset))
    db_stocks = result.scalars().all()

    response_items = [to_search_item(stock) for stock in db_stocks]

    return StockSearchListResponse(stocks=response_items, total_count=int(total))


@router.get("/stocks/{ticker}/research", response_model=ResearchReportResponse)
async def get_stock_research(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
    redis: RedisClient,
    refresh: bool = False,
) -> ResearchReportResponse:
    """
    Get research report for a stock.

    Args:
        ticker: Stock ticker symbol
        current_user: Authenticated user
        db: Database session
        refresh: Regenerate even if the cached report is still fresh

    Returns:
        Research report
    """
    from sqlalchemy import select

    from app.models.research import ResearchReport

    ticker_upper = ticker.upper()

    # Check cache / database first
    stmt = select(ResearchReport).where(ResearchReport.ticker == ticker_upper)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    max_age = timedelta(hours=settings.research_cache_max_age_hours)
    if (
        not refresh
        and report
        and report.structured_json
        and datetime.utcnow() - report.updated_at < max_age
    ):
        return ResearchReportResponse(**{**report.structured_json, "generated_at": report.updated_at})

    # Each generation is a paid LLM call, so cap it per user.
    await enforce_rate_limit(
        redis,
        f"research:{current_user['id']}",
        settings.research_generation_limit_per_hour,
        3600,
    )
    report_data = await research_engine.generate_research_report(
        db,
        ticker_upper,
        openai_api_key=current_user["openai_api_key"],
        sec_user_agent=current_user["sec_user_agent"],
    )

    if not report_data and report and report.structured_json:
        # Refresh failed: a stale report beats an error.
        return ResearchReportResponse(**{**report.structured_json, "generated_at": report.updated_at})
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate research report for {ticker}",
        )

    return ResearchReportResponse(**{**report_data, "generated_at": datetime.utcnow()})


class PricePoint(BaseModel):
    """One close in a price history series."""

    date: str
    close: float


class PriceHistoryResponse(BaseModel):
    """Closing prices for a ticker over a range."""

    ticker: str
    range: str
    points: list[PricePoint]
    change_pct: float


# range -> (yfinance period, interval); weekly bars keep 5Y responses small
_HISTORY_RANGES: dict[str, tuple[str, str]] = {
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
}
_HISTORY_TTL_SECONDS = 15 * 60
_history_cache: dict[tuple[str, str], tuple[float, list[PricePoint]]] = {}


def _download_history(ticker: str, range_: str) -> list[PricePoint]:
    import yfinance as yf

    period, interval = _HISTORY_RANGES[range_]
    frame = yf.Ticker(ticker).history(period=period, interval=interval)
    if "Close" not in frame:
        return []
    return [
        PricePoint(date=ts.strftime("%Y-%m-%d"), close=round(float(v), 4))
        for ts, v in frame["Close"].dropna().items()
    ]


@router.get("/stocks/{ticker}/history", response_model=PriceHistoryResponse)
async def get_price_history(
    ticker: str,
    current_user: CurrentUser,
    range: Annotated[Literal["1M", "6M", "1Y", "5Y"], Query()] = "1Y",
) -> PriceHistoryResponse:
    """Closing price history for charts (cached for 15 minutes per ticker and range)."""
    import asyncio
    import time

    key = (ticker.upper(), range)
    cached = _history_cache.get(key)
    if cached and time.monotonic() - cached[0] < _HISTORY_TTL_SECONDS:
        points = cached[1]
    else:
        try:
            points = await asyncio.to_thread(_download_history, key[0], range)
        except Exception:
            points = []
        if points:  # don't cache failures
            _history_cache[key] = (time.monotonic(), points)

    if not points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price history found for {key[0]}",
        )
    change = (points[-1].close / points[0].close - 1) * 100 if points[0].close else 0.0
    return PriceHistoryResponse(
        ticker=key[0], range=range, points=points, change_pct=round(change, 2)
    )

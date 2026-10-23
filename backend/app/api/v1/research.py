"""Research API endpoints."""


from datetime import datetime, timedelta
from typing import Annotated, Any

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
    updated_at: datetime | None = None
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
        updated_at=stock.last_updated,
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

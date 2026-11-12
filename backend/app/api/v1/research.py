"""Research API endpoints."""


import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.clock import utcnow
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
    outlook_score: float | None = None  # absent on reports from before the outlook existed
    generated_at: datetime | None = None


class StockSearchItem(BaseModel):
    """Stock item schema for explorer list."""

    ticker: str
    name: str
    price: str
    cap: str
    risk: float | None
    signal: str
    status: str
    change_pct: float | None = None
    price_updated_at: datetime | None = None
    sector: str | None = None
    pe: float | None = None
    beta: float | None = None
    roe_pct: float | None = None
    debt_to_equity: float | None = None
    revenue_growth_pct: float | None = None
    profit_margin_pct: float | None = None
    dividend_yield_pct: float | None = None
    return_1y_pct: float | None = None
    roce_pct: float | None = None
    revenue_cagr_3y_pct: float | None = None
    profit_cagr_3y_pct: float | None = None
    promoter_pct: float | None = None
    promoter_change_pp: float | None = None
    rsi_14: float | None = None
    sma50_gap_pct: float | None = None
    sma200_gap_pct: float | None = None
    from_high_52w_pct: float | None = None
    from_low_52w_pct: float | None = None
    turnover_1d: float | None = None
    turnover_20d: float | None = None
    exchange: str | None = None
    tracked: bool = True  # False: directory-only, no price or scores until someone opens it
    call: str | None = None  # Buy / Hold / Avoid from the stock's numbers (moderate profile, no signals)


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


def _directory_item(d: Any) -> StockSearchItem:
    """Explorer row for an untracked listing: end-of-day price where the exchange file has one."""
    change = round((d.close / d.prev_close - 1) * 100, 2) if d.close and d.prev_close else None
    return StockSearchItem(
        ticker=d.ticker, name=d.name, price=format_price(d.close, d.ticker), cap="N/A", risk=None,
        signal="Unrated", status="neutral" if not change else "up" if change > 0 else "down", change_pct=change,
        price_updated_at=datetime.combine(d.price_date, datetime.min.time()) if d.price_date else None,
        exchange=d.exchange, tracked=False,
    )


def to_search_item(stock: Any) -> StockSearchItem:
    """Explorer row for a Stock record."""
    from app.services.stock_call import data_call

    call = data_call(stock).verdict
    sig_str = "Unrated"
    if stock.research_score is not None:
        sig_str = "Neutral"
        if stock.research_score >= 88:
            sig_str = "Strong"
        elif stock.research_score >= 70:
            sig_str = "High"
        elif stock.research_score < 40:
            sig_str = "Weak"

    change_pct = (
        round((stock.price / stock.previous_close - 1) * 100, 2)
        if stock.price and stock.previous_close
        else None
    )
    return StockSearchItem(
        ticker=stock.ticker,
        name=stock.name or stock.ticker,
        price=format_price(stock.price, stock.ticker),
        cap=format_market_cap(stock.market_cap, stock.ticker),
        risk=stock.risk_score,
        signal=sig_str,
        status="neutral" if not change_pct else "up" if change_pct > 0 else "down",
        change_pct=change_pct,
        price_updated_at=stock.price_updated_at,
        sector=stock.sector,
        pe=stock.pe_ratio,
        beta=stock.beta,
        roe_pct=stock.roe_pct,
        debt_to_equity=stock.debt_to_equity,
        revenue_growth_pct=stock.revenue_growth_pct,
        profit_margin_pct=stock.profit_margin_pct,
        dividend_yield_pct=stock.dividend_yield_pct,
        return_1y_pct=stock.return_1y_pct,
        roce_pct=stock.roce_pct,
        revenue_cagr_3y_pct=stock.revenue_cagr_3y_pct,
        profit_cagr_3y_pct=stock.profit_cagr_3y_pct,
        promoter_pct=stock.promoter_pct,
        promoter_change_pp=stock.promoter_change_pp,
        rsi_14=stock.rsi_14,
        sma50_gap_pct=stock.sma50_gap_pct,
        sma200_gap_pct=stock.sma200_gap_pct,
        from_high_52w_pct=stock.from_high_52w_pct,
        from_low_52w_pct=stock.from_low_52w_pct,
        turnover_1d=stock.turnover_1d,
        turnover_20d=stock.turnover_20d,
        call=None if call == "Unrated" else call,
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
    roe_min: float | None = None,
    debt_to_equity_max: float | None = None,
    revenue_growth_min: float | None = None,
    profit_margin_min: float | None = None,
    dividend_yield_min: float | None = None,
    return_1y_min: float | None = None,
    roce_min: float | None = None,
    revenue_cagr_3y_min: float | None = None,
    profit_cagr_3y_min: float | None = None,
    promoter_min: float | None = None,
    promoter_change_min: float | None = None,
    rsi_min: float | None = None,
    rsi_max: float | None = None,
    sma50_gap_min: float | None = None,
    sma50_gap_max: float | None = None,
    sma200_gap_min: float | None = None,
    sma200_gap_max: float | None = None,
    from_high_min: float | None = None,
    from_low_max: float | None = None,
    turnover_min_cr: float | None = None,
    sort: Annotated[str | None, Query(pattern=r"^-?(ticker|market_cap|pe|roe|roce|revenue_growth|revenue_cagr_3y|profit_cagr_3y|profit_margin|dividend_yield|return_1y|promoter|promoter_change|risk|rsi|turnover|from_high)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    track: bool = False,
) -> StockSearchListResponse:
    """
    Search stocks with criteria filters and optional market region.

    Tracked stocks come first, ordered by ticker. Without data filters (P/E, beta, risk,
    signals) the list continues into the directory of every listed NSE/BSE/US security.
    `track=true` (the stock page) starts tracking an exact-ticker directory hit.
    `total_count` is the number of matches before paging.
    """
    from sqlalchemy import and_, case, func, or_, select

    from app.models.listed_security import ListedSecurity
    from app.models.signal import Signal
    from app.models.stock import Stock

    if track and query and await db.get(Stock, query.strip().upper()) is None:
        if await db.get(ListedSecurity, query.strip().upper()) is not None:
            from app.services.stock_lookup import get_or_track_stock

            if await get_or_track_stock(db, query.strip().upper()) is not None:
                await db.commit()

    # A tracked ticker no exchange lists any more (delisted, renamed after a demerger) would show up
    # next to its successor, so search skips it; its page still opens by URL
    stmt = select(Stock).where(
        or_(Stock.ticker.in_(select(ListedSecurity.ticker)), ~select(ListedSecurity.ticker).exists())
    )
    directory = select(ListedSecurity)

    # Market region filter (US vs India)
    if market:
        m = market.strip().lower()
        if m in ("in", "india", "nse", "bse"):
            stmt = stmt.where(or_(Stock.ticker.ilike("%.NS"), Stock.ticker.ilike("%.BO")))
            directory = directory.where(ListedSecurity.exchange.in_(["NSE", "BSE"]))
        elif m in ("us", "usa", "nyse", "nasdaq"):
            stmt = stmt.where(and_(~Stock.ticker.ilike("%.NS"), ~Stock.ticker.ilike("%.BO")))
            directory = directory.where(ListedSecurity.exchange.not_in(["NSE", "BSE"]))

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
    for column, bound, is_min in (
        (Stock.roe_pct, roe_min, True), (Stock.debt_to_equity, debt_to_equity_max, False),
        (Stock.revenue_growth_pct, revenue_growth_min, True), (Stock.profit_margin_pct, profit_margin_min, True),
        (Stock.dividend_yield_pct, dividend_yield_min, True), (Stock.return_1y_pct, return_1y_min, True),
        (Stock.roce_pct, roce_min, True), (Stock.revenue_cagr_3y_pct, revenue_cagr_3y_min, True),
        (Stock.profit_cagr_3y_pct, profit_cagr_3y_min, True), (Stock.promoter_pct, promoter_min, True),
        (Stock.promoter_change_pp, promoter_change_min, True), (Stock.rsi_14, rsi_min, True),
        (Stock.rsi_14, rsi_max, False), (Stock.sma50_gap_pct, sma50_gap_min, True),
        (Stock.sma50_gap_pct, sma50_gap_max, False), (Stock.sma200_gap_pct, sma200_gap_min, True),
        (Stock.sma200_gap_pct, sma200_gap_max, False), (Stock.from_high_52w_pct, from_high_min, True),
        (Stock.from_low_52w_pct, from_low_max, False),
        # 20-session average traded value; the filter is in crore (₹1 Cr = 1e7)
        (Stock.turnover_20d, turnover_min_cr * 1e7 if turnover_min_cr is not None else None, True),
    ):
        if bound is not None:
            stmt = stmt.where(column >= bound if is_min else column <= bound)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    sort_columns: dict[str, Any] = {
        "ticker": Stock.ticker, "market_cap": Stock.market_cap, "pe": Stock.pe_ratio, "roe": Stock.roe_pct,
        "revenue_growth": Stock.revenue_growth_pct, "profit_margin": Stock.profit_margin_pct,
        "dividend_yield": Stock.dividend_yield_pct, "return_1y": Stock.return_1y_pct, "risk": Stock.risk_score,
        "roce": Stock.roce_pct, "revenue_cagr_3y": Stock.revenue_cagr_3y_pct, "profit_cagr_3y": Stock.profit_cagr_3y_pct,
        "promoter": Stock.promoter_pct, "promoter_change": Stock.promoter_change_pp,
        "rsi": Stock.rsi_14, "turnover": Stock.turnover_1d, "from_high": Stock.from_high_52w_pct,
    }
    # Traded value is in the listing currency, so rupee filters and rankings cover Indian listings only
    if turnover_min_cr is not None or (sort or "").lstrip("-") == "turnover":
        stmt = stmt.where(or_(Stock.ticker.ilike("%.NS"), Stock.ticker.ilike("%.BO")))
    order: Any = Stock.ticker
    if sort:
        column = sort_columns[sort.lstrip("-")]
        order = (column.desc() if sort.startswith("-") else column.asc()).nulls_last()
    result = await db.execute(stmt.order_by(order, Stock.ticker).limit(limit).offset(offset))
    db_stocks = result.scalars().all()

    response_items = [to_search_item(stock) for stock in db_stocks]

    data_filters = (pe_min, pe_max, beta_min, beta_max, risk_min, risk_max, signals, roe_min, debt_to_equity_max,
                    revenue_growth_min, profit_margin_min, dividend_yield_min, return_1y_min, roce_min,
                    revenue_cagr_3y_min, profit_cagr_3y_min, promoter_min, promoter_change_min, rsi_min, rsi_max,
                    sma50_gap_min, sma50_gap_max, sma200_gap_min, sma200_gap_max, from_high_min, from_low_max,
                    turnover_min_cr)
    if all(f is None for f in data_filters):
        q = (query or "").strip().upper()
        directory = directory.where(~ListedSecurity.ticker.in_(select(Stock.ticker)))
        if q:
            directory = directory.where(
                or_(ListedSecurity.ticker.ilike(f"%{q}%"), ListedSecurity.name.ilike(f"%{q}%"))
            )
        dir_total = (await db.execute(select(func.count()).select_from(directory.subquery()))).scalar_one()
        room = limit - len(response_items)
        if room > 0:
            # Exact symbol (TCS.NS / TCS.BO / TCS) first, then symbol prefix, then name matches
            import re

            from app.services.stock_lookup import EXCHANGE_PREFERENCE

            # Exact symbol, symbol prefix, name prefix, whole-word name match, then any substring
            # ("ITC" inside "Fitch" last); ties go to NSE, BSE, then US
            rank = case(
                (or_(ListedSecurity.ticker == q, ListedSecurity.ticker.ilike(f"{q}.%")), 0),
                (ListedSecurity.ticker.ilike(f"{q}%"), 1),
                (ListedSecurity.name.ilike(f"{q}%"), 2),
                (ListedSecurity.name.op("~*")(rf"\m{re.escape(q)}"), 3),
                else_=4,
            )
            hits = await db.execute(
                directory.order_by(rank, EXCHANGE_PREFERENCE, func.length(ListedSecurity.ticker), ListedSecurity.ticker)
                .limit(room)
                .offset(max(0, offset - total))
            )
            response_items += [_directory_item(d) for d in hits.scalars()]
        total += dir_total

    return StockSearchListResponse(stocks=response_items, total_count=int(total))


class ResolvedTicker(BaseModel):
    ticker: str
    name: str | None = None
    exchange: str | None = None


@router.get("/stocks/resolve", response_model=ResolvedTicker)
async def resolve_stock(q: str, current_user: CurrentUser, db: DBSession) -> ResolvedTicker:
    """The listed ticker meant by a typed symbol or name ("ITC" -> ITC.NS, "infosys" -> INFY.NS)."""
    from app.models.listed_security import ListedSecurity
    from app.services.stock_lookup import resolve_ticker

    ticker = await resolve_ticker(db, q)
    if ticker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No listed security matches {q!r}")
    listed = await db.get(ListedSecurity, ticker)
    return ResolvedTicker(ticker=ticker, name=listed.name if listed else None, exchange=listed.exchange if listed else None)


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
        and "outlook_score" in report.structured_json  # older reports regenerate to get one
        and utcnow() - report.updated_at < max_age
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

    return ResearchReportResponse(**{**report_data, "generated_at": utcnow()})


class FilingRequest(BaseModel):
    """Link to an earnings filing PDF (call transcript, results or investor presentation)."""

    url: str = Field(..., max_length=1000)


class FilingResponse(BaseModel):
    """The filing currently used as research context for a stock."""

    url: str | None
    updated_at: datetime | None
    chars: int


def _filing_response(stock: Any) -> FilingResponse:
    return FilingResponse(
        url=stock.filing_url if stock else None,
        updated_at=stock.filing_updated_at if stock else None,
        chars=len(stock.filing_text or "") if stock else 0,
    )


@router.get("/stocks/{ticker}/filing", response_model=FilingResponse)
async def get_stock_filing(ticker: str, current_user: CurrentUser, db: DBSession) -> FilingResponse:
    """The linked earnings filing for a stock, if any."""
    from sqlalchemy import select

    from app.models.stock import Stock

    stock = (
        await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    ).scalar_one_or_none()
    return _filing_response(stock)


@router.put("/stocks/{ticker}/filing", response_model=FilingResponse)
async def set_stock_filing(
    ticker: str,
    request: FilingRequest,
    current_user: CurrentUser,
    db: DBSession,
    redis: RedisClient,
) -> FilingResponse:
    """Download the PDF now, so a bad link fails here rather than silently at research time."""
    from app.providers.filing import FilingError, fetch_filing_text
    from app.services.stock_lookup import get_or_track_stock

    await enforce_rate_limit(redis, f"filing:{current_user['id']}", 10, 60)
    stock = await get_or_track_stock(db, ticker)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown ticker {ticker}")
    try:
        text = await fetch_filing_text(request.url.strip())
    except FilingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    stock.filing_url = request.url.strip()
    stock.filing_text = text
    stock.filing_updated_at = utcnow()
    await db.commit()
    return _filing_response(stock)


@router.delete("/stocks/{ticker}/filing", status_code=status.HTTP_204_NO_CONTENT)
async def clear_stock_filing(ticker: str, current_user: CurrentUser, db: DBSession) -> None:
    """Stop using the linked filing for a stock."""
    from sqlalchemy import update

    from app.models.stock import Stock

    await db.execute(
        update(Stock)
        .where(Stock.ticker == ticker.upper())
        .values(filing_url=None, filing_text=None, filing_updated_at=None)
    )
    await db.commit()


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


class TechnicalsResponse(BaseModel):
    """Latest technical indicators from one year of daily closes."""

    ticker: str
    price: float
    rsi_14: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    macd: float | None
    macd_signal: float | None
    high_1y: float
    low_1y: float
    pct_from_high: float | None
    notes: list[str]


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


@router.get("/stocks/{ticker}/technicals", response_model=TechnicalsResponse)
async def get_technicals(ticker: str, current_user: CurrentUser) -> TechnicalsResponse:
    """RSI, moving averages and MACD, from the cached 1-year price history."""
    from app.services.technicals import indicators

    history = await get_price_history(ticker, current_user, "1Y")
    values = indicators([p.close for p in history.points])
    if values is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Not enough price history for {history.ticker}",
        )
    return TechnicalsResponse(ticker=history.ticker, **values)


class ShareholdingQuarter(BaseModel):
    quarter: str
    promoter_pct: float
    fii_pct: float | None
    dii_pct: float | None
    mf_pct: float | None
    retail_pct: float | None
    shareholders: int | None


@router.get("/stocks/{ticker}/shareholding", response_model=list[ShareholdingQuarter])
async def get_shareholding(ticker: str, current_user: CurrentUser, db: DBSession) -> list[ShareholdingQuarter]:
    """Promoter, FII, DII, mutual fund and retail holding for the last 8 quarters, newest first (NSE stocks)."""
    from app.services.shareholding import shareholding_pattern

    ticker = ticker.upper()
    if not ticker.endswith(".NS") or not re.fullmatch(r"[A-Z0-9&-]{1,20}\.NS", ticker):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shareholding is available for NSE stocks")
    rows = await shareholding_pattern(db, ticker)
    return [
        ShareholdingQuarter(quarter=r.quarter.isoformat(), promoter_pct=r.promoter_pct, fii_pct=r.fii_pct, dii_pct=r.dii_pct,
                            mf_pct=r.mf_pct, retail_pct=r.retail_pct, shareholders=r.shareholders)
        for r in rows
    ]

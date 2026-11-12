"""Market data API endpoints."""

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.clock import utcnow
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.core.logging import get_logger
from app.models.stock import Stock
from app.services import nse_market

logger = get_logger(__name__)

router = APIRouter()


class VIXSnapshot(BaseModel):
    """VIX snapshot schema."""

    value: float
    change: float
    change_percent: float
    status: str


class MarketAlert(BaseModel):
    """Market alert schema."""

    id: int
    time: str
    type: str
    text: str


class MarketRegionInfo(BaseModel):
    """Market region summary schema."""

    name: str
    country: str
    index_name: str
    index_value: float
    index_change: str
    vix: float
    status: str  # "OPEN" | "CLOSED"
    # Second exchange benchmark sharing the session, e.g. BSE SENSEX beside NSE NIFTY 50
    secondary_index_name: str | None = None
    secondary_index_value: float | None = None
    secondary_index_change: str | None = None
    trading_hours: str


class MarketStatusResponse(BaseModel):
    """Market status response schema."""

    vix: VIXSnapshot
    alerts: list[MarketAlert]
    us_market: MarketRegionInfo | None = None
    india_market: MarketRegionInfo | None = None


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status() -> MarketStatusResponse:
    """
    Get live market VIX feed, dual-market status (US + India), and macroeconomic alerts.
    """
    quotes = await _get_quotes()
    vix_val, vix_change = quotes["^VIX"]
    india_vix_val, _ = quotes["^INDIAVIX"]
    spx_val, spx_change = quotes["^GSPC"]
    nifty_val, nifty_change = quotes["^NSEI"]
    sensex_val, sensex_change = quotes["^BSESN"]

    vix_snapshot = VIXSnapshot(
        value=vix_val,
        change=vix_change,
        change_percent=_pct(vix_val, vix_change),
        status=_vix_status(vix_val),
    )

    now_utc = datetime.now(UTC)

    ist_now = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    ist_mins = ist_now.hour * 60 + ist_now.minute
    is_nse_open = ist_now.weekday() < 5 and (9 * 60 + 15 <= ist_mins <= 15 * 60 + 30)

    india_market = MarketRegionInfo(
        name="NSE / BSE",
        country="India",
        index_name="NIFTY 50",
        index_value=nifty_val,
        index_change=f"{_pct(nifty_val, nifty_change):+.2f}%",
        vix=india_vix_val,
        status="OPEN" if is_nse_open else "CLOSED",
        trading_hours="09:15 - 15:30 IST",
        secondary_index_name="SENSEX",
        secondary_index_value=sensex_val,
        secondary_index_change=f"{_pct(sensex_val, sensex_change):+.2f}%",
    )

    ny_now = now_utc.astimezone(ZoneInfo("America/New_York"))
    ny_mins = ny_now.hour * 60 + ny_now.minute
    is_nyse_open = ny_now.weekday() < 5 and (9 * 60 + 30 <= ny_mins <= 16 * 60)

    us_market = MarketRegionInfo(
        name="NYSE / NASDAQ",
        country="United States",
        index_name="S&P 500",
        index_value=spx_val,
        index_change=f"{_pct(spx_val, spx_change):+.2f}%",
        vix=vix_val,
        status="OPEN" if is_nyse_open else "CLOSED",
        trading_hours="09:30 - 16:00 ET",
    )

    return MarketStatusResponse(
        vix=vix_snapshot,
        alerts=_build_alerts(quotes),
        us_market=us_market,
        india_market=india_market,
    )


# Last known levels, used when Yahoo Finance is unreachable.
_FALLBACK_QUOTES: dict[str, tuple[float, float]] = {
    "^VIX": (14.22, 0.0),
    "^INDIAVIX": (16.04, 0.0),
    "^GSPC": (5218.40, 0.0),
    "^NSEI": (22739.85, 0.0),
    "^BSESN": (74671.28, 0.0),
}
_QUOTE_TTL_SECONDS = 60.0
_quote_cache: dict[str, Any] = {"at": 0.0, "quotes": None}


def _fetch_quotes_sync() -> dict[str, tuple[float, float]]:
    """Fetch latest close and day change for each tracked symbol."""
    quotes = dict(_FALLBACK_QUOTES)
    for symbol in _FALLBACK_QUOTES:
        try:
            closes = yf.Ticker(symbol).history(period="5d", interval="1d")["Close"].dropna()
            if len(closes) >= 2:
                last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                quotes[symbol] = (round(last, 2), round(last - prev, 2))
        except Exception as e:
            logger.warning(f"Market quote fetch failed for {symbol}: {e}")
    return quotes


async def _get_quotes() -> dict[str, tuple[float, float]]:
    """Return cached quotes, refreshing at most once per TTL."""
    now = time.monotonic()
    if _quote_cache["quotes"] is None or now - _quote_cache["at"] > _QUOTE_TTL_SECONDS:
        _quote_cache["quotes"] = await asyncio.to_thread(_fetch_quotes_sync)
        _quote_cache["at"] = now
    quotes: dict[str, tuple[float, float]] = _quote_cache["quotes"]
    return quotes


def _pct(value: float, change: float) -> float:
    prev = value - change
    return round(change / prev * 100, 2) if prev else 0.0


def _vix_status(vix: float) -> str:
    if vix > 20:
        return "high"
    if vix > 15:
        return "moderate"
    return "low"


def _build_alerts(quotes: dict[str, tuple[float, float]]) -> list[MarketAlert]:
    """Derive macro alerts from the live index and volatility moves."""
    now_str = datetime.now().strftime("%H:%M:%S")
    alerts: list[MarketAlert] = []

    for symbol, label in (("^GSPC", "S&P 500"), ("^NSEI", "NIFTY 50"), ("^BSESN", "SENSEX")):
        value, change = quotes[symbol]
        pct = _pct(value, change)
        if pct >= 0.25:
            alert_type = "BULLISH"
        elif pct <= -0.25:
            alert_type = "BEARISH"
        else:
            alert_type = "NEUTRAL"
        alerts.append(
            MarketAlert(
                id=len(alerts) + 1,
                time=now_str,
                type=alert_type,
                text=f"{label} AT {value:,.2f} ({pct:+.2f}% D/D).",
            )
        )

    for symbol, label in (("^VIX", "US VIX"), ("^INDIAVIX", "INDIA VIX")):
        value, change = quotes[symbol]
        pct = _pct(value, change)
        regime = _vix_status(value).upper()
        alerts.append(
            MarketAlert(
                id=len(alerts) + 1,
                time=now_str,
                type="VOLATILITY" if abs(pct) >= 5 or value > 20 else "NEUTRAL",
                text=f"{label} AT {value:.2f} ({pct:+.2f}%). VOLATILITY REGIME: {regime}.",
            )
        )

    return alerts


PRICES_STALE_AFTER_HOURS = 2  # the price job stamps every stock each 15-minute pass, weekends included
DIRECTORY_STALE_AFTER_HOURS = 48


class DataHealthResponse(BaseModel):
    """How old the app's own data is, so a stopped background job can't pass for live numbers."""

    prices_updated_at: datetime | None
    prices_stale: bool
    directory_updated_at: datetime | None
    directory_stale: bool
    tracked: int = 0  # stocks the background jobs maintain
    with_fundamentals: int = 0  # of those, how many have fundamentals so far (a call needs them)


@router.get("/data-health", response_model=DataHealthResponse)
async def get_data_health(current_user: CurrentUser, db: DBSession) -> DataHealthResponse:
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.core.clock import utcnow
    from app.models.listed_security import ListedSecurity
    from app.models.stock import Stock

    prices = (await db.execute(select(func.max(Stock.price_updated_at)))).scalar()
    directory = (await db.execute(select(func.max(ListedSecurity.updated_at)))).scalar()
    tracked, with_fundamentals = (await db.execute(
        select(func.count(), func.count(Stock.fundamentals_updated_at))
    )).one()
    now = utcnow()
    return DataHealthResponse(
        prices_updated_at=prices,
        prices_stale=prices is not None and now - prices > timedelta(hours=PRICES_STALE_AFTER_HOURS),
        directory_updated_at=directory,
        directory_stale=directory is not None and now - directory > timedelta(hours=DIRECTORY_STALE_AFTER_HOURS),
        tracked=tracked,
        with_fundamentals=with_fundamentals,
    )


class IndexQuote(BaseModel):
    name: str
    last: float | None
    change: float | None
    change_pct: float | None


class Breadth(BaseModel):
    advances: int
    declines: int
    unchanged: int


class InstitutionalFlow(BaseModel):
    category: str
    date: str | None
    buy: float | None
    sell: float | None
    net: float | None


class Mover(BaseModel):
    ticker: str
    name: str | None
    price: float
    change_pct: float
    turnover: float | None = None  # last session's traded value (most-traded list)


class SectorSummary(BaseModel):
    sector: str
    stocks: int
    avg_change_pct: float
    avg_pe: float | None


class MarketOverviewResponse(BaseModel):
    """None for a section means its source is unavailable right now."""

    indices: list[IndexQuote] | None
    sector_indices: list[IndexQuote] | None
    breadth: Breadth | None
    flows: list[InstitutionalFlow] | None
    gainers: list[Mover]
    losers: list[Mover]
    sectors: list[SectorSummary]
    most_traded: list[Mover] = []


MOVERS_SHOWN = 10
# Gainers/losers skip shares that barely traded (a ₹3 stock up 40% on ₹10 lakh of trades)
MOVER_MIN_TURNOVER = 1e7  # ₹1 crore in the last session
# Long enough to span a holiday weekend, short enough to drop stocks the price job no longer updates
PRICE_MAX_AGE = timedelta(days=5)


def summarize_stocks(stocks: list[Stock]) -> tuple[list[Mover], list[Mover], list[SectorSummary]]:
    """Top movers and per-sector averages among stocks with a recent price and previous close."""
    moved: list[tuple[Stock, float]] = []
    cutoff = utcnow() - PRICE_MAX_AGE
    for s in stocks:
        if s.price and s.previous_close and s.price_updated_at and s.price_updated_at >= cutoff:
            moved.append((s, round((s.price / s.previous_close - 1) * 100, 2)))
    moved.sort(key=lambda m: m[1], reverse=True)

    def mover(s: Stock, pct: float) -> Mover:
        return Mover(ticker=s.ticker, name=s.name, price=float(s.price or 0), change_pct=pct)

    liquid = [(s, p) for s, p in moved if (s.turnover_1d or 0) >= MOVER_MIN_TURNOVER]
    gainers = [mover(s, p) for s, p in liquid[:MOVERS_SHOWN] if p > 0]
    losers = [mover(s, p) for s, p in reversed(liquid[-MOVERS_SHOWN:]) if p < 0]

    groups: dict[str, list[tuple[Stock, float]]] = {}
    for s, pct in moved:
        if s.sector:
            groups.setdefault(s.sector, []).append((s, pct))
    sectors = []
    for name, members in groups.items():
        pes = [s.pe_ratio for s, _ in members if s.pe_ratio and s.pe_ratio > 0]
        sectors.append(SectorSummary(
            sector=name,
            stocks=len(members),
            avg_change_pct=round(sum(p for _, p in members) / len(members), 2),
            avg_pe=round(sum(pes) / len(pes), 1) if pes else None,
        ))
    sectors.sort(key=lambda x: x.avg_change_pct, reverse=True)
    return gainers, losers, sectors


def most_traded(stocks: list[Stock]) -> list[Mover]:
    """Highest traded value in the last session, from the daily technicals snapshot."""
    cutoff = utcnow() - PRICE_MAX_AGE
    ranked = sorted(
        (s for s in stocks if s.turnover_1d and s.price and s.price_updated_at and s.price_updated_at >= cutoff),
        key=lambda s: s.turnover_1d or 0, reverse=True,
    )[:MOVERS_SHOWN]
    return [
        Mover(ticker=s.ticker, name=s.name, price=float(s.price or 0), turnover=s.turnover_1d,
              change_pct=round((s.price / s.previous_close - 1) * 100, 2) if s.price and s.previous_close else 0.0)
        for s in ranked
    ]


async def _indian_stocks(db: DBSession) -> list[Stock]:
    return list((await db.execute(select(Stock).where(Stock.ticker.like("%.NS")))).scalars().all())


@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview(current_user: CurrentUser, db: DBSession) -> MarketOverviewResponse:
    """Indian market today: indices, breadth, institutional flows, movers and sectors."""
    (feed, flows), quotes = await asyncio.gather(nse_market.market_feeds(), _get_quotes())
    indices = feed["headline"] if feed else None
    # Sensex is not on NSE; skip it rather than show the fallback level when Yahoo is unreachable
    sensex = quotes["^BSESN"]
    if indices is not None and sensex != _FALLBACK_QUOTES["^BSESN"]:
        indices = [{"name": "SENSEX", "last": sensex[0], "change": sensex[1], "change_pct": _pct(*sensex)}, *indices]
    stocks = await _indian_stocks(db)
    gainers, losers, sectors = summarize_stocks(stocks)
    return MarketOverviewResponse(
        indices=indices,
        sector_indices=feed["sectors"] if feed else None,
        breadth=feed["breadth"] if feed else None,
        flows=flows,
        gainers=gainers,
        losers=losers,
        sectors=sectors,
        most_traded=most_traded(stocks),
    )


class EarningsEvent(BaseModel):
    ticker: str
    company: str | None
    date: str
    detail: str | None


class CorporateAction(BaseModel):
    ticker: str
    company: str | None
    subject: str | None
    kind: str
    ex_date: str | None
    record_date: str | None


class IpoIssue(BaseModel):
    symbol: str | None
    company: str | None
    status: str
    start_date: str | None
    end_date: str | None
    listing_date: str | None
    price: str | None
    segment: str | None
    subscribed_times: float | None


class MarketEventsResponse(BaseModel):
    """None for a section means its source is unavailable right now."""

    earnings: list[EarningsEvent] | None
    corporate_actions: list[CorporateAction] | None
    ipos: list[IpoIssue] | None


@router.get("/events", response_model=MarketEventsResponse)
async def get_market_events(current_user: CurrentUser) -> MarketEventsResponse:
    """Upcoming results, corporate actions and IPOs from NSE."""
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return MarketEventsResponse(**await nse_market.event_feeds(today))


class ThemeMember(BaseModel):
    ticker: str
    name: str | None
    change_pct: float | None
    return_1y_pct: float | None


class Theme(BaseModel):
    name: str
    members: list[ThemeMember]
    avg_change_pct: float | None


@router.get("/themes", response_model=list[Theme])
async def get_market_themes(current_user: CurrentUser, db: DBSession) -> list[Theme]:
    """Theme baskets from NSE index constituents, with today's move for the stocks we track."""
    baskets = await nse_market.theme_members()
    tracked = {s.ticker: s for s in await _indian_stocks(db)}
    themes = []
    for name, members in baskets.items():
        rows = []
        for m in members:
            s = tracked.get(m["ticker"])
            pct = round((s.price / s.previous_close - 1) * 100, 2) if s and s.price and s.previous_close else None
            rows.append(ThemeMember(ticker=m["ticker"], name=m["name"], change_pct=pct,
                                    return_1y_pct=s.return_1y_pct if s else None))
        moves = [r.change_pct for r in rows if r.change_pct is not None]
        themes.append(Theme(name=name, members=rows,
                            avg_change_pct=round(sum(moves) / len(moves), 2) if moves else None))
    return themes


class IpoAnalysisResponse(BaseModel):
    """AI read of an IPO from NSE's issue data and its prospectus. Not investment advice."""

    issue: dict[str, Any]
    summary: str
    financials: str
    valuation: str
    pros: list[str]
    cons: list[str]
    recommendation: str | None  # Apply | Apply for listing gains | Avoid
    reasoning: str
    confidence: float | None
    read_prospectus: bool
    cached: bool = False


IPO_ANALYSIS_TTL = 6 * 3600  # demand changes daily while bidding; the prospectus doesn't
IPO_ANALYSES_PER_HOUR = 10  # each fresh one is a paid model call on the server's key


@router.get("/ipos/{symbol}/analysis", response_model=IpoAnalysisResponse)
async def get_ipo_analysis(
    symbol: str,
    current_user: CurrentUser,
    redis: RedisClient,
    series: Literal["EQ", "SME"] = Query("EQ"),
) -> IpoAnalysisResponse:
    """Pros, cons and Apply / Apply for listing gains / Avoid for one NSE IPO (cached for 6 hours)."""
    import json

    from app.services.ipo_analysis import analyze_ipo

    symbol = symbol.upper()
    if not re.fullmatch(r"[A-Z0-9&-]{1,20}", symbol):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Not an NSE symbol")
    key = f"ipo-analysis:{symbol}:{series}"
    if cached := await redis.get(key):
        return IpoAnalysisResponse(**json.loads(cached), cached=True)
    await enforce_rate_limit(redis, f"ipo-analysis:{current_user['id']}", IPO_ANALYSES_PER_HOUR, 3600)
    try:
        result = await analyze_ipo(symbol, series)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    await redis.set(key, json.dumps(result), ex=IPO_ANALYSIS_TTL)
    return IpoAnalysisResponse(**result)


class Filing(BaseModel):
    ticker: str
    company: str | None
    category: str | None
    summary: str | None
    filed_at: str | None
    pdf_url: str | None


def parse_announcements(rows: list[dict]) -> list[Filing]:
    """NSE corporate announcements, newest first."""
    out = []
    for r in rows:
        when = r.get("sort_date") or r.get("an_dt")
        out.append(Filing(
            ticker=f"{r.get('symbol')}.NS", company=r.get("sm_name"), category=r.get("desc"),
            summary=r.get("attchmntText"), filed_at=str(when) if when else None,
            pdf_url=r.get("attchmntFile") if str(r.get("attchmntFile") or "").startswith("https://") else None,
        ))
    return sorted(out, key=lambda f: f.filed_at or "", reverse=True)


@router.get("/filings", response_model=list[Filing] | None)
async def get_filings(current_user: CurrentUser, days: int = Query(1, ge=1, le=7)) -> list[Filing] | None:
    """Exchange announcements from every NSE company over the last `days`; None when NSE is unavailable."""
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    start = today - timedelta(days=days - 1)
    path = f"api/corporate-announcements?index=equities&from_date={start:%d-%m-%Y}&to_date={today:%d-%m-%Y}"
    data = await nse_market.nse_json(path, ttl=180)
    rows = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
    return parse_announcements(rows) if isinstance(rows, list) else None


class DeclaredResult(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    market_cap: float | None
    quarter_end: str
    filed_at: str
    consolidated: bool
    revenue: float | None
    profit: float | None
    eps: float | None
    revenue_yoy_pct: float | None
    profit_yoy_pct: float | None
    revenue_qoq_pct: float | None
    profit_qoq_pct: float | None
    pdf_url: str | None


@router.get("/earnings", response_model=list[DeclaredResult])
async def get_declared_results(current_user: CurrentUser, db: DBSession, days: int = Query(45, ge=1, le=120)) -> list[dict]:
    """Results declared by tracked NSE stocks, newest first, with growth against a year and a quarter ago."""
    from app.services.earnings import declared_results

    return await declared_results(db, days)


class Concall(BaseModel):
    ticker: str
    company: str | None
    kind: Literal["transcript", "recording", "schedule"]
    summary: str | None
    filed_at: str | None
    pdf_url: str | None


class ConcallSummary(Concall):
    quarter: str
    tone: Literal["Positive", "Neutral", "Cautious"] | None
    guidance: str
    highlights: list[str]
    concerns: list[str]
    cached: bool = False


CONCALL_SUMMARY_TTL = 30 * 24 * 3600  # a transcript never changes; a newer one gets a new key
CONCALL_SUMMARIES_PER_HOUR = 10  # each fresh one is a paid model call on the server's key


@router.get("/concalls", response_model=list[Concall] | None)
async def get_concalls(current_user: CurrentUser, days: int = Query(7, ge=1, le=30)) -> list[dict] | None:
    """Earnings-call schedules, recordings and transcripts from every NSE company; None when NSE is unavailable."""
    from app.services.concalls import recent_concalls

    return await recent_concalls(days)


@router.get("/concalls/{symbol}/summary", response_model=ConcallSummary)
async def get_concall_summary(symbol: str, current_user: CurrentUser, redis: RedisClient) -> ConcallSummary:
    """AI summary of the company's newest transcript: tone, guidance, highlights and concerns."""
    import hashlib
    import json

    from app.services.concalls import WINDOW_DAYS, latest_transcript, summarize_call

    symbol = symbol.upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9&-]{1,20}", symbol):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Not an NSE symbol")
    try:
        call = await latest_transcript(symbol)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    if call is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No transcript from {symbol} in the last {WINDOW_DAYS} days")
    key = "concall-summary:" + hashlib.sha256(call["pdf_url"].encode()).hexdigest()[:32]
    if cached := await redis.get(key):
        return ConcallSummary(**json.loads(cached), cached=True)
    await enforce_rate_limit(redis, f"concall-summary:{current_user['id']}", CONCALL_SUMMARIES_PER_HOUR, 3600)
    try:
        result = await summarize_call(call)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    await redis.set(key, json.dumps(result), ex=CONCALL_SUMMARY_TTL)
    return ConcallSummary(**result)


class Deal(BaseModel):
    ticker: str
    company: str | None
    deal_date: str
    kind: Literal["bulk", "block"]
    client: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float
    value: float


@router.get("/deals", response_model=list[Deal])
async def get_deals(current_user: CurrentUser, db: DBSession, days: int = Query(7, ge=1, le=90)) -> list[Deal]:
    """NSE bulk and block deals kept since tracking began, newest and largest first."""
    from app.models.large_deal import LargeDeal

    since = datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=days - 1)
    rows = (await db.execute(
        select(LargeDeal).where(LargeDeal.deal_date >= since)
        .order_by(LargeDeal.deal_date.desc(), (LargeDeal.quantity * LargeDeal.price).desc())
    )).scalars().all()
    # A block trade big enough to be a bulk deal is in both NSE files: show it once, as a block deal
    seen: dict[tuple, LargeDeal] = {}
    for d in rows:
        key = (d.deal_date, d.symbol, d.client, d.side, d.quantity, d.price)
        if key not in seen or d.kind == "block":
            seen[key] = d
    return [
        Deal(ticker=f"{d.symbol}.NS", company=d.company, deal_date=d.deal_date.isoformat(), kind=d.kind,
             client=d.client, side=d.side, quantity=d.quantity, price=d.price, value=d.quantity * d.price)
        for d in seen.values()
    ]


class IndexSummary(BaseModel):
    name: str
    category: str
    last: float | None
    change_pct: float | None
    pe: float | None
    pb: float | None
    dividend_yield: float | None
    year_high: float | None
    year_low: float | None
    return_30d: float | None
    return_1y: float | None
    advances: int | None
    declines: int | None


class IndexMember(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    price: float | None
    change_pct: float | None
    pe: float | None
    market_cap: float | None
    return_1y_pct: float | None


class IndexDetail(BaseModel):
    index: IndexSummary | None
    members: list[IndexMember] | None  # None: NSE publishes no constituent list for this index


class Etf(BaseModel):
    symbol: str
    underlying: str | None
    category: str
    price: float | None
    change_pct: float | None
    nav: float | None
    premium_pct: float | None
    traded_value: float | None
    year_high: float | None
    year_low: float | None
    return_30d: float | None
    return_1y: float | None


@router.get("/indices", response_model=list[IndexSummary] | None)
async def get_indices(current_user: CurrentUser) -> list[dict] | None:
    """Every NSE index: level, P/E, P/B, dividend yield, 52-week range, returns, breadth; None when NSE is down."""
    return await nse_market.index_list()


@router.get("/indices/{name}", response_model=IndexDetail)
async def get_index(name: str, current_user: CurrentUser, db: DBSession) -> IndexDetail:
    """One index with its constituents and our data for each (price, P/E, 1-year return)."""
    name = name.strip().upper()
    if not re.fullmatch(r"[A-Z0-9 &:/().-]{2,60}", name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Not an index name")
    summaries, members = await asyncio.gather(nse_market.index_list(), nse_market.index_members(name))
    summary = next((i for i in summaries or [] if i["name"].upper() == name), None)
    if summary is None and summaries is not None and members is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"NSE has no index called {name}")
    rows = None
    if members is not None:
        stocks = {s.ticker: s for s in (await db.execute(
            select(Stock).where(Stock.ticker.in_([m["ticker"] for m in members]))
        )).scalars()}
        rows = []
        for m in members:
            s = stocks.get(m["ticker"])
            rows.append(IndexMember(
                ticker=m["ticker"], name=m["name"], sector=s.sector if s else None, price=s.price if s else None,
                change_pct=round((s.price / s.previous_close - 1) * 100, 2) if s and s.price and s.previous_close else None,
                pe=s.pe_ratio if s else None, market_cap=s.market_cap if s else None,
                return_1y_pct=s.return_1y_pct if s else None,
            ))
        rows.sort(key=lambda r: r.market_cap or 0, reverse=True)
    return IndexDetail(index=IndexSummary(**summary) if summary else None, members=rows)


@router.get("/etfs", response_model=list[Etf] | None)
async def get_etfs(current_user: CurrentUser) -> list[dict] | None:
    """Every NSE ETF, most traded first; None when NSE is unavailable."""
    return await nse_market.etf_list()

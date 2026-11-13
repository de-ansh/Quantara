"""The one daily Slack message: market highlights at the close, plus news on watched or held stocks.

Everything else (signals, transcripts, price alerts) shows in the app's bell and lands here once a day,
instead of as a stream of separate pings.
"""

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import sleep_wall, utcnow
from app.core.config import settings
from app.core.logging import get_logger
from app.models.portfolio import PortfolioPosition
from app.models.price_alert import PriceAlert
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.watchlist import WatchlistItem
from app.services.notify import notify_slack
from app.services.nse_market import event_feeds

logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")
DIGEST_HOUR_IST = 16  # NSE closes 15:30; by 16:00 the 15-minute price job has the closing prices
DIGEST_CHECK_SECONDS = 10 * 60
MOVERS_IN_DIGEST = 3
SIGNAL_MAX_AGE = timedelta(days=7)  # a signal saved today about an older event still counts; backfill doesn't


def digest(events: dict, tickers: set[str], day: date) -> str | None:
    """Lines for `day`'s results meetings and ex-dates on `tickers`, or None when there are none."""
    when = day.isoformat()
    lines = [
        f"• {e['ticker']}: results board meeting" for e in events.get("earnings") or []
        if e["date"] == when and e["ticker"] in tickers
    ] + [
        f"• {a['ticker']}: ex-date for {a['subject']}" for a in events.get("corporate_actions") or []
        if a["ex_date"] == when and a["ticker"] in tickers
    ]
    return "\n".join(lines) if lines else None


def _pct(price: float | None, prev: float | None) -> float | None:
    return (price / prev - 1) * 100 if price and prev else None


def _link(stock: Stock) -> str:
    """Slack link to the stock's research page."""
    url = f"{settings.frontend_url.rstrip('/')}/research/{stock.ticker}"
    return f"<{url}|{stock.name or stock.ticker}>"


def _price(stock: Stock) -> str:
    symbol = "₹" if stock.ticker.endswith((".NS", ".BO")) else "$"
    pct = _pct(stock.price, stock.previous_close)
    return f"{symbol}{stock.price:,.2f}" + (f" ({pct:+.1f}%)" if pct is not None else "") if stock.price else "no price"


async def build_daily_digest(
    db: AsyncSession, indices: dict[str, tuple[float, float]], events: dict, today: date
) -> str:
    """The digest text. `indices` maps a name to (level, day change); `events` is nse_market.event_feeds()."""
    from app.api.v1.market import _indian_stocks, summarize_stocks

    since = utcnow() - timedelta(hours=24)
    lines = [f":bar_chart: *Market close, {today:%a %d %b}*"]
    if indices:
        lines.append(" · ".join(
            f"{name} {level:,.0f} ({change / (level - change) * 100:+.2f}%)" if level != change else f"{name} {level:,.0f}"
            for name, (level, change) in indices.items()
        ))
    gainers, losers, _ = summarize_stocks(await _indian_stocks(db))
    for label, movers in (("Top gainers", gainers), ("Top losers", losers)):
        if movers:
            lines.append(f"{label}: " + ", ".join(f"{m.name or m.ticker} {m.change_pct:+.1f}%" for m in movers[:MOVERS_IN_DIGEST]))

    tickers = set((await db.execute(
        union(select(WatchlistItem.ticker), select(PortfolioPosition.ticker))
    )).scalars().all())
    if tickers:
        stocks = (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)).order_by(Stock.ticker))).scalars().all()
        news: dict[str, list[str]] = {s.ticker: [] for s in stocks}
        alerts = (await db.execute(select(PriceAlert).where(
            PriceAlert.ticker.in_(tickers), PriceAlert.triggered_at >= since
        ))).scalars().all()
        for a in alerts:
            news.setdefault(a.ticker, []).append(f"price alert hit ({a.direction} {a.target_price:g})")
        signals = (await db.execute(select(Signal).where(
            Signal.ticker.in_(tickers), Signal.created_at >= since, Signal.timestamp >= utcnow() - SIGNAL_MAX_AGE
        ))).scalars().all()
        for sig in signals:
            news.setdefault(sig.ticker, []).append(sig.signal_type.replace("_", " "))
        for s in stocks:
            if s.filing_updated_at and s.filing_updated_at >= since:
                news[s.ticker].append("earnings-call transcript in, AI summary ready")
        lines.append("\n*Your stocks*")
        for s in stocks:
            extra = "; ".join(dict.fromkeys(news[s.ticker]))  # dedupe, keep order
            lines.append(f"• {_link(s)} {_price(s)}" + (f": {extra}" if extra else ""))

        tomorrow = today + timedelta(days=1)
        upcoming = digest(events, tickers, tomorrow)
        if upcoming:
            lines.append(f"\n*Tomorrow ({tomorrow:%a %d %b})*\n{upcoming}")
    return "\n".join(lines)


async def _market_indices() -> dict[str, tuple[float, float]]:
    from app.api.v1.market import _FALLBACK_QUOTES, _get_quotes

    quotes = await _get_quotes()
    # Leave out an index Yahoo didn't answer for, rather than print a stale fallback level
    return {
        name: quotes[sym] for sym, name in (("^NSEI", "NIFTY 50"), ("^BSESN", "SENSEX"))
        if quotes.get(sym) and quotes[sym] != _FALLBACK_QUOTES[sym]
    }


async def send_daily_digest_if_due(now: datetime | None = None) -> bool:
    """Send today's digest once, on a weekday after DIGEST_HOUR_IST; returns whether it was sent.

    shortcut: NSE holidays still get a digest (of the last session); check the holiday list if that annoys.
    """
    from app.core.database import AsyncSessionLocal

    now = now or datetime.now(IST)
    if now.weekday() >= 5 or now.hour < DIGEST_HOUR_IST or not settings.slack_webhook_url:
        return False
    today = now.date()
    key = f"digest:sent:{today.isoformat()}"
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        if await redis.exists(key):
            return False
        indices, events = await asyncio.gather(_market_indices(), event_feeds(today))
        async with AsyncSessionLocal() as db:
            text = await build_daily_digest(db, indices, events, today)
        # Claimed only once built, so a failed build retries next check; NX keeps it to one send across workers
        if not await redis.set(key, "1", nx=True, ex=3 * 86400):
            return False
    finally:
        await redis.aclose()
    await notify_slack(text)
    logger.info("Daily Slack digest sent")
    return True


async def run_periodic_daily_digest(interval_seconds: int = DIGEST_CHECK_SECONDS) -> None:
    """Background loop: checks every few minutes whether today's digest is due."""
    import sentry_sdk

    while True:
        try:
            await send_daily_digest_if_due()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error sending daily digest: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)
        await sleep_wall(interval_seconds)

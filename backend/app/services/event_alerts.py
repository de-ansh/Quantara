"""The one daily Slack message: market highlights at the close, plus news on watched or held stocks.

Signals and transcripts show in the app's bell and land here once a day, instead of as a stream of separate pings.
Price alerts are the exception: the user set a level and wants to know when it's crossed, so they are also DMed
as they fire (price_service).
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
from app.services.notify import linked_users, notify_slack, slack_configured
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


async def portfolio_section(db: AsyncSession, user_id: int, today: date) -> str | None:
    """One user's part of the digest: their mix against target, holdings rated Avoid, and verdicts that changed."""
    from app.api.v1.portfolio import get_all_balance
    from app.core.dependencies import user_dict
    from app.models.portfolio import Portfolio
    from app.models.user import User
    from app.models.verdict_snapshot import VerdictSnapshot
    from app.services.portfolio_balance import CLASSES

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    lines: list[str] = []
    portfolios = (await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))).scalars().all()
    if portfolios:
        balance = await get_all_balance(user_dict(user), db, 0)
        mix, t = balance.mix.get("INR"), balance.target
        if mix:
            shares = " · ".join(f"{round(mix[c])}% {c}" for c in CLASSES if mix.get(c))
            off = any(f.kind == "mix" for f in balance.flags)
            lines.append(f"Mix: {shares} (target {t.equity:g}/{t.debt:g}/{t.cash:g}/{t.gold:g} equity/debt/cash/gold)"
                         + (": off target, the rebalancing plan says what to move" if off else ": on target"))
        avoid = [f.ticker for f in balance.flags if f.kind == "verdict" and f.ticker]
        if avoid:
            lines.append(f"Rated Avoid for you ({len(avoid)}): " + ", ".join(await _names(db, avoid)))

    if user.risk_level:
        held = {p.ticker for pf in portfolios for p in pf.positions if p.shares > 0}
        held |= set((await db.execute(select(WatchlistItem.ticker).where(WatchlistItem.user_id == user_id))).scalars())
        days = (await db.execute(
            select(VerdictSnapshot.day).where(VerdictSnapshot.day <= today).distinct()
            .order_by(VerdictSnapshot.day.desc()).limit(2)
        )).scalars().all()
        if held and len(days) == 2:
            rows = (await db.execute(select(VerdictSnapshot.day, VerdictSnapshot.ticker, VerdictSnapshot.verdict).where(
                VerdictSnapshot.day.in_(days), VerdictSnapshot.ticker.in_(held), VerdictSnapshot.risk_level == user.risk_level,
            ))).all()
            by_day: dict[date, dict[str, str]] = {d: {} for d in days}
            for day, ticker, verdict in rows:
                by_day[day][ticker] = verdict
            now, before = by_day[days[0]], by_day[days[1]]
            changed = sorted(t for t in now if t in before and now[t] != before[t])
            if changed:
                names = dict(zip(changed, await _names(db, changed), strict=True))
                lines.append(f"Verdicts changed since {days[1]:%a %d %b}: "
                             + "; ".join(f"{names[t]} {before[t]} → {now[t]}" for t in changed))
    if not lines:
        return None
    url = f"{settings.frontend_url.rstrip('/')}/portfolios"
    return f"*<{url}|Your portfolios>*\n" + "\n".join(f"• {line}" for line in lines)


async def _names(db: AsyncSession, tickers: list[str]) -> list[str]:
    found = dict((await db.execute(select(Stock.ticker, Stock.name).where(Stock.ticker.in_(tickers)))).tuples().all())
    return [found.get(t) or t for t in tickers]


async def send_daily_digest_if_due(now: datetime | None = None) -> bool:
    """Send today's digest once per recipient, on a weekday after DIGEST_HOUR_IST; returns whether any was sent.

    With the bot, each linked user gets a DM with their own portfolio section; with only a webhook, the shared
    part goes to its channel. A recipient whose send fails is tried again at the next check.
    shortcut: NSE holidays still get a digest (of the last session); check the holiday list if that annoys.
    """
    from app.core.database import AsyncSessionLocal

    now = now or datetime.now(IST)
    if now.weekday() >= 5 or now.hour < DIGEST_HOUR_IST or not slack_configured():
        return False
    today = now.date()
    users = sorted(set(linked_users(settings.slack_users).values())) if settings.slack_bot_token else []
    recipients: list[int | None] = list(users) or [None]
    keys = {uid: f"digest:sent:{today.isoformat()}" + (f":{uid}" if uid is not None else "") for uid in recipients}
    sent = 0
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        due = [uid for uid in recipients if not await redis.exists(keys[uid])]
        if not due:
            return False
        indices, events = await asyncio.gather(_market_indices(), event_feeds(today))
        async with AsyncSessionLocal() as db:
            shared = await build_daily_digest(db, indices, events, today)
            for uid in due:
                mine = await portfolio_section(db, uid, today) if uid is not None else None
                text = f"{shared}\n\n{mine}" if mine else shared
                # Claimed only once built, so a failed build retries next check; NX keeps it to one send across workers
                if not await redis.set(keys[uid], "1", nx=True, ex=3 * 86400):
                    continue
                if await (notify_slack(text, uid) if uid is not None else notify_slack(text)):
                    sent += 1
                else:
                    await redis.delete(keys[uid])  # so the next check tries again
    finally:
        await redis.aclose()
    if sent:
        logger.info(f"Daily Slack digest sent to {sent} recipient(s)")
    return sent > 0


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

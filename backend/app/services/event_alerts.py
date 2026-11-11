"""A daily Slack digest of tomorrow's results and ex-dates for watched or held stocks."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import PortfolioPosition
from app.models.watchlist import WatchlistItem
from app.services.notify import notify_slack
from app.services.nse_market import event_feeds


def digest(events: dict, tickers: set[str], day: date) -> str | None:
    """Slack text for `day`'s events on `tickers`, or None when there are none."""
    when = day.isoformat()
    lines = [
        f"• {e['ticker']}: results board meeting" for e in events.get("earnings") or []
        if e["date"] == when and e["ticker"] in tickers
    ] + [
        f"• {a['ticker']}: ex-date for {a['subject']}" for a in events.get("corporate_actions") or []
        if a["ex_date"] == when and a["ticker"] in tickers
    ]
    return f":calendar: Your stocks on {when}:\n" + "\n".join(lines) if lines else None


async def notify_upcoming_events(db: AsyncSession) -> bool:
    """Send tomorrow's digest. shortcut: relies on the daily job's cadence to avoid repeats; a day can be missed if the job drifts past midnight, add a sent-log if that matters."""
    held = union(select(WatchlistItem.ticker), select(PortfolioPosition.ticker))
    tickers = set((await db.execute(held)).scalars().all())
    if not tickers:
        return False
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    text = digest(await event_feeds(today), tickers, today + timedelta(days=1))
    if text is None:
        return False
    await notify_slack(text)
    return True

"""Nightly research for stocks someone watches or holds, so their verdicts stay current unopened.

Each report is a paid LLM call on the server's key, so a run is capped at MAX_REPORTS_PER_RUN.
"""

import asyncio
from datetime import timedelta

import sentry_sdk
from sqlalchemy import func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import sleep_wall, utcnow
from app.core.config import settings
from app.core.logging import get_logger
from app.models.portfolio import PortfolioPosition
from app.models.research import ResearchReport
from app.models.watchlist import WatchlistItem

logger = get_logger(__name__)

HELD_RESEARCH_LOCK_ID = 7_301_005
HELD_RESEARCH_INTERVAL_SECONDS = 24 * 3600
MAX_REPORTS_PER_RUN = 50


async def stale_held_tickers(db: AsyncSession, limit: int = MAX_REPORTS_PER_RUN) -> list[str]:
    """Watched or held tickers whose report is missing, older than the cache age, or has no outlook."""
    held = union(select(WatchlistItem.ticker), select(PortfolioPosition.ticker)).subquery()
    cutoff = utcnow() - timedelta(hours=settings.research_cache_max_age_hours)
    rows = await db.execute(
        select(held.c.ticker)
        .outerjoin(ResearchReport, ResearchReport.ticker == held.c.ticker)
        .where(or_(
            ResearchReport.ticker.is_(None),
            ResearchReport.updated_at < cutoff,
            func.json_extract_path(ResearchReport.structured_json, "outlook_score").is_(None),
        ))
        .order_by(ResearchReport.updated_at.asc().nulls_first())  # longest without a report first
        .limit(limit)
    )
    return [t for (t,) in rows.all()]


async def refresh_held_research(db: AsyncSession, limit: int = MAX_REPORTS_PER_RUN) -> int:
    """Regenerate stale reports for watched/held stocks; returns how many succeeded."""
    from app.services.research_engine import ResearchEngine

    engine = ResearchEngine()
    done = 0
    for ticker in await stale_held_tickers(db, limit):
        try:
            if await engine.generate_research_report(db, ticker, sec_user_agent=settings.sec_user_agent):
                done += 1
        except Exception as e:  # one bad ticker shouldn't stop the rest
            logger.warning(f"Nightly research failed for {ticker}: {e}")
    return done


async def run_periodic_held_research(interval_seconds: int = HELD_RESEARCH_INTERVAL_SECONDS) -> None:
    """Background loop; one worker runs at a time via an advisory lock."""
    from app.core.database import AsyncSessionLocal, run_exclusive

    async def _job() -> None:
        async with AsyncSessionLocal() as db:
            logger.info(f"Nightly research refreshed {await refresh_held_research(db)} watched/held stocks")

    while True:
        try:
            await run_exclusive(HELD_RESEARCH_LOCK_ID, _job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in nightly research: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)  # no-op when Sentry is not configured
        await sleep_wall(interval_seconds)

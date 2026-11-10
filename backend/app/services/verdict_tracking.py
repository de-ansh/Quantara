"""Verdicts for a stock, a daily record of them, and how each verdict's stocks went on to do.

The record starts on the first snapshot: past verdicts can't be rebuilt honestly, since a research
report generated now would see what happened after the date it is meant to judge.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.verdict_snapshot import VerdictSnapshot
from app.services.recommendation_engine import RecommendationEngine, signal_score

logger = get_logger(__name__)
engine = RecommendationEngine()

RISK_LEVELS = ("Conservative", "Moderate", "Aggressive")
DEFAULT_TOLERANCE = 60.0
# A snapshot price within this many days after the horizon counts (weekends, days the job didn't run)
PRICE_LOOKAHEAD_DAYS = 7


@dataclass
class StockVerdict:
    verdict: str
    final_score: float
    reasons: list[str]


async def verdict_for(db: AsyncSession, stock: Stock, risk_level: str, tolerance: float | None) -> StockVerdict | None:
    """Buy / Hold / Avoid for one stock and risk profile; None until it has research and risk scores."""
    if stock.research_score is None or stock.risk_score is None:
        return None
    signals = (await db.execute(select(Signal.strength, Signal.data).where(Signal.ticker == stock.ticker))).all()
    [rec] = engine.rank_recommendations(
        [{"ticker": stock.ticker, "sector": stock.sector or "Unknown", "risk_score": stock.risk_score,
          "research_score": stock.research_score, "signal_score": signal_score([tuple(r) for r in signals])}],
        risk_level,
        tolerance if tolerance is not None else DEFAULT_TOLERANCE,
        top_n=1,
    )
    label, reasons = engine.verdict(rec.scores)
    return StockVerdict(label, rec.scores.final_score, reasons)


async def snapshot_verdicts(db: AsyncSession, day: date | None = None) -> int:
    """Record today's verdict and price for every rated stock and risk profile; repeat runs add nothing."""
    day = day or date.today()
    stocks = (await db.execute(
        select(Stock).where(Stock.research_score.is_not(None), Stock.risk_score.is_not(None), Stock.price.is_not(None))
    )).scalars().all()
    rows = []
    for stock in stocks:
        for level in RISK_LEVELS:
            v = await verdict_for(db, stock, level, None)
            if v is not None:
                rows.append({"day": day, "ticker": stock.ticker, "risk_level": level, "verdict": v.verdict,
                             "final_score": round(v.final_score, 2), "price": stock.price})
    if rows:
        await db.execute(insert(VerdictSnapshot).values(rows).on_conflict_do_nothing(constraint="uq_verdict_snapshot_day"))
        await db.commit()
    return len(rows)


async def track_record(db: AsyncSession, risk_level: str, horizon_days: int, today: date | None = None) -> dict:
    """Average return `horizon_days` after each verdict, against the average of all rated stocks."""
    today = today or date.today()
    # shortcut: loads every snapshot; fine for a personal app's few hundred stocks, move to SQL if it grows
    snaps = (await db.execute(select(VerdictSnapshot).order_by(VerdictSnapshot.day))).scalars().all()
    prices: dict[str, dict[date, float]] = defaultdict(dict)
    for s in snaps:
        prices[s.ticker][s.day] = s.price

    def later_price(ticker: str, target: date) -> float | None:
        return next((prices[ticker][d] for d in sorted(prices[ticker]) if target <= d <= target + timedelta(days=PRICE_LOOKAHEAD_DAYS)), None)

    returns: dict[str, list[float]] = defaultdict(list)
    for s in snaps:
        if s.risk_level != risk_level or s.price <= 0 or s.day + timedelta(days=horizon_days) > today:
            continue
        end = later_price(s.ticker, s.day + timedelta(days=horizon_days))
        if end is not None:
            returns[s.verdict].append(end / s.price - 1)

    everything = [r for rs in returns.values() for r in rs]
    baseline = sum(everything) / len(everything) if everything else None
    since = min((s.day for s in snaps), default=None)
    return {
        "risk_level": risk_level,
        "horizon_days": horizon_days,
        "tracking_since": since,
        "first_results_on": since + timedelta(days=horizon_days) if since else None,
        "all_rated_avg_return_pct": round(baseline * 100, 2) if baseline is not None else None,
        "verdicts": [
            {
                "verdict": label,
                "count": len(rs),
                "avg_return_pct": round(sum(rs) / len(rs) * 100, 2),
                "vs_all_rated_pct": round((sum(rs) / len(rs) - baseline) * 100, 2),
                "share_that_rose_pct": round(sum(r > 0 for r in rs) / len(rs) * 100, 1),
            }
            for label in ("Buy", "Hold", "Avoid")
            if (rs := returns.get(label))
        ],
    }

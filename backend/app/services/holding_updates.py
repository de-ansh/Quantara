"""What happened lately, and what's coming, for the stocks in someone's portfolios (the dashboard's feed)."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.price_alert import PriceAlert
from app.models.quarterly_result import QuarterlyResult
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.verdict_snapshot import VerdictSnapshot

logger = get_logger(__name__)

RECENT = timedelta(days=7)
AHEAD = timedelta(days=14)


@dataclass
class HoldingUpdate:
    kind: str  # signal, alert, transcript, results, verdict, event
    day: date
    text: str
    tone: str = "neutral"  # good, bad or neutral, for colour only
    upcoming: bool = False


def signal_text(signal_type: str, data: dict | None) -> tuple[str, str]:
    """A signal in words, and its tone."""
    d = data or {}
    tone = {"bullish": "good", "bearish": "bad"}.get(str(d.get("direction")), "neutral")
    if signal_type == "large_deal" and d.get("net_pct_of_company") is not None:
        net = float(d["net_pct_of_company"])
        return f"Bulk/block deals: net {'buying' if net >= 0 else 'selling'} of {abs(net):.2f}% of the company", tone
    if signal_type == "promoter_pledge" and d.get("pledged_pct_of_promoter") is not None:
        return f"Promoters have pledged {float(d['pledged_pct_of_promoter']):.1f}% of their shares", tone
    if signal_type == "promoter_holding_change" and d.get("change_pp") is not None:
        change = float(d["change_pp"])
        return f"Promoter stake {'up' if change >= 0 else 'down'} {abs(change):.2f} points this quarter", tone
    return signal_type.replace("_", " ").capitalize(), tone


def _crore(rupees: float) -> str:
    return f"₹{rupees / 1e7:,.0f} Cr"


def results_text(latest: QuarterlyResult, year_ago: QuarterlyResult | None) -> tuple[str, str]:
    """"Results for the quarter to 30 Sep 2026: profit ₹1,234 Cr, up 12% on a year ago" (or a loss, in words)."""
    text = f"Results for the quarter to {latest.quarter_end:%d %b %Y}"
    now, before = latest.profit, year_ago.profit if year_ago else None
    if now is None:
        return text, "neutral"
    text += f": {'profit' if now >= 0 else 'loss'} {_crore(abs(now))}"
    if before is None or before == 0:
        return text, "neutral" if now >= 0 else "bad"
    if now >= 0 and before > 0:
        change = (now / before - 1) * 100
        return text + f", {'up' if change >= 0 else 'down'} {abs(change):.0f}% on a year ago", "good" if change >= 0 else "bad"
    if now >= 0:
        return text + ", against a loss a year ago", "good"
    return text + (", against a profit a year ago" if before > 0 else ", after a loss a year ago too"), "bad"


def upcoming_events(events: dict, tickers: set[str], today: date) -> dict[str, list[HoldingUpdate]]:
    """Results meetings and ex-dates in the next two weeks, from nse_market.event_feeds()."""
    out: dict[str, list[HoldingUpdate]] = {}
    last = today + AHEAD

    def add(ticker: str, when: str | None, text: str) -> None:
        try:
            day = date.fromisoformat(str(when))
        except ValueError:
            return
        if ticker in tickers and today <= day <= last:
            out.setdefault(ticker, []).append(HoldingUpdate("event", day, text, upcoming=True))

    for e in events.get("earnings") or []:
        add(e["ticker"], e.get("date"), "Board meeting on results")
    for a in events.get("corporate_actions") or []:
        add(a["ticker"], a.get("ex_date"), f"Ex-date: {a.get('subject') or 'corporate action'}")
    return out


async def holding_updates(
    db: AsyncSession, tickers: set[str], user_id: int, risk_level: str, events: dict, today: date
) -> dict[str, list[HoldingUpdate]]:
    """Ticker -> updates: the last 7 days (newest first), then what's due in the next 14 days."""
    if not tickers:
        return {}
    since = utcnow() - RECENT
    found: dict[str, list[HoldingUpdate]] = {t: [] for t in tickers}

    signals = (await db.execute(select(Signal).where(
        Signal.ticker.in_(tickers), Signal.timestamp >= since
    ))).scalars().all()
    for s in signals:
        text, tone = signal_text(s.signal_type, s.data)
        found[s.ticker].append(HoldingUpdate("signal", s.timestamp.date(), text, tone))

    alerts = (await db.execute(select(PriceAlert).where(
        PriceAlert.user_id == user_id, PriceAlert.ticker.in_(tickers), PriceAlert.triggered_at >= since
    ))).scalars().all()
    for a in alerts:
        if a.triggered_at is not None:
            found[a.ticker].append(HoldingUpdate(
                "alert", a.triggered_at.date(), f"Price alert hit: went {a.direction} {a.target_price:g}"
            ))

    stocks = (await db.execute(select(Stock).where(
        Stock.ticker.in_(tickers), Stock.filing_updated_at >= since
    ))).scalars().all()
    for st in stocks:
        if st.filing_updated_at is not None:
            found[st.ticker].append(HoldingUpdate(
                "transcript", st.filing_updated_at.date(), "Earnings-call transcript in; AI summary ready"
            ))

    results = (await db.execute(select(QuarterlyResult).where(
        QuarterlyResult.ticker.in_(tickers), QuarterlyResult.filed_at >= since
    ))).scalars().all()
    for r in results:
        year_ago = await db.get(QuarterlyResult, (r.ticker, r.quarter_end.replace(year=r.quarter_end.year - 1)))
        text, tone = results_text(r, year_ago)
        found[r.ticker].append(HoldingUpdate("results", (r.filed_at or utcnow()).date(), text, tone))

    # A verdict change: one day's call differs from the day before it, at the user's risk level
    snaps = (await db.execute(select(VerdictSnapshot).where(
        VerdictSnapshot.ticker.in_(tickers), VerdictSnapshot.risk_level == risk_level,
        VerdictSnapshot.day >= today - RECENT - timedelta(days=1),
    ).order_by(VerdictSnapshot.ticker, VerdictSnapshot.day))).scalars().all()
    for before, after in zip(snaps, snaps[1:], strict=False):
        if before.ticker == after.ticker and before.verdict != after.verdict:
            tone = {"Buy": "good", "Avoid": "bad"}.get(after.verdict, "neutral")
            found[after.ticker].append(HoldingUpdate("verdict", after.day, f"Verdict changed: {before.verdict} → {after.verdict}", tone))

    for items in found.values():
        items.sort(key=lambda u: u.day, reverse=True)
    for ticker, items in upcoming_events(events, tickers, today).items():
        found[ticker] += sorted(items, key=lambda u: u.day)
    return {t: items for t, items in found.items() if items}

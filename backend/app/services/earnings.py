"""Declared quarterly results for tracked NSE stocks, from NSE's integrated filings.

Each results XBRL holds only the quarter and the year to date, so growth comes from stored rows:
a stock's latest quarter and the same quarter a year earlier (fetched once when missing).
"""

import asyncio
import re
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.quarterly_result import QuarterlyResult
from app.models.stock import Stock
from app.services import nse_market

logger = get_logger(__name__)

FILINGS_PATH = "api/integrated-filing-results?index=equities&symbol={symbol}"
CHECKS_PER_PASS = 50  # each is one NSE call plus up to two XBRL downloads; ~2,600 stocks a day
RECHECK_AFTER = timedelta(hours=24)
PAUSE_SECONDS = 0.5
_REVENUE_TAGS = ("RevenueFromOperations", "Income", "TotalIncome", "InterestEarned")
_PROFIT_TAGS = ("ProfitLossForPeriod", "ProfitLossForThePeriod", "NetProfitLossForThePeriod")
_EPS_TAGS = ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "BasicEarningsLossPerShareFromContinuingOperations")


def _day(value: str | None) -> date | None:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip().title(), fmt).date()
        except ValueError:
            continue
    return None


def _when(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(value).strip(), "%d-%b-%Y %H:%M:%S")
    except ValueError:
        return None


def pick_filings(rows: list[dict]) -> dict[date, dict]:
    """Quarter end -> the financial filing to use: consolidated when filed, newest revision."""
    best: dict[date, dict] = {}
    for row in rows:
        if not str(row.get("type", "")).endswith("Financials") or not row.get("xbrl"):
            continue
        quarter = _day(row.get("qe_Date"))
        if quarter is None:
            continue
        rank = (row.get("consolidated") == "Consolidated", _when(row.get("creation_Date")) or datetime.min)
        current = best.get(quarter)
        if current is None or rank > (current.get("consolidated") == "Consolidated", _when(current.get("creation_Date")) or datetime.min):
            best[quarter] = row
    return best


def _value(xml: str, tags: tuple[str, ...]) -> float | None:
    for tag in tags:
        m = re.search(rf'<[\w-]+:{tag} contextRef="OneD"[^>]*>\s*([-\d.]+)\s*<', xml)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def parse_result_xbrl(xml: str) -> dict:
    """The quarter's revenue, profit and EPS (context OneD is the quarter itself)."""
    return {"revenue": _value(xml, _REVENUE_TAGS), "profit": _value(xml, _PROFIT_TAGS), "eps": _value(xml, _EPS_TAGS)}


def growth(now: float | None, before: float | None) -> float | None:
    """Percent change; None when either side is missing or the base is zero or negative."""
    if now is None or before is None or before <= 0:
        return None
    return round((now / before - 1) * 100, 1)


async def _store(db: AsyncSession, ticker: str, quarter: date, filing: dict, client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(filing["xbrl"])
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Results XBRL unavailable for {ticker} {quarter}: {e}")
        return False
    values = parse_result_xbrl(resp.text)
    if values["revenue"] is None and values["profit"] is None:
        return False
    row = {"ticker": ticker, "quarter_end": quarter, "consolidated": filing.get("consolidated") == "Consolidated",
           "filed_at": _when(filing.get("creation_Date")), "pdf_url": filing.get("pdf_attach"), **values}
    await db.execute(insert(QuarterlyResult).values(row).on_conflict_do_update(
        index_elements=["ticker", "quarter_end"], set_={k: v for k, v in row.items() if k not in ("ticker", "quarter_end")}
    ))
    return True


async def refresh_results(db: AsyncSession, limit: int = CHECKS_PER_PASS) -> int:
    """Check the stocks least recently checked for a new quarter; returns how many quarters were stored."""
    due = (await db.execute(
        select(Stock).where(Stock.ticker.like("%.NS"))
        .where(or_(Stock.results_checked_at.is_(None), Stock.results_checked_at < utcnow() - RECHECK_AFTER))
        .order_by(Stock.results_checked_at.asc().nulls_first()).limit(limit)
    )).scalars().all()
    stored = 0
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Quantara/1.0"}) as client:
        for stock in due:
            symbol = stock.ticker.removesuffix(".NS")
            data = await nse_market.nse_json(FILINGS_PATH.format(symbol=symbol), ttl=0)
            stock.results_checked_at = utcnow()
            rows = data.get("data") if isinstance(data, dict) else None
            filings = pick_filings(rows or [])
            if filings:
                have = set((await db.execute(
                    select(QuarterlyResult.quarter_end).where(QuarterlyResult.ticker == stock.ticker)
                )).scalars().all())
                latest = max(filings)
                year_ago = next((q for q in filings if abs((latest - q).days - 365) <= 10), None)
                previous = next((q for q in sorted(filings, reverse=True) if q < latest), None)
                for quarter in {q for q in (latest, year_ago, previous) if q is not None} - have:
                    stored += await _store(db, stock.ticker, quarter, filings[quarter], client)
            await db.commit()
            await asyncio.sleep(PAUSE_SECONDS)
    if due:
        logger.info(f"Results: checked {len(due)} stocks, stored {stored} quarters")
    return stored


async def declared_results(db: AsyncSession, days: int = 45) -> list[dict]:
    """Latest declared quarter per tracked stock filed in the last `days`, with year-on-year and quarter-on-quarter growth."""
    since = utcnow() - timedelta(days=days)
    rows = (await db.execute(
        select(QuarterlyResult, Stock.name, Stock.sector, Stock.market_cap)
        .join(Stock, Stock.ticker == QuarterlyResult.ticker)
        .order_by(QuarterlyResult.ticker, QuarterlyResult.quarter_end.desc())
    )).all()
    by_ticker: dict[str, list] = {}
    for r in rows:
        by_ticker.setdefault(r[0].ticker, []).append(r)
    out = []
    for ticker, quarters in by_ticker.items():
        latest, name, sector, cap = quarters[0]
        if latest.filed_at is None or latest.filed_at < since:
            continue
        older = {q[0].quarter_end: q[0] for q in quarters[1:]}
        year_ago = next((v for k, v in older.items() if abs((latest.quarter_end - k).days - 365) <= 10), None)
        previous = next((older[k] for k in sorted(older, reverse=True) if k < latest.quarter_end), None)
        out.append({
            "ticker": ticker, "name": name, "sector": sector, "market_cap": cap,
            "quarter_end": latest.quarter_end.isoformat(), "filed_at": latest.filed_at.isoformat(),
            "consolidated": latest.consolidated, "revenue": latest.revenue, "profit": latest.profit, "eps": latest.eps,
            "revenue_yoy_pct": growth(latest.revenue, year_ago.revenue if year_ago else None),
            "profit_yoy_pct": growth(latest.profit, year_ago.profit if year_ago else None),
            "revenue_qoq_pct": growth(latest.revenue, previous.revenue if previous else None),
            "profit_qoq_pct": growth(latest.profit, previous.profit if previous else None),
            "pdf_url": latest.pdf_url,
        })
    return sorted(out, key=lambda r: r["filed_at"], reverse=True)

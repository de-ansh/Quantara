"""Promoter holding by quarter from NSE, its change, and a signal when promoters buy or sell.

NSE's all-companies file has only the latest quarter, so history accumulates here quarter by
quarter; a tracked stock without an earlier quarter gets its own history once (per-company call,
capped per run to go easy on NSE).
"""

import asyncio
from datetime import date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.shareholding import Shareholding
from app.models.stock import Stock
from app.services.signal_engine import Signal, SignalType, save_signal_to_db

logger = get_logger(__name__)

MASTER = "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities"
HISTORY = "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}"
HISTORY_CALLS_PER_RUN = 50
SIGNAL_MIN_CHANGE_PP = 1.0  # promoters moving their stake by a point or more in a quarter
FULL_SIGNAL_CHANGE_PP = 5.0
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}


def parse_rows(rows: list[dict]) -> list[dict]:
    """(ticker, quarter, promoter_pct) from NSE shareholding records; unparseable rows skipped."""
    out = []
    for r in rows or []:
        try:
            out.append({
                "ticker": f"{r['symbol']}.NS",
                "quarter": datetime.strptime(r["date"], "%d-%b-%Y").date(),
                "promoter_pct": float(str(r["pr_and_prgrp"]).strip()),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def holding_change(history: list[tuple[date, float]]) -> tuple[date, float, float | None] | None:
    """Latest quarter, its promoter %, and the change in points from the quarter before."""
    if not history:
        return None
    ordered = sorted(history, reverse=True)
    latest_q, latest = ordered[0]
    return latest_q, latest, round(latest - ordered[1][1], 2) if len(ordered) > 1 else None


def change_signal(ticker: str, quarter: date, change_pp: float) -> Signal | None:
    if abs(change_pp) < SIGNAL_MIN_CHANGE_PP:
        return None
    return Signal(
        ticker=ticker,
        signal_type=SignalType.PROMOTER_HOLDING_CHANGE,
        strength=min(abs(change_pp) / FULL_SIGNAL_CHANGE_PP * 100, 100.0),
        confidence=90.0,  # exchange filings; the reason (buyback, sale, dilution) isn't in the data
        timestamp=datetime.combine(quarter, datetime.min.time()),
        metadata={"direction": "bullish" if change_pp > 0 else "bearish", "change_pp": change_pp,
                  "source": "NSE shareholding pattern"},
    )


async def _get_json(client: httpx.AsyncClient, url: str) -> list[dict] | None:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else None
    except (httpx.HTTPError, ValueError) as e:  # nseindia.com/api often refuses scripts; next run retries
        logger.warning(f"NSE shareholding unavailable ({url}): {e}")
        return None


async def _store(db: AsyncSession, rows: list[dict]) -> list[dict]:
    """Upsert, one row per stock and quarter; returns the rows kept."""
    # A revised filing sits beside the original for the same quarter; NSE lists the newer first
    unique: dict[tuple, dict] = {}
    for r in rows:
        unique.setdefault((r["ticker"], r["quarter"]), r)
    if unique:
        stmt = insert(Shareholding).values(list(unique.values()))
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["ticker", "quarter"], set_={"promoter_pct": stmt.excluded.promoter_pct}
        ))
    return list(unique.values())


async def refresh_shareholding(db: AsyncSession) -> int:
    """Update promoter holding for tracked NSE stocks; returns how many promoter-change signals were found."""
    tracked = set((await db.execute(select(Stock.ticker).where(Stock.ticker.ilike("%.NS")))).scalars())
    if not tracked:
        return 0
    async with httpx.AsyncClient(timeout=60.0, headers=_HEADERS) as client:
        latest = await _get_json(client, MASTER)
        await _store(db, [r for r in parse_rows(latest or []) if r["ticker"] in tracked])
        quarters: dict[str, list[tuple[date, float]]] = {}
        for t, q, p in (await db.execute(
            select(Shareholding.ticker, Shareholding.quarter, Shareholding.promoter_pct)
            .where(Shareholding.ticker.in_(tracked))
        )).all():
            quarters.setdefault(t, []).append((q, p))
        # Stocks with fewer than two quarters stored get their own history once
        for ticker in [t for t in sorted(tracked) if len(quarters.get(t, [])) < 2][:HISTORY_CALLS_PER_RUN]:
            history = await _get_json(client, HISTORY.format(symbol=ticker.removesuffix(".NS")))
            rows = await _store(db, parse_rows(history or []))
            quarters[ticker] = [(r["quarter"], r["promoter_pct"]) for r in rows] or quarters.get(ticker, [])
            await asyncio.sleep(0.3)

    signals = []
    for stock in (await db.execute(select(Stock).where(Stock.ticker.in_(quarters)))).scalars():
        summary = holding_change(quarters[stock.ticker])
        if summary is None:
            continue
        stock.shareholding_quarter, stock.promoter_pct, stock.promoter_change_pp = summary
        if summary[2] is not None and (signal := change_signal(stock.ticker, summary[0], summary[2])):
            signals.append(signal)
    await db.commit()
    for signal in signals:
        await save_signal_to_db(db, signal)  # one per stock per quarter
    return len(signals)

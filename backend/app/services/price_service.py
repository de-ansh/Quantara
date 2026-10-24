"""Keep stock market data current: 15-minute quotes, daily fundamentals, and the background loop."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.stock import Stock

logger = get_logger(__name__)

# Arbitrary app-wide key for the Postgres advisory lock guarding the price refresh.
PRICE_REFRESH_LOCK_ID = 7_301_002
PRICE_REFRESH_INTERVAL_SECONDS = 15 * 60


def fetch_quotes(tickers: list[str]) -> dict[str, tuple[float, float | None]]:
    """{ticker: (last close, previous close)} from one batched Yahoo download; missing tickers omitted."""
    if not tickers:
        return {}
    closes = yf.download(tickers, period="5d", interval="1d", auto_adjust=False, progress=False)[
        "Close"
    ]
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(tickers[0])
    quotes: dict[str, tuple[float, float | None]] = {}
    for t in tickers:
        if t not in closes:
            continue
        series = closes[t].dropna()
        if series.empty:
            continue
        prev = float(series.iloc[-2]) if len(series) > 1 else None
        quotes[t] = (float(series.iloc[-1]), prev)
    return quotes


async def _trigger_price_alerts(db: AsyncSession, prices: dict[str, float], now: datetime) -> None:
    """Mark untriggered alerts whose condition holds at the fresh price (one-shot)."""
    from app.models.price_alert import PriceAlert

    if not prices:
        return
    pending = (
        await db.execute(
            select(PriceAlert).where(
                PriceAlert.triggered_at.is_(None), PriceAlert.ticker.in_(list(prices))
            )
        )
    ).scalars().all()
    for alert in pending:
        price = prices[alert.ticker]
        crossed = price >= alert.target_price if alert.direction == "above" else price <= alert.target_price
        if crossed:
            alert.triggered_at = now
            alert.triggered_price = price


async def refresh_prices(db: AsyncSession, tickers: list[str] | None = None) -> int:
    """Update price/previous_close for the given (default: all) stocks; returns how many changed."""
    stmt = select(Stock)
    if tickers is not None:
        stmt = stmt.where(Stock.ticker.in_([t.upper() for t in tickers]))
    stocks = (await db.execute(stmt)).scalars().all()
    if not stocks:
        return 0

    try:
        quotes = await asyncio.to_thread(fetch_quotes, [s.ticker for s in stocks])
    except Exception as e:
        logger.warning(f"Price refresh download failed: {e}")
        return 0

    now = datetime.utcnow()
    for stock in stocks:
        if stock.ticker in quotes:
            stock.price, stock.previous_close = quotes[stock.ticker]
            stock.price_updated_at = now
    await _trigger_price_alerts(db, {t: q[0] for t, q in quotes.items()}, now)
    await db.commit()
    logger.info(f"Refreshed prices for {len(quotes)}/{len(stocks)} stocks")
    return len(quotes)


FUNDAMENTALS_MAX_AGE = timedelta(hours=24)

# Yahoo sector names -> the names the app uses (sector caps, peer grouping)
YAHOO_SECTORS = {
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Financial Services": "Financials",
    "Basic Materials": "Materials",
}


def fetch_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Name, sector, market cap, trailing P/E and beta from Yahoo; None if unavailable."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        logger.warning(f"Fundamentals lookup failed for {ticker}: {e}")
        return None
    if not info.get("marketCap") and not info.get("longName"):
        return None
    sector = info.get("sector")
    return {
        "name": info.get("longName") or info.get("shortName"),
        "sector": YAHOO_SECTORS.get(sector, sector) if sector else None,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "beta": info.get("beta"),
    }


async def refresh_fundamentals(db: AsyncSession, max_age: timedelta = FUNDAMENTALS_MAX_AGE) -> int:
    """Refresh fundamentals for stocks not updated within `max_age`; returns how many changed.

    Only fields Yahoo returns are overwritten, so a missing P/E never erases a known one.
    """
    cutoff = datetime.utcnow() - max_age
    due = (
        await db.execute(
            select(Stock).where(
                or_(Stock.fundamentals_updated_at.is_(None), Stock.fundamentals_updated_at < cutoff)
            )
        )
    ).scalars().all()
    updated = 0
    for stock in due:
        data = await asyncio.to_thread(fetch_fundamentals, stock.ticker)
        if data is None:
            continue
        for field, value in data.items():
            if value is not None:
                setattr(stock, field, value)
        stock.fundamentals_updated_at = datetime.utcnow()
        updated += 1
    await db.commit()
    if due:
        logger.info(f"Refreshed fundamentals for {updated}/{len(due)} stocks")
    return updated


async def run_periodic_price_refresh(interval_seconds: int = PRICE_REFRESH_INTERVAL_SECONDS) -> None:
    """Background loop; one worker refreshes at a time via an advisory lock."""
    from app.core.database import AsyncSessionLocal, run_exclusive

    async def _job() -> None:
        async with AsyncSessionLocal() as db:
            await refresh_prices(db)
            await refresh_fundamentals(db)  # no-op unless a stock is >24h stale

    while True:
        try:
            await run_exclusive(PRICE_REFRESH_LOCK_ID, _job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in price refresh: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)

"""Find a tracked stock, or verify an untracked ticker against Yahoo and start tracking it."""

import asyncio

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.stock import Stock

logger = get_logger(__name__)


def last_close(ticker: str) -> float | None:
    """Latest close from Yahoo, or None when the ticker is unknown/unreachable."""
    try:
        history = yf.Ticker(ticker).history(period="5d")
    except Exception as e:
        logger.warning(f"Yahoo lookup failed for {ticker}: {e}")
        return None
    return None if history.empty else float(history["Close"].iloc[-1])


async def get_or_track_stock(db: AsyncSession, ticker: str) -> Stock | None:
    """Stock row for `ticker`, inserting (flushed, not committed) a verified new one; None if unknown."""
    ticker = ticker.upper()
    stock = (await db.execute(select(Stock).where(Stock.ticker == ticker))).scalar_one_or_none()
    if stock is not None:
        return stock
    price = await asyncio.to_thread(last_close, ticker)
    if price is None:
        return None
    stock = Stock(ticker=ticker, name=ticker, price=price)
    db.add(stock)
    await db.flush()
    return stock

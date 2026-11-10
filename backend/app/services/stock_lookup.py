"""Find a tracked stock, or verify an untracked ticker against Yahoo and start tracking it."""

import asyncio
import re

import yfinance as yf
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.listed_security import ListedSecurity
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


# Indian listings first: a bare symbol the user types ("ITC", "INFY") means the NSE share, and Yahoo
# alone would read it as a US ticker (an unrelated company, or an ADR in dollars)
EXCHANGE_PREFERENCE = case(
    (ListedSecurity.exchange == "NSE", 0), (ListedSecurity.exchange == "BSE", 1), else_=2
)


async def resolve_ticker(db: AsyncSession, text: str) -> str | None:
    """The listed ticker a user means by `text`: an exact listing, a bare symbol, or a company name.

    A bare symbol tries NSE, then BSE, then US; a name picks the best-named listing (same exchange
    order). Returns `text` as typed when the directory isn't loaded yet, None when nothing matches.
    """
    raw = text.strip()
    symbol = raw.upper()
    if not symbol:
        return None
    if await db.scalar(select(ListedSecurity.ticker).limit(1)) is None:
        return symbol
    candidates = [symbol] if symbol.endswith((".NS", ".BO")) else [f"{symbol}.NS", f"{symbol}.BO", symbol.replace(".", "-")]
    listed = set((await db.execute(select(ListedSecurity.ticker).where(ListedSecurity.ticker.in_(candidates)))).scalars())
    for candidate in candidates:
        if candidate in listed:
            return candidate
    if await db.get(Stock, symbol) is not None:  # tracked but in no exchange list (e.g. an index fund)
        return symbol
    name_starts = ListedSecurity.name.ilike(f"{raw}%")
    best: str | None = await db.scalar(
        select(ListedSecurity.ticker)
        .where(or_(name_starts, ListedSecurity.name.op("~*")(rf"\m{re.escape(raw)}")))
        .order_by(case((name_starts, 0), else_=1), EXCHANGE_PREFERENCE, func.length(ListedSecurity.ticker))
        .limit(1)
    )
    return best


async def get_or_track_stock(db: AsyncSession, ticker: str) -> Stock | None:
    """Stock row for `ticker`, inserting (flushed, not committed) a verified new one; None if unknown."""
    ticker = await resolve_ticker(db, ticker) or ticker.strip().upper()
    stock = (await db.execute(select(Stock).where(Stock.ticker == ticker))).scalar_one_or_none()
    if stock is not None:
        return stock
    price = await asyncio.to_thread(last_close, ticker)
    if price is None:
        return None
    listed = await db.get(ListedSecurity, ticker)  # the exchange's name, so the stock is findable by it
    stock = Stock(ticker=ticker, name=listed.name if listed else ticker, price=price, price_updated_at=utcnow())
    db.add(stock)
    await db.flush()
    return stock

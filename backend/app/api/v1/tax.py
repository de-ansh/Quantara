"""Tax harvesting from an uploaded tradebook. Nothing is stored: the trades are used for this one answer."""

import asyncio
from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DBSession
from app.services.stock_lookup import resolve_ticker
from app.services.tax_harvest import Trade, build_book, harvest_plan

router = APIRouter()
SPLIT_LOOKUPS_AT_ONCE = 8


def _split_dates(ticker: str) -> list[date] | None:
    """Split and bonus dates from Yahoo (it records bonuses as splits); None when the lookup fails."""
    import yfinance as yf

    try:
        return [d.date() for d in yf.Ticker(ticker).splits.index]
    except Exception:
        return None


async def _all_split_dates(tickers: set[str]) -> dict[str, list[date] | None]:
    gate = asyncio.Semaphore(SPLIT_LOOKUPS_AT_ONCE)

    async def one(t: str) -> list[date] | None:
        async with gate:
            return await asyncio.to_thread(_split_dates, t)

    found = await asyncio.gather(*(one(t) for t in tickers))
    return dict(zip(tickers, found, strict=True))


class TradeIn(BaseModel):
    symbol: str = Field(..., pattern=r"^[A-Za-z0-9&.\-^]{1,20}$")
    date: date
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0)


class HarvestRequest(BaseModel):
    trades: list[TradeIn] = Field(..., min_length=1, max_length=50_000)


@router.post("/harvest")
async def tax_harvest(request: HarvestRequest, current_user: CurrentUser, db: DBSession) -> dict:
    """Realised gains this financial year and what selling (and buying back) could save."""
    from app.models.stock import Stock

    # Each broker symbol to the tracked listing ("ITC" -> ITC.NS), so lots and prices line up
    symbols = {t.symbol.upper() for t in request.trades}
    resolved = {s: await resolve_ticker(db, s) or s for s in symbols}
    trades = [Trade(resolved[t.symbol.upper()], t.date, t.side, t.quantity, t.price) for t in request.trades]
    today = date.today()
    splits = await _all_split_dates({t.symbol for t in trades})
    book = build_book(trades, today, {s: d for s, d in splits.items() if d})
    unchecked = sorted(s for s, d in splits.items() if d is None)
    if unchecked:
        book.warnings.append(f"Couldn't check for bonuses or splits on {', '.join(unchecked)}; verify those with your broker")
    held = {lot.symbol for lot in book.lots}
    rows = (await db.execute(select(Stock.ticker, Stock.price).where(Stock.ticker.in_(held)))).all() if held else []
    prices = {ticker: float(price) for ticker, price in rows if price}
    plan = harvest_plan(book, prices, today)
    plan["no_price"] = sorted(held - prices.keys())
    return plan

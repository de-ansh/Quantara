"""Watchlist API endpoints: tickers a user has pinned."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.research import StockSearchItem, to_search_item
from app.core.dependencies import CurrentUser, DBSession
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.services.stock_lookup import get_or_track_stock

router = APIRouter()

MAX_WATCHLIST_SIZE = 50
ALERT_WINDOW = timedelta(days=7)


class WatchlistAdd(BaseModel):
    """Add-to-watchlist request schema."""

    ticker: str = Field(..., pattern=r"^[A-Za-z0-9.\-^]{1,20}$")


class WatchlistResponse(BaseModel):
    """Watchlist response schema."""

    items: list[StockSearchItem]


class WatchlistAlert(BaseModel):
    """A signal detected for a watched ticker."""

    id: int
    ticker: str
    signal_type: str
    strength: float
    detected_at: datetime
    unread: bool


class WatchlistAlertsResponse(BaseModel):
    """Recent watchlist alerts."""

    alerts: list[WatchlistAlert]
    unread_count: int


async def _list(db: DBSession, user_id: int) -> WatchlistResponse:
    rows = (
        await db.execute(
            select(Stock)
            .join(WatchlistItem, WatchlistItem.ticker == Stock.ticker)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.created_at)
        )
    ).scalars()
    return WatchlistResponse(items=[to_search_item(s) for s in rows])


@router.get("/", response_model=WatchlistResponse)
async def get_watchlist(current_user: CurrentUser, db: DBSession) -> WatchlistResponse:
    """List the current user's watched tickers with their latest stock data."""
    return await _list(db, int(current_user["id"]))


@router.post("/", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    request: WatchlistAdd, current_user: CurrentUser, db: DBSession
) -> WatchlistResponse:
    """Watch a ticker. Tickers not yet tracked are verified against Yahoo, then added."""
    user_id = int(current_user["id"])
    ticker = request.ticker.upper()

    existing = (
        await db.execute(
            select(WatchlistItem.ticker).where(WatchlistItem.user_id == user_id)
        )
    ).scalars().all()
    if ticker in existing:
        return await _list(db, user_id)
    if len(existing) >= MAX_WATCHLIST_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Watchlist is limited to {MAX_WATCHLIST_SIZE} tickers",
        )

    if await get_or_track_stock(db, ticker) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No market data found for {ticker}",
        )

    db.add(WatchlistItem(user_id=user_id, ticker=ticker))
    await db.commit()
    return await _list(db, user_id)


@router.get("/alerts", response_model=WatchlistAlertsResponse)
async def get_watchlist_alerts(current_user: CurrentUser, db: DBSession) -> WatchlistAlertsResponse:
    """Signals detected in the last 7 days for the user's watched tickers, newest first."""
    user_id = int(current_user["id"])
    seen_at = (
        await db.execute(select(User.alerts_seen_at).where(User.id == user_id))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Signal)
            .join(WatchlistItem, WatchlistItem.ticker == Signal.ticker)
            .where(
                WatchlistItem.user_id == user_id,
                Signal.created_at >= datetime.utcnow() - ALERT_WINDOW,
            )
            .order_by(Signal.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    alerts = [
        WatchlistAlert(
            id=s.id,
            ticker=s.ticker,
            signal_type=s.signal_type,
            strength=s.strength,
            detected_at=s.created_at,
            unread=seen_at is None or s.created_at > seen_at,
        )
        for s in rows
    ]
    return WatchlistAlertsResponse(alerts=alerts, unread_count=sum(a.unread for a in alerts))


@router.post("/alerts/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_alerts_seen(current_user: CurrentUser, db: DBSession) -> None:
    """Mark every current alert as read."""
    user = (await db.execute(select(User).where(User.id == int(current_user["id"])))).scalar_one()
    user.alerts_seen_at = datetime.utcnow()
    await db.commit()


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(ticker: str, current_user: CurrentUser, db: DBSession) -> None:
    """Stop watching a ticker."""
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == int(current_user["id"]),
                WatchlistItem.ticker == ticker.upper(),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not on watchlist")
    await db.delete(item)
    await db.commit()

"""Price alert API: create, list and delete one-shot price-crossing alerts."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DBSession
from app.models.price_alert import PriceAlert
from app.services.stock_lookup import get_or_track_stock

router = APIRouter()

MAX_ACTIVE_ALERTS = 50


class PriceAlertCreate(BaseModel):
    """Create-alert request schema."""

    ticker: str = Field(..., pattern=r"^[A-Za-z0-9.\-^]{1,20}$")
    direction: Literal["above", "below"]
    target_price: float = Field(..., gt=0)


class PriceAlertResponse(BaseModel):
    """Price alert response schema."""

    id: int
    ticker: str
    direction: str
    target_price: float
    created_at: datetime
    triggered_at: datetime | None
    triggered_price: float | None


def _to_response(a: PriceAlert) -> PriceAlertResponse:
    return PriceAlertResponse(
        id=a.id,
        ticker=a.ticker,
        direction=a.direction,
        target_price=a.target_price,
        created_at=a.created_at,
        triggered_at=a.triggered_at,
        triggered_price=a.triggered_price,
    )


@router.get("/", response_model=list[PriceAlertResponse])
async def list_price_alerts(
    current_user: CurrentUser, db: DBSession, ticker: str | None = None
) -> list[PriceAlertResponse]:
    """The user's price alerts (optionally for one ticker), newest first."""
    stmt = select(PriceAlert).where(PriceAlert.user_id == int(current_user["id"]))
    if ticker:
        stmt = stmt.where(PriceAlert.ticker == ticker.upper())
    rows = (await db.execute(stmt.order_by(PriceAlert.created_at.desc()))).scalars().all()
    return [_to_response(a) for a in rows]


@router.post("/", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_price_alert(
    request: PriceAlertCreate, current_user: CurrentUser, db: DBSession
) -> PriceAlertResponse:
    """Alert when the ticker's price goes above / below the target (checked every 15 min)."""
    user_id = int(current_user["id"])
    active = (
        await db.execute(
            select(func.count()).where(
                PriceAlert.user_id == user_id, PriceAlert.triggered_at.is_(None)
            )
        )
    ).scalar_one()
    if active >= MAX_ACTIVE_ALERTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can have at most {MAX_ACTIVE_ALERTS} active price alerts",
        )
    ticker = request.ticker.upper()
    if await get_or_track_stock(db, ticker) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No market data found for {ticker}"
        )
    alert = PriceAlert(
        user_id=user_id,
        ticker=ticker,
        direction=request.direction,
        target_price=request.target_price,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _to_response(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price_alert(alert_id: int, current_user: CurrentUser, db: DBSession) -> None:
    """Remove one of the user's price alerts."""
    alert = (
        await db.execute(
            select(PriceAlert).where(
                PriceAlert.id == alert_id, PriceAlert.user_id == int(current_user["id"])
            )
        )
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.delete(alert)
    await db.commit()

"""Saved screener filters."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DBSession
from app.models.saved_screen import SavedScreen

router = APIRouter()

MAX_SCREENS = 50


class ScreenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    filters: dict[str, str] = Field(max_length=30)
    sort: str = Field(default="", max_length=40)


class ScreenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filters: dict[str, str]
    sort: str
    created_at: datetime


@router.get("/", response_model=list[ScreenOut])
async def list_screens(current_user: CurrentUser, db: DBSession) -> list[SavedScreen]:
    query = select(SavedScreen).where(SavedScreen.user_id == int(current_user["id"])).order_by(SavedScreen.name)
    return list((await db.execute(query)).scalars().all())


@router.post("/", response_model=ScreenOut)
async def save_screen(body: ScreenIn, current_user: CurrentUser, db: DBSession) -> SavedScreen:
    """Save under a name; saving the same name again replaces it."""
    user_id = int(current_user["id"])
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Give the screen a name")
    screen = (
        await db.execute(select(SavedScreen).where(SavedScreen.user_id == user_id, SavedScreen.name == name))
    ).scalar_one_or_none()
    if screen is None:
        count = (await db.execute(select(func.count()).where(SavedScreen.user_id == user_id))).scalar_one()
        if count >= MAX_SCREENS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"You can save up to {MAX_SCREENS} screens")
        screen = SavedScreen(user_id=user_id, name=name, filters=body.filters, sort=body.sort)
        db.add(screen)
    else:
        screen.filters, screen.sort = body.filters, body.sort
    await db.commit()
    await db.refresh(screen)
    return screen


@router.delete("/{screen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_screen(screen_id: int, current_user: CurrentUser, db: DBSession) -> None:
    screen = await db.get(SavedScreen, screen_id)
    if screen is None or screen.user_id != int(current_user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Screen not found")
    await db.delete(screen)
    await db.commit()

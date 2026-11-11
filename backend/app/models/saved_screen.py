"""Screener filters a user has saved under a name."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class SavedScreen(Base):
    __tablename__ = "saved_screens"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_screen_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    sort: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

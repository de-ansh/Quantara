"""A research chat, saved for its owner automatically; other signed-in users can read it only while it's shared (listed)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class SharedChat(Base):
    __tablename__ = "shared_chats"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # Opt-in sharing: other signed-in users can open and find it in the gallery; otherwise owner-only
    listed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)

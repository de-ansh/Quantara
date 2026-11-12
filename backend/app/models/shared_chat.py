"""A research chat its owner published at an unguessable link, and optionally listed in the gallery."""

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
    # Opt-in: only chats the owner chose to list appear in the gallery; the rest stay link-only
    listed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)

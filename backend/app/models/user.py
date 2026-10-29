"""User model for authentication and risk profiles."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.core.database import Base


class User(Base):
    """User model with risk profile information."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Risk Profile
    risk_level: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Conservative, Moderate, Aggressive"
    )
    volatility_tolerance: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0-100 scale"
    )
    investment_horizon: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Investment horizon in months"
    )
    sector_preferences: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Preferred sectors and weights"
    )

    # External Credentials & Overrides
    openai_api_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Encrypted external OpenAI API key"
    )
    sec_user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Custom SEC User-Agent header"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Bumped on logout; tokens carrying an older version are rejected.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # Watchlist alerts detected after this are unread
    alerts_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, risk_level={self.risk_level})>"

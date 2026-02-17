"""User model for authentication and risk profiles."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """User model with risk profile information."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Risk Profile
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Conservative, Moderate, Aggressive"
    )
    volatility_tolerance: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="0-100 scale"
    )
    investment_horizon: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Investment horizon in months"
    )
    sector_preferences: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Preferred sectors and weights"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, risk_level={self.risk_level})>"

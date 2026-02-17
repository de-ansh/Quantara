"""Audit log model for tracking all system actions and AI reasoning."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """Audit log model for security and AI reasoning tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    
    # Action Information
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Action type: login, update_profile, generate_recommendation, etc."
    )
    entity: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Entity type affected"
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="ID of affected entity"
    )
    
    # AI Reasoning
    reasoning_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="AI reasoning, prompts, and outputs"
    )
    
    # Request Details
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional Context
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Additional context and data"
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success",
        comment="success, failure, error"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_user_action_time", "user_id", "action", "timestamp"),
        Index("idx_entity", "entity", "entity_id"),
        Index("idx_status_time", "status", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, "
            f"status={self.status}, timestamp={self.timestamp})>"
        )

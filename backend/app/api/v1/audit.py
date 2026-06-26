"""Audit log API endpoints."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DBSession, CurrentUser
from app.models.audit import AuditLog

router = APIRouter()


class AuditLogResponse(BaseModel):
    """Audit log response schema."""
    id: int
    user_id: Optional[int]
    action: str
    entity: Optional[str]
    entity_id: Optional[str]
    status: str
    timestamp: datetime
    metadata: Optional[dict]


class AuditLogsListResponse(BaseModel):
    """List of audit logs response schema."""
    logs: List[AuditLogResponse]
    total_count: int


async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    data: Optional[dict] = None,
) -> AuditLog:
    """
    Create and persist an audit log entry.
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        status=status,
        error_message=error_message,
        data=data,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.get("/logs", response_model=AuditLogsListResponse)
async def get_audit_logs(
    current_user: CurrentUser,
    db: DBSession,
    action: Optional[str] = None,
    limit: int = 100,
) -> AuditLogsListResponse:
    """
    Get audit logs for current user.
    
    Args:
        current_user: Authenticated user
        db: Database session
        action: Optional action filter
        limit: Number of logs to return
    
    Returns:
        List of audit logs
    """
    stmt = select(AuditLog).where(AuditLog.user_id == int(current_user["id"]))
    
    if action:
        stmt = stmt.where(AuditLog.action == action)
        
    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    return AuditLogsListResponse(
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                entity=log.entity,
                entity_id=log.entity_id,
                status=log.status,
                timestamp=log.timestamp,
                metadata=log.data or {},
            )
            for log in logs
        ],
        total_count=len(logs),
    )

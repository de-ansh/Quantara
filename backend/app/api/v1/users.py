"""User management API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.user import User
from app.api.v1.audit import create_audit_log

router = APIRouter()


class RiskProfileUpdate(BaseModel):
    """Risk profile update schema."""
    risk_level: str = Field(..., pattern="^(Conservative|Moderate|Aggressive)$")
    volatility_tolerance: float = Field(..., ge=0, le=100)
    investment_horizon: int = Field(..., ge=1, description="Investment horizon in months")
    sector_preferences: Optional[dict] = None


class UserResponse(BaseModel):
    """User response schema."""
    id: int
    email: str
    risk_level: Optional[str]
    volatility_tolerance: Optional[float]
    investment_horizon: Optional[int]
    sector_preferences: Optional[dict]


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: CurrentUser,
    db: DBSession,
) -> UserResponse:
    """
    Get current user profile.
    
    Args:
        current_user: Authenticated user
        db: Database session
    
    Returns:
        User profile data
    """
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    return UserResponse(
        id=user.id,
        email=user.email,
        risk_level=user.risk_level,
        volatility_tolerance=user.volatility_tolerance,
        investment_horizon=user.investment_horizon,
        sector_preferences=user.sector_preferences,
    )


@router.post("/risk-profile", response_model=UserResponse)
async def update_risk_profile(
    profile: RiskProfileUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> UserResponse:
    """
    Update user risk profile.
    
    Args:
        profile: Risk profile data
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Updated user profile
    """
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    user.risk_level = profile.risk_level
    user.volatility_tolerance = profile.volatility_tolerance
    user.investment_horizon = profile.investment_horizon
    user.sector_preferences = profile.sector_preferences
    
    await db.commit()
    await db.refresh(user)
    
    await create_audit_log(
        db,
        user_id=user.id,
        action="update_profile",
        entity="user",
        entity_id=str(user.id),
        status="success",
        data={
            "risk_level": profile.risk_level,
            "volatility_tolerance": profile.volatility_tolerance,
            "investment_horizon": profile.investment_horizon,
        },
    )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        risk_level=user.risk_level,
        volatility_tolerance=user.volatility_tolerance,
        investment_horizon=user.investment_horizon,
        sector_preferences=user.sector_preferences,
    )

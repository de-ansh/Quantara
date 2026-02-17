"""User management API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import DBSession, CurrentUser

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
    # TODO: Fetch from database
    return UserResponse(
        id=int(current_user["id"]),
        email=current_user.get("email", ""),
        risk_level=None,
        volatility_tolerance=None,
        investment_horizon=None,
        sector_preferences=None,
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
    # TODO: Update user in database
    
    return UserResponse(
        id=int(current_user["id"]),
        email=current_user.get("email", ""),
        risk_level=profile.risk_level,
        volatility_tolerance=profile.volatility_tolerance,
        investment_horizon=profile.investment_horizon,
        sector_preferences=profile.sector_preferences,
    )

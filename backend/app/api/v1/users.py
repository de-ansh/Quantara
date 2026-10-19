"""User management API endpoints."""


from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.audit import create_audit_log
from app.core.dependencies import CurrentUser, DBSession
from app.models.user import User

router = APIRouter()


class RiskProfileUpdate(BaseModel):
    """Risk profile update schema."""

    risk_level: str = Field(..., pattern="^(Conservative|Moderate|Aggressive)$")
    volatility_tolerance: float = Field(..., ge=0, le=100)
    investment_horizon: int = Field(..., ge=1, description="Investment horizon in months")
    sector_preferences: dict | None = None


class UserCredentialsUpdate(BaseModel):
    """External credentials update schema."""

    openai_api_key: str | None = None
    sec_user_agent: str | None = None


class UserCredentialsResponse(BaseModel):
    """External credentials response schema."""

    has_openai_key: bool
    openai_key_masked: str | None = None
    sec_user_agent: str | None = None


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    email: str
    risk_level: str | None
    volatility_tolerance: float | None
    investment_horizon: int | None
    sector_preferences: dict | None
    has_openai_key: bool = False
    openai_key_masked: str | None = None
    sec_user_agent: str | None = None


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

    has_key = bool(user.openai_api_key)
    masked_key = None
    if has_key:
        from app.core.security import decrypt_credential, mask_credential

        decrypted = decrypt_credential(user.openai_api_key)
        masked_key = mask_credential(decrypted)

    return UserResponse(
        id=user.id,
        email=user.email,
        risk_level=user.risk_level,
        volatility_tolerance=user.volatility_tolerance,
        investment_horizon=user.investment_horizon,
        sector_preferences=user.sector_preferences,
        has_openai_key=has_key,
        openai_key_masked=masked_key,
        sec_user_agent=user.sec_user_agent,
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

    has_key = bool(user.openai_api_key)
    masked_key = None
    if has_key:
        from app.core.security import decrypt_credential, mask_credential

        decrypted = decrypt_credential(user.openai_api_key)
        masked_key = mask_credential(decrypted)

    return UserResponse(
        id=user.id,
        email=user.email,
        risk_level=user.risk_level,
        volatility_tolerance=user.volatility_tolerance,
        investment_horizon=user.investment_horizon,
        sector_preferences=user.sector_preferences,
        has_openai_key=has_key,
        openai_key_masked=masked_key,
        sec_user_agent=user.sec_user_agent,
    )


@router.get("/credentials", response_model=UserCredentialsResponse)
async def get_user_credentials(
    current_user: CurrentUser,
    db: DBSession,
) -> UserCredentialsResponse:
    """
    Get current user external credentials status and masked preview.
    """
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    has_key = bool(user.openai_api_key)
    masked_key = None
    if has_key:
        from app.core.security import decrypt_credential, mask_credential

        decrypted = decrypt_credential(user.openai_api_key)
        masked_key = mask_credential(decrypted)

    return UserCredentialsResponse(
        has_openai_key=has_key,
        openai_key_masked=masked_key,
        sec_user_agent=user.sec_user_agent,
    )


@router.put("/credentials", response_model=UserCredentialsResponse)
async def update_user_credentials(
    credentials: UserCredentialsUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> UserCredentialsResponse:
    """
    Update user external credentials securely with encryption and audit logging.
    """
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    from app.core.security import decrypt_credential, encrypt_credential, mask_credential

    # Update OpenAI Key if explicitly provided
    if credentials.openai_api_key is not None:
        if credentials.openai_api_key.strip():
            user.openai_api_key = encrypt_credential(credentials.openai_api_key.strip())
        else:
            user.openai_api_key = None

    # Update SEC User-Agent if explicitly provided
    if credentials.sec_user_agent is not None:
        if credentials.sec_user_agent.strip():
            user.sec_user_agent = credentials.sec_user_agent.strip()
        else:
            user.sec_user_agent = None

    await db.commit()
    await db.refresh(user)

    # Record security audit log (strictly omits raw secret values)
    await create_audit_log(
        db,
        user_id=user.id,
        action="update_credentials",
        entity="user",
        entity_id=str(user.id),
        status="success",
        data={
            "has_openai_key": bool(user.openai_api_key),
            "sec_user_agent": user.sec_user_agent,
        },
    )

    has_key = bool(user.openai_api_key)
    masked_key = None
    if has_key:
        decrypted = decrypt_credential(user.openai_api_key)
        masked_key = mask_credential(decrypted)

    return UserCredentialsResponse(
        has_openai_key=has_key,
        openai_key_masked=masked_key,
        sec_user_agent=user.sec_user_agent,
    )


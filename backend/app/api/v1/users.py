"""User management API endpoints."""


from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.v1.audit import create_audit_log
from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.core.security import verify_password
from app.models.audit import AuditLog
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.price_alert import PriceAlert
from app.models.recommendation import Recommendation
from app.models.user import User
from app.models.watchlist import WatchlistItem

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



class DeleteAccountRequest(BaseModel):
    """Account deletion requires re-entering the password."""

    password: str


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


@router.get("/me/export")
async def export_my_data(current_user: CurrentUser, db: DBSession) -> JSONResponse:
    """Everything stored about the user, as a downloadable JSON file (no secrets)."""
    user_id = int(current_user["id"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()

    portfolios = (await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))).scalars().all()
    watchlist = (await db.execute(select(WatchlistItem).where(WatchlistItem.user_id == user_id))).scalars().all()
    alerts = (await db.execute(select(PriceAlert).where(PriceAlert.user_id == user_id))).scalars().all()
    recs = (await db.execute(select(Recommendation).where(Recommendation.user_id == user_id))).scalars().all()
    logs = (await db.execute(select(AuditLog).where(AuditLog.user_id == user_id))).scalars().all()

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "profile": {
            "id": user.id,
            "email": user.email,
            "risk_level": user.risk_level,
            "volatility_tolerance": user.volatility_tolerance,
            "investment_horizon": user.investment_horizon,
            "sector_preferences": user.sector_preferences,
            "sec_user_agent": user.sec_user_agent,
            "has_openai_key": bool(user.openai_api_key),  # the key itself is never exported
            "created_at": _iso(user.created_at),
        },
        "portfolios": [
            {
                "name": p.name,
                "description": p.description,
                "initial_investment": p.initial_investment,
                "created_at": _iso(p.created_at),
                "positions": [
                    {"ticker": pos.ticker, "weight": pos.weight, "shares": pos.shares,
                     "cost_basis": pos.cost_basis}
                    for pos in p.positions
                ],
            }
            for p in portfolios
        ],
        "watchlist": [{"ticker": w.ticker, "added_at": _iso(w.created_at)} for w in watchlist],
        "price_alerts": [
            {"ticker": a.ticker, "direction": a.direction, "target_price": a.target_price,
             "created_at": _iso(a.created_at), "triggered_at": _iso(a.triggered_at),
             "triggered_price": a.triggered_price}
            for a in alerts
        ],
        "recommendations": [
            {"ticker": r.ticker, "final_score": r.final_score, "created_at": _iso(r.created_at)}
            for r in recs
        ],
        "activity_log": [
            {"action": log.action, "status": log.status, "timestamp": _iso(log.timestamp)}
            for log in logs
        ],
    }
    await create_audit_log(db, user_id=user_id, action="export_data", entity="user", entity_id=str(user_id))
    return JSONResponse(
        payload,
        headers={"Content-Disposition": 'attachment; filename="quantara-my-data.json"'},
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    request: DeleteAccountRequest,
    current_user: CurrentUser,
    db: DBSession,
    redis: RedisClient,
    response: Response,
) -> None:
    """Permanently delete the account and everything it owns."""
    from app.api.v1.auth import REFRESH_COOKIE, REFRESH_COOKIE_PATH

    user_id = int(current_user["id"])
    await enforce_rate_limit(
        redis, f"delete-account:{user_id}", settings.login_rate_limit_per_minute, 60
    )
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect")

    # Tables without ON DELETE CASCADE are cleared explicitly; watchlist and price
    # alerts cascade with the user row.
    portfolio_ids = select(Portfolio.id).where(Portfolio.user_id == user_id)
    await db.execute(delete(PortfolioPosition).where(PortfolioPosition.portfolio_id.in_(portfolio_ids)))
    await db.execute(delete(Portfolio).where(Portfolio.user_id == user_id))
    await db.execute(delete(Recommendation).where(Recommendation.user_id == user_id))
    await db.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    # Keep an anonymous record that an erasure happened (no user id or email)
    await create_audit_log(db, user_id=None, action="delete_account", entity="user")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)

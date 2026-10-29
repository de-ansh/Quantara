"""FastAPI dependencies for dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import decrypt_credential, verify_token

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Get Redis client connection."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from sqlalchemy import select

    from app.models.user import User

    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or payload.get("ver", 0) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "risk_level": user.risk_level,
        "volatility_tolerance": user.volatility_tolerance,
        "investment_horizon": user.investment_horizon,
        "sector_preferences": user.sector_preferences,
        "is_active": user.is_active,
        "openai_api_key": decrypt_credential(user.openai_api_key),
        "sec_user_agent": user.sec_user_agent,
    }


async def enforce_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window counter in Redis; raises 429 once `limit` hits occur within the window."""
    try:
        count = await redis.incr(f"ratelimit:{key}")
        if count == 1:
            await redis.expire(f"ratelimit:{key}", window_seconds)
    except Exception as e:
        # Fail open: a Redis outage should degrade protection, not take auth down.
        logger.warning(f"Rate limiter unavailable, allowing request: {e}")
        return
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please try again later.",
            headers={"Retry-After": str(window_seconds)},
        )


# Type aliases for common dependencies
DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

"""Authentication API endpoints."""


from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.v1.audit import create_audit_log
from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Change-password request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Token response schema. The refresh token travels only in an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"


# Scoped to the auth routes and invisible to page scripts; SameSite=Strict keeps
# cross-site requests from carrying it (CSRF), since the UI and API are same-site.
REFRESH_COOKIE = "quantara_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _issue_tokens(user: User, response: Response) -> TokenResponse:
    claims = {"sub": str(user.id), "email": user.email, "ver": user.token_version}
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(data=claims),
        max_age=settings.refresh_token_expire_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )
    return TokenResponse(access_token=create_access_token(data=claims))


async def _user_from_refresh_cookie(request: Request, db: DBSession) -> User | None:
    """The active user a still-valid refresh cookie belongs to, else None."""
    token = request.cookies.get(REFRESH_COOKIE)
    payload = verify_token(token, token_type="refresh") if token else None
    if not payload or not payload.get("sub"):
        return None
    user = (
        await db.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active or payload.get("ver", 0) != user.token_version:
        return None
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: DBSession,
    redis: RedisClient,
    http_request: Request,
    response: Response,
) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        JWT access token
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    await enforce_rate_limit(
        redis, f"login:{client_ip}:{request.email.lower()}", settings.login_rate_limit_per_minute, 60
    )

    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and user.is_active and verify_password(request.password, user.hashed_password):
        await create_audit_log(
            db,
            user_id=user.id,
            action="login",
            entity="user",
            entity_id=str(user.id),
            status="success",
        )
        return _issue_tokens(user, response)

    await create_audit_log(
        db,
        user_id=None,
        action="login",
        entity="user",
        status="failure",
        error_message="Incorrect email or password",
        data={"email": request.email},
    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: DBSession,
    redis: RedisClient,
    http_request: Request,
    response: Response,
) -> TokenResponse:
    """
    Register new user.

    Args:
        request: Registration data
        db: Database session

    Returns:
        JWT access token
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    await enforce_rate_limit(
        redis, f"register:{client_ip}", settings.login_rate_limit_per_minute, 60
    )

    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Hash password
    hashed_password = get_password_hash(request.password)

    # Create user in database
    user = User(
        email=request.email,
        hashed_password=hashed_password,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await create_audit_log(
        db,
        user_id=user.id,
        action="register",
        entity="user",
        entity_id=str(user.id),
        status="success",
    )

    return _issue_tokens(user, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: DBSession) -> TokenResponse:
    """Exchange the refresh cookie for a new access token (and rotated cookie)."""
    user = await _user_from_refresh_cookie(request, db)
    if user is None:
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(user, response)


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
    redis: RedisClient,
    response: Response,
) -> TokenResponse:
    """Change the password, sign out every other session, and return fresh tokens."""
    await enforce_rate_limit(
        redis, f"change-password:{current_user['id']}", settings.login_rate_limit_per_minute, 60
    )
    user = (
        await db.execute(select(User).where(User.id == int(current_user["id"])))
    ).scalar_one()

    if not verify_password(request.current_password, user.hashed_password):
        await create_audit_log(
            db, user_id=user.id, action="change_password", entity="user",
            entity_id=str(user.id), status="failure", error_message="Wrong current password",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    if request.new_password == request.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current one",
        )

    user.hashed_password = get_password_hash(request.new_password)
    user.token_version += 1
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="change_password", entity="user", entity_id=str(user.id)
    )
    return _issue_tokens(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DBSession) -> None:
    """Revoke every token issued to the cookie's user and clear the cookie.

    Keyed on the refresh cookie rather than the access token, so logging out still
    works after the short-lived access token has expired.
    """
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    user = await _user_from_refresh_cookie(request, db)
    if user is None:
        return
    user.token_version += 1
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="logout", entity="user", entity_id=str(user.id)
    )

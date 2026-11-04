"""Authentication API endpoints."""

from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.v1.audit import create_audit_log
from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    encrypt_credential,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.core.two_factor import (
    new_recovery_codes,
    new_secret,
    provisioning_uri,
    verify_second_factor,
    verify_totp,
)
from app.models.user import User
from app.services.notify import notify_slack

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str
    # Authenticator-app code or a recovery code; required once two-factor login is on
    totp_code: str | None = Field(None, max_length=32)


# Login reply when the password is right but a two-factor code is still needed
TWO_FACTOR_REQUIRED = "two_factor_required"


class RegisterRequest(BaseModel):
    """Registration request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Change-password request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Forgot-password request schema."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset-password request schema."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    # For someone who lost both their authenticator app and their recovery codes
    disable_two_factor: bool = False


RESET_TOKEN_MINUTES = 15


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
        if user.totp_enabled:
            if not request.totp_code:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=TWO_FACTOR_REQUIRED,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not verify_second_factor(user, request.totp_code):
                await create_audit_log(
                    db, user_id=user.id, action="login", entity="user", entity_id=str(user.id),
                    status="failure", error_message="Wrong two-factor code",
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid two-factor code",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            await db.commit()  # records the used code step / recovery code
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


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DBSession,
    redis: RedisClient,
    http_request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Post a reset link to Slack. Same reply whether or not the email exists."""
    if not settings.slack_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is not configured (set SLACK_WEBHOOK_URL)",
        )
    client_ip = http_request.client.host if http_request.client else "unknown"
    await enforce_rate_limit(
        redis, f"forgot-password:{client_ip}", settings.login_rate_limit_per_minute, 60
    )

    user = (
        await db.execute(select(User).where(User.email == request.email))
    ).scalar_one_or_none()
    if user and user.is_active:
        # Single use: the reset bumps token_version, which this token is pinned to
        token = create_access_token(
            {"sub": str(user.id), "ver": user.token_version},
            expires_delta=timedelta(minutes=RESET_TOKEN_MINUTES),
            token_type="reset",
        )
        link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={quote(token)}"
        # In the background so response time doesn't reveal whether the account exists
        background_tasks.add_task(
            notify_slack,
            f"Quantara password reset requested for {user.email}. "
            f"Link valid for {RESET_TOKEN_MINUTES} minutes: {link}",
        )
        await create_audit_log(
            db, user_id=user.id, action="forgot_password", entity="user", entity_id=str(user.id)
        )
    return {"detail": "If that account exists, a reset link has been posted to Slack."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(request: ResetPasswordRequest, db: DBSession) -> None:
    """Set a new password from a reset link and sign out every session."""
    payload = verify_token(request.token, token_type="reset")
    user = None
    if payload and payload.get("sub"):
        user = (
            await db.execute(select(User).where(User.id == int(payload["sub"])))
        ).scalar_one_or_none()
    if not payload or user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid, expired or already used",
        )

    user.hashed_password = get_password_hash(request.new_password)
    user.token_version += 1
    turned_off = request.disable_two_factor and user.totp_enabled
    if turned_off:
        _clear_two_factor(user)
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="reset_password", entity="user", entity_id=str(user.id),
        data={"two_factor_disabled": turned_off},
    )
    if turned_off:
        # Anyone who can read the reset channel could do this, so make it loud
        await notify_slack(
            f"Two-factor login was turned off for {user.email} through a password-reset link. "
            "If that wasn't you, reset the password again and turn two-factor back on."
        )


class TwoFactorSetupResponse(BaseModel):
    """Secret to add to an authenticator app, as text and as an otpauth:// link for a QR code."""

    secret: str
    otpauth_uri: str


class TwoFactorCodeRequest(BaseModel):
    """A 6-digit code from the authenticator app."""

    code: str = Field(..., max_length=32)


class TwoFactorEnabledResponse(BaseModel):
    """Single-use recovery codes, shown once."""

    recovery_codes: list[str]


class TwoFactorDisableRequest(BaseModel):
    """Turning two-factor off or replacing recovery codes needs the password and a code."""

    password: str
    code: str = Field(..., max_length=32)


def _clear_two_factor(user: User) -> None:
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_counter = None
    user.totp_recovery_codes = None


async def _current_user_row(current_user: dict, db: DBSession) -> User:
    return (await db.execute(select(User).where(User.id == int(current_user["id"])))).scalar_one()


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(current_user: CurrentUser, db: DBSession) -> TwoFactorSetupResponse:
    """Start two-factor setup with a fresh secret; it takes effect only after /2fa/enable."""
    user = await _current_user_row(current_user, db)
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor login is already on")
    secret = new_secret()
    user.totp_secret = encrypt_credential(secret)
    user.totp_last_counter = None
    await db.commit()
    return TwoFactorSetupResponse(secret=secret, otpauth_uri=provisioning_uri(secret, user.email))


@router.post("/2fa/enable", response_model=TwoFactorEnabledResponse)
async def enable_two_factor(
    request: TwoFactorCodeRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient
) -> TwoFactorEnabledResponse:
    """Turn two-factor on once the app's code matches; returns recovery codes (shown once)."""
    await enforce_rate_limit(
        redis, f"2fa:{current_user['id']}", settings.login_rate_limit_per_minute, 60
    )
    user = await _current_user_row(current_user, db)
    if user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start two-factor setup first")
    if not verify_totp(user, request.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That code doesn't match; try the newest one")
    codes, hashes = new_recovery_codes()
    user.totp_enabled = True
    user.totp_recovery_codes = hashes
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="enable_two_factor", entity="user", entity_id=str(user.id)
    )
    return TwoFactorEnabledResponse(recovery_codes=codes)


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_two_factor(
    request: TwoFactorDisableRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient
) -> None:
    """Turn two-factor off (needs the password and a code)."""
    await enforce_rate_limit(
        redis, f"2fa:{current_user['id']}", settings.login_rate_limit_per_minute, 60
    )
    user = await _current_user_row(current_user, db)
    if not user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor login is already off")
    if not verify_password(request.password, user.hashed_password) or not verify_second_factor(
        user, request.code
    ):
        await create_audit_log(
            db, user_id=user.id, action="disable_two_factor", entity="user", entity_id=str(user.id),
            status="failure", error_message="Wrong password or code",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong password or code")
    _clear_two_factor(user)
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="disable_two_factor", entity="user", entity_id=str(user.id)
    )


@router.post("/2fa/recovery-codes", response_model=TwoFactorEnabledResponse)
async def regenerate_recovery_codes(
    request: TwoFactorDisableRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient
) -> TwoFactorEnabledResponse:
    """Replace every recovery code (needs the password and a code); returns the new ones, shown once."""
    await enforce_rate_limit(
        redis, f"2fa:{current_user['id']}", settings.login_rate_limit_per_minute, 60
    )
    user = await _current_user_row(current_user, db)
    if not user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor login is off")
    if not verify_password(request.password, user.hashed_password) or not verify_second_factor(
        user, request.code
    ):
        await create_audit_log(
            db, user_id=user.id, action="regenerate_recovery_codes", entity="user",
            entity_id=str(user.id), status="failure", error_message="Wrong password or code",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong password or code")
    codes, hashes = new_recovery_codes()
    user.totp_recovery_codes = hashes
    await db.commit()
    await create_audit_log(
        db, user_id=user.id, action="regenerate_recovery_codes", entity="user", entity_id=str(user.id)
    )
    return TwoFactorEnabledResponse(recovery_codes=codes)


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

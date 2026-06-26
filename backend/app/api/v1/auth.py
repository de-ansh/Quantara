"""Authentication API endpoints."""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.core.dependencies import DBSession
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User
from app.api.v1.audit import create_audit_log

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: DBSession,
) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    
    Args:
        request: Login credentials
        db: Database session
    
    Returns:
        JWT access token
    """
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user and verify_password(request.password, user.hashed_password):
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        await create_audit_log(
            db,
            user_id=user.id,
            action="login",
            entity="user",
            entity_id=str(user.id),
            status="success",
        )
        return TokenResponse(access_token=access_token)
    
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
) -> TokenResponse:
    """
    Register new user.
    
    Args:
        request: Registration data
        db: Database session
    
    Returns:
        JWT access token
    """
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
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    return TokenResponse(access_token=access_token)

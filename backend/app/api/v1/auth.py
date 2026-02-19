"""Authentication API endpoints."""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.dependencies import DBSession
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings

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
    # TODO: Fetch user from database
    # For now, mock authentication
    
    # Mock user validation
    if request.email == "test@quantara.com" and request.password == "password":
        access_token = create_access_token(
            data={"sub": "1", "email": request.email}
        )
        return TokenResponse(access_token=access_token)
    
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
    # TODO: Check if user exists
    # TODO: Create user in database
    
    # Mock user creation
    # Hash password
    hashed_password = get_password_hash(request.password)
    
    access_token = create_access_token(
        data={"sub": "1", "email": request.email}
    )
    
    return TokenResponse(access_token=access_token)

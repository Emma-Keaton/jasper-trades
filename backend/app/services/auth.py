"""
Authentication Service

Provides JWT-based authentication for the API.

Features:
- JWT token generation and verification
- Password hashing and verification
- FastAPI dependency for protected endpoints
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.hash import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.config import settings


# Configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        return bcrypt.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Payload data (should include user_id)
        expires_delta: Optional expiration time override

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# HTTP Basic token
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current authenticated user from JWT token.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}

    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user
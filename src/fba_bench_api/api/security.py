"""Security utilities for password hashing and JWT token management."""

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Password context for hashing and verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
import os

# JWT Configuration
# CRITICAL: Fail safely if SECRET_KEY is missing in production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Allow loose defaults ONLY in non-production if explicitly flagged, otherwise fail
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("FATAL: SECRET_KEY must be set in production!")
    else:
        # Fallback for local dev only - still risky but better than silent random
        import logging
        logging.getLogger(__name__).warning("Using unsafe default SECRET_KEY for development.")
        SECRET_KEY = "dev-secret-change-me" 

ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data model."""

    email: Optional[str] = None


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    """Get current user from JWT token."""
    payload = decode_token(token)
    if payload is None:
        return None

    email: str = payload.get("sub")
    if email is None:
        return None

    return {"email": email, "id": payload.get("user_id")}

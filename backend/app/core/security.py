"""
AMASCI Security Module
=======================
JWT token management, password hashing, and RBAC utilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.enums import UserRole

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiration_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


# --- RBAC Permission Matrix ---
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {
        "upload:write", "upload:read",
        "pipeline:execute", "pipeline:read",
        "model:train", "model:read",
        "forecast:generate", "forecast:read",
        "graph:build", "graph:read", "graph:update",
        "tpke:execute", "tpke:read",
        "graphrag:query",
        "rootcause:analyze",
        "dashboard:read",
        "analytics:read",
        "users:manage",
    },
    UserRole.ANALYST: {
        "upload:write", "upload:read",
        "pipeline:execute", "pipeline:read",
        "model:train", "model:read",
        "forecast:generate", "forecast:read",
        "graph:build", "graph:read", "graph:update",
        "tpke:execute", "tpke:read",
        "graphrag:query",
        "rootcause:analyze",
        "dashboard:read",
        "analytics:read",
    },
    UserRole.VIEWER: {
        "upload:read",
        "pipeline:read",
        "model:read",
        "forecast:read",
        "graph:read",
        "tpke:read",
        "dashboard:read",
        "analytics:read",
    },
}


def has_permission(role: UserRole, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())

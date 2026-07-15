"""
AMASCI API Dependencies
========================
FastAPI dependency injection for database sessions, auth, and services.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import decode_access_token, has_permission
from app.database.postgres import get_db_session

logger = logging.getLogger(__name__)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide database session via dependency injection."""
    async for session in get_db_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict:
    """Extract and validate current user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "viewer"),
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_permission(permission: str):
    """Factory for permission-checking dependencies."""

    async def check_permission(current_user: CurrentUser) -> dict:
        role = UserRole(current_user.get("role", "viewer"))
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )
        return current_user

    return check_permission


# Common permission dependencies
RequireAdmin = Depends(require_permission("users:manage"))
RequireAnalyst = Depends(require_permission("upload:write"))
RequireViewer = Depends(require_permission("dashboard:read"))

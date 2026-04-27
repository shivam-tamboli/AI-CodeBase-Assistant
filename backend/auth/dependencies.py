"""
Authentication Dependencies

FastAPI dependencies for route protection.

Phase 13: Production Ready
"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.auth.jwt import verify_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Dependency to require authentication.

    Use this for protected endpoints that require valid JWT.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User payload from JWT

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
    }


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Dependency for optional authentication.

    Use this for endpoints that work with or without auth.
    Returns None if no valid token provided.

    Args:
        credentials: Optional Bearer token

    Returns:
        User payload if valid token, None otherwise
    """
    if credentials is None:
        return None

    payload = verify_token(credentials.credentials)

    if payload is None:
        return None

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
    }

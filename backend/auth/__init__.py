"""
JWT Authentication Module

Phase 13: Production Ready
"""

from backend.auth.jwt import create_access_token, verify_token
from backend.auth.dependencies import get_current_user, get_optional_user

__all__ = [
    "create_access_token",
    "verify_token",
    "get_current_user",
    "get_optional_user",
]

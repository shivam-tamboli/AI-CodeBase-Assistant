"""
Rate Limiting Middleware

Uses SlowAPI for request rate limiting.

Phase 13: Production Ready
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from functools import wraps

limiter = Limiter(key_func=get_remote_address)


def rate_limit(limit_string: str):
    """
    Decorator for applying rate limits to endpoints.

    Args:
        limit_string: Rate limit specification (e.g., "10/minute", "60/hour")

    Usage:
        @router.post("/chat")
        @rate_limit("10/minute")
        async def chat_endpoint():
            ...

    Rate limit examples:
        - "10/minute" - 10 requests per minute
        - "60/hour" - 60 requests per hour
        - "1000/day" - 1000 requests per day
        - "5/second" - 5 requests per second
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        wrapper.__rate_limit = limit_string
        return wrapper
    return decorator


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Handler for rate limit exceeded errors.

    Returns a standardized error response.
    """
    return {
        "detail": "Rate limit exceeded. Please slow down.",
        "error_code": "RATE_LIMIT_EXCEEDED",
        "limit": str(exc.detail),
        "retry_after": getattr(exc, "retry_after", None),
    }

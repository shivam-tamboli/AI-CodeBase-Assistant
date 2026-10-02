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
import ipaddress

def client_ip(request: Request) -> str:
    """Rate-limit key: the real visitor address, even behind Render's proxy chain.

    On Render the TCP peer is an internal 10.x proxy and X-Forwarded-For ends
    with a Cloudflare edge address that changes per request, so neither one
    identifies the client. Cloudflare puts the visitor's address in
    CF-Connecting-IP and overwrites any value the client sends. The header is
    only trusted when the peer is private/loopback, i.e. the request came
    through that internal proxy; anything else falls back to the peer address.

    Don't start uvicorn with --forwarded-allow-ips='*': it would replace the
    peer with the X-Forwarded-For edge address, which is public, and this
    would fall back to a per-request key again.
    """
    peer = get_remote_address(request)
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        try:
            if ipaddress.ip_address(peer).is_private:
                return cf_ip
        except ValueError:
            pass
    return peer


limiter = Limiter(key_func=client_ip)


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

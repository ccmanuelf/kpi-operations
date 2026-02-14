"""
Rate Limiting Middleware (SEC-001)
API rate limiting using slowapi to prevent abuse and DDoS attacks

Configuration:
- General endpoints: 100 requests/minute
- Auth endpoints (login, register): 10 requests/minute
- Adds X-RateLimit headers to responses

Environment Variables:
- DISABLE_RATE_LIMIT: Set to "1" or "true" to disable rate limiting (for E2E tests)
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Optional
import time
import os

# Check if rate limiting should be disabled (for testing)
RATE_LIMIT_DISABLED = os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes")


# Create limiter instance with remote address as key
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="memory://",
    strategy="fixed-window",
    enabled=not RATE_LIMIT_DISABLED,
)


# Rate limit configurations
class RateLimitConfig:
    """Rate limiting configuration constants"""

    # General API endpoints: 100 requests per minute
    GENERAL_LIMIT = "100/minute"

    # Auth endpoints (login, register): 10 requests per minute (stricter)
    AUTH_LIMIT = "10/minute"

    # Sensitive operations (password reset, etc.): 5 requests per minute
    SENSITIVE_LIMIT = "5/minute"

    # CSV upload/batch operations: 20 requests per minute
    UPLOAD_LIMIT = "20/minute"

    # Report generation: 10 requests per minute
    REPORT_LIMIT = "10/minute"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware to add rate limit headers to all responses

    Headers added:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining in window
    - X-RateLimit-Reset: Timestamp when limit resets
    """

    def __init__(self, app, limiter_instance: Limiter = None):
        super().__init__(app)
        self.limiter = limiter_instance or limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add rate limit headers to response"""

        # Get client identifier
        client_ip = get_remote_address(request)

        # Calculate current window
        current_time = int(time.time())
        window_start = current_time - (current_time % 60)  # 1-minute windows
        window_reset = window_start + 60

        # Call the actual endpoint
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Reset"] = str(window_reset)

        # Note: Actual remaining count is managed by slowapi internally
        # These are informational headers
        response.headers["X-RateLimit-Policy"] = "100 requests per minute"

        return response


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key based on client IP and optional user ID

    Combines IP address with authenticated user ID (if available)
    to provide per-user rate limiting for authenticated requests
    """
    client_ip = get_remote_address(request)

    # Try to get user from request state (set by auth dependency)
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        return f"{client_ip}:{user_id}"

    return client_ip


# No-op decorator for when rate limiting is disabled
def _noop_decorator():
    """No-op decorator that does nothing (for disabled rate limiting)"""

    def decorator(func):
        return func

    return decorator


# Pre-defined rate limiters for different endpoint types
def auth_rate_limit():
    """Rate limiter for authentication endpoints (login, register)"""
    if RATE_LIMIT_DISABLED:
        return _noop_decorator()
    return limiter.limit(RateLimitConfig.AUTH_LIMIT)


def general_rate_limit():
    """Rate limiter for general API endpoints"""
    if RATE_LIMIT_DISABLED:
        return _noop_decorator()
    return limiter.limit(RateLimitConfig.GENERAL_LIMIT)


def sensitive_rate_limit():
    """Rate limiter for sensitive operations (password reset)"""
    if RATE_LIMIT_DISABLED:
        return _noop_decorator()
    return limiter.limit(RateLimitConfig.SENSITIVE_LIMIT)


def upload_rate_limit():
    """Rate limiter for CSV upload/batch operations"""
    if RATE_LIMIT_DISABLED:
        return _noop_decorator()
    return limiter.limit(RateLimitConfig.UPLOAD_LIMIT)


def report_rate_limit():
    """Rate limiter for report generation"""
    if RATE_LIMIT_DISABLED:
        return _noop_decorator()
    return limiter.limit(RateLimitConfig.REPORT_LIMIT)


def configure_rate_limiting(app):
    """
    Configure rate limiting for FastAPI application

    Args:
        app: FastAPI application instance

    Usage:
        from backend.middleware.rate_limit import configure_rate_limiting

        app = FastAPI()
        configure_rate_limiting(app)

    Environment:
        Set DISABLE_RATE_LIMIT=1 to disable rate limiting (for E2E tests)
    """
    if RATE_LIMIT_DISABLED:
        # Skip rate limiting configuration entirely
        return app

    # Add limiter to app state
    app.state.limiter = limiter

    # Add exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add custom middleware for rate limit headers
    app.add_middleware(RateLimitMiddleware, limiter_instance=limiter)

    return app


# Export decorators for easy use in routes
__all__ = [
    "limiter",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "configure_rate_limiting",
    "auth_rate_limit",
    "general_rate_limit",
    "sensitive_rate_limit",
    "upload_rate_limit",
    "report_rate_limit",
    "get_rate_limit_key",
]

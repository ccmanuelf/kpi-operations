"""
Backend middleware for multi-tenant authorization, client isolation, and rate limiting
"""

from .client_auth import verify_client_access, get_user_client_filter, ClientAccessError
from .rate_limit import (
    limiter,
    RateLimitConfig,
    configure_rate_limiting,
    auth_rate_limit,
    general_rate_limit,
    sensitive_rate_limit,
    upload_rate_limit,
    report_rate_limit,
)

__all__ = [
    # Client authorization
    "verify_client_access",
    "get_user_client_filter",
    "ClientAccessError",
    # Rate limiting
    "limiter",
    "RateLimitConfig",
    "configure_rate_limiting",
    "auth_rate_limit",
    "general_rate_limit",
    "sensitive_rate_limit",
    "upload_rate_limit",
    "report_rate_limit",
]

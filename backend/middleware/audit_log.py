"""
Audit Logging Middleware

Logs admin-level actions (POST, PUT, DELETE) on /api/ routes to a structured
application log.  This is a lightweight observability layer — no database writes,
no request-body capture.

Log format:
    [AUDIT] POST /api/production | user=42 | status=201 | time=12ms
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("audit")

# Methods that represent state-changing admin actions
_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that emits structured audit log lines for every
    state-changing request that hits an ``/api/`` path.

    Non-mutating methods (GET, HEAD, OPTIONS) and non-API paths (health
    checks, static assets, docs) are silently passed through.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Fast-path: skip methods and paths we don't care about
        if request.method not in _AUDITED_METHODS:
            return await call_next(request)

        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000)

        # Extract user_id from request state (set by auth dependencies) or
        # fall back to "anonymous".
        user_id = getattr(request.state, "user_id", None) or "anonymous"

        logger.info(
            "[AUDIT] %s %s | user=%s | status=%s | time=%dms",
            request.method,
            request.url.path,
            user_id,
            response.status_code,
            elapsed_ms,
        )

        return response

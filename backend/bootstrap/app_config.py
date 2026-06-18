"""Middleware wiring and global exception handlers."""

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.config import settings
from backend.exceptions.domain_exceptions import (
    DomainException,
    ResourceNotFoundError,
    ValidationError as DomainValidationError,
)
from backend.middleware.audit_log import AuditLogMiddleware
from backend.middleware.rate_limit import configure_rate_limiting
from backend.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


# =============================================================================
# API Version Path-Rewrite Middleware
# =============================================================================


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Rewrites /api/v1/... paths to /api/... so that versioned requests
    are handled by the existing route handlers without any route changes.

    Both /api/v1/<path> and /api/<path> resolve to the same handler.

    Also normalises 3xx Location headers on the way out: when a request
    arrived at /api/v1/... and FastAPI emits a slash-redirect (e.g. for
    routes registered with a trailing slash), the Location is generated
    against the rewritten /api/... path AND comes back as an absolute
    URL pointing at the backend host. In dev that absolute URL skips
    the Vite proxy and triggers a cross-origin redirect, which strips
    the browser's Authorization header → spurious 401 → forced logout.
    Rewriting the Location to (a) re-include /v1 and (b) be relative
    (path-only) keeps the redirect same-origin and authenticated.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.scope["path"]
        original_was_v1 = path.startswith("/api/v1/") or path == "/api/v1"
        if path.startswith("/api/v1/"):
            # Strip the /v1 segment: "/api/v1/foo" -> "/api/foo"
            request.scope["path"] = "/api/" + path[8:]
        elif path == "/api/v1":
            request.scope["path"] = "/api"
        response = await call_next(request)

        if original_was_v1 and response.status_code in (301, 302, 307, 308):
            loc = response.headers.get("location")
            if loc:
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(loc)
                new_path = parsed.path
                # Re-add the /v1 segment if FastAPI emitted /api/... .
                if new_path.startswith("/api/") and not new_path.startswith("/api/v1/"):
                    new_path = "/api/v1/" + new_path[len("/api/") :]
                elif new_path == "/api":
                    new_path = "/api/v1"
                # Drop scheme+netloc so the redirect stays relative —
                # browser keeps the original origin and the Vite proxy
                # (or nginx in prod) handles the next hop with auth
                # headers intact.
                response.headers["location"] = urlunparse(
                    ("", "", new_path, parsed.params, parsed.query, parsed.fragment)
                )
        return response


def configure_middleware(app: FastAPI) -> None:
    # Security headers middleware (SEC-010)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting middleware (SEC-001)
    configure_rate_limiting(app)

    # Audit logging middleware — logs POST/PUT/PATCH/DELETE on /api/ paths
    app.add_middleware(AuditLogMiddleware)

    # API version path-rewrite middleware — rewrites /api/v1/... to /api/...
    # Added before CORS so that CORS (outermost) runs first, then this middleware
    # rewrites the path before it reaches rate limiting, audit, and route handlers.
    app.add_middleware(APIVersionMiddleware)

    # CORS middleware — added last so it runs first (outermost in LIFO order),
    # ensuring CORS preflight OPTIONS requests are handled before rate limiting
    # and audit logging middleware process them.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )


def register_exception_handlers(app: FastAPI) -> None:
    async def domain_validation_error_handler(request: Request, exc: DomainValidationError) -> JSONResponse:
        """Handle domain validation errors -> 400"""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "code": exc.code},
        )

    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        """Handle resource not found -> 404"""
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message, "code": exc.code},
        )

    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        """Handle all other domain exceptions -> 400"""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "code": exc.code},
        )

    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Handle database errors -> 503"""
        logger.exception("Database error: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database service temporarily unavailable"},
        )

    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors -> 500 with sanitized message"""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    app.add_exception_handler(DomainValidationError, domain_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DomainException, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)

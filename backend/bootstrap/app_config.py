"""Middleware wiring and global exception handlers."""

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.audit.capture import register_audit_listener
from backend.config import settings
from backend.exceptions.domain_exceptions import (
    DomainException,
    ResourceNotFoundError,
    ValidationError as DomainValidationError,
)
from backend.middleware.audit_actor_context import AuditActorContextMiddleware
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
    # Attach ORM-level audit capture (entity-level change capture into
    # AUDIT_ENTRY for the 14 tables in backend/audit/registry.py). Idempotent;
    # safe under repeated calls. Registered HERE -- inside configure_middleware(),
    # not at backend/bootstrap/app_config.py's module-import time -- so it only
    # activates when something actually builds the app (main.py calls this
    # unconditionally at import), not merely when something imports this
    # module or package (e.g. a future script or alembic/env.py importing a
    # sibling of app_config without needing the app itself). Fix round 1
    # (2026-08-12): moved from module level per adversarial review, which
    # confirmed nothing breaks today but noted the module-import trigger was
    # incidental, not structural.
    #
    # KNOWN PERMANENT SIDE EFFECT: register_audit_listener() also forces
    # `active_history=True` on every column of the 14 audited mappers (required
    # so UPDATE diffs see the real pre-expiry value instead of `old: None` under
    # SessionLocal's expire_on_commit=True -- see the docstring on
    # _force_active_history_for_audited_tables in backend/audit/capture.py for
    # the verified failure mode). That flag is process-wide and is NOT undone by
    # unregister_audit_listener(); once this function has run once in a
    # process, it stays on for the rest of that process's life. The concrete
    # consequence: setting an attribute on a DETACHED instance of one of the 14
    # audited tables (e.g. after `session.expunge(obj)`), where its attributes
    # were previously expired by a commit, now raises DetachedInstanceError
    # instead of silently reloading -- there was no live session to reload from.
    # Verified via `grep -rn "expunge\|make_transient" backend/` (excluding
    # tests) at wiring time: no application code does this today, so the blast
    # radius is nil, but a maintainer who adds such a pattern to one of the 14
    # audited tables' code paths later will hit this. Grep for `active_history`
    # in this repo before assuming a DetachedInstanceError here is unrelated.
    register_audit_listener()

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

    # CORS middleware — added after APIVersionMiddleware so CORS runs first of
    # the two, ensuring CORS preflight OPTIONS requests are handled before the
    # path rewrite, rate limiting and audit logging see them. NOT the outermost
    # layer overall: AuditActorContextMiddleware is added after this one and is
    # therefore outside it (see the comment on that call below).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    # Audit actor-context seed — added LAST so it is the true OUTERMOST
    # layer (runs first on the way in, last on the way out), ahead of every
    # other middleware above. It must seed backend.audit.context's holder
    # before ANY of them calls call_next() -- SecurityHeaders, RateLimit,
    # AuditLog and APIVersion are all BaseHTTPMiddleware, and each one's
    # call_next forks the asyncio context (as does FastAPI's own dependency
    # resolution, further in). A fork that happens before the seed would
    # carry no reference to the holder at all. See
    # backend/middleware/audit_actor_context.py and
    # backend/audit/context.py (_ActorHolder) for the full mechanism.
    app.add_middleware(AuditActorContextMiddleware)


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

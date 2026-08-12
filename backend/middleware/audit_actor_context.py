"""
Audit Actor Context Middleware

Seeds the audit-trail acting-user holder (backend.audit.context) for every
HTTP request, as early as possible in the ASGI stack -- registered LAST in
backend/bootstrap/app_config.py so it is the OUTERMOST layer and runs before
any downstream middleware's ``call_next`` or FastAPI's dependency-resolution
machinery can fork the request's ``contextvars.Context`` away from it.

Deliberately plain ASGI (``__call__(scope, receive, send)``), not
``BaseHTTPMiddleware``: it needs nothing from the Request object, and a
``BaseHTTPMiddleware`` subclass would add one more ``anyio`` task-spawn fork
of its own between this middleware and the route it's trying to seed for.

See backend/audit/context.py (``_ActorHolder``, ``seed_actor_context``) for
why a mutable holder -- not a bare ContextVar rebind -- is required for the
value to survive those forks, and backend/bootstrap/app_config.py for why
this must be the outermost middleware.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from backend.audit.context import current_actor, seed_actor_context


class AuditActorContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # method/path come straight from the ASGI scope, the only place they
        # are available this early (no Request object is built yet, and the
        # ORM flush hooks that consume them never see one at all). Seeded now
        # rather than read later so an AUDIT_ENTRY row can be tied back to the
        # request-level "[AUDIT] POST /api/... | user=42" log line
        # AuditLogMiddleware writes. `scope["path"]` is the raw, pre-rewrite
        # path: APIVersionMiddleware (inner) rewrites /api/v1/... -> /api/...
        # afterwards, so what lands in AUDIT_ENTRY is what the client actually
        # requested, which is the more useful thing to tie back to.
        token = seed_actor_context(method=scope.get("method"), path=scope.get("path"))
        try:
            await self.app(scope, receive, send)
        finally:
            current_actor.reset(token)

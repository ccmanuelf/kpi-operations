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

        token = seed_actor_context()
        try:
            await self.app(scope, receive, send)
        finally:
            current_actor.reset(token)

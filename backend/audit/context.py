"""Request-scoped context for audit capture.

SQLAlchemy flush hooks run without a request object, so they cannot read
``request.state.user_id``. The acting user is carried here instead, set by the
auth dependency at the same point ``request.state.user_id`` is assigned so
attribution has one source of truth.

FIX ROUND 1 (critical, found by adversarial review): a bare ``ContextVar``
rebind here is NOT enough. FastAPI dispatches every sync dependency
(``get_current_user`` included) and every sync path operation through
``anyio.to_thread.run_sync``, and Starlette's ``BaseHTTPMiddleware`` drives
``call_next`` through its own ``anyio`` task spawn -- both copy the current
``contextvars.Context``. A ``.set()`` made inside one such copy is invisible
everywhere else: not back in the caller, and not in a *different* copy taken
from an earlier point (e.g. the ORM flush listener, which runs inside
whichever copy hosts the sync endpoint function). Verified directly against
the installed FastAPI/Starlette: a rebind inside ``get_current_user`` was
silently discarded, and every audit row landed with ``actor_username="system"``.

The fix mirrors why ``request.state.user_id`` already works: ``Request`` is a
shared *mutable* object passed by reference, so a copy still points at the
same object and mutating one of its fields is visible through every copy
holding that reference. ``_ActorHolder`` is that same trick applied to the
audit contextvar: `AuditActorContextMiddleware` (backend/middleware/
audit_actor_context.py) seeds a fresh holder here, in the real per-request
context, before any FastAPI/Starlette boundary can fork it away; `set_actor`
then mutates that holder's field in place (from wherever it happens to run)
instead of rebinding the ContextVar.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional


class _ActorHolder:
    """Mutable box for the request's audit attribution -- see module docstring
    for why a bare ContextVar rebind is not enough.

    Carries four values, all of them things AUDIT_ENTRY records and none of
    them reconstructable after the fact:

    - ``user_id`` / ``username``: who. Both, not just the id, because
      ``AUDIT_ENTRY.actor_username`` is a deliberate *snapshot* -- its whole
      reason to exist is that history stays readable after the user is renamed
      or deactivated, which is exactly when it is read. Deriving it from
      ``user_id`` at read time would defeat that; deriving it at write time
      from a second query would be a query per audited row.
    - ``method`` / ``path``: which HTTP request. Seeded by
      `AuditActorContextMiddleware` from the ASGI scope (the ORM flush hooks
      have no request object), so an AUDIT_ENTRY row can be tied back to the
      request-level ``[AUDIT] POST /api/... | user=42`` middleware log line.
      Both stay None for non-request writes (scheduler, CLI, migrations).
    """

    __slots__ = ("user_id", "username", "method", "path")

    def __init__(
        self,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.method = method
        self.path = path


current_actor: ContextVar[Optional["_ActorHolder"]] = ContextVar("audit_current_actor", default=None)
_suppressed: ContextVar[bool] = ContextVar("audit_suppressed", default=False)


def seed_actor_context(method: Optional[str] = None, path: Optional[str] = None) -> Token:
    """Bind a fresh holder for this request/task, carrying its request shape.

    Must be called exactly once, as early as possible in the ASGI stack --
    before FastAPI's dependency resolution (or any BaseHTTPMiddleware
    ``call_next``) can fork the context away from it. `AuditActorContextMiddleware`
    is the only intended caller in the running app. Returns a Token; the
    caller resets it once the request is fully handled (mirrors
    `audit_suppressed` below).

    ``method``/``path`` are known at seed time (they come from the ASGI scope)
    whereas the actor is not known until authentication runs, which is why
    they are seeded here and the actor is mutated in later by `set_actor`.
    """
    return current_actor.set(_ActorHolder(method=method, path=path))


def set_actor(user_id: Optional[str], username: Optional[str] = None) -> Optional[Token]:
    """Record the acting user (id and username snapshot).

    If a holder is already bound in this context (the real-request path,
    seeded by `seed_actor_context()`), mutates it in place so the value
    survives later context copies -- see module docstring. Returns None in
    that case: there is nothing new for the caller to reset, since the
    holder's own seed/reset already brackets the whole request. Mutating in
    place also preserves the request method/path the middleware seeded.

    If no holder is bound (unit tests calling this directly with no
    middleware in the loop -- the shape every pre-existing caller of this
    function uses), falls back to binding a fresh one, exactly as before.
    Returns a Token the caller must reset.
    """
    holder = current_actor.get()
    if holder is not None:
        holder.user_id = user_id
        holder.username = username
        return None
    return current_actor.set(_ActorHolder(user_id, username))


def get_actor() -> Optional[str]:
    """The acting user's id, or None for system-initiated writes."""
    holder = current_actor.get()
    return holder.user_id if holder is not None else None


def get_actor_username() -> Optional[str]:
    """The acting user's username snapshot, or None when unknown.

    Distinct from `get_actor()` on purpose: the id is a stable key, the
    username is the human-readable value frozen at write time.
    """
    holder = current_actor.get()
    return holder.username if holder is not None else None


def get_request_shape() -> tuple:
    """``(method, path)`` of the HTTP request this write belongs to.

    ``(None, None)`` for writes with no request behind them -- scheduler jobs,
    CLI scripts, migrations -- which is a meaningful value, not a gap.
    """
    holder = current_actor.get()
    if holder is None:
        return (None, None)
    return (holder.method, holder.path)


def is_suppressed() -> bool:
    """True when the current context has opted out of audit capture."""
    return _suppressed.get()


@contextmanager
def audit_suppressed() -> Iterator[None]:
    """Opt out of audit capture for deliberate bulk work.

    Used by the demo seeder and CSV importers, which write thousands of rows
    that carry no decision. Deliberately narrow: unsuppressed bulk writes are
    still captured, so this cannot become an ambient default.
    """
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)

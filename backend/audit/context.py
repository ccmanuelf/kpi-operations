"""Request-scoped context for audit capture.

SQLAlchemy flush hooks run without a request object, so they cannot read
``request.state.user_id``. The acting user is carried here instead, set by the
auth dependency at the same point ``request.state.user_id`` is assigned so
attribution has one source of truth.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

current_actor: ContextVar[Optional[str]] = ContextVar("audit_current_actor", default=None)
_suppressed: ContextVar[bool] = ContextVar("audit_suppressed", default=False)


def set_actor(user_id: Optional[str]) -> Token:
    """Record the acting user. Returns a token the caller may reset with."""
    return current_actor.set(user_id)


def get_actor() -> Optional[str]:
    """The acting user, or None for system-initiated writes."""
    return current_actor.get()


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

"""Acting-user context and suppression for audit capture.

ORM flush hooks have no request object, so the acting user travels through a
ContextVar set by the auth dependency.
"""

from backend.audit.context import audit_suppressed, get_actor, is_suppressed, set_actor


def test_actor_defaults_to_none():
    assert get_actor() is None


def test_set_actor_round_trips():
    from backend.audit.context import current_actor

    token = set_actor("user-123")
    try:
        assert get_actor() == "user-123"
    finally:
        current_actor.reset(token)
    assert get_actor() is None


def test_not_suppressed_by_default():
    assert is_suppressed() is False


def test_audit_suppressed_suppresses_inside_only():
    assert is_suppressed() is False
    with audit_suppressed():
        assert is_suppressed() is True
    assert is_suppressed() is False


def test_audit_suppressed_restores_on_exception():
    try:
        with audit_suppressed():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert is_suppressed() is False

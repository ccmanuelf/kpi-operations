"""The listener is registered, and the real auth dependency attributes the actor.

These are BEHAVIOURAL on purpose. An earlier draft asserted on module source
text (`"set_actor(" in inspect.getsource(jwt)`); that passes if the call
appears in a comment and breaks on harmless refactors — the green-while-dead
shape this codebase has been bitten by three times.

Note the trap this avoids: a TestClient test cannot use
`app.dependency_overrides[get_current_user]`, because that replaces the very
function under test. The real dependency is therefore called directly with a
real token.
"""

from backend.audit import capture
from backend.audit.context import current_actor, get_actor
from backend.auth.jwt import create_access_token, get_current_user
from backend.tests.fixtures.factories import TestDataFactory


def test_listener_is_registered_at_app_startup():
    from backend.bootstrap import app_config  # noqa: F401  (import registers it)

    assert capture._listener_registered is True


def test_real_auth_dependency_sets_the_audit_actor(transactional_db):
    """Calling the REAL get_current_user must populate the audit contextvar."""

    class _FakeRequest:
        """Minimal stand-in exposing the .state the dependency writes to."""

        class _State:
            pass

        def __init__(self):
            self.state = _FakeRequest._State()

    user = TestDataFactory.create_user(
        transactional_db, user_id="wire-u1", username="wire_user", role="admin", client_id=None
    )
    transactional_db.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    request = _FakeRequest()

    # Reset first so a leaked value from another test cannot make this pass.
    reset_token = current_actor.set(None)
    try:
        resolved = get_current_user(request=request, token=token, db=transactional_db)
        assert resolved.user_id == "wire-u1"
        assert get_actor() == "wire-u1", (
            "get_current_user must set the audit contextvar; ORM flush hooks "
            "have no request object and read it instead."
        )
        # Same source of truth as the existing middleware attribution.
        assert request.state.user_id == "wire-u1"
    finally:
        current_actor.reset(reset_token)

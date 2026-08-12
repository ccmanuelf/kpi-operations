"""The listener is registered, and the real auth dependency attributes the actor.

These are BEHAVIOURAL on purpose. An earlier draft asserted on module source
text (`"set_actor(" in inspect.getsource(jwt)`); that passes if the call
appears in a comment and breaks on harmless refactors — the green-while-dead
shape this codebase has been bitten by three times.

Note the trap this avoids: a TestClient test cannot use
`app.dependency_overrides[get_current_user]`, because that replaces the very
function under test. The real dependency is therefore called directly with a
real token in `test_real_auth_dependency_sets_the_audit_actor`.

FIX ROUND 1 (critical, found by adversarial review): the direct-call test
above still isn't sufficient proof by itself. It calls `get_current_user` as
a plain Python function, so its `set_actor()` call lands in the SAME context
`get_actor()` reads next -- it passes regardless of whether the value would
survive a real request. In production, FastAPI dispatches `get_current_user`
(and this app's sync path operations) through `anyio.to_thread.run_sync`,
which runs the call in a COPY of the current context; a plain ContextVar
rebind made there is discarded the moment the dependency returns and never
reaches the ORM flush listener, which runs inside a *different* copy of that
same context. `test_actor_context_survives_a_real_request_through_the_asgi_app`
below is the test that actually catches that: it drives a real POST through
`TestClient` (real ASGI dispatch, real threadpool hops) and asserts the
resulting AUDIT_ENTRY row is NOT attributed to "system".

Reading the DB back out after the request must go through
`test_client.app.dependency_overrides[get_db]` -- the exact callable the
`test_client` fixture wired up -- rather than importing
`backend.tests.conftest.get_test_engine` directly. pytest's own conftest
auto-import and a fully-qualified `from backend.tests.conftest import ...`
land in different `sys.modules` entries (`tests.conftest` vs
`backend.tests.conftest`), each with its own copy of that module's
`_test_engine` singleton -- a direct import silently reads from the wrong
copy and always sees an empty database. Discovered while writing this test.
"""

from backend.audit import capture
from backend.audit.context import current_actor, get_actor
from backend.auth.jwt import create_access_token, get_current_user
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry
from backend.tests.fixtures.factories import TestDataFactory


def test_listener_is_registered_at_app_startup():
    from backend.main import app  # noqa: F401  (configure_middleware(app) already ran at import)

    assert capture._listener_registered is True


def test_real_auth_dependency_sets_the_audit_actor(transactional_db):
    """Calling the REAL get_current_user must populate the audit contextvar.

    Necessary but NOT sufficient: this proves get_current_user calls
    set_actor with the right value, in a single-context call. It cannot
    catch the threadpool-boundary propagation bug fixed in round 1 -- see
    the test below for that.
    """

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


def test_actor_context_survives_a_real_request_through_the_asgi_app(test_client, admin_auth_headers):
    """A real POST through the real ASGI app must attribute the resulting
    AUDIT_ENTRY row to the authenticated user, not "system".

    This is the one that catches the round-1 critical: FastAPI dispatches
    the sync `get_current_user` dependency, and this app's sync
    `create_client_endpoint`, through `anyio.to_thread.run_sync` -- each in
    its OWN copy of the request's contextvars.Context. A plain ContextVar
    rebind made inside one copy never reaches a different copy, including
    the one the ORM flush listener runs in when the endpoint commits. Before
    the round-1 fix, this test failed: the row landed with
    actor_user_id=None / actor_username="system" regardless of who
    authenticated.
    """
    client_id = "AUD-WIRE-REQ1"

    response = test_client.post(
        "/api/clients",
        json={"client_id": client_id, "client_name": "Wiring Request Test Co"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 201

    # Read back through the SAME dependency override the request used (see
    # module docstring for why a direct `get_test_engine()` import is unsafe
    # here).
    db_override = test_client.app.dependency_overrides[get_db]
    db_gen = db_override()
    session = next(db_gen)
    try:
        row = (
            session.query(AuditEntry)
            .filter(AuditEntry.table_name == "CLIENT", AuditEntry.record_pk == client_id)
            .order_by(AuditEntry.entry_id.desc())
            .first()
        )
        assert row is not None, "expected an AUDIT_ENTRY row for the CLIENT insert"
        assert row.actor_user_id == "USR-ADMINTEST", (
            f"expected the authenticated admin's user_id, got {row.actor_user_id!r} -- "
            "the actor context did not survive FastAPI's real request dispatch"
        )
    finally:
        db_gen.close()

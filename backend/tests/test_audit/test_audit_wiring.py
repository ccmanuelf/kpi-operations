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
from backend.audit.context import current_actor, get_actor, get_actor_username
from backend.auth.jwt import create_access_token, get_current_user
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.orm.user import User
from backend.orm.user_client_assignment import UserClientAssignment
from backend.tests.fixtures.factories import TestDataFactory


def test_listener_is_registered_at_app_startup():
    """Building the app must register the capture listeners.

    ORDER-ROBUSTNESS (fix round 2): an earlier version of this test just did
    `import backend.main` and asserted `capture._listener_registered is True`.
    That only proves anything when `backend.main` is not already in
    `sys.modules` -- on a re-import Python returns the cached module without
    re-running `configure_middleware(app)`, so the assertion was really
    reading whatever global state an earlier test happened to leave behind.
    It passed only because alphabetical collection put this file before
    `test_capture.py`, whose autouse fixture calls `unregister_audit_listener()`
    after every test; run this module second (`-p no:randomly` off, `-k`
    selection, a future rename) and it failed on a flag that says nothing
    about the wiring.

    This version does not read the ambient flag at all. It forces the flag to
    a known-false state, calls the real wiring function
    (`configure_middleware`, the same one `backend.main` calls at import) on a
    throwaway FastAPI app, and asserts the flag flipped -- so it exercises the
    wiring on every run, in any order, and restores whatever state it found.
    """
    from fastapi import FastAPI

    from backend.bootstrap.app_config import configure_middleware

    original = capture._listener_registered
    try:
        # Start from a genuinely unregistered state so a leaked True from an
        # earlier test cannot make this pass without the wiring running.
        capture.unregister_audit_listener()
        assert capture._listener_registered is False

        configure_middleware(FastAPI())

        assert capture._listener_registered is True, (
            "configure_middleware() must call register_audit_listener(); "
            "without it, nothing in the running app captures any change."
        )
    finally:
        if original:
            capture.register_audit_listener()
        else:
            capture.unregister_audit_listener()


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
        assert get_actor_username() == "wire_user", (
            "get_current_user must also carry the USERNAME: AUDIT_ENTRY."
            "actor_username is a snapshot taken at write time so history stays "
            "readable after this user is renamed or deactivated."
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


def test_request_driven_write_records_username_method_and_path(test_client, admin_auth_headers):
    """A real request must populate actor_username, request_method and
    request_path -- the three columns that were being written as
    id-duplicate / NULL / NULL.

    None of the three is backfillable: `actor_username` is a snapshot whose
    whole purpose is to survive the user being renamed or deactivated, and
    the request method/path exist only for the duration of the request that
    made the change. They are asserted here, through the real ASGI stack,
    because that is the only place all three sources meet -- the middleware
    (ASGI scope), the auth dependency (User row) and the mapper-level writer.

    Was failing before this fix: actor_username held "USR-ADMINTEST" (the id
    again) and both request columns were NULL for every row ever written.
    """
    client_id = "AUD-WIRE-REQ2"

    response = test_client.post(
        "/api/clients",
        json={"client_id": client_id, "client_name": "Request Shape Test Co"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 201

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
        assert row.actor_user_id == "USR-ADMINTEST"
        assert row.actor_username == "admin_testuser", (
            f"expected the admin's USERNAME snapshot, got {row.actor_username!r} -- "
            "if this equals actor_user_id, the column is a duplicate and delivers nothing"
        )
        assert row.actor_username != row.actor_user_id
        assert row.request_method == "POST"
        assert row.request_path == "/api/clients"
    finally:
        db_gen.close()


def test_deleting_a_user_captures_its_client_assignment_deletes(test_client, admin_auth_headers):
    """DELETE /api/users/{id} must leave a trail for the tenant-access grants
    it removes, not only for the USER row.

    USER_CLIENT_ASSIGNMENT.user_id declares ondelete="CASCADE" and there is no
    ORM relationship between User and UserClientAssignment, so before the fix
    the child rows were removed by the DATABASE: SQLAlchemy never saw them,
    the mapper events never fired, and an audited access-control grant vanished
    with zero trail. The trail recorded the grant being created and never
    recorded it being revoked -- on the one table added to the allow-list
    specifically because it confers tenant reach.

    Was failing before the fix: `assignment_deletes` was empty.
    """
    db_override = test_client.app.dependency_overrides[get_db]

    # Seed a disposable user with two client grants, committed the same way a
    # real one would be (through the app's own session factory).
    setup_gen = db_override()
    setup = next(setup_gen)
    try:
        client_a = TestDataFactory.create_client(setup, client_id="AUD-DELC-A", client_name="Grant A Co")
        client_b = TestDataFactory.create_client(setup, client_id="AUD-DELC-B", client_name="Grant B Co")
        victim = TestDataFactory.create_user(
            setup, user_id="AUD-DELU-1", username="aud_del_user", role="operator", client_id=None
        )
        setup.add(UserClientAssignment(user_id=victim.user_id, client_id=client_a.client_id, assigned_by="seed"))
        setup.add(UserClientAssignment(user_id=victim.user_id, client_id=client_b.client_id, assigned_by="seed"))
        setup.commit()
    finally:
        setup_gen.close()

    response = test_client.delete("/api/users/AUD-DELU-1", headers=admin_auth_headers)
    assert response.status_code == 204

    verify_gen = db_override()
    verify = next(verify_gen)
    try:
        # The grants really are gone (so the trail is describing a real removal).
        assert verify.query(UserClientAssignment).filter_by(user_id="AUD-DELU-1").count() == 0
        assert verify.query(User).filter_by(user_id="AUD-DELU-1").count() == 0

        assignment_deletes = (
            verify.query(AuditEntry)
            .filter(
                AuditEntry.table_name == "USER_CLIENT_ASSIGNMENT",
                AuditEntry.operation == AuditOperation.DELETE,
            )
            .all()
        )
        deleted_for_victim = [e for e in assignment_deletes if e.changes.get("user_id", {}).get("old") == "AUD-DELU-1"]
        assert len(deleted_for_victim) == 2, (
            "expected one AUDIT_ENTRY DELETE row per revoked tenant grant, got "
            f"{len(deleted_for_victim)} -- the cascade removed them behind the ORM's back"
        )
        assert sorted(e.changes["client_id"]["old"] for e in deleted_for_victim) == ["AUD-DELC-A", "AUD-DELC-B"]
        # Attributed like every other request-driven change, not to "system".
        assert {e.actor_user_id for e in deleted_for_victim} == {"USR-ADMINTEST"}
        assert {e.request_method for e in deleted_for_victim} == {"DELETE"}

        # The USER row itself is still captured (the fix must not displace it).
        user_deletes = (
            verify.query(AuditEntry)
            .filter(
                AuditEntry.table_name == "USER",
                AuditEntry.record_pk == "AUD-DELU-1",
                AuditEntry.operation == AuditOperation.DELETE,
            )
            .count()
        )
        assert user_deletes == 1
    finally:
        verify_gen.close()

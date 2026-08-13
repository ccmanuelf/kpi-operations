"""Audit read API: behaviour and authorization."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.routes.audit import router as audit_router
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture(autouse=True)
def _no_audit_capture_noise():
    """These tests exercise the read API against explicitly-seeded rows;
    capture correctness is Phase A1's job (test_capture.py). The mapper-level
    listener is process-wide, not session-scoped (see capture.py's
    docstring): if some earlier, unrelated test in this pytest process
    registered it and never tore it down, our own fixture's admin-user
    INSERT below would itself become an extra AUDIT_ENTRY row and break the
    exact-count assertions.

    Save-and-restore, not an unconditional unregister: test_audit_wiring.py's
    request-driven tests rely on the listener already being registered from
    the `test_client` fixture's one-time app construction and never
    re-register it themselves, so leaving it force-off after this module
    would break whichever of those tests runs next in the same process.
    """
    from backend.audit import capture

    original = capture._listener_registered
    capture.unregister_audit_listener()
    yield
    if original:
        capture.register_audit_listener()
    else:
        capture.unregister_audit_listener()


@pytest.fixture
def admin_audit_client(transactional_db):
    admin = TestDataFactory.create_user(
        transactional_db, user_id="aud-admin", username="aud_admin", role="admin", client_id=None
    )
    transactional_db.commit()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: transactional_db
    app.dependency_overrides[get_current_user] = lambda: admin
    return TestClient(app), transactional_db


@pytest.fixture
def operator_audit_client(transactional_db):
    operator = TestDataFactory.create_user(
        transactional_db, user_id="aud-operator", username="aud_operator", role="operator", client_id=None
    )
    transactional_db.commit()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: transactional_db
    app.dependency_overrides[get_current_user] = lambda: operator
    return TestClient(app), transactional_db


def _seed_entry(db, record_pk="HOLD-1", table_name="HOLD_ENTRY", actor="user-1"):
    db.add(
        AuditEntry(
            occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
            actor_user_id=actor,
            actor_username="alice",
            table_name=table_name,
            record_pk=record_pk,
            operation=AuditOperation.UPDATE,
            changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
            client_id="CLIENT-1",
        )
    )
    db.flush()


def test_list_returns_entries_for_admin(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db)

    response = client.get("/api/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["entries"][0]["table_name"] == "HOLD_ENTRY"
    assert body["entries"][0]["changes"]["hold_status"]["new"] == "RELEASED"


def test_list_filters_by_table_name(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", table_name="HOLD_ENTRY")
    _seed_entry(db, record_pk="WO-1", table_name="WORK_ORDER")

    response = client.get("/api/audit?table_name=WORK_ORDER")

    assert response.status_code == 200
    assert [e["record_pk"] for e in response.json()["entries"]] == ["WO-1"]


def test_list_reports_when_the_trail_started(admin_audit_client):
    """No backfill exists, so an absent old change is correct, not a bug."""
    client, db = admin_audit_client
    _seed_entry(db)

    body = client.get("/api/audit").json()

    assert body["trail_started_at"] is not None


def test_empty_trail_reports_null_start(admin_audit_client):
    client, _db = admin_audit_client

    body = client.get("/api/audit").json()

    assert body["total"] == 0
    assert body["trail_started_at"] is None


def test_list_excludes_entries_before_start_date(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db)

    response = client.get("/api/audit?start_date=2026-08-12")

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_list_includes_entries_on_end_date_next_midnight_boundary(admin_audit_client):
    """occurred_at is a DateTime; an inclusive end_date must not drop rows
    recorded later on that same day (i.e. compare against the next midnight,
    not the date at midnight)."""
    client, db = admin_audit_client
    db.add(
        AuditEntry(
            # Naive UTC, matching what the capture engine actually writes
            # (backend/orm/audit_entry.py: neither SQLite nor MariaDB retain
            # a UTC offset on this column).
            occurred_at=datetime(2026, 8, 11, 23, 59),
            actor_user_id="user-1",
            actor_username="alice",
            table_name="HOLD_ENTRY",
            record_pk="HOLD-1",
            operation=AuditOperation.UPDATE,
            changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
            client_id="CLIENT-1",
        )
    )
    db.flush()

    response = client.get("/api/audit?end_date=2026-08-11")

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_list_rejects_non_admin(operator_audit_client):
    client, db = operator_audit_client
    _seed_entry(db)

    response = client.get("/api/audit")

    assert response.status_code == 403


def test_entity_history_returns_only_that_entity(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1")
    _seed_entry(db, record_pk="HOLD-2")

    response = client.get("/api/audit/HOLD_ENTRY/HOLD-1")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-1"]


def test_entity_history_of_unknown_record_is_empty_not_an_error(admin_audit_client):
    """No backfill: nothing recorded is a legitimate answer."""
    client, _db = admin_audit_client

    response = client.get("/api/audit/HOLD_ENTRY/NEVER-TOUCHED")

    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.parametrize("role", ["poweruser", "leader", "supervisor", "operator", "viewer"])
def test_non_admin_roles_are_forbidden(transactional_db, role):
    """Admin-only, pinned per role. One expected status per assertion."""
    user = TestDataFactory.create_user(
        transactional_db, user_id=f"aud-{role}", username=f"aud_{role}", role=role, client_id=None
    )
    transactional_db.commit()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: transactional_db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    assert client.get("/api/audit").status_code == 403
    assert client.get("/api/audit/HOLD_ENTRY/HOLD-1").status_code == 403

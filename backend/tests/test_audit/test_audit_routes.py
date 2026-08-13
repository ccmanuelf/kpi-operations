"""Audit read API: behaviour and authorization."""

from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.routes.audit import _end_of_day
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


def _seed_entry(
    db,
    record_pk="HOLD-1",
    table_name="HOLD_ENTRY",
    actor="user-1",
    client_id="CLIENT-1",
    occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
):
    db.add(
        AuditEntry(
            occurred_at=occurred_at,
            actor_user_id=actor,
            actor_username="alice",
            table_name=table_name,
            record_pk=record_pk,
            operation=AuditOperation.UPDATE,
            changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
            client_id=client_id,
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
    # `operation` is an Enum(AuditOperation) column read into a `str` response
    # field. Pinned because the serialized value is what every consumer reads
    # and nothing else asserts it: a plain str(enum) anywhere on that path
    # would emit "AuditOperation.UPDATE" and silently break them.
    assert body["entries"][0]["operation"] == "UPDATE"


def test_list_filters_by_table_name(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", table_name="HOLD_ENTRY")
    _seed_entry(db, record_pk="WO-1", table_name="WORK_ORDER")

    response = client.get("/api/audit?table_name=WORK_ORDER")

    assert response.status_code == 200
    assert [e["record_pk"] for e in response.json()["entries"]] == ["WO-1"]


def test_list_filters_by_actor_user_id(admin_audit_client):
    """The actor filter had NO test: the review deleted the clause and the
    whole audit suite stayed green. Two actors, one asked for, the other
    must be absent."""
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", actor="user-1")
    _seed_entry(db, record_pk="HOLD-2", actor="user-2")

    response = client.get("/api/audit?actor_user_id=user-2")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-2"]
    assert body["total"] == 1


def test_list_filters_by_client_id(admin_audit_client):
    """Same blind spot as the actor filter — deleting the client_id clause
    left the suite green. Two tenants, only the requested one comes back."""
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", client_id="CLIENT-1")
    _seed_entry(db, record_pk="HOLD-2", client_id="CLIENT-2")

    response = client.get("/api/audit?client_id=CLIENT-2")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-2"]
    assert body["total"] == 1


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


def test_end_of_day_does_not_overflow_at_the_maximum_date():
    """``end_date`` is a plain ``Optional[date]``, so FastAPI accepts every
    representable date -- including ``date.max``, which is a legitimate
    MariaDB DATETIME day and not a nonsense value the API should reject.

    ``date.max`` has no next midnight: ``datetime.combine(date.max, time.min)
    + timedelta(days=1)`` raises ``OverflowError: date value out of range``,
    which no handler catches. The bound must clamp instead.
    """
    bound = _end_of_day(date.max)

    assert bound == datetime.max
    # Naive, matching AUDIT_ENTRY.occurred_at's naive-UTC contract: an aware
    # bound compares wrongly (or raises) against a naive column.
    assert bound.tzinfo is None


def test_list_accepts_the_maximum_end_date(admin_audit_client):
    """``GET /api/audit?end_date=9999-12-31`` must return that day's entries,
    not crash. FastAPI validates the value happily, so before the clamp this
    was an unhandled ``OverflowError`` -- a 500 on accepted input.
    """
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1")

    response = client.get("/api/audit?end_date=9999-12-31")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-1"]
    assert body["total"] == 1


@pytest.mark.parametrize("path", ["/api/audit", "/api/audit/HOLD_ENTRY/HOLD-1"])
def test_largest_accepted_offset_still_answers(admin_audit_client, path):
    """The crash guard must not narrow what already worked: 2**63-1 is the
    largest OFFSET both engines take, and it must still return a page (empty,
    since nothing is that deep) rather than 422."""
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1")

    response = client.get(f"{path}?offset=9223372036854775807")

    assert response.status_code == 200
    assert response.json()["entries"] == []


@pytest.mark.parametrize("path", ["/api/audit", "/api/audit/HOLD_ENTRY/HOLD-1"])
def test_offset_beyond_the_engine_limit_is_rejected_not_a_crash(admin_audit_client, path):
    """Same defect class as the end_date overflow: ``offset`` had no upper
    bound, so FastAPI accepted 2**63 and the driver then raised
    ``OverflowError: Python int too large to convert to SQLite INTEGER`` --
    an unhandled 500 on accepted input, on BOTH endpoints. It must be
    rejected as invalid input instead.
    """
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1")

    response = client.get(f"{path}?offset=9223372036854775808")

    assert response.status_code == 422


def test_list_excludes_entries_after_end_date(admin_audit_client):
    """The missing half of the end_date contract.

    test_list_includes_entries_on_end_date_next_midnight_boundary is one-sided
    by construction: it proves the bound is not too EARLY, so the entire
    end_date clause could be deleted and it would still pass (it did — the
    review removed the clause and the suite stayed green). This proves the
    bound excludes something, which only a real filter can do.
    """
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-ON-DAY", occurred_at=datetime(2026, 8, 11, 23, 59))
    _seed_entry(db, record_pk="HOLD-NEXT-DAY", occurred_at=datetime(2026, 8, 12, 0, 1))

    response = client.get("/api/audit?end_date=2026-08-11")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-ON-DAY"]
    assert body["total"] == 1


# ---------------------------------------------------------------------------
# Pagination + ordering. Both endpoints sliced with .offset().limit() and had
# NO test: the review deleted the slice from both and the suite stayed green,
# so a caller asking for page 2 silently got page 1 (every row, in fact).
#
# These also pin the newest-first tiebreaker. On production MariaDB
# occurred_at is a whole-second DATETIME, so rows written in the same second
# (a single flush; a CSV upload writes hundreds per second) tie, and without
# ORDER BY entry_id DESC the trail can come back oldest-first AND offset
# paging over the tied set can repeat or skip rows. Seeded here in one second
# on purpose — spread-out timestamps cannot see either defect.
# ---------------------------------------------------------------------------


def test_list_orders_newest_first_within_the_same_second(admin_audit_client):
    same_second = datetime(2026, 8, 11, 12, 0, 0)
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-OLDEST", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-MIDDLE", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-NEWEST", occurred_at=same_second)

    response = client.get("/api/audit?table_name=HOLD_ENTRY")

    assert response.status_code == 200
    assert [e["record_pk"] for e in response.json()["entries"]] == [
        "HOLD-NEWEST",
        "HOLD-MIDDLE",
        "HOLD-OLDEST",
    ]


def test_list_pagination_returns_the_second_row_and_keeps_total(admin_audit_client):
    same_second = datetime(2026, 8, 11, 12, 0, 0)
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-OLDER", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-NEWER", occurred_at=same_second)

    response = client.get("/api/audit?table_name=HOLD_ENTRY&limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-OLDER"]
    # total counts every MATCHING row, not the returned page.
    assert body["total"] == 2


def test_entity_history_orders_newest_first_within_the_same_second(admin_audit_client):
    same_second = datetime(2026, 8, 11, 12, 0, 0)
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", actor="user-first", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-1", actor="user-second", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-1", actor="user-third", occurred_at=same_second)

    response = client.get("/api/audit/HOLD_ENTRY/HOLD-1")

    assert response.status_code == 200
    assert [e["actor_user_id"] for e in response.json()["entries"]] == [
        "user-third",
        "user-second",
        "user-first",
    ]


def test_entity_history_pagination_returns_the_second_row_and_keeps_total(admin_audit_client):
    same_second = datetime(2026, 8, 11, 12, 0, 0)
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", actor="user-older", occurred_at=same_second)
    _seed_entry(db, record_pk="HOLD-1", actor="user-newer", occurred_at=same_second)

    response = client.get("/api/audit/HOLD_ENTRY/HOLD-1?limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert [e["actor_user_id"] for e in body["entries"]] == ["user-older"]
    assert body["total"] == 2


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


def test_entity_history_filters_by_table_not_just_record_pk(admin_audit_client):
    """record_pk is a stringified single-column PK, so collisions across
    tables are realistic (e.g. EMPLOYEE.employee_id and
    EMPLOYEE_CLIENT_ASSIGNMENT.assignment_id can both stringify to "1").
    Seeding the SAME record_pk under two different table_names is the only
    way to prove the table_name filter itself is doing something — a test
    that varies record_pk alone (as in
    test_entity_history_returns_only_that_entity) would still pass even if
    the table_name clause were deleted."""
    client, db = admin_audit_client
    _seed_entry(db, record_pk="1", table_name="EMPLOYEE")
    _seed_entry(db, record_pk="1", table_name="EMPLOYEE_CLIENT_ASSIGNMENT")

    response = client.get("/api/audit/EMPLOYEE/1")

    assert response.status_code == 200
    body = response.json()
    assert [e["table_name"] for e in body["entries"]] == ["EMPLOYEE"]
    assert body["total"] == 1


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

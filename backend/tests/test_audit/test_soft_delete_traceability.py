"""A soft delete has to say who did it and when — provable through the API.

``is_active`` alone makes a soft-deleted row indistinguishable from one that
was never active, which is worse than a hard delete in one specific way: a hard
delete leaves an absence somebody might notice. So each of the eleven records
three things, and each is asserted here through the running application rather
than by inspecting the writer:

* ``deleted_at`` / ``deleted_by`` on the row itself;
* an ``AUDIT_ENTRY`` row with ``operation=DELETE``, the actor, and the full
  pre-delete snapshot;
* both reachable through the admin audit API at ``/api/audit/{table}/{pk}``.

The nine tables ``AUDITED_TABLES`` deliberately excludes as high-volume routine
data entry are covered too. Entering a production row every shift is routine;
deleting one is a discretionary act. That is a narrower promise than auditing
the table — every soft delete is attributable, not every change is — and it is
parametrized over all eleven so it cannot quietly hold for only the two tables
that were already audited.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.audit.capture import register_audit_listener, unregister_audit_listener
from backend.audit.context import set_actor
from backend.database import get_db
from backend.db.soft_delete_filter import include_inactive
from backend.db.soft_delete_registry import AUTO_FILTERED_TABLES, AUTO_FILTERED_WITHOUT_DELETE_ENDPOINT
from backend.middleware.audit_actor_context import AuditActorContextMiddleware
from backend.orm.audit_entry import AuditEntry
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.soft_delete_rows import PK_ATTR, build_transaction_rows

# table -> (single-resource path prefix, fixture key holding a deletable row)
DELETABLE = {
    "ATTENDANCE_ENTRY": ("/api/attendance", "ATTENDANCE_ENTRY"),
    "DEFECT_DETAIL": ("/api/defects", "DEFECT_DETAIL"),
    "DOWNTIME_ENTRY": ("/api/downtime", "DOWNTIME_ENTRY"),
    "FLOATING_POOL": ("/api/floating-pool", "FLOATING_POOL"),
    "HOLD_ENTRY": ("/api/holds", "HOLD_ENTRY"),
    "JOB": ("/api/jobs", "JOB"),
    "PART_OPPORTUNITIES": ("/api/part-opportunities", "PART_OPPORTUNITIES"),
    "PRODUCTION_ENTRY": ("/api/production", "PRODUCTION_ENTRY"),
    "QUALITY_ENTRY": ("/api/quality", "QUALITY_ENTRY_leaf"),
    "WORK_ORDER": ("/api/work-orders", "WORK_ORDER_leaf"),
    "shift_coverage": ("/api/coverage", "shift_coverage"),
}
TABLES = sorted(DELETABLE)


def test_every_deletable_auto_filtered_table_is_covered_here():
    """Anti-vacuity: a new auto-filtered table must be added to DELETABLE, or
    every parametrized test below silently stops covering it. ALERT is excluded
    because it has no DELETE endpoint — it is only ever hidden by cascade, and
    that exemption is itself gated in the registry guards."""
    assert set(DELETABLE) == set(AUTO_FILTERED_TABLES) - set(AUTO_FILTERED_WITHOUT_DELETE_ENDPOINT)


@pytest.fixture(scope="function")
def audited_env():
    """The eleven routers behind the real audit listener and actor middleware."""
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    built = build_transaction_rows(session)
    supervisor = built["supervisor"]

    from backend.auth.jwt import get_current_active_supervisor, get_current_admin, get_current_user
    from backend.routes.attendance import router as attendance_router
    from backend.routes.audit import router as audit_router
    from backend.routes.coverage import router as coverage_router
    from backend.routes.defect import router as defect_router
    from backend.routes.downtime import router as downtime_router
    from backend.routes.floating_pool import router as floating_pool_router
    from backend.routes.holds import router as holds_router
    from backend.routes.jobs import router as jobs_router
    from backend.routes.part_opportunities import router as part_opportunities_router
    from backend.routes.production import router as production_router
    from backend.routes.quality import router as quality_router
    from backend.routes.work_orders import router as work_orders_router

    app = FastAPI()
    for router in (
        attendance_router,
        audit_router,
        coverage_router,
        defect_router,
        downtime_router,
        floating_pool_router,
        holds_router,
        jobs_router,
        part_opportunities_router,
        production_router,
        quality_router,
        work_orders_router,
    ):
        app.include_router(router)
    app.add_middleware(AuditActorContextMiddleware)

    def _override_get_db():
        yield session

    def _current_user():
        # Exactly what backend/auth/jwt.py:227 does once it has resolved the
        # token, so the actor reaches AUDIT_ENTRY the same way it does live
        # rather than being planted by the test.
        set_actor(supervisor.user_id, supervisor.username)
        return supervisor

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_active_supervisor] = _current_user
    app.dependency_overrides[get_current_admin] = _current_user

    register_audit_listener()
    try:
        yield TestClient(app), session, built
    finally:
        unregister_audit_listener()
        session.close()
        engine.dispose()


def _delete(http, table, built):
    resource, key = DELETABLE[table]
    pk = getattr(built[key], PK_ATTR[table])
    response = http.delete(f"{resource}/{pk}")
    assert response.status_code == 204, f"{resource}/{pk} -> {response.status_code} {response.text}"
    return pk


@pytest.mark.parametrize("table", TABLES)
def test_the_audit_api_says_who_deleted_the_row_and_when(audited_env, table):
    """The verification bar, stated as one assertion set per table."""
    http, _session, built = audited_env
    supervisor = built["supervisor"]
    before = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)

    pk = _delete(http, table, built)

    payload = http.get(f"/api/audit/{table}/{pk}").json()
    deletions = [e for e in payload["entries"] if e["operation"] == "DELETE"]

    assert len(deletions) == 1
    entry = deletions[0]
    assert entry["actor_user_id"] == supervisor.user_id
    assert entry["actor_username"] == supervisor.username
    assert entry["record_pk"] == str(pk)
    assert datetime.fromisoformat(entry["occurred_at"]) >= before
    assert entry["request_method"] == "DELETE"


@pytest.mark.parametrize("table", TABLES)
def test_the_audit_entry_carries_the_row_as_it_was_before_the_delete(audited_env, table):
    """A DELETE entry whose snapshot already showed is_active False would be
    recording the aftermath, not the row that was lost."""
    http, _session, built = audited_env
    pk = _delete(http, table, built)

    entry = [e for e in http.get(f"/api/audit/{table}/{pk}").json()["entries"] if e["operation"] == "DELETE"][0]

    assert entry["changes"]["is_active"] == {"old": True, "new": None}


@pytest.mark.parametrize("table", TABLES)
def test_the_row_itself_records_who_deleted_it_and_when(audited_env, table):
    """deleted_at/deleted_by on the record, so the row is self-describing even
    without joining the audit trail."""
    http, session, built = audited_env
    supervisor = built["supervisor"]
    before = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)

    _resource, key = DELETABLE[table]
    entity = built[key]
    _delete(http, table, built)
    session.expire_all()

    with include_inactive(session):
        session.refresh(entity)
        assert entity.is_active is False
        assert entity.deleted_by == supervisor.user_id
        assert entity.deleted_at is not None
        assert entity.deleted_at.replace(tzinfo=None) >= before


@pytest.mark.parametrize("table", TABLES)
def test_a_refused_or_absent_delete_records_nothing(audited_env, table):
    """The trail must not fill up with deletions that did not happen."""
    http, session, built = audited_env
    resource, _key = DELETABLE[table]

    assert http.delete(f"{resource}/NO-SUCH-ID-12345").status_code in (404, 422)

    written = session.query(AuditEntry).filter(AuditEntry.operation == "DELETE").count()
    assert written == 0


def test_a_delete_refused_with_409_writes_no_audit_entry(audited_env):
    """A blocked delete is not a delete."""
    http, session, built = audited_env
    work_order_id = built["WORK_ORDER"].work_order_id

    assert http.delete(f"/api/work-orders/{work_order_id}").status_code == 409

    assert session.query(AuditEntry).filter(AuditEntry.record_pk == work_order_id).count() == 0

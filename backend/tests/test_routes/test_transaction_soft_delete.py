"""The eleven transaction DELETE endpoints: 204, then gone from every read.

Before this suite existed all eleven returned 404 for *every* id, valid ones
included: the CRUD layer called ``soft_delete()``, which sets ``is_active =
False``, and none of the eleven models had that column — so it returned False
and the route raised 404. Four of them reach a user through a grid or form
delete action, so this was a live user-facing defect, not a testing limitation.

Seven were found by the contract harness. The last four — jobs, coverage,
floating-pool, part-opportunities — have the identical defect and were
invisible to it only because the seeder writes no rows for them, so they were
filed as a seed gap rather than a 404.

Each case proves the full round trip against a real Alembic-built schema:
DELETE -> 204, GET by id -> 404, and the id absent from the list read.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database import get_db
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.soft_delete_rows import PK_ATTR, build_transaction_rows

# (case id, collection path, single-resource path prefix, id field in the list rows)
CASES = [
    ("attendance", "/api/attendance", "/api/attendance", "attendance_entry_id"),
    ("coverage", "/api/coverage", "/api/coverage", "coverage_id"),
    ("defects", "/api/defects", "/api/defects", "defect_detail_id"),
    ("downtime", "/api/downtime", "/api/downtime", "downtime_entry_id"),
    ("floating-pool", "/api/floating-pool", "/api/floating-pool", "pool_id"),
    ("holds", "/api/holds", "/api/holds", "hold_entry_id"),
    ("jobs", "/api/jobs", "/api/jobs", "job_id"),
    ("part-opportunities", "/api/part-opportunities", "/api/part-opportunities", "part_number"),
    ("production", "/api/production", "/api/production", "production_entry_id"),
    ("quality", "/api/quality/", "/api/quality", "quality_entry_id"),
    ("work-orders", "/api/work-orders", "/api/work-orders", "work_order_id"),
]

CASE_IDS = [c[0] for c in CASES]


@pytest.fixture(scope="function")
def soft_delete_env():
    """One DB holding a row for each of the seven models, plus a wired-up app."""
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    built = build_transaction_rows(session)
    supervisor = built["supervisor"]

    ids = {
        "attendance": built["ATTENDANCE_ENTRY"].attendance_entry_id,
        "coverage": built["shift_coverage"].coverage_id,
        "defects": built["DEFECT_DETAIL"].defect_detail_id,
        "downtime": built["DOWNTIME_ENTRY"].downtime_entry_id,
        "floating-pool": built["FLOATING_POOL"].pool_id,
        "holds": built["HOLD_ENTRY"].hold_entry_id,
        "jobs": built["JOB"].job_id,
        "part-opportunities": built["PART_OPPORTUNITIES"].part_number,
        "production": built["PRODUCTION_ENTRY"].production_entry_id,
        # Leaf rows: WORK_ORDER and QUALITY_ENTRY are refused with 409 while
        # visible children reference them, so the round trip uses childless
        # rows of the same tables. The refusal itself is asserted separately in
        # test_delete_is_refused_with_409_while_visible_children_reference_it.
        "quality": built["QUALITY_ENTRY_leaf"].quality_entry_id,
        "work-orders": built["WORK_ORDER_leaf"].work_order_id,
    }

    from backend.auth.jwt import get_current_active_supervisor, get_current_user
    from backend.routes.attendance import router as attendance_router
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

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: supervisor
    app.dependency_overrides[get_current_active_supervisor] = lambda: supervisor

    yield TestClient(app), session, ids, built

    session.close()
    engine.dispose()


def _list_ids(http, collection, id_field):
    response = http.get(collection, params={"limit": 500})
    assert response.status_code == 200, f"{collection} list read failed: {response.status_code} {response.text}"
    return [row[id_field] for row in response.json()]


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_delete_returns_204_for_a_valid_id(soft_delete_env, case, collection, resource, id_field):
    """The defect itself: every one of these answered 404 for a real row."""
    http, _session, ids, _built = soft_delete_env
    response = http.delete(f"{resource}/{ids[case]}")
    assert response.status_code == 204, f"DELETE {resource}/{ids[case]} -> {response.status_code} {response.text}"


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_deleted_row_is_gone_from_by_id_and_list_reads(soft_delete_env, case, collection, resource, id_field):
    """A soft delete that does not hide the row is not a delete."""
    http, _session, ids, _built = soft_delete_env
    target = ids[case]

    assert target in _list_ids(http, collection, id_field)

    assert http.delete(f"{resource}/{target}").status_code == 204

    assert http.get(f"{resource}/{target}").status_code == 404
    assert target not in _list_ids(http, collection, id_field)


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_deleting_twice_returns_404_the_second_time(soft_delete_env, case, collection, resource, id_field):
    """The row is hidden from the delete path too, not only from reads."""
    http, _session, ids, _built = soft_delete_env
    target = ids[case]
    assert http.delete(f"{resource}/{target}").status_code == 204
    assert http.delete(f"{resource}/{target}").status_code == 404


# ---------------------------------------------------------------------------
# The delete is refused while anything visible still references the row.
# ---------------------------------------------------------------------------

# (case, table key in the fixture, child tables that must be named as blockers)
BLOCKED_CASES = [
    (
        "work-orders",
        "WORK_ORDER",
        {"DOWNTIME_ENTRY", "HOLD_ENTRY", "JOB", "PRODUCTION_ENTRY", "QUALITY_ENTRY"},
    ),
    ("quality", "QUALITY_ENTRY", {"DEFECT_DETAIL"}),
]
BLOCKED_IDS = [c[0] for c in BLOCKED_CASES]


@pytest.mark.parametrize("case,table,expected_blockers", BLOCKED_CASES, ids=BLOCKED_IDS)
def test_delete_is_refused_with_409_while_visible_children_reference_it(
    soft_delete_env, case, table, expected_blockers
):
    """Hiding a parent while its children stay readable is incoherent, and
    cascading the hide would remove rows from KPIs nobody asked to delete. The
    decided behaviour is to refuse, loudly and reversibly.
    """
    http, _session, _ids, built = soft_delete_env
    resource = dict((c[0], c[2]) for c in CASES)[case]
    target = getattr(built[table], PK_ATTR[table])

    response = http.delete(f"{resource}/{target}")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert {entry["table"] for entry in detail["blocked_by"]} == expected_blockers
    assert all(entry["count"] >= 1 for entry in detail["blocked_by"])


@pytest.mark.parametrize("case,table,expected_blockers", BLOCKED_CASES, ids=BLOCKED_IDS)
def test_the_refusal_names_the_blockers_rather_than_returning_a_bare_status(
    soft_delete_env, case, table, expected_blockers
):
    """A 409 the caller cannot act on is only marginally better than a 404."""
    http, _session, _ids, built = soft_delete_env
    resource = dict((c[0], c[2]) for c in CASES)[case]
    target = getattr(built[table], PK_ATTR[table])

    detail = http.delete(f"{resource}/{target}").json()["detail"]

    for child_table in expected_blockers:
        assert child_table in detail["message"]
    assert "Delete or reassign them first" in detail["message"]


@pytest.mark.parametrize("case,table,expected_blockers", BLOCKED_CASES, ids=BLOCKED_IDS)
def test_the_row_survives_a_refused_delete(soft_delete_env, case, table, expected_blockers):
    """A refusal must not half-apply: 409 and the row is still fully readable."""
    http, _session, _ids, built = soft_delete_env
    resource = dict((c[0], c[2]) for c in CASES)[case]
    target = getattr(built[table], PK_ATTR[table])

    assert http.delete(f"{resource}/{target}").status_code == 409
    assert http.get(f"{resource}/{target}").status_code == 200


def test_deleting_the_children_first_unblocks_the_parent(soft_delete_env):
    """The refusal is reversible by the caller, which is the whole argument for
    it over a silent cascade: delete what blocks, then the parent goes."""
    http, _session, _ids, built = soft_delete_env
    quality_id = built["QUALITY_ENTRY"].quality_entry_id
    defect_id = built["DEFECT_DETAIL"].defect_detail_id

    assert http.delete(f"/api/quality/{quality_id}").status_code == 409
    assert http.delete(f"/api/defects/{defect_id}").status_code == 204
    assert http.delete(f"/api/quality/{quality_id}").status_code == 204
    assert http.get(f"/api/quality/{quality_id}").status_code == 404

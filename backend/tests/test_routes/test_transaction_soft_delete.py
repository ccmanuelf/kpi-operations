"""The seven transaction DELETE endpoints: 204, then gone from every read.

Before this suite existed all seven returned 404 for *every* id, valid ones
included: the CRUD layer called ``soft_delete()``, which sets ``is_active =
False``, and none of the seven models had that column — so it returned False
and the route raised 404. Six of the seven are wired to frontend delete
buttons, so this was a live user-facing defect, not a testing limitation.

Each case proves the full round trip against a real Alembic-built schema:
DELETE -> 204, GET by id -> 404, and the id absent from the list read.
"""

from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database import get_db
from backend.orm import ClientType
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory

# (case id, collection path, single-resource path prefix, id field in the list rows)
CASES = [
    ("attendance", "/api/attendance", "/api/attendance", "attendance_entry_id"),
    ("defects", "/api/defects", "/api/defects", "defect_detail_id"),
    ("downtime", "/api/downtime", "/api/downtime", "downtime_entry_id"),
    ("holds", "/api/holds", "/api/holds", "hold_entry_id"),
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
    TestDataFactory.reset_counters()

    client = TestDataFactory.create_client(
        session, client_id="SD-CLIENT", client_name="Soft Delete Client", client_type=ClientType.HOURLY_RATE
    )
    supervisor = TestDataFactory.create_user(
        session, user_id="sd-super-1", username="sd_supervisor", role="supervisor", client_id=client.client_id
    )
    employee = TestDataFactory.create_employee(session, client_id=client.client_id, employee_name="SD Worker")
    product = TestDataFactory.create_product(
        session, client_id=client.client_id, product_code="SD-P1", product_name="SD Product"
    )
    shift = TestDataFactory.create_shift(
        session, client_id=client.client_id, shift_name="SD Shift", start_time="06:00:00", end_time="14:00:00"
    )
    session.flush()

    work_order = TestDataFactory.create_work_order(session, client_id=client.client_id)
    production = TestDataFactory.create_production_entry(
        session,
        client_id=client.client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=supervisor.user_id,
        production_date=date.today(),
    )
    hold = TestDataFactory.create_hold_entry(
        session, work_order_id=work_order.work_order_id, client_id=client.client_id, created_by=supervisor.user_id
    )
    downtime = TestDataFactory.create_downtime_entry(
        session,
        client_id=client.client_id,
        reported_by=supervisor.user_id,
        work_order_id=work_order.work_order_id,
        shift_date=datetime.now(tz=timezone.utc),
    )
    attendance = TestDataFactory.create_attendance_entry(
        session, employee_id=employee.employee_id, client_id=client.client_id, shift_id=shift.shift_id
    )
    quality = TestDataFactory.create_quality_entry(
        session,
        work_order_id=work_order.work_order_id,
        client_id=client.client_id,
        inspector_id=supervisor.user_id,
    )
    defect = TestDataFactory.create_defect_detail(
        session, quality_entry_id=quality.quality_entry_id, client_id_fk=client.client_id
    )
    session.commit()

    ids = {
        "attendance": attendance.attendance_entry_id,
        "defects": defect.defect_detail_id,
        "downtime": downtime.downtime_entry_id,
        "holds": hold.hold_entry_id,
        "production": production.production_entry_id,
        "quality": quality.quality_entry_id,
        "work-orders": work_order.work_order_id,
    }

    from backend.auth.jwt import get_current_active_supervisor, get_current_user
    from backend.routes.attendance import router as attendance_router
    from backend.routes.defect import router as defect_router
    from backend.routes.downtime import router as downtime_router
    from backend.routes.holds import router as holds_router
    from backend.routes.production import router as production_router
    from backend.routes.quality import router as quality_router
    from backend.routes.work_orders import router as work_orders_router

    app = FastAPI()
    for router in (
        attendance_router,
        defect_router,
        downtime_router,
        holds_router,
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

    yield TestClient(app), session, ids

    session.close()
    engine.dispose()


def _list_ids(http, collection, id_field):
    response = http.get(collection, params={"limit": 500})
    assert response.status_code == 200, f"{collection} list read failed: {response.status_code} {response.text}"
    return [row[id_field] for row in response.json()]


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_delete_returns_204_for_a_valid_id(soft_delete_env, case, collection, resource, id_field):
    """The defect itself: every one of these answered 404 for a real row."""
    http, _session, ids = soft_delete_env
    response = http.delete(f"{resource}/{ids[case]}")
    assert response.status_code == 204, f"DELETE {resource}/{ids[case]} -> {response.status_code} {response.text}"


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_deleted_row_is_gone_from_by_id_and_list_reads(soft_delete_env, case, collection, resource, id_field):
    """A soft delete that does not hide the row is not a delete."""
    http, _session, ids = soft_delete_env
    target = ids[case]

    assert target in _list_ids(http, collection, id_field)

    assert http.delete(f"{resource}/{target}").status_code == 204

    assert http.get(f"{resource}/{target}").status_code == 404
    assert target not in _list_ids(http, collection, id_field)


@pytest.mark.parametrize("case,collection,resource,id_field", CASES, ids=CASE_IDS)
def test_deleting_twice_returns_404_the_second_time(soft_delete_env, case, collection, resource, id_field):
    """The row is hidden from the delete path too, not only from reads."""
    http, _session, ids = soft_delete_env
    target = ids[case]
    assert http.delete(f"{resource}/{target}").status_code == 204
    assert http.delete(f"{resource}/{target}").status_code == 404

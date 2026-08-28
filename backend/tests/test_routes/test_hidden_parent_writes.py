"""Nothing may attach itself to a soft-deleted row — the write half of the rule.

Review found the 409 blocking rule holds only at delete time, and escaped it in
two API calls::

    DELETE /api/work-orders/WO-0002              -> 204   (parent hidden)
    POST   /api/jobs {work_order_id: "WO-0002"}  -> 201   (child visible)

The database foreign key is satisfied because the parent row physically exists;
it is merely invisible. The KPI-moving symptom came straight back — the new
production entry counted 1 in a plain read and 0 through the analytics inner
join, which is exactly what the whole cascade decision set out to eliminate.

These tests drive the real routers and assert the property by its name: after a
delete, the parent cannot be referenced again, and a plain read and an
inner-join read of the children still agree.
"""

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from backend.database import get_db
from backend.orm.production_entry import ProductionEntry
from backend.orm.work_order import WorkOrder
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.soft_delete_rows import build_transaction_rows


@pytest.fixture(scope="function")
def write_env():
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    built = build_transaction_rows(session)
    supervisor = built["supervisor"]

    from backend.auth.jwt import get_current_active_supervisor, get_current_user
    from backend.routes.downtime import router as downtime_router
    from backend.routes.jobs import router as jobs_router
    from backend.routes.production import router as production_router
    from backend.routes.work_orders import router as work_orders_router

    app = FastAPI()
    for router in (downtime_router, jobs_router, production_router, work_orders_router):
        app.include_router(router)

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: supervisor
    app.dependency_overrides[get_current_active_supervisor] = lambda: supervisor

    yield TestClient(app), session, built
    session.close()
    engine.dispose()


def _job_body(work_order_id, client_id, job_id="NEW-JOB-1"):
    return {
        "job_id": job_id,
        "work_order_id": work_order_id,
        "client_id_fk": client_id,
        "operation_name": "Assembly",
        "operation_code": "ASSY",
        "sequence_number": 9,
        "part_number": "NEW-PART",
        "planned_quantity": 10,
    }


def _production_body(work_order_id, built):
    today = str(date.today())
    return {
        "client_id": built["client"].client_id,
        "product_id": built["product"].product_id,
        "shift_id": built["shift"].shift_id,
        "work_order_id": work_order_id,
        "production_date": today,
        "shift_date": today,
        "units_produced": 100,
        "run_time_hours": "8.0",
        "employees_assigned": 5,
    }


def _delete_the_leaf_work_order(http, built):
    work_order_id = built["WORK_ORDER_leaf"].work_order_id
    assert http.delete(f"/api/work-orders/{work_order_id}").status_code == 204
    assert http.get(f"/api/work-orders/{work_order_id}").status_code == 404
    return work_order_id


def test_a_job_cannot_be_created_against_a_deleted_work_order(write_env):
    """The exact sequence review used to break the invariant."""
    http, _session, built = write_env
    work_order_id = _delete_the_leaf_work_order(http, built)

    response = http.post("/api/jobs", json=_job_body(work_order_id, built["client"].client_id))

    assert response.status_code == 422
    assert response.json()["detail"]["hidden_parents"] == [f"WORK_ORDER '{work_order_id}'"]


def test_a_production_entry_cannot_be_created_against_a_deleted_work_order(write_env):
    http, _session, built = write_env
    work_order_id = _delete_the_leaf_work_order(http, built)

    response = http.post("/api/production", json=_production_body(work_order_id, built))

    assert response.status_code == 422


def test_an_existing_row_cannot_be_repointed_at_a_deleted_work_order(write_env):
    """Updates carry the same risk as creates and are checked the same way.

    Uses downtime because ``DowntimeEventUpdate.work_order_id`` is one of only
    two update schemas in the API that can actually move a row onto a different
    auto-filtered parent (``DefectDetailUpdate.quality_entry_id`` is the other).
    ``ProductionEntryUpdate`` deliberately exposes no ``work_order_id``, so a
    production entry cannot be repointed at all — asserted below so this test
    does not silently start passing for the wrong reason.
    """
    http, _session, built = write_env
    work_order_id = _delete_the_leaf_work_order(http, built)
    downtime_id = built["DOWNTIME_ENTRY"].downtime_entry_id

    response = http.put(f"/api/downtime/{downtime_id}", json={"work_order_id": work_order_id})

    assert response.status_code == 422


def test_a_production_entry_cannot_be_repointed_because_the_schema_forbids_it(write_env):
    """The reason the test above does not use production. If this ever starts
    failing, ProductionEntryUpdate grew a work_order_id and the update path
    above should cover it too."""
    from backend.schemas.production import ProductionEntryUpdate

    assert "work_order_id" not in ProductionEntryUpdate.model_fields


def test_creating_against_a_visible_work_order_still_works(write_env):
    """Non-vacuity: the guard must reject the deleted parent, not every parent."""
    http, _session, built = write_env
    _delete_the_leaf_work_order(http, built)

    response = http.post("/api/jobs", json=_job_body(built["WORK_ORDER"].work_order_id, built["client"].client_id))

    assert response.status_code == 201


def test_the_plain_read_and_the_analytics_join_cannot_be_made_to_disagree(write_env):
    """The symptom itself, asserted by its name rather than by proxy.

    Review's sequence produced a production entry that a plain read counted and
    an inner join on its parent did not. The counts are compared before, after
    the parent is deleted, and after the rejected attempt to attach a new child
    to it.
    """
    http, session, built = write_env

    def plain():
        return session.query(func.count(ProductionEntry.production_entry_id)).scalar()

    def joined():
        return (
            session.query(func.count(ProductionEntry.production_entry_id))
            .join(WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id)
            .scalar()
        )

    assert plain() == joined()

    work_order_id = _delete_the_leaf_work_order(http, built)
    session.expire_all()
    assert plain() == joined()

    assert http.post("/api/production", json=_production_body(work_order_id, built)).status_code == 422
    session.rollback()
    session.expire_all()
    assert plain() == joined()

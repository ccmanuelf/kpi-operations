"""The transition route must not persist a change it then fails to report.

`POST /api/workflow/work-orders/{work_order_id}/transition` used to
`db.commit()` and then return two raw ORM instances under
`response_model=Dict`. Pydantic cannot serialize an ORM object that way, so
FastAPI raised PydanticSerializationError AFTER the commit: 500 to the caller,
work order already moved.

Declaring `WorkOrderTransitionResult` fixes the serialization. It does NOT by
itself close the ordering hazard -- FastAPI validates `response_model` after
the endpoint returns, so ANY future mismatch (a NULL in a non-optional field,
an enum that stops coercing) reproduces commit-then-500. The handler therefore
validates the payload itself BEFORE committing.

These live in the contract suite rather than beside the route's unit tests
because both need the seeded database and the real ASGI path -- which is where
the bug lived, and what a CRUD-level test cannot reach.
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.orm.work_order import WorkOrder
from backend.schemas.work_order import WorkOrderResponse
from backend.tests.contract.conftest import _Harness

WORK_ORDER = "DEMO-HOURLY-WO-0001"


def _status(engine: Any, work_order_id: str) -> Any:
    with engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT status FROM WORK_ORDER WHERE work_order_id = :w"), {"w": work_order_id}
        ).scalar()


def test_a_failed_serialization_leaves_the_work_order_unmoved(harness: _Harness) -> None:
    """The ordering guarantee, forced rather than hoped for.

    Makes the response model reject the payload, then requires BOTH that the
    request failed and that nothing was persisted. Asserting only the status
    code would have passed against the original bug, which also answered 500 --
    while having moved the work order. The two together are the invariant.
    """
    from backend.schemas import workflow as workflow_schemas

    harness.restore()
    before = _status(harness.engine, WORK_ORDER)

    original = workflow_schemas.WorkOrderTransitionResult.model_validate

    def _refuse(cls: Any, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("simulated response-model mismatch")

    setattr(workflow_schemas.WorkOrderTransitionResult, "model_validate", classmethod(_refuse))
    try:
        response = harness.client.post(
            f"/api/workflow/work-orders/{WORK_ORDER}/transition", json={"to_status": "CLOSED"}
        )
    finally:
        setattr(workflow_schemas.WorkOrderTransitionResult, "model_validate", original)

    after = _status(harness.engine, WORK_ORDER)

    assert response.status_code == 500, response.text[:200]
    assert after == before, (
        f"the request failed but the work order moved {before!r} -> {after!r}: the commit is "
        "running before the response is known to be serializable, which is the original defect"
    )


def test_the_route_still_succeeds_when_the_model_is_not_sabotaged(harness: _Harness) -> None:
    """Guards the guard above: with the model working, the SAME request must
    succeed and persist. Otherwise the previous test would pass against a route
    that simply never transitions anything."""
    harness.restore()

    response = harness.client.post(f"/api/workflow/work-orders/{WORK_ORDER}/transition", json={"to_status": "CLOSED"})

    assert response.status_code == 200, response.text[:200]
    assert set(response.json()) == {"work_order", "transition", "success"}
    assert _status(harness.engine, WORK_ORDER) == "CLOSED"


def test_every_seeded_work_order_survives_the_response_model(harness: _Harness) -> None:
    """The composed model is only safe if REAL rows validate, not just the
    factory-built one the route's unit tests construct.

    A seeded row carrying a NULL in a field the schema requires would 500 the
    route for that work order alone -- invisible to a test that builds its own.
    """
    failures = []
    with Session(harness.engine) as session:
        work_orders = session.query(WorkOrder).all()
        for work_order in work_orders:
            try:
                WorkOrderResponse.model_validate(work_order).model_dump_json()
            except Exception as exc:  # noqa: BLE001 -- the failure itself is the finding
                failures.append(f"{work_order.work_order_id}: {type(exc).__name__}: {exc}")

    assert work_orders, "no seeded work orders -- this test would pass on nothing"
    assert not failures, failures

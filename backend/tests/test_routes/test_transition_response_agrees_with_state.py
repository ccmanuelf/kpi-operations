"""`POST /api/workflow/work-orders/{id}/transition` must not commit and then fail.

The route was `response_model=Dict` over a payload holding two raw ORM
instances:

    {"work_order": <WorkOrder>, "transition": <WorkflowTransition>, "success": True}

Pydantic cannot serialize an ORM object under a bare `Dict`, so FastAPI raised

    PydanticSerializationError: Unable to serialize unknown type:
    <class 'backend.orm.work_order.WorkOrder'>

*after* the handler's `db.commit()`. Every successful transition answered 500
while the work order had already moved -- the caller was told the operation
failed, and it had not. Verified against the seeded database before the fix:
status 500, work order status CLOSED, committed True.

FastAPI serializes after the endpoint returns, so a response error is
post-commit by construction. The defence is therefore a correct model, not an
ordering change -- and a test that the status code and the persisted state
cannot disagree.
"""

import pytest

from backend.crud.workflow.operations import transition_work_order
from backend.orm.work_order import WorkOrder
from backend.schemas.workflow import WorkOrderTransitionResult
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture
def seeded(db_session):
    client = TestDataFactory.create_client(db_session, client_id="TRN-C1", client_name="Transition Client")
    user = TestDataFactory.create_user(db_session, user_id="TRN-U1", role="admin")
    work_order = TestDataFactory.create_work_order(db_session, work_order_id="TRN-WO-1", client_id=client.client_id)
    db_session.commit()
    return {"client": client, "user": user, "work_order": work_order}


def test_the_result_is_serializable_by_the_declared_model(db_session, seeded):
    """The regression, at the layer that produced it.

    `transition_work_order` returns ORM instances. Validating them through
    the declared response model is exactly what FastAPI does on the way out,
    so this fails with the same PydanticSerializationError the route did if
    the model is ever loosened back to `Dict` -- without needing the ASGI
    stack to reproduce it.
    """
    result = transition_work_order(
        db=db_session,
        work_order_id=seeded["work_order"].work_order_id,
        to_status="RELEASED",
        current_user=seeded["user"],
    )
    db_session.commit()

    validated = WorkOrderTransitionResult.model_validate(result)

    assert validated.success is True
    assert validated.work_order.work_order_id == seeded["work_order"].work_order_id
    assert validated.transition.to_status == "RELEASED"
    # The whole failure was at JSON encoding, not at field access.
    assert validated.model_dump_json()


def test_a_committed_transition_is_never_reported_as_a_failure(db_session, seeded):
    """The invariant the bug broke: persisted state and reported outcome agree.

    Asserted as a conjunction rather than two separate checks, because the
    bug satisfied each half on its own -- the write really happened, and the
    route really answered. Only together do they catch it.
    """
    work_order_id = seeded["work_order"].work_order_id

    result = transition_work_order(
        db=db_session, work_order_id=work_order_id, to_status="RELEASED", current_user=seeded["user"]
    )
    db_session.commit()

    reported_success = WorkOrderTransitionResult.model_validate(result).success
    persisted = db_session.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first().status
    moved = str(persisted).endswith("RELEASED")

    assert reported_success is moved, (
        f"reported success={reported_success} but persisted status={persisted!r}: "
        "the response and the database disagree, which is the defect this route had"
    )


def test_the_route_does_not_declare_a_bare_dict_response():
    """Structural, and the reason the two tests above stay meaningful.

    They validate through `WorkOrderTransitionResult` explicitly. If the route
    goes back to `response_model=Dict` they would both still pass while the
    endpoint 500s again, so what the ROUTE declares is pinned separately.
    """
    from backend.main import app
    from backend.tests.contract.param_resolution import route_index

    # `route_index`, not a scan of `app.routes`: routers are nested behind
    # _IncludedRouter, so a flat iteration finds nothing and the assertion
    # would pass on an empty list -- the vacuous-gate failure this repo has
    # hit before.
    route = route_index(app).get("POST /api/workflow/work-orders/{work_order_id}/transition")
    assert route is not None, "route not registered -- enumeration broke, which is itself a finding"

    model = getattr(route, "response_model", None)
    assert model is WorkOrderTransitionResult, f"declares {model!r}, which cannot serialize ORM instances"

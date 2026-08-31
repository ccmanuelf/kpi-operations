"""Gates for `body_specs.BODY_REGISTRY`.

The bodies themselves are declared there. What is asserted here is that the
registry and the application agree in both directions, and that the shapes the
bodies unlock are real rather than technically-2xx.
"""

import json
from pathlib import Path
from typing import Dict, List

from backend.tests.contract.body_specs import BODY_REGISTRY
from backend.tests.contract.conftest import _Harness
from backend.tests.contract.param_resolution import route_index
from backend.tests.contract.query_specs import DEFERRED_TO_WRITE_CAPTURE
from backend.tests.contract.test_query_resolution import _is_required

GOLDEN = Path(__file__).parent / "golden" / "api_shapes.json"

#: Registered routes whose successful answer is a byte stream, not JSON. Their
#: golden entry is `<non-json>`, and that is a SUCCESS -- it is what the route
#: returns. Distinguished from a `<status:...>` placeholder, which means the
#: harness never got a real answer at all. Named rather than pattern-matched,
#: so a route that stops streaming fails instead of being waved through.
STREAMS_A_BODY = frozenset({"POST /api/qr/generate/image"})


def _golden() -> Dict[str, List[str]]:
    data: Dict[str, List[str]] = json.loads(GOLDEN.read_text())
    return data


def test_every_registered_body_belongs_to_a_route_that_wants_one() -> None:
    """An entry for a route needing no body would be sent anyway, and FastAPI
    would ignore it -- a spec that reads as load-bearing while doing nothing."""
    from backend.main import app

    index = route_index(app)
    pointless = {}
    for route_key in BODY_REGISTRY:
        route = index.get(route_key)
        assert route is not None, f"{route_key} is registered here but not on the app"
        if not any(_is_required(param) for param in route.dependant.body_params):
            pointless[route_key] = "route requires no body"

    assert not pointless, pointless


def test_no_route_needing_a_body_is_left_without_one_or_a_declared_reason() -> None:
    """The other direction. A route requiring a body is either given one here,
    or declared deferred -- never silently left recording its 422.

    This is the gate that would have caught the whole class earlier: eleven
    routes sat at `<status:422>` for months because nothing asserted that a
    422 needs an owner.
    """
    from backend.main import app

    index = route_index(app)
    unowned = {}
    for route_key, shape in sorted(_golden().items()):
        route = index.get(route_key)
        if route is None:
            continue
        if not any(_is_required(param) for param in route.dependant.body_params):
            continue
        if route_key in BODY_REGISTRY or route_key in DEFERRED_TO_WRITE_CAPTURE:
            continue
        unowned[route_key] = shape[0] if shape else None

    assert not unowned, (
        "routes requiring a request body with neither a BODY_REGISTRY entry nor a deferral: " f"{unowned}"
    )


def test_the_bodies_produced_real_shapes_not_merely_2xx(captured_shapes: Dict[str, List[str]]) -> None:
    """A status code is not evidence for these routes.

    Every registered route must have captured named fields. A `<status:...>`
    entry means the body was wrong; an empty capture means the route answered
    with nothing to describe. Both are failures that a 2xx check would miss.
    """
    bad = {}
    for route_key in BODY_REGISTRY:
        shape = captured_shapes.get(route_key)
        if route_key in STREAMS_A_BODY:
            # A stream's honest answer IS `<non-json>`; anything else means the
            # body was wrong or the route stopped streaming.
            if shape != ["<non-json>"]:
                bad[route_key] = shape
            continue
        if not shape or str(shape[0]).startswith("<"):
            bad[route_key] = shape

    assert not bad, f"registered a body but captured no real shape: {bad}"


def test_the_streaming_declarations_still_describe_streaming_routes(
    captured_shapes: Dict[str, List[str]],
) -> None:
    """The other side of `STREAMS_A_BODY`.

    Declaring a route as streaming exempts it from the real-shape assertion
    above, so a stale entry would hide a route that quietly started returning
    JSON -- and its fields would go uncaptured while the gate stayed green.
    """
    not_streaming = {
        route: captured_shapes.get(route) for route in STREAMS_A_BODY if captured_shapes.get(route) != ["<non-json>"]
    }

    assert not not_streaming, (
        f"declared as streaming but no longer answers <non-json> -- capture the real shape "
        f"and drop the declaration: {not_streaming}"
    )


def test_the_known_empty_list_gap_is_still_exactly_one_field(captured_shapes: Dict[str, List[str]]) -> None:
    """`allocation_suggestions` records as a BARE key, not `allocation_suggestions[]`.

    The seeder writes no floating-pool employees (`is_floating_pool` is false
    everywhere and FLOATING_POOL has no rows), so the optimiser returns an
    empty list -- and `shape_of` records an empty list as a leaf, capturing
    nothing of the element shape. The route's own contract is therefore
    partially unknown.

    Asserted rather than ignored, in both directions: if the seeder gains
    floating-pool employees this fails and the entry can be promoted; if
    another field starts collapsing the same way, it fails too.
    """
    shape = captured_shapes["POST /api/floating-pool/simulation/optimize-allocation"]

    assert "allocation_suggestions" in shape, shape
    assert "allocation_suggestions[]" not in shape, (
        "the optimiser now returns allocations -- the empty-list gap is closed, so capture the "
        "element shape and delete this test"
    )
    collapsed = [field for field in shape if not field.endswith("[]") and field == "allocation_suggestions"]
    assert collapsed == ["allocation_suggestions"], shape


def test_kpi_thresholds_wrote_a_scoped_row_not_a_global_one(harness: _Harness) -> None:
    """`PUT /api/kpi-thresholds` with a null client_id writes a GLOBAL threshold,
    which is exactly what `GET /api/kpi-thresholds` reads -- its golden entry
    would silently gain fields from this route's capture.

    The body therefore always carries a client_id, and this pins that: the
    capture must leave no client-less row behind.
    """
    import sqlalchemy as sa

    from backend.tests.contract.param_resolution import Resolver

    harness.restore()
    body = BODY_REGISTRY["PUT /api/kpi-thresholds"].build(Resolver(engine=harness.engine))
    assert body["client_id"], "the body must scope its threshold to a client"

    harness.client.put("/api/kpi-thresholds", json=body)
    with harness.engine.connect() as connection:
        global_rows = connection.execute(sa.text("SELECT COUNT(*) FROM KPI_THRESHOLD WHERE client_id IS NULL")).scalar()

    assert global_rows == 0, "the capture wrote a global threshold row, which GET /api/kpi-thresholds reads"


def test_the_isolated_phase_is_order_independent(harness: _Harness) -> None:
    """Reversing the isolated phase must not change a single shape.

    Bodies made this question sharp. `PUT /api/workflow/config/{client_id}`
    and `POST .../apply-template` write the SAME CLIENT_CONFIG row, and that
    row drives the workflow state machine for allowed-transitions, validate
    and transition. The transition body drives DEMO-HOURLY-WO-0001 to CLOSED,
    a terminal status several other golden routes read. If `restore()` per
    request were not enough, the capture would depend on the order routes
    happen to be planned in -- and the golden master would look stable while
    resting on an accident.

    Stronger than `test_the_isolated_phase_restores_between_mutations`, which
    drives ONE route twice: that proves a route does not contaminate itself.
    This proves no route contaminates any other, which is what writing bodies
    put at risk. Measured: 45 isolated routes, 0 differences.
    """
    from backend.tests.contract.capture import capture_isolated

    plan = harness.plan
    forward = capture_isolated(harness.client, plan.isolated, plan.urls, harness.restore)
    reverse = capture_isolated(harness.client, list(reversed(plan.isolated)), plan.urls, harness.restore)

    divergent = {
        route: {"forward": forward.get(route), "reversed": reverse.get(route)}
        for route in set(forward) | set(reverse)
        if forward.get(route) != reverse.get(route)
    }

    assert plan.isolated, "no isolated routes -- this test would pass on nothing"
    assert not divergent, f"shapes depend on capture order: {divergent}"


def test_the_attendance_body_pairs_an_employee_with_their_own_client(harness: _Harness) -> None:
    """The mismatch this route would NOT report.

    `mark-all-present` answers 404 when its client_id and shift_id disagree, so
    that pairing defends itself. `bulk_create_attendance_records` checks
    nothing of the kind, and the harness engine runs without
    `PRAGMA foreign_keys=ON`, so a body naming another client's employee writes
    a cross-tenant attendance row and still answers 201. The capture would be a
    clean-looking record of a contract violation.

    Asserted against the database rather than against the spec's SQL, so
    rewriting that SQL cannot make this pass by agreeing with itself.
    """
    import sqlalchemy as sa

    from backend.tests.contract.param_resolution import Resolver

    body = BODY_REGISTRY["POST /api/attendance/bulk"].build(Resolver(engine=harness.engine))
    row = body[0]

    with harness.engine.connect() as connection:
        assigned = connection.execute(
            sa.text("SELECT client_id_assigned FROM EMPLOYEE WHERE employee_id = :e"),
            {"e": row["employee_id"]},
        ).scalar()

    assert assigned, f"employee {row['employee_id']} has no client assignment at all"
    clients = {part.strip() for part in str(assigned).split(",")}
    assert row["client_id"] in clients, (
        f"body pairs client {row['client_id']!r} with employee {row['employee_id']}, who belongs "
        f"to {assigned!r} -- the route would write it anyway and answer 201"
    )


def test_the_attendance_capture_exercised_both_branches(harness: _Harness) -> None:
    """One row succeeding and one failing, in a single 201.

    The route catches every per-row exception and answers 201 unconditionally,
    so 2xx is not evidence it did anything. And an all-valid body leaves
    `errors` an EMPTY list, which records as a bare leaf -- the error shape
    would go uncaptured while the entry looked complete.

    Checked on the live response rather than on the golden entry, because the
    golden entry is what this is defending: if the second row ever stops
    failing, `errors[].index` and `errors[].error` vanish from the capture and
    this says why.
    """
    from backend.tests.contract.param_resolution import Resolver

    harness.restore()
    body = BODY_REGISTRY["POST /api/attendance/bulk"].build(Resolver(engine=harness.engine))
    payload = harness.client.post("/api/attendance/bulk", json=body).json()

    assert payload["successful"] >= 1, f"no row was created, so `created_ids[]` is empty: {payload}"
    assert payload["failed"] >= 1, (
        "no row failed, so `errors` comes back empty and its element shape goes uncaptured: " f"{payload}"
    )
    assert payload["errors"][0]["index"] == 1, payload["errors"]
    # The REASON, not just that something failed. Row 2 differs from row 1
    # only by `allocations`, so a unique constraint on (employee, date) -- or
    # any other incidental rejection -- would satisfy every assertion above
    # while the captured `errors[].error` described something else entirely.
    # Measured: a plain duplicate of row 1 gives failed=0, so no such
    # constraint exists today and the allocations rejection is the only thing
    # making this body work.
    assert "allocations" in payload["errors"][0]["error"], (
        "row 2 failed for a reason other than the allocations rejection this body relies on: "
        f"{payload['errors'][0]['error']!r}"
    )


def test_every_payload_key_matches_what_the_route_consumes() -> None:
    """A spec must not send a route the wrong kind of request.

    `payload_key` is typed `Literal["json", "data", "files"]`, which stops a
    typo, but not a valid key aimed at the wrong route -- a JSON body sent as
    `files`, or a multipart route sent `json`, both of which 422 and record
    that 422 as the route's contract.

    FastAPI distinguishes the two structurally: an `UploadFile` parameter
    lands in `dependant.body_params` with a form-ish field type, while a
    Pydantic model body does not. So the declaration is checked against the
    route rather than trusted.
    """
    from backend.main import app

    index = route_index(app)
    wrong = {}
    for route_key, spec in BODY_REGISTRY.items():
        route = index[route_key]
        takes_upload = any(
            "UploadFile" in str(getattr(param, "annotation", "") or getattr(param.field_info, "annotation", ""))
            for param in route.dependant.body_params
        )
        expected = "files" if takes_upload else "json"
        if spec.payload_key != expected:
            wrong[route_key] = {"declared": spec.payload_key, "route wants": expected}

    assert not wrong, f"payload_key disagrees with the route's own body params: {wrong}"

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
        if not shape or str(shape[0]).startswith("<"):
            bad[route_key] = shape

    assert not bad, f"registered a body but captured no real shape: {bad}"


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

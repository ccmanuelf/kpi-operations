def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """71 routes still needing a response model, after Batch R2 converts 7
       of the prior 78 across `/api/quality` (6 of 8) and `/api/capacity`
       (1 of 2) (`backend/schemas/quality_contracts.py` +
       `capacity_contracts.py`). 78 - 7 = 71, mirrored by `ALLOWLIST`
       shrinking by the same 7 entries. `/api/pivot`'s 2 routes and 6 more
       across the batch's 3 areas need query params or a request body and
       stay allowlisted for Task 16's write-capture harness.

       78 itself is Batch R3's count: 90 - 12 across `/api/floating-pool`
       (4), `/api/work-orders` (3 GET + 1 POST), `/api/attendance` (2),
       `/api/alerts` (2) (`backend/schemas/floor_contracts.py` +
       `workorder_contracts.py`).

       90 itself is Batch R4's count: 108 - 18 across `/api/cache`,
       `/api/kpi-thresholds`, `/api/predictions`, `/api/data-completeness`,
       `/api/my-shift`, `/api/shifts`, `/api/plan-vs-actual`
       (`backend/schemas/ops_contracts.py`).

       90 itself is Batch R4's count: 108 - 18 across `/api/cache`,
       `/api/kpi-thresholds`, `/api/predictions`, `/api/data-completeness`,
       `/api/my-shift`, `/api/shifts`, `/api/plan-vs-actual`
       (`backend/schemas/ops_contracts.py`).

       This measurement is also where `flatten_api_routes` (capture.py) earned
       its second iteration: FastAPI's `_IncludedRouter` wrapper only bakes a
       route's full prefix into `.path` for a SINGLE include level. A router
       included without its own prefix and then included again one level up
       (`quality_router.include_router(pareto_router)`, `pareto_router` itself
       unprefixed) leaves the underlying route's `.path` as the router-local
       fragment (`/kpi/by-product`), not the effective `/api/quality/kpi/
       by-product` -- a naive recursive `original_router.routes` walk (the
       first version of this fix) silently missed such routes entirely rather
       than mis-measuring by one, undercounting this test's own assertion by
       16 before `effective_route_contexts()` (the mechanism FastAPI itself
       exposes for exactly this, already used by `test_openapi_surface.py`)
       replaced it.

       108 itself was re-measured 2026-08-25 after Task 10 and its review
       follow-up. Task 10 found its 20-route
       area was mostly file downloads, not JSON: 17 `/api/export` +
       `/api/reports/*/{pdf,excel}` routes were annotated `-> Any` while
       actually returning `StreamingResponse`, so they were never loose in
       substance, only in declaration. Fixing the annotation and scoping
       them out of the ratchet via `response_scope.routes_needing_a_response_model`
       (gated two-sided in test_response_scope.py) drops 17; converting the
       one genuine JSON route, GET /api/reports/available, drops 1 more.
       131 - 17 - 1 = 113.

       The review follow-up found /api/qr's 5 routes (employee/product/
       work-order/job/generate image, one of them a POST) are the SAME
       class as those 17 -- all `-> Response`, already `response_model=None`
       -- and appear in NO Task 11-14 grouping, so leaving them in ALLOWLIST
       would make them a permanent, unclaimed exception, exactly what the
       scope rule exists to avoid. Folded into OUT_OF_SCOPE_ROUTES the same
       way. 113 - 5 = 108, the corrected target.

       131 itself came from Task 9 converting the 9 `/api/workflow` GET
       routes (templates, config/{client_id}, analytics/{client_id}/
       average-times, analytics/{client_id}/stage-durations,
       statistics/{client_id}/status-distribution, statistics/{client_id}/
       transitions, work-orders/{id}/allowed-transitions, work-orders/{id}/
       elapsed-time, work-orders/{id}/transition-times) to typed response
       models, shrinking a prior 140 (itself shrunk from 155 by Task 7's
       fifteen remaining `/api/kpi/*` routes, and from 164 by Task 6's nine
       trend routes).

       The original 160 came from a string-prefix predicate that could not see through
       typing.List[...] wrappers and silently dropped four live routes. See is_loose.
    The count is pinned so a
       route that stops being enumerated — a decorator change, a router rename —
       fails here instead of quietly leaving the refactor's scope."""
    from backend.main import app
    from backend.tests.contract.response_scope import routes_needing_a_response_model

    routes = routes_needing_a_response_model(app)

    assert len(routes) == 71
    methods = {m for m, _, _ in routes}
    assert methods == {"GET", "POST", "PUT", "DELETE"}


def test_is_loose_sees_through_typing_wrappers():
    """The predicate must inspect structure, not the repr.

    A string-prefix test on `str(model)` cannot see through a wrapper, because
    wrapping moves the marker off position 0. `typing.List[dict]` then reads as
    TYPED and the route leaves the refactor's scope permanently -- it is absent
    from the work list AND from the ratchet allowlist, so nothing ever flags it
    again. Four live routes were lost that way: GET /api/products, GET /api/shifts,
    GET /api/shifts/active, and the workflow transition-times route.

    `typing.List[...]` is the dominant annotation style in this codebase, so the
    blind spot pointed straight at the common case.
    """
    from typing import Any, Dict, List, Optional

    from pydantic import BaseModel

    from backend.tests.contract.capture import is_loose

    class Modelled(BaseModel):
        x: int

    # wrapped-but-loose: the wrapper constrains the container, not the values
    assert is_loose(List[dict]) is True
    assert is_loose(Optional[dict]) is True
    assert is_loose(List[Dict]) is True
    assert is_loose(Dict[str, Any]) is True

    # a RootModel is a wrapper too, and get_origin() sees only a plain class --
    # dormant today, but this refactor is precisely when someone might reach for
    # one while "fixing" a loose route, and it would escape the ratchet as well
    from pydantic import RootModel

    class LooseRoot(RootModel[Dict[str, Any]]):
        pass

    assert is_loose(LooseRoot) is True

    # wrapped-and-typed: these must NOT be swept into the refactor's scope
    assert is_loose(List[Modelled]) is False
    assert is_loose(Optional[Modelled]) is False
    assert is_loose(Dict[str, int]) is False

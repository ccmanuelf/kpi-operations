def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """108 routes still needing a response model, re-measured 2026-08-25
       after Task 10 and its review follow-up. Task 10 found its 20-route
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

    assert len(routes) == 108
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

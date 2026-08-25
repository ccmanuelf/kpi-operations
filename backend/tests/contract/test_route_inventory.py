def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """164 loose routes, re-measured 2026-08-25 after the predicate was fixed.

       The original 160 came from a string-prefix predicate that could not see through
       typing.List[...] wrappers and silently dropped four live routes. See is_loose.
    The count is pinned so a
       route that stops being enumerated — a decorator change, a router rename —
       fails here instead of quietly leaving the refactor's scope."""
    from backend.main import app
    from backend.tests.contract.capture import loose_routes

    routes = loose_routes(app)

    assert len(routes) == 164
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

    # wrapped-and-typed: these must NOT be swept into the refactor's scope
    assert is_loose(List[Modelled]) is False
    assert is_loose(Optional[Modelled]) is False
    assert is_loose(Dict[str, int]) is False

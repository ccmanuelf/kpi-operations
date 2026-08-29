def test_capture_records_nested_keys_not_values():
    """The harness records SHAPE. Two responses differing only in values must
    produce an identical record, or the golden master churns on every reseed."""
    from backend.tests.contract.capture import shape_of

    a = {"total": 5, "nested": {"x": 1.5}, "rows": [{"id": "A", "v": 2}]}
    b = {"total": 9, "nested": {"x": 9.9}, "rows": [{"id": "B", "v": 7}]}

    assert shape_of(a) == shape_of(b)
    assert shape_of(a) == ["nested.x", "rows[].id", "rows[].v", "total"]


def test_an_error_response_is_recorded_as_a_status_not_a_shape():
    """A 404's body has keys too. Recording them as the route's shape would
    freeze `{"detail"}` into the golden master and pass forever after."""
    from backend.tests.contract.capture import capture_all

    class _Stub:
        def request(self, method, path, **kw):
            class R:
                status_code = 404

                def json(self):
                    return {"detail": "Not Found"}

            return R()

    result = capture_all(_Stub(), [("GET", "/api/missing", {})])
    assert result == {"GET /api/missing": ["<status:404>"]}


def test_a_value_keyed_map_records_one_stable_entry_not_its_data():
    """/api/alerts/dashboard keys by_severity on alert data, so the SAME endpoint
    with UNCHANGED code recorded a different shape depending on which severities
    happened to be active -- and a severity with zero active alerts looked
    exactly like a dropped field. The harness must not manufacture the signal it
    exists to give."""
    from backend.tests.contract.capture import shape_of

    busy = {"total": 3, "by_severity": {"critical": 2, "high": 1}}
    quiet = {"total": 5, "by_severity": {"high": 5}}

    assert shape_of(busy) == ["by_severity.*", "total"]
    assert shape_of(quiet) == ["by_severity.*", "total"]


def test_map_fields_are_exactly_the_known_five():
    """MAP_FIELDS cannot be derived -- nothing distinguishes {"critical": 2} from
    an object with a "critical" attribute -- so it is listed, and pinned here so
    that adding one is a deliberate act rather than a quiet widening of what the
    golden master stops watching."""
    from backend.tests.contract.capture import MAP_FIELDS

    assert MAP_FIELDS == frozenset(
        {"by_severity", "by_category", "weekly_demand", "pieces_by_product", "fulfillment_by_product"}
    )


def test_flatten_api_routes_changes_the_observed_route_set():
    """Pins the fact `flatten_api_routes` exists to close, so it stops being
    prose someone has to take on faith: today, on this repo's pinned
    fastapi (`backend/requirements.lock`), `app.routes` is NOT a flat list
    of `APIRoute` objects -- `APIRouter.include_router` unconditionally
    wraps each include in an `_IncludedRouter`, so a naive `isinstance
    (route, APIRoute)` walk sees zero of the ~470 `/api` routes.

    Both halves are exact, per the repo's "one exact expected value, never
    a bound" rule -- a first version used `< 5`/`> 400`, which a PARTIAL
    regression (a handful of routes losing coverage, the realistic failure
    mode since includes are per-router, not all-or-nothing) would pass
    right through.

    Half 1 is `== []`: the wrapping this helper routes around is real
    today, not hypothetical -- a naive walk finds NONE of the app's real
    `/api` routes. This is what stops the test passing vacuously if a
    future FastAPI version reverts to flattening includes at
    `include_router()` time (the mechanism `flatten_api_routes` exists to
    route around would then have nothing to route around, and this half
    would fail LOUDLY naming that -- the exact signal PR #110/commit
    c516ed9's regression lacked).

    Half 2 compares two INDEPENDENTLY computed sets for exact equality
    rather than pinning a hardcoded count: `flatten_api_routes`'s own
    `/api` (method, path) pairs against the same pairs read off
    `app.openapi()`'s `paths` -- FastAPI's own, separately-implemented
    route-surface computation, used for `/docs` and `/openapi.json` today.
    A hardcoded count would churn every time an UNRELATED route is added
    or removed anywhere in the app; this doesn't, because both sides move
    together, and it still fails if `flatten_api_routes` itself diverges
    from what FastAPI considers the real surface -- confirmed non-vacuous:
    `test_route_inventory.py`'s golden-master-derived 164 keys are a
    proper subset of both sets today, so an accidentally-empty `openapi()`
    response could not pass this by both sides coincidentally going empty.
    """
    from fastapi.routing import APIRoute

    from backend.main import app
    from backend.tests.contract.capture import flatten_api_routes

    naive = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")]
    assert naive == []

    via_flatten = {
        (method, route.path)
        for route in flatten_api_routes(app.routes)
        if route.path.startswith("/api")
        for method in set(route.methods) - {"HEAD", "OPTIONS"}
    }
    via_openapi = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api")
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}
    }
    assert via_flatten == via_openapi

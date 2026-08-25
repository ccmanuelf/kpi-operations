def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """160 loose routes were measured on 2026-08-25. The count is pinned so a
    route that stops being enumerated — a decorator change, a router rename —
    fails here instead of quietly leaving the refactor's scope."""
    from backend.main import app
    from backend.tests.contract.capture import loose_routes

    routes = loose_routes(app)

    assert len(routes) == 160
    methods = {m for m, _, _ in routes}
    assert methods == {"GET", "POST", "PUT", "DELETE"}

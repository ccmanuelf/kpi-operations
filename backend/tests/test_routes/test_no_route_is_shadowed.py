"""A literal path must be registered before its parameterised sibling.

FastAPI matches routes in REGISTRATION order. If `/{thing_id}` is declared
first, a sibling literal path is captured as an id and never reaches its own
handler. Two routes were in that state:

    GET /api/holds/pending-approvals   -> 404 {"detail": "WIP hold not found"}
        `hold_id` is a STRING, so the shadow matched, looked up a hold named
        "pending-approvals", found none, and answered a misleading 404. A
        caller asking for a list was told a hold did not exist.

    DELETE /api/filters/history        -> 422 int_parsing on filter_id
        `filter_id` is an int, so the parse failed and at least the error
        named the real cause.

Both were dead over HTTP. Unit tests calling their CRUD directly would pass
while no client could reach them, which is why this is asserted at the routing
layer instead.

The property is what is pinned, not the two routes. A test asserting 200 and
204 on them would pass again the moment somebody adds a third literal path
after a `/{param}` tomorrow.
"""

from typing import List, Tuple

from backend.main import app
from backend.tests.contract.capture import flatten_api_routes


def _registration_order() -> List[Tuple[str, str]]:
    """Every (method, path) under /api, in the order FastAPI will match them.

    `flatten_api_routes`, not a walk of `app.routes`: routers nest behind
    `_IncludedRouter`, and a naive walk sees NINE pairs instead of 460. The
    first version of this scan did exactly that and reported zero shadowed
    routes while two were provably broken.
    """
    ordered: List[Tuple[str, str]] = []
    for route in flatten_api_routes(app.routes):
        path = str(route.path)
        if not path.startswith("/api"):
            continue
        for method in sorted(set(route.methods or ()) - {"HEAD", "OPTIONS"}):
            ordered.append((method, path))
    return ordered


def _shadowed() -> List[Tuple[str, str, str]]:
    seen: dict = {}
    found: List[Tuple[str, str, str]] = []
    for index, (method, path) in enumerate(_registration_order()):
        segments = path.split("/")
        parent, last = "/".join(segments[:-1]), segments[-1]

        # A TRAILING SLASH is not a literal segment. `/api/alerts/config/` and
        # `/api/client-config/` are registered with one, which makes each a
        # distinct path that `/{param}` does not capture -- both answer 200.
        # Normalising the slash away flagged them as victims (my first scan
        # did, twice), and treating the empty segment as a literal flags them
        # again. Verified by request, not by reasoning.
        if last == "":
            continue

        if last.startswith("{") and last.endswith("}"):
            seen.setdefault((method, parent), (index, path))
        elif (method, parent) in seen:
            earlier_index, earlier_path = seen[(method, parent)]
            if earlier_index < index:
                found.append((method, path, earlier_path))
    return found


def test_no_literal_path_is_registered_after_its_parameterised_sibling() -> None:
    assert not _shadowed(), (
        "these literal paths are declared AFTER a same-method /{param} sibling, so FastAPI "
        "captures them as ids and their handlers are unreachable — move each declaration above "
        f"its sibling: {_shadowed()}"
    )


def test_the_scan_actually_sees_the_whole_route_table() -> None:
    """Guards the guard, and it is not hypothetical.

    The first version of this scan walked `app.routes` directly, saw 9 pairs,
    and reported a clean bill of health for a codebase with two broken routes.
    A shadowing check over almost no routes is worse than none, because it
    reads as evidence.
    """
    ordered = _registration_order()

    assert len(ordered) > 400, f"only {len(ordered)} routes enumerated — the walk is not descending"
    assert ("GET", "/api/holds/pending-approvals") in ordered
    assert ("DELETE", "/api/filters/history") in ordered


def test_the_two_routes_that_were_dead_now_answer(test_client) -> None:
    """The symptom, alongside the property.

    The ordering test above is the durable one -- it catches a third route
    added wrongly tomorrow. This one records what was actually broken, so the
    fix is legible without reconstructing it from the ordering rule: these two
    URLs were unreachable, and a caller of the first was told a hold did not
    exist when it had asked for a list.
    """
    from backend.auth.jwt import get_current_user
    from backend.main import app
    from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

    app.dependency_overrides[get_current_user] = _mock_admin
    try:
        holds = test_client.get("/api/holds/pending-approvals")
        history = test_client.delete("/api/filters/history")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert holds.status_code != 404, "still shadowed by /{hold_id} — it answers 'WIP hold not found'"
    assert holds.status_code == 200, holds.text[:200]
    assert isinstance(holds.json(), list), holds.text[:200]

    assert history.status_code != 422, "still shadowed by /{filter_id} — int parsing of 'history'"
    assert history.status_code == 204, history.text[:200]

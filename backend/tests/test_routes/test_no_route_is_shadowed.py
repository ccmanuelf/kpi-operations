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

import re
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


def _as_pattern(path: str) -> "re.Pattern[str]":
    """A route path as the regex FastAPI effectively matches it with."""
    return re.compile(
        "^" + re.sub(r"\{[^}]+\}", "[^/]+", re.escape(path).replace(r"\{", "{").replace(r"\}", "}")) + "$"
    )


def _shadowed() -> List[Tuple[str, str, str]]:
    """Every literal route already matched by an EARLIER parameterised one.

    Asked as "does an earlier pattern match this path", not as "is there a
    `/{param}` sibling under the same prefix". The sibling formulation was the
    first version and it is narrower in one direction and wronger in another:

    * it only sees a param in the LAST segment, so `/api/x/{id}/sub` shadowing
      `/api/x/literal/sub` would slip past;
    * it needed a special case for trailing slashes, because normalising them
      away invented collisions for `/api/alerts/config/` and
      `/api/client-config/`, both of which answer 200. Anchored matching gets
      that right for free -- the trailing slash makes the strings differ, so
      no pattern matches.
    """
    ordered = _registration_order()
    found: List[Tuple[str, str, str]] = []
    for later, (method, path) in enumerate(ordered):
        if "{" in path:
            continue
        for earlier_method, earlier_path in ordered[:later]:
            if earlier_method != method or "{" not in earlier_path:
                continue
            if _as_pattern(earlier_path).match(path):
                found.append((method, path, earlier_path))
                break
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

    # An exact count, not a threshold. `> 400` would let a scanner regression
    # from 460 to 410 pass while the check quietly stopped covering fifty
    # routes -- and a shadowing scan over a subset reads as evidence while
    # proving nothing. Changing this number should mean routes really were
    # added or removed.
    assert len(ordered) == 460, (
        f"{len(ordered)} routes enumerated, expected 460. If routes were genuinely added or "
        "removed, update this number; if not, the walk has stopped descending into "
        "_IncludedRouter and this scan is no longer covering the whole table."
    )
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


def test_alerts_config_answers_with_and_without_a_trailing_slash(test_client) -> None:
    """The third victim of the same rule, and the one the scan could not see.

    `GET /api/alerts/config` answered 404 "Alert not found" -- swallowed by
    `GET /api/alerts/{alert_id}` -- because the route was registered as
    `/config/` and the no-slash spelling never matched it. `{alert_id}`
    FULL-matched first, so FastAPI's slash-redirect never got the chance to
    fire, and reordering the routers alone did not help.

    Invisible to `_shadowed()` above, which compares REGISTERED paths: the
    broken spelling was not a registered path at all. That is the limit of a
    structural scan, and the reason this URL is asserted directly.

    Registered as `/config` now, so the bare spelling serves directly and the
    slashed one redirects to it. Both are pinned -- swapping the declaration
    back to `/config/` breaks the first.
    """
    from backend.auth.jwt import get_current_user
    from backend.main import app
    from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

    app.dependency_overrides[get_current_user] = _mock_admin
    try:
        bare = test_client.get("/api/alerts/config")
        slashed = test_client.get("/api/alerts/config/", follow_redirects=True)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert bare.status_code != 404, "still swallowed by /{alert_id} — it answers 'Alert not found'"
    assert bare.status_code == 200, bare.text[:200]
    assert isinstance(bare.json(), list), bare.text[:200]
    assert slashed.status_code == 200, slashed.text[:200]

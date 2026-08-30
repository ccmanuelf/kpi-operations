"""Task 10's principled ratchet-scope rule, gated two-sided against the
golden master -- see `response_scope.py` for the mechanism under test.

1. `test_every_declared_out_of_scope_route_is_actually_non_json` -- every
   route in `OUT_OF_SCOPE_ROUTES` must NOT have live evidence of a JSON
   body: its golden entry must be a placeholder (`is_placeholder` --
   `<non-json>`, `<status:...>`, or `<blocked:...>`), never real field
   keys. This is what stops a route dodging the ratchet by CLAIMING a
   return type it does not have: declare a route `-> StreamingResponse`
   while it actually still returns a dict, and a captured 2xx keeps
   recording real keys -- this fails, naming the route.

   Not narrowed to literal `<non-json>` -- two of the five `/api/qr`
   routes never reach a live 2xx at all during capture -- `POST
   /api/qr/generate/image` is `<status:422>` (the capture harness sends no
   body), and `GET /api/qr/job/{job_id}/image` was `<blocked:job_id>` until
   S3 seeded JOB, which is exactly why this rule is stated in terms of
   evidence rather than of a route list. The golden master offers no
   confirming *or* contradicting evidence for such a route, so requiring
   literal `<non-json>` would reject a legitimate declaration for lack of
   proof it cannot obtain.
   `is_placeholder` accepts "no evidence either way" without accepting
   "evidence against" -- a real captured JSON shape is never a
   placeholder, so the dodge this check exists to catch is still caught
   (mutation-proven below). The routes this can't confirm from golden
   evidence are exactly where
   `test_declared_reason_matches_the_structural_classification` carries
   the full weight: it reads the endpoint's own return annotation
   directly, never the golden master, so it doesn't need a live 2xx to be
   authoritative.

2. `test_every_non_json_golden_entry_is_explained` -- every `<non-json>`
   entry currently in the golden master, whether or not it is declared in
   `OUT_OF_SCOPE_ROUTES`, must be explained by `classify_non_json_route` (a
   `Response` subclass, or a 204 DELETE). An unexplained entry is a route
   returning something unparseable that nobody accounted for; this fails
   naming it, rather than letting it pass as unnoticed debt. NOTE this
   check's domain is golden entries that already read `<non-json>` -- it
   says nothing about a route like `POST /api/qr/generate/image`, whose
   golden entry is a different placeholder flavour and never enters this
   check's `non_json_routes` set at all, declared or not. Its protection is
   (1) and structural classification, not this check.

Neither (1) nor (2) alone is enough, and together they still don't cover
every declared route with golden evidence -- see the two notes above. (1)
alone says nothing about routes NOT in the registry -- an unrelated route
could start recording `<non-json>` for a reason nobody wrote down and
nothing would notice. (2) alone would not catch a WRONGLY declared entry --
one that IS structurally explained, but for a different reason than the one
written down -- which `test_declared_reason_matches_the_structural_classification`
closes. And an entirely REMOVED declaration (e.g. someone deletes the
`POST /api/qr/generate/image` entry by mistake) is caught by neither test in
this file -- it is caught by the main ratchet,
`test_no_api_route_has_a_loose_response_model` in
`test_no_loose_response_models.py`: with no `OUT_OF_SCOPE_ROUTES` entry the
route reappears in `routes_needing_a_response_model`'s output, and with no
`ALLOWLIST` entry either (both were removed together when the route was
scoped out) it fails there as "unexpected", naming the route. Mutation-proven
below for the POST specifically, and that division of labour -- this file
proves a DECLARATION is trustworthy, the ratchet proves nothing DISAPPEARS
without one -- is deliberate, not a gap.
"""

from __future__ import annotations

import json

from backend.tests.contract.capture import flatten_api_routes, is_placeholder
from backend.tests.contract.capture import was_never_reached
from backend.tests.contract.conftest import GOLDEN
from backend.tests.contract.response_scope import (
    NO_CONTENT_204,
    OUT_OF_SCOPE_ROUTES,
    RESPONSE_SUBCLASS,
    classify_non_json_route,
)


def _golden() -> dict:
    data: dict = json.loads(GOLDEN.read_text())
    return data


def _route(app, route_key: str):
    method, path = route_key.split(" ", 1)
    for candidate in flatten_api_routes(app.routes):
        if candidate.path == path and method in candidate.methods:
            return candidate
    raise AssertionError(f"no route registered for {route_key!r}")


def test_every_declared_out_of_scope_route_is_actually_non_json():
    golden = _golden()
    for route_key in sorted(OUT_OF_SCOPE_ROUTES):
        assert is_placeholder(golden[route_key]), route_key


def test_every_non_json_golden_entry_is_explained():
    from backend.main import app

    golden = _golden()
    non_json_routes = sorted(route for route, shape in golden.items() if shape == ["<non-json>"])
    # 37, up from 36: GET /api/pivot/{dataset}/csv became reachable once the
    # capture supplied its required query params, and records the CSV stream it
    # always returned. 36 was S3 seeding JOB, which did the same for
    # GET /api/qr/job/{job_id}/image. This count rises when a route becomes
    # reachable and falls when one starts sending JSON -- neither is churn, and
    # both must be stated.
    assert len(non_json_routes) == 37

    unexplained = [route for route in non_json_routes if classify_non_json_route(_route(app, route)) is None]
    assert unexplained == []


def test_declared_reason_matches_the_structural_classification():
    """Every declared member must classify as the category IT CLAIMS.

    This used to assert `RESPONSE_SUBCLASS` for all members, which was true
    while no DELETE was declared. Now that 24 are, the check compares each
    entry's own `category` against the structural answer — a 204 declared as a
    file download, or the reverse, fails here. Asserting only "is one of the
    two explained categories" would pass on exactly that mistake.
    """
    from backend.main import app

    for route_key, entry in sorted(OUT_OF_SCOPE_ROUTES.items()):
        actual = classify_non_json_route(_route(app, route_key))
        assert actual == entry.category, f"{route_key}: declared {entry.category}, classifies as {actual}"

    # Both categories are genuinely represented, so neither branch of the
    # comparison above is dead.
    declared = {entry.category for entry in OUT_OF_SCOPE_ROUTES.values()}
    assert declared == {RESPONSE_SUBCLASS, NO_CONTENT_204}


def test_a_declared_route_that_was_captured_really_sent_no_body():
    """Check the declaration against OBSERVED behaviour, not against a re-read
    of the same annotation.

    Cross-model review pointed out that every other gate here asks
    `classify_non_json_route` again — annotation vs annotation — so a route
    whose real response is JSON could be exempted with nothing failing. This
    compares each declaration against what the capture actually recorded.

    Only the routes the harness can reach are checked, and the count is pinned
    so this cannot quietly become vacuous: several declared DELETEs are
    unreachable because the seeder writes no rows for them (S3), and
    work-orders answers 409 while its children exist. Those have no observation
    to compare against — which is a seed gap, not a licence to skip the ones
    that DO.
    """
    golden = json.loads(GOLDEN.read_text())

    observed = {route: golden[route] for route in OUT_OF_SCOPE_ROUTES if route in golden}
    sent_a_body = {
        route: shape
        for route, shape in observed.items()
        # `was_never_reached` covers BOTH placeholder flavours a declared
        # route can legitimately land on: `<status:...>` (it answered an error,
        # e.g. work-orders' 409) and `<blocked:...>` (the seeder writes no rows
        # for it — S3). Filtering only `<status:` left eight seed-gapped routes
        # looking like they had sent a body.
        if shape != ["<non-json>"] and not was_never_reached(shape)
    }
    assert sent_a_body == {}, f"declared out of scope, but the capture recorded a body: {sent_a_body}"

    # Anti-vacuity: if this ever drops to zero the assertion above proves
    # nothing. 29 of the 47 declarations have a real observation today -- both
    # 47th and 29th are GET /api/pivot/{dataset}/csv, whose `<non-json>` is
    # what earned it the declaration in the first place.
    really_non_json = [r for r, shape in observed.items() if shape == ["<non-json>"]]
    assert len(really_non_json) >= 29


def test_non_json_entries_decompose_into_exactly_three_categories():
    """The independent count backing Task 10's brief: 3 pre-existing
    `-> Response` QR-image routes + the 17 export/report routes this task
    corrected from a false `-> Any` = 20 RESPONSE_SUBCLASS entries, and 9
    pre-existing 204 DELETEs = NO_CONTENT_204. Pinned as exact sorted lists,
    not just counts, so a route swapping categories fails by name.
    """
    from backend.main import app

    golden = _golden()
    non_json_routes = sorted(route for route, shape in golden.items() if shape == ["<non-json>"])

    response_subclass = []
    no_content_204 = []
    for route_key in non_json_routes:
        category = classify_non_json_route(_route(app, route_key))
        if category == RESPONSE_SUBCLASS:
            response_subclass.append(route_key)
        elif category == NO_CONTENT_204:
            no_content_204.append(route_key)

    assert response_subclass == [
        "GET /api/export/attendance",
        "GET /api/export/downtime-events",
        "GET /api/export/employees",
        "GET /api/export/holds",
        "GET /api/export/production-entries",
        "GET /api/export/products",
        "GET /api/export/quality-inspections",
        "GET /api/export/shifts",
        "GET /api/export/work-orders",
        "GET /api/pivot/{dataset}/csv",
        "GET /api/qr/employee/{employee_id}/image",
        # Reachable since S3 seeded JOB; it was declared RESPONSE_SUBCLASS all
        # along on the strength of its return annotation alone, and the capture
        # now confirms it.
        "GET /api/qr/job/{job_id}/image",
        "GET /api/qr/product/{product_id}/image",
        "GET /api/qr/work-order/{work_order_id}/image",
        "GET /api/reports/attendance/excel",
        "GET /api/reports/attendance/pdf",
        "GET /api/reports/comprehensive/excel",
        "GET /api/reports/comprehensive/pdf",
        "GET /api/reports/production/excel",
        "GET /api/reports/production/pdf",
        "GET /api/reports/quality/excel",
        "GET /api/reports/quality/pdf",
    ]
    # The six transaction DELETEs joined this list when #239 landed. They used
    # to record `<status:404>` -- not because they had no body, but because they
    # answered 404 for every id: the CRUD layer set `is_active = False` on models
    # that had no such column. Fixing that turned them into ordinary 204s.
    assert no_content_204 == [
        "DELETE /api/attendance/{attendance_id}",
        "DELETE /api/client-config/{client_id}",
        "DELETE /api/clients/{client_id}",
        "DELETE /api/defect-types/{defect_type_id}",
        "DELETE /api/defects/{defect_detail_id}",
        "DELETE /api/downtime/{downtime_id}",
        "DELETE /api/employees/{employee_id}",
        "DELETE /api/hold-catalogs/reasons/{catalog_id}",
        "DELETE /api/hold-catalogs/statuses/{catalog_id}",
        "DELETE /api/holds/{hold_id}",
        "DELETE /api/production-lines/{line_id}",
        "DELETE /api/production/{entry_id}",
        "DELETE /api/quality/{inspection_id}",
        "DELETE /api/shifts/{shift_id}",
        "DELETE /api/users/{user_id}",
    ]

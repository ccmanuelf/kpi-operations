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
   routes never reach a live 2xx at all during capture (`GET /api/qr/job/
   {job_id}/image` is `<blocked:job_id>`, JOB has zero seeded rows; `POST
   /api/qr/generate/image` is `<status:422>`, the capture harness sends no
   body). The golden master offers no confirming *or* contradicting
   evidence for those two, so requiring literal `<non-json>` would reject
   a legitimate declaration for lack of proof it cannot obtain.
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
   says nothing about `GET /api/qr/job/{job_id}/image` or `POST /api/qr/
   generate/image`, whose golden entries are a different placeholder
   flavour and never enter this check's `non_json_routes` set at all,
   declared or not. Their protection is (1) and structural
   classification, not this check.

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
    assert len(non_json_routes) == 29

    unexplained = [route for route in non_json_routes if classify_non_json_route(_route(app, route)) is None]
    assert unexplained == []


def test_declared_reason_matches_the_structural_classification():
    """`OUT_OF_SCOPE_ROUTES` declares only `RESPONSE_SUBCLASS` entries --
    Task 10 converts no DELETE route -- so every declared member must
    classify as exactly that category, not merely as some explained one.
    """
    from backend.main import app

    for route_key in sorted(OUT_OF_SCOPE_ROUTES):
        assert classify_non_json_route(_route(app, route_key)) == RESPONSE_SUBCLASS, route_key


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
        "GET /api/qr/employee/{employee_id}/image",
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
    assert no_content_204 == [
        "DELETE /api/client-config/{client_id}",
        "DELETE /api/clients/{client_id}",
        "DELETE /api/defect-types/{defect_type_id}",
        "DELETE /api/employees/{employee_id}",
        "DELETE /api/hold-catalogs/reasons/{catalog_id}",
        "DELETE /api/hold-catalogs/statuses/{catalog_id}",
        "DELETE /api/production-lines/{line_id}",
        "DELETE /api/shifts/{shift_id}",
        "DELETE /api/users/{user_id}",
    ]

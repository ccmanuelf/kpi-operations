"""Task 10's ratchet-scope rule: which routes have NO JSON body at all, and
therefore cannot leak a Decimal no matter how loosely they are typed.

`capture.is_loose` treats `response_model is None` as loose -- correctly, in
general, because `None` usually just means "nobody annotated this yet".
But FastAPI collapses `response_model` to that exact same `None` for TWO
routes that already have a real, deliberate answer:

  * a route whose return annotation IS a `Response` subclass (a file
    download): there is no body for Pydantic to validate, so there is
    nothing for a Decimal to hide inside.
  * a `DELETE` returning `204 No Content` (`-> None`): no body is sent at
    all.

`route.response_model` cannot tell these apart from an unannotated route --
both collapse to the same `None` -- so telling them apart means reading the
endpoint's OWN return annotation directly (`classify_non_json_route`,
below), never `route.response_model`.

`OUT_OF_SCOPE_ROUTES` declares the routes removed from the ratchet: the 17
`/api/export/*` and `/api/reports/*/{pdf,excel}` routes corrected from a
false `-> Any` to their real `-> StreamingResponse` in
`backend/routes/export.py` and `backend/routes/reports/*.py`, plus 5
`/api/qr` routes (`backend/routes/qr.py`, untouched by this task's edits --
already `-> Response`) folded in on review: a classification sweep over the
remaining routes found `/api/qr` claimed by no Task 11-14 grouping at all,
so leaving its 5 routes in `ALLOWLIST` would make them a permanent,
unclaimed exception -- precisely the outcome this scope rule exists to
prevent. One of the 5, `POST /api/qr/generate/image`, is a POST: the scope
rule is about JSON-body-or-not, never about method, and
`classify_non_json_route` never inspects `route.methods` for the
`RESPONSE_SUBCLASS` branch, so it classifies correctly regardless (verified
directly, and mutation-proven in `test_response_scope.py`).

The 204 DELETEs are now populated, which is what Task 10 built the reusable
`classify_non_json_route` predicate FOR. Measured rather than assumed: 24 of
the 25 allowlisted DELETE routes annotate `-> None` and send no body, not the
9 the plan estimated -- that figure predates the routes being annotated. The
one exception, `DELETE /api/v2/simulation/scenarios/{scenario_id}`, returns a
JSON body and stays in the ratchet where it belongs.

Reachability is deliberately NOT a factor here. Four of these routes cannot be
captured at all because the seeder writes no rows for them (S3), and
work-orders answers 409 when its children exist. None of that changes whether
the route CAN carry a JSON body, which is a static property of its return
annotation -- so the seed gap does not block this declaration.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi.responses import Response
from fastapi.routing import APIRoute

#: The two (and only two) reasons a route can legitimately record
#: `<non-json>` in the golden master. A third would be a genuine finding --
#: see `classify_non_json_route`.
RESPONSE_SUBCLASS = "response_subclass"
NO_CONTENT_204 = "204_no_content"


@dataclass(frozen=True)
class ScopeEntry:
    """`reason` names the real return type and where it was verified.

    `category` is the classification this declaration CLAIMS. It exists so the
    gate can compare a per-entry claim against what the code actually does,
    rather than checking membership in "one of the two allowed categories" --
    a weaker test that would let a 204 be declared as a file download and pass.
    """

    reason: str
    category: str = RESPONSE_SUBCLASS


#: route -> why it is out of the ratchet's domain, and which category that
#: reason claims. Each entry's `category` is compared against the structural
#: answer by `test_declared_reason_matches_the_structural_classification`, so a
#: 204 declared as a file download fails there rather than passing quietly.
OUT_OF_SCOPE_ROUTES: Dict[str, ScopeEntry] = {
    "GET /api/export/production-entries": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/work-orders": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/quality-inspections": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/downtime-events": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/attendance": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/employees": ScopeEntry(
        "-> StreamingResponse built inline (not via _build_csv_response, but the same shape)."
    ),
    "GET /api/export/products": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/shifts": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/export/holds": ScopeEntry("-> StreamingResponse via _build_csv_response (CSV)."),
    "GET /api/reports/comprehensive/pdf": ScopeEntry("-> StreamingResponse wrapping a PDF buffer."),
    "GET /api/reports/comprehensive/excel": ScopeEntry("-> StreamingResponse wrapping an Excel buffer."),
    "GET /api/reports/quality/pdf": ScopeEntry("-> StreamingResponse wrapping a PDF buffer."),
    "GET /api/reports/quality/excel": ScopeEntry("-> StreamingResponse wrapping an Excel buffer."),
    "GET /api/reports/attendance/pdf": ScopeEntry("-> StreamingResponse wrapping a PDF buffer."),
    "GET /api/reports/attendance/excel": ScopeEntry("-> StreamingResponse wrapping an Excel buffer."),
    "GET /api/reports/production/pdf": ScopeEntry("-> StreamingResponse wrapping a PDF buffer."),
    "GET /api/reports/production/excel": ScopeEntry("-> StreamingResponse wrapping an Excel buffer."),
    "GET /api/qr/employee/{employee_id}/image": ScopeEntry("-> Response wrapping a raw PNG QR image."),
    "GET /api/qr/job/{job_id}/image": ScopeEntry("-> Response wrapping a raw PNG QR image."),
    "GET /api/qr/product/{product_id}/image": ScopeEntry("-> Response wrapping a raw PNG QR image."),
    "GET /api/qr/work-order/{work_order_id}/image": ScopeEntry("-> Response wrapping a raw PNG QR image."),
    "POST /api/qr/generate/image": ScopeEntry(
        "-> Response wrapping a raw PNG QR image. A POST, deliberately: the scope "
        "rule is about whether a route has a JSON body, never about its method."
    ),
    # --- 204 No Content DELETEs ------------------------------------------
    "DELETE /api/attendance/{attendance_id}": ScopeEntry(
        "-> None, 204 No Content: deletes an attendance entry and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/break-times/{break_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a break time and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/client-config/{client_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a client config and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/clients/{client_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a client and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/coverage/{coverage_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a shift coverage row and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/defect-types/{defect_type_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a defect-type catalog row and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/defects/{defect_detail_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a defect detail and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/downtime/{downtime_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a downtime entry and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/employees/{employee_id}": ScopeEntry(
        "-> None, 204 No Content: deletes an employee and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/equipment/{equipment_id}": ScopeEntry(
        "-> None, 204 No Content: deletes an equipment record and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/filters/history": ScopeEntry(
        "-> None, 204 No Content: deletes a saved-filter history and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/filters/{filter_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a saved filter and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/floating-pool/{pool_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a floating-pool entry and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/hold-catalogs/reasons/{catalog_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a hold-reason catalog row and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/hold-catalogs/statuses/{catalog_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a hold-status catalog row and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/holds/{hold_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a WIP hold and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/jobs/{job_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a job and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/part-opportunities/{part_number}": ScopeEntry(
        "-> None, 204 No Content: deletes a part-opportunity row and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/production-lines/{line_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a production line and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/production/{entry_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a production entry and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/quality/{inspection_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a quality inspection and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/shifts/{shift_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a shift and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/users/{user_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a user and sends no body.", NO_CONTENT_204
    ),
    "DELETE /api/work-orders/{work_order_id}": ScopeEntry(
        "-> None, 204 No Content: deletes a work order and sends no body.", NO_CONTENT_204
    ),
}


def _real_return_annotation(route: APIRoute):
    """The endpoint's own return annotation, read off its live signature --
    NOT `route.response_model`, which FastAPI collapses to `None` for a
    `Response` subclass and for a bare `-> None` 204 route alike. Telling
    those two apart is this module's whole job, so `response_model` -- having
    already erased the distinction -- is the one place that cannot be
    consulted to make it.
    """
    return inspect.signature(route.endpoint).return_annotation


def classify_non_json_route(route: APIRoute) -> Optional[str]:
    """Which of the two known reasons explains `route` recording `<non-json>`
    in the golden master, or `None` if neither does.

    Purely structural -- it inspects the same two facts a human would check
    by reading the route (its real return annotation, and whether it is a
    204 DELETE) -- so it explains a `<non-json>` entry whether or not anyone
    remembered to add it to `OUT_OF_SCOPE_ROUTES`. That independence is the
    completeness half of the two-sided gate: `OUT_OF_SCOPE_ROUTES` only ever
    needs the routes THIS task's ratchet exemption covers, while this
    function is what proves every OTHER `<non-json>` entry -- the ones
    nobody had to declare, because their annotation was never wrong -- is
    still accounted for and not silently unexplained.
    """
    annotation = _real_return_annotation(route)
    if isinstance(annotation, type) and issubclass(annotation, Response):
        return RESPONSE_SUBCLASS
    if annotation is None and "DELETE" in route.methods and route.status_code == 204:
        return NO_CONTENT_204
    return None


def routes_needing_a_response_model(app) -> list:
    """`capture.loose_routes(app)`, minus the routes declared
    `OUT_OF_SCOPE_ROUTES` -- the routes this refactor's ratchet must still
    either convert or allowlist. `capture.loose_routes` itself stays
    untouched and purely structural; the domain correction lives here,
    one layer up, where it can be gated two-sided against the golden master
    without teaching the capture harness about response contracts.
    """
    from backend.tests.contract.capture import loose_routes

    return [
        (method, path, kwargs)
        for method, path, kwargs in loose_routes(app)
        if f"{method} {path}" not in OUT_OF_SCOPE_ROUTES
    ]

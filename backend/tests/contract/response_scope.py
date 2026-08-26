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

`OUT_OF_SCOPE_ROUTES` declares the routes THIS task removes from the ratchet
-- the 17 `/api/export/*` and `/api/reports/*/{pdf,excel}` routes corrected
from a false `-> Any` to their real `-> StreamingResponse` in
`backend/routes/export.py` and `backend/routes/reports/*.py`. It is
deliberately NOT populated with the 9 pre-existing 204 DELETEs or the 3
pre-existing `-> Response` QR-image routes: those routes' files are outside
this task's edits, and `routes_needing_a_response_model` only ever shrinks
the ratchet for routes actually declared here -- see
`test_response_scope.py` for the two-sided gate that keeps this trustworthy,
and Task 10's brief for why the 204 taxonomy is built as a REUSABLE
predicate (`classify_non_json_route`) rather than inlined, for Task 17 to
extend when it takes on the DELETE routes.
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
    """`reason` names the real return type and where it was verified."""

    reason: str


#: route -> why it is out of the ratchet's domain. Every member here MUST be
#: RESPONSE_SUBCLASS today -- Task 10 converts no DELETE route -- pinned by
#: `test_declared_reason_matches_the_structural_classification`.
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

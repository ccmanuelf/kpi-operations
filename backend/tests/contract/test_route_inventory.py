def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """28 routes still needing a response model, after the query-param capture
       scoped `GET /api/pivot/{dataset}/csv` out of the ratchet.

       DIRECTION: this number may only FALL. The ratchet
       (`test_no_loose_response_models.py`) already refuses a NEW loose route,
       so a conversion is the only thing that can lower it -- and a RISE here
       does not mean someone added work, it means a route stopped being
       enumerated, which is the failure this count is pinned to catch.

       S4a removes exactly 1, and the distinction matters more than the
       number. It taught the capture to supply REQUIRED QUERY PARAMS
       (`tests/contract/query_specs.py`), which turned nine golden entries
       from `<status:422>` -- a status the HARNESS provoked by omitting a
       parameter, not an answer the route gave -- into real evidence. SIX of
       those nine were allowlisted; five of the six still are, and
       deliberately so: capturing a real shape says what a route sends, not
       that anyone has typed it. Conflating the two is what #244 did once
       already. (The sixth is the one removal below. The three that were
       never allowlisted -- GET /api/kpi/labor-hours, GET /api/kpi/{metric}/
       cause and GET /api/capacity/kpi/variance -- are worth noting for the
       opposite reason: two already HAD response models written while their
       golden entry was a 422, i.e. modelled without the capture ever having
       seen a response.)

       The 1 that leaves is not a conversion either. `GET /api/pivot/{dataset}
       /csv` answers with a CSV `StreamingResponse` and, asked properly,
       records `<non-json>`: it can never carry a JSON body, so it cannot
       carry a response model, so a queue named "awaiting a response model" is
       the wrong place for it. That is Task 10's existing scope rule
       (`response_scope.py`) applied to a route that only now has the evidence
       to be classified -- the same fold-in the /api/qr review made, and made
       for the stated reason that leaving such a route allowlisted creates a
       permanent unclaimed exception. Its JSON twin `GET /api/pivot/{dataset}`
       stays in the ratchet, because that one does return a body. 29 - 1 = 28.

       29 was the count before S4a, after Batch R1 typed the six
       `GET /api/jobs/{job_id}/*` KPI routes.

       R1 removes exactly 6, the whole remaining `/api/jobs` group -- yield,
       efficiency, performance, ppm, dpmo, kpi-summary -- typed across one new
       module, `backend/schemas/job_kpi_contracts.py` (the seventh route the
       plan sized into R1, `GET /api/jobs/kpi/rty-summary`, was converted
       early, in R5). `ALLOWLIST` shrinks by the same 6: none of them leaves
       the ratchet's scope, all six are converted. 35 - 6 = 29.

       R1 was scheduled LAST for a reason the plan states plainly: 6 of its 7
       routes had `<blocked:job_id>` for a golden entry, because JOB had zero
       seeded rows. #244 seeded a routing and #243's `job_id` spec resolves the
       id from PRODUCTION_ENTRY rather than JOB (`param_specs.py`), which is
       what put every one of the six on its POPULATED branch and made this the
       first increment able to model them from measured evidence. It paid
       immediately: `GET /api/jobs/{job_id}/yield` was serving
       `"yield_percentage":"99.00"` -- a JSON STRING -- while `kpi-summary`
       served `99.0` for the same job and the same metric in the same capture.
       Four of the six carry a no-entries branch and are registered in
       `EXCLUDE_UNSET_ROUTES`; see `schemas/job_kpi_contracts.py`.

       35 was the count before R1, after S2 scoped the 204 DELETEs out of the
       ratchet.

       S2 removes 24, not the 9 the plan estimated. That figure predates the
       DELETE routes carrying return annotations; measured against the code,
       24 of the 25 allowlisted DELETEs annotate `-> None` and send no body.
       The one exception, `DELETE /api/v2/simulation/scenarios/{scenario_id}`,
       returns a JSON payload and stays in the ratchet.

       Reachability is deliberately not a factor: four of the 24 cannot be
       captured at all (the seeder writes no rows -- S3) and work-orders
       answers 409 while its children exist. Whether a route CAN carry a JSON
       body is a static property of its annotation, so a seed gap never
       justified leaving it in a queue labelled "awaiting a response model".

       59 was the count before S2, after Batch R5 -- the
       LAST conversion batch, per task-R5-brief.md -- disposes of 12 of the
       prior 71: 11 typed across two new modules,
       `backend/schemas/reference_contracts.py` (`/api/defect-types`
       constants + template/download, `/api/products`,
       `/api/downtime-reasons`, `/api/filters/statistics`,
       `/api/v2/simulation/`, `/api/import-logs`) and
       `backend/schemas/kpi_metrics_contracts.py`
       (`/api/jobs/kpi/rty-summary`, `/api/inference/cycle-time/{product_id}`,
       `/api/client-config/{client_id}/effective`,
       `/api/metrics/calculate/run-nightly`) -- plus 1 more,
       `GET /api/v2/simulation/schema`, scoped OUT of the ratchet rather than
       modeled: it returns `SimulationConfig.model_json_schema()` verbatim
       (a JSON-Schema document, not a payload), declared in
       `backend/tests/contract/schema_document_routes.py` the same way Task 10
       scoped out the `-> Response` routes. 71 - 12 = 59, mirrored by
       `ALLOWLIST` shrinking by the same 11 entries (the 12th, the schema
       route, was never in a position to be "converted" -- it leaves the
       ratchet's scope instead). Every remaining allowlisted route is now
       blocked on infrastructure (a write-capture harness, seeder rows, a
       product bug fix), not on modelling effort -- see "The 59 unreachable
       routes" in docs/superpowers/plans/2026-08-25-response-model-refactor.md.

       71 itself is Batch R2's count: 78 - 7 across `/api/quality` (6 of 8)
       and `/api/capacity` (1 of 2) (`backend/schemas/quality_contracts.py` +
       `capacity_contracts.py`). `/api/pivot`'s 2 routes and 6 more across
       that batch's 3 areas needed query params or a request body and stayed
       allowlisted for the write-capture harness.

       78 itself is Batch R3's count: 90 - 12 across `/api/floating-pool`
       (4), `/api/work-orders` (3 GET + 1 POST), `/api/attendance` (2),
       `/api/alerts` (2) (`backend/schemas/floor_contracts.py` +
       `workorder_contracts.py`).

       90 itself is Batch R4's count: 108 - 18 across `/api/cache`,
       `/api/kpi-thresholds`, `/api/predictions`, `/api/data-completeness`,
       `/api/my-shift`, `/api/shifts`, `/api/plan-vs-actual`
       (`backend/schemas/ops_contracts.py`).

       This measurement is also where `flatten_api_routes` (capture.py) earned
       its second iteration: FastAPI's `_IncludedRouter` wrapper only bakes a
       route's full prefix into `.path` for a SINGLE include level. A router
       included without its own prefix and then included again one level up
       (`quality_router.include_router(pareto_router)`, `pareto_router` itself
       unprefixed) leaves the underlying route's `.path` as the router-local
       fragment (`/kpi/by-product`), not the effective `/api/quality/kpi/
       by-product` -- a naive recursive `original_router.routes` walk (the
       first version of this fix) silently missed such routes entirely rather
       than mis-measuring by one, undercounting this test's own assertion by
       16 before `effective_route_contexts()` (the mechanism FastAPI itself
       exposes for exactly this, already used by `test_openapi_surface.py`)
       replaced it.

       108 itself was re-measured 2026-08-25 after Task 10 and its review
       follow-up. Task 10 found its 20-route
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
    from backend.tests.contract.schema_document_routes import routes_needing_a_response_model

    routes = routes_needing_a_response_model(app)

    assert len(routes) == 20
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

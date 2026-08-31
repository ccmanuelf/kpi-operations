"""WHAT each REQUIRED QUERY param resolves to. The HOW lives in
`param_resolution.py`, next to the path-param resolver it extends.

`param_specs.py` closed one half of "the caller owns id resolution": a route
template's `{...}` params. This closes the other half that a GET can have.
Nine golden entries recorded `<status:422>` -- a status meaning "the route
rejected the request" -- when what actually happened is that the harness never
supplied a parameter the route requires. That is the same class of defect as
the literal-brace URLs: an answer recorded as the route's, produced by a
question nobody meant to ask.

DETECTION IS THE APP'S, NOT OURS. Required-ness is read off FastAPI's own
`route.dependant` (see `param_resolution.required_query_params`), never
re-derived from `inspect.signature`. The two declaration forms in this
codebase look nothing alike --

    start_date: date                                    # bare, required
    client_id: str = Query(..., description="Client ID")  # required-ness is
                                                          # inside the default

-- and a signature scan that reads "has a default" as "optional" sees the
second as optional and silently leaves `GET /api/capacity/kpi/variance`
unresolved. FastAPI already answers this question correctly for both forms
(it is how the app itself decides to 422), so asking IT is both less code and
the only version that cannot disagree with the running route.

THREE KINDS OF VALUE, and the rule for each is the same one `param_specs.py`
states: derive, do not hardcode.

  ids       reuse the path registry's spec OBJECTS (`REGISTRY[...]` below --
            the same object, not a copy), so `client_id` and `product_id`
            have exactly one SQL, one cache entry and one place to fix when
            the seeder moves.
  dates     `Kind.SEED_WINDOW`, anchored on `SeededToday.today()` -- the
            SAME pin the captured routes read (`conftest.CLOCK_READING_
            ROUTE_MODULES`). Anchoring on the real clock instead would give
            every one of these entries a quiet expiry date, which is exactly
            what #245 spent a pass removing; anchoring on a second copy of
            `SEED_AS_OF` would let the two drift. `SeededToday` raises when
            unpinned, so an unpinned capture cannot silently fall back to the
            calendar.
  enums     `Kind.LITERAL` plus `choices` imported from the module the route
            validates against (`pivot.buckets.VALID_BUCKETS`). The literal
            names which member is asked for; `choices` is what makes a stale
            copy impossible.

WHAT IS DELIBERATELY NOT RESOLVED HERE is as load-bearing as what is, and
both exclusions are declared below rather than left to be inferred from an
empty result: `DEFERRED_TO_WRITE_CAPTURE` (mutating routes) and the one
`Kind.BLOCKED` entry (a route whose params all resolve but whose answer is
empty under this seed).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, FrozenSet, Tuple

from backend.pivot.buckets import VALID_BUCKETS
from backend.orm.work_order import WorkOrderStatus
from backend.schemas.workflow import WORKFLOW_TEMPLATES
from backend.tests.contract.param_specs import REGISTRY, Kind, ParamSpec

#: How far back the captured date window reaches from the seed's own "today".
#:
#: The smoke profile's transactional rows span 13 days ending the day before
#: `SEED_AS_OF`, so 90 is wide margin rather than a fitted number -- and
#: `test_query_resolution.test_the_window_actually_covers_the_seeded_rows`
#: asserts that against the DATABASE, so "wide enough" is measured every run
#: instead of believed. It must stay a fixed span off a fixed anchor: any
#: value works, a value read from the calendar does not.
WINDOW_DAYS = 90


def _seed_window(key: str, offset_days: int, note: str) -> ParamSpec:
    return ParamSpec(key=key, kind=Kind.SEED_WINDOW, offset_days=offset_days, note=note)


#: param name -> ordered (path fragment, spec key), exactly as
#: `param_specs.FAMILY_ROUTER` works and for the same reason: one name, more
#: than one meaning. A param listed here whose route matches no fragment
#: RAISES rather than falling back, so a new route family has to be a
#: deliberate entry.
#:
#: `client_id` is the only such name today. As a query param it means the same
#: entity everywhere -- what differs is that on `/api/capacity/kpi/variance`
#: there is nothing for it to find (see the BLOCKED spec below), which is a
#: property of the route, not of the id. Routing it is how that route-level
#: fact gets a declaration and a staleness gate instead of a comment.
QUERY_FAMILY_ROUTER: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "client_id": (
        ("/api/capacity/kpi/variance", "client_id@capacity-variance"),
        ("/api/onboarding/status", "client_id@onboarding"),
        ("/api/hold-catalogs/seed-defaults", "client_id@onboarding"),
        ("/api/attendance/mark-all-present", "client_id@onboarding"),
        # Bodies resolve ids through the same registry as params, so a body
        # carrying a client_id needs a fragment exactly as a query param does.
        ("/api/kpi-thresholds", "client_id@onboarding"),
    ),
    "shift_id": (
        ("/api/attendance/mark-all-present", "shift_id@client-consistent"),
        ("/api/floating-pool/simulation/shift-coverage", "shift_id@client-consistent"),
        ("/api/floating-pool/simulation/optimize-allocation", "shift_id@client-consistent"),
    ),
}


#: Query params FastAPI marks OPTIONAL that the route nonetheless refuses to
#: answer without. `required_query_params` reads `route.dependant`, which is
#: the right source for required-ness and is what stops the harness provoking
#: 422s -- but it can only see what FastAPI was told. A route that declares
#: `Query(None)` and then raises in its own body is required in every sense
#: that matters to a caller, and invisible there.
#:
#: `/api/onboarding/status` is the one such route today. Its `client_id` is
#: `Query(None)`; `_resolve_client_id` falls back to the caller's assigned
#: client and raises 400 ("client_id query parameter is required for this
#: user role") when there is none. The capture user has none, so the golden
#: master recorded `<status:400>` as this route's contract -- the same defect
#: class the query layer removes, arriving through a door the required-param
#: scan does not watch.
#:
#: Declared rather than discovered: a heuristic that treats any 4xx as a
#: missing param would silently start sending params to routes that are
#: 4xx for real reasons (authorization, a genuinely absent entity), and the
#: harness would record whatever came back. `test_effectively_required_
#: params_are_declared_not_discovered` gates the other direction -- a golden
#: 4xx on a route with optional query params has to appear here or be
#: explained.
EFFECTIVELY_REQUIRED_QUERY_PARAMS: Dict[str, Tuple[str, ...]] = {
    "/api/onboarding/status": ("client_id",),
}


#: The other half of the same question. A golden `<status:4xx>` on a route
#: with OPTIONAL query params has exactly two explanations: the harness never
#: sent a param the route actually needs (above), or the route means it. They
#: look identical in the golden master, so each route carrying that shape is
#: named here with the evidence that told them apart.
STATUS_IS_THE_ROUTES_OWN_ANSWER: Dict[str, str] = {
    "GET /api/predictions/health/{kpi_type}": (
        "400 'Insufficient data for health assessment'. NOT a missing param: `client_id` is "
        "`Query(None)` and the handler defaults it to the caller's client, else the literal "
        "'DEMO-CLIENT-001', so a request without it is already a request with one. Asked "
        "explicitly with every seeded client -- DEMO-HOURLY, DEMO-HYBRID, DEMO-PIECE, "
        "SAMPLE_REF -- and with DEMO-CLIENT-001 itself: all five answer 400 with the same "
        "detail. The gate is `get_historical_kpi_data` returning too few points, which is a "
        "property of the seed, not of the request. Seeding enough history promotes this route "
        "to a real shape and this entry should then be deleted."
    ),
}


#: Every required query param on a golden route the harness resolves, and
#: nothing else. Gated both directions by `test_query_resolution.py`.
QUERY_REGISTRY: Dict[str, ParamSpec] = {
    # --- ids: the path registry's own objects, not copies --------------
    "product_id": REGISTRY["product_id"],
    # --- dates ---------------------------------------------------------
    "start_date": _seed_window(
        "start_date",
        WINDOW_DAYS,
        note="Window opens WINDOW_DAYS before the seed's today. Every route taking this pairs "
        "it with end_date and calls validate_date_range, which 422s a reversed range.",
    ),
    "end_date": _seed_window(
        "end_date",
        0,
        note="The seed's own today -- the last day its universe covers, one day after the last "
        "day it has transactional rows for.",
    ),
    "date": _seed_window(
        "date",
        0,
        note="A SINGLE day, not a window: GET /api/kpi/{metric}/cause asks 'what drove this "
        "metric on this date'. Anchored at the same end as the ranges above.",
    ),
    # --- enums ---------------------------------------------------------
    "bucket": ParamSpec(
        key="bucket",
        kind=Kind.LITERAL,
        literal="week",
        choices=VALID_BUCKETS,
        note="The engine emits only buckets that have rows, and `week` over the captured window "
        "produces THREE of them (the seeded days span two and a bit ISO weeks) -- so `rows[]` "
        "comes back non-empty and contributes its per-row keys, while still being evidence that "
        "bucketing ran at all, which a bucket coarse enough to collapse the seed into a single "
        "row would not be. `choices` is pivot.buckets.VALID_BUCKETS, the tuple routes/pivot.py "
        "itself validates against.",
    ),
    # --- the four mutating routes un-deferred once every mutator became
    # --- isolated (#249). Their params are query params, not bodies.
    "shift_id@client-consistent": ParamSpec(
        key="shift_id@client-consistent",
        kind=Kind.SEEDED_ROW,
        table="SHIFT",
        sql=(
            "SELECT shift_id FROM SHIFT WHERE client_id = "
            "(SELECT client_id FROM CLIENT ORDER BY client_id LIMIT 1) "
            "ORDER BY shift_id LIMIT 1"
        ),
        note="Routed, and therefore keyed, separately because `Resolver._cache` is keyed on the "
        "SPEC KEY: a spec called `shift_id` shares its cache entry with the path registry's "
        "`shift_id`, so whichever resolved first would answer for both and this SQL would never "
        "run. NOT `REGISTRY['shift_id']`, which is the first shift by id and belongs to whichever "
        "client happens to sort first in SHIFT -- DEMO-PIECE, while `client_id@onboarding` "
        "resolves DEMO-HOURLY. `POST /api/attendance/mark-all-present` takes both and 404s "
        "('Shift 1 not found for client DEMO-HOURLY') when they disagree, which the capture would "
        "have recorded as the route's answer. The subquery is the client spec's OWN sql, so the "
        "pair cannot drift apart the way two independent LIMIT 1 lookups did. "
        "`shift-coverage` routes here too: it only echoes the id back, so consistency costs it "
        "nothing and one spec beats two that could disagree.",
    ),
    "shift_date": _seed_window(
        "shift_date",
        0,
        note="The last day of the seeded universe. `POST /api/attendance/mark-all-present` "
        "writes an attendance row per employee for this date, so it wants a day the seed "
        "actually covers; offset 0 is that day. Anchored on SeededToday like every other "
        "window here, so it cannot drift into a date the seed has no shift for.",
    ),
    "template_id": ParamSpec(
        key="template_id",
        kind=Kind.LITERAL,
        literal="standard",
        choices=tuple(WORKFLOW_TEMPLATES),
        note="`choices` is schemas/workflow.WORKFLOW_TEMPLATES, the mapping "
        "routes/workflow.py::apply_workflow_template itself looks the id up in -- so a template "
        "the app stops shipping fails at capture instead of becoming a 422 recorded as the "
        "route's answer. `standard` rather than the first key by sort order: naming the member "
        "keeps the golden master stable when a template is added.",
    ),
    "to_status": ParamSpec(
        key="to_status",
        kind=Kind.LITERAL,
        literal="IN_PROGRESS",
        choices=tuple(status.value for status in WorkOrderStatus),
        note="`choices` is orm.work_order.WorkOrderStatus, the enum the workflow validates "
        "against. IN_PROGRESS is a mid-lifecycle status, so validating a transition INTO it "
        "exercises the rule engine rather than a trivially-allowed terminal hop.",
    ),
    # --- simulation inputs: values the caller supplies, not values the seed
    # --- holds. `POST /api/floating-pool/simulation/shift-coverage` computes
    # --- from these numbers and writes nothing derived from a lookup, so there
    # --- is nothing to derive them FROM -- unlike every id above, a query
    # --- would be inventing a source. Literals with the arithmetic spelled out.
    "shift_name": ParamSpec(
        key="shift_name",
        kind=Kind.LITERAL,
        literal="Contract Capture Shift",
        note="A label echoed back in the simulation result; the route neither looks it up nor "
        "validates it. Named for what it is so a reader of the golden master knows the row came "
        "from the harness rather than the seeder.",
    ),
    "regular_employees": ParamSpec(
        key="regular_employees",
        kind=Kind.LITERAL,
        literal="8",
        note="Two short of required_employees=10, a shortfall floating_pool_available=5 covers. "
        "The route counts the pool into availability, so the reported `coverage_gap` is 0 and the "
        "recommendation reads 'Assign 2 floating pool employees to cover gap' -- the covered "
        "branch, chosen because `recommendations` is a LIST and an empty one would record no "
        "shape at all. Measured: a genuine shortfall (8/1/20) returns the same nine keys, so the "
        "choice is about populating that list, not about which keys exist.",
    ),
    "floating_pool_available": ParamSpec(
        key="floating_pool_available",
        kind=Kind.LITERAL,
        literal="5",
        note="More than the two-employee shortfall above, so the pool covers it with slack and "
        "the recommendation names the covered branch -- see `regular_employees`.",
    ),
    "required_employees": ParamSpec(
        key="required_employees",
        kind=Kind.LITERAL,
        literal="10",
        note="Two more than `regular_employees`, creating the coverable shortfall -- see that "
        "spec. NOTE for the response-model pass: this route returns `coverage_percent` as a JSON "
        "STRING ('100.00'), the Decimal-under-Pydantic leak #248 fixed on quality-score. Its "
        "model should declare that field `float`.",
    ),
    # --- resolvable, but the answer is empty under this seed ------------
    "client_id@onboarding": replace(
        REGISTRY["client_id"],
        key="client_id@onboarding",
        note=(
            "Same entity and same seeded row as the path-param `client_id` -- reusing "
            "REGISTRY['client_id']'s own field values rather than retyping the query, so a "
            "change to how a client id is found cannot leave this route resolving a stale one. "
            "Routed separately only because EFFECTIVELY_REQUIRED_QUERY_PARAMS has to name a "
            "spec, and `client_id` alone already routes to the BLOCKED variance entry."
        ),
    ),
    "client_id@capacity-variance": ParamSpec(
        key="client_id@capacity-variance",
        kind=Kind.BLOCKED,
        table="CAPACITY_KPI_COMMITMENT",
        reason=(
            "CAPACITY_KPI_COMMITMENT has zero seeded rows, so KPIIntegrationService."
            "calculate_variance_detailed returns `[]` for EVERY client -- verified by asking "
            "with a real seeded client_id, not inferred. The id resolves fine; there is "
            "nothing for it to find. Recording that `[]` would put an entry with no fields in "
            "the golden master, where `test_no_route_lost_a_field` would compare it against "
            "itself forever and `ALLOWLIST` would look ready to be closed from it -- the "
            "'unblocked into no-entries-found' trap #244 hit. Declared instead, with the "
            "staleness gate in test_capture_integrity counting this table's rows every run, so "
            "seeding commitments promotes the route rather than being ignored."
        ),
    ),
}


#: Golden routes that DO have required query params and are deliberately left
#: unrequested, so their entries stay `<status:422>` until the write-capture
#: harness (S4) can ask them properly.
#:
#: Every one is a mutation, and the reason is not "mutations are hard": the
#: capture isolates a mutating route against a restored snapshot only when it
#: carries a PATH param (`param_specs.MUTATING_METHODS`, `capture_isolated`).
#: A paramless POST supplied with query params would run inside the READ pass
#: and leave its writes behind for every route captured after it -- so
#: supplying them is not a smaller step towards S4, it is a regression in
#: capture isolation. Most also need a request body, which is S4's actual
#: subject.
#:
#: Gated two-sided by
#: `test_query_resolution.test_deferred_routes_are_exactly_the_mutating_ones`:
#: a GET that lands here, or a mutation that escapes it, fails by name.
DEFERRED_TO_WRITE_CAPTURE: FrozenSet[str] = frozenset(
    {
        # Needs prerequisite DATA, not a body: CAPACITY_SCENARIO has zero
        # seeded rows, so the only 2xx it can give is `[]` -- an entry with no
        # fields, which `ALLOWLIST` would then look ready to close from. The
        # "unblocked into no-entries-found" trap #244 hit.
        "POST /api/capacity/scenarios/compare",
        # Shares DEMO-HOURLY-WO-0001 with the transition route above and drives
        # it to a terminal status. Both in one capture would make the pair
        # order-dependent, and its response recurses into element 0 only, so a
        # single body cannot capture both the success and failure branches.
        "POST /api/workflow/bulk-transition",
        # Needs a token minted at REQUEST time from the live SECRET_KEY. A
        # checked-in literal is green locally and red in CI, which is worse
        # than not capturing it.
        "POST /api/auth/reset-password",
        # multipart/form-data, not JSON. `kwargs["json"]` cannot express an
        # UploadFile; the registry would need a `files=` shape first.
        "POST /api/defect-types/upload/{client_id}",
        # Sends real email. Deliberately left until the transport can be
        # stubbed for capture -- a decision taken separately from this layer.
        "POST /api/reports/email-config/test",
        "POST /api/reports/send-manual",
        # Wants two ids that must agree (client_id and employee_id) and the
        # existing employee spec resolves a DIFFERENT client's employee. Needs
        # an `employee_id@client-consistent` spec first, exactly as
        # mark-all-present needed one for shift_id.
        "POST /api/attendance/bulk",
    }
)

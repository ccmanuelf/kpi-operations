"""WHAT each path param resolves to. The HOW lives in `param_resolution.py`.

Split out purely for size: this half is a declaration -- one entry per path
param that appears in a golden master key, plus the two collision tables and
the two behavioural declarations that go with them -- and it grew past the
500-line limit sitting next to the resolver.

Read `param_resolution.py`'s docstring first; it explains the defect all of
this exists to close, and the DERIVE-DO-NOT-HARDCODE rule that every
`SEEDED_ROW` entry below obeys.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple


class Kind(Enum):
    SEEDED_ROW = "seeded_row"
    LITERAL = "literal"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ParamSpec:
    """How one `(param_name, route_family)` pair resolves.

    `table` is required for SEEDED_ROW (so a seeder regression names the table
    it expected rows in) and for BLOCKED (so `test_param_resolution`'s
    staleness gate can assert the table is STILL empty, and go red the moment
    the seeder starts writing it). It is meaningless for LITERAL, where the
    param is not a row id.
    """

    key: str
    kind: Kind
    table: Optional[str] = None
    sql: Optional[str] = None
    literal: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None
    #: What to substitute when asking "does this route's answer depend on this
    #: param?" -- LITERAL only, and only where the question makes sense.
    #:
    #: A SEEDED_ROW param needs no declaration: an id that cannot exist is
    #: derived from the real one's shape. For a LITERAL there IS no id, so
    #: "an id that cannot exist" is a category error -- feeding `NO-SUCH-ID`
    #: to `{kpi_type}` reaches `raise ValueError(f"Unknown KPI type: ...")`
    #: and prints a real traceback inside a green run, which teaches readers
    #: to ignore tracebacks. Left None, the param is not substituted at all.
    #:
    #: `{pattern}` is the exception and carries one, because there the
    #: substitution IS the question being asked: the param is a free-form
    #: cache-key prefix, so "does the shape depend on the prefix?" is exactly
    #: what the probe should ask. Without it that route would be compared
    #: against itself -- a vacuous pass, which
    #: `test_a_2xx_is_proof_the_id_was_right_except_where_declared` refuses.
    bogus: Optional[str] = None


#: param name -> ordered (path fragment, spec key). First match wins; a param
#: listed here whose route matches NO fragment raises rather than falling back
#: to the bare param name.
#:
#: These four names each mean two unrelated entities depending on the route
#: family, so keying the registry on the param name alone is a guaranteed
#: wrong-entity capture. `catalog_id` is the sharpest: same param name, same
#: COLUMN name, two tables (`HOLD_STATUS_CATALOG` / `HOLD_REASON_CATALOG`),
#: both plain autoincrement ints starting at 1, both fully seeded.
#:
#: Measured against the harness's own seed, because the received wisdom that
#: this "404s today only by luck of row counts" is FALSE: statuses hold ids
#: 1-16, reasons hold 1-12, and 12 values exist in both. Feeding a status id
#: to the reasons route returns a wrong-entity 204 RIGHT NOW, for 12 of the 16
#: possible picks, including the id both specs actually resolve to (1).
#:
#: And the golden master cannot see it. Both routes record `<non-json>` -- a
#: 204 with an empty body -- so if family routing broke and both resolved
#: against one table, the golden file would not move a single byte. A reader
#: must not take those two green entries as evidence the routing works.
#:
#: TWO structural tests check it, and it takes both, because routing to the
#: right spec and that spec reading the right table are separate failures:
#:   * `test_catalog_id_resolves_to_a_different_table_per_route_family`
#:     -- each route reaches its own spec, and the two name different tables;
#:   * `test_a_seeded_spec_reads_the_table_it_names`
#:     -- the table a spec NAMES is the table its SQL queries. Without this
#:     one, the first is a check on a decorative label: resolution executes
#:     `spec.sql` and never reads `spec.table` at all, so the reason spec
#:     could read HOLD_STATUS_CATALOG with its label untouched and the whole
#:     suite stayed green. Verified, then closed.
#:
#: The `@capacity` / `@capacity-calendar` keys are deliberately NOT registered:
#: no capacity route carries a path param in the golden master's 164, so a
#: lookup landing on one means a new route family showed up against an
#: already-colliding name -- exactly the case this table exists to catch. An
#: unregistered key raises `UnresolvableParam`, loudly, rather than silently
#: resolving against the wrong table.
FAMILY_ROUTER: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "line_id": (
        ("/api/capacity/lines/", "line_id@capacity"),
        ("/api/production-lines/", "line_id@production-lines"),
        ("/api/employee-line-assignments/", "line_id@production-lines"),
    ),
    "scenario_id": (
        ("/api/capacity/scenarios/", "scenario_id@capacity"),
        ("/api/v2/simulation/scenarios/", "scenario_id@simulation"),
    ),
    "entry_id": (
        ("/api/capacity/calendar/", "entry_id@capacity-calendar"),
        ("/api/production/", "entry_id@production"),
        ("/api/kpi/calculate/", "entry_id@production"),
    ),
    "catalog_id": (
        ("/api/hold-catalogs/statuses/", "catalog_id@hold-status"),
        ("/api/hold-catalogs/reasons/", "catalog_id@hold-reason"),
    ),
}


def _seeded(key: str, table: str, sql: str, note: Optional[str] = None) -> ParamSpec:
    return ParamSpec(key=key, kind=Kind.SEEDED_ROW, table=table, sql=sql, note=note)


def _literal(key: str, literal: str, note: Optional[str] = None, bogus: Optional[str] = None) -> ParamSpec:
    return ParamSpec(key=key, kind=Kind.LITERAL, literal=literal, note=note, bogus=bogus)


def _blocked(key: str, table: str, reason: str) -> ParamSpec:
    return ParamSpec(key=key, kind=Kind.BLOCKED, table=table, reason=reason)


#: Every path param that appears in a golden master key, and nothing else.
#: `test_param_resolution` gates both directions: an unregistered param fails
#: the capture, and a registered key no golden route uses fails as dead weight.
#:
#: Several param names LIE about their column. `inspection_id` has no such
#: column anywhere in the schema (it is `QUALITY_ENTRY.quality_entry_id`);
#: `hold_id`, `entry_id`, `downtime_id` and `attendance_id` are all
#: `<table>_entry_id`; `defect_type_id` is `{client}-DT-{code}`, NOT the bare
#: defect code stored in `DEFECT_DETAIL.defect_type`. The SQL below is the
#: authority, not the param name.
REGISTRY: Dict[str, ParamSpec] = {
    "client_id": _seeded(
        "client_id",
        "CLIENT",
        "SELECT client_id FROM CLIENT ORDER BY client_id LIMIT 1",
        note="Uniform across all 13 client-scoped routes EXCEPT "
        "DELETE /api/kpi-thresholds/{client_id}/{kpi_key}, whose two halves are a "
        "composite PK and are resolved together -- see COMPOSITES.",
    ),
    "work_order_id": _seeded(
        "work_order_id",
        "WORK_ORDER",
        "SELECT work_order_id FROM WORK_ORDER ORDER BY work_order_id LIMIT 1",
    ),
    "employee_id": _seeded(
        "employee_id",
        "EMPLOYEE",
        "SELECT MIN(employee_id) FROM EMPLOYEE",
        note="Polymorphic by route: every route but one declares `employee_id: int`, while "
        "GET /api/qr/employee/{employee_id}/image declares `str` and tries int() first, "
        "falling back to EMPLOYEE.employee_code. The numeric PK stringified satisfies both, "
        "so this is ONE spec rather than a family split that would resolve to the same value.",
    ),
    "line_id@production-lines": _seeded(
        "line_id@production-lines",
        "PRODUCTION_LINE",
        "SELECT line_id FROM PRODUCTION_LINE ORDER BY line_id LIMIT 1",
    ),
    "entry_id@production": _seeded(
        "entry_id@production",
        "PRODUCTION_ENTRY",
        "SELECT production_entry_id FROM PRODUCTION_ENTRY ORDER BY production_entry_id LIMIT 1",
    ),
    "hold_id": _seeded(
        "hold_id",
        "HOLD_ENTRY",
        "SELECT hold_entry_id FROM HOLD_ENTRY ORDER BY hold_entry_id LIMIT 1",
        note="HOLD_ENTRY rows are RNG-gated per eligible work order: smoke + seed=7 yields "
        "zero holds, smoke + seed=1234 yields 5. Reading the id back is the only safe option.",
    ),
    "shift_id": _seeded("shift_id", "SHIFT", "SELECT shift_id FROM SHIFT ORDER BY shift_id LIMIT 1"),
    "catalog_id@hold-status": _seeded(
        "catalog_id@hold-status",
        "HOLD_STATUS_CATALOG",
        "SELECT catalog_id FROM HOLD_STATUS_CATALOG ORDER BY catalog_id LIMIT 1",
    ),
    "catalog_id@hold-reason": _seeded(
        "catalog_id@hold-reason",
        "HOLD_REASON_CATALOG",
        "SELECT catalog_id FROM HOLD_REASON_CATALOG ORDER BY catalog_id LIMIT 1",
    ),
    "user_id": _seeded(
        "user_id",
        "USER",
        'SELECT user_id FROM "USER" ORDER BY user_id LIMIT 1',
        note="Resolves to USR-DEMO-ADMIN, which is safe to DELETE only because the capture "
        "authenticates as the _mock_admin SimpleNamespace (user_id='USER-SMOKE'), so the "
        "route's self-delete guard is not tripped. Switching the harness to a real seeded "
        "identity would need this spec to target a different user.",
    ),
    "downtime_id": _seeded(
        "downtime_id",
        "DOWNTIME_ENTRY",
        "SELECT downtime_entry_id FROM DOWNTIME_ENTRY ORDER BY downtime_entry_id LIMIT 1",
    ),
    "attendance_id": _seeded(
        "attendance_id",
        "ATTENDANCE_ENTRY",
        "SELECT attendance_entry_id FROM ATTENDANCE_ENTRY ORDER BY attendance_entry_id LIMIT 1",
    ),
    "inspection_id": _seeded(
        "inspection_id",
        "QUALITY_ENTRY",
        "SELECT quality_entry_id FROM QUALITY_ENTRY ORDER BY quality_entry_id LIMIT 1",
    ),
    "defect_detail_id": _seeded(
        "defect_detail_id",
        "DEFECT_DETAIL",
        "SELECT defect_detail_id FROM DEFECT_DETAIL ORDER BY defect_detail_id LIMIT 1",
    ),
    "defect_type_id": _seeded(
        "defect_type_id",
        "DEFECT_TYPE_CATALOG",
        "SELECT defect_type_id FROM DEFECT_TYPE_CATALOG ORDER BY defect_type_id LIMIT 1",
    ),
    "product_id": _seeded(
        "product_id",
        "PRODUCT",
        "SELECT product_id FROM PRODUCT ORDER BY product_id LIMIT 1",
        note="GET /api/inference/cycle-time/{product_id} is int-strict (a product_code gives "
        "422, not 404); the QR image route accepts either. The integer PK satisfies both.",
    ),
    "kpi_type": _literal(
        "kpi_type",
        "efficiency",
        note="A KPIType enum member, not a row. GET /api/predictions/{kpi_type} 400s under the "
        "smoke profile whatever value is passed (14 seeded days < its hardcoded 30-point "
        "floor), which is a profile-density problem, not an id problem.",
    ),
    "dataset": _literal("dataset", "production", note="A pivot dataset name; anything else is 422."),
    "metric": _literal("metric", "efficiency", note="A KPI metric name on /api/kpi/{metric}/cause."),
    "pattern": _literal(
        "pattern",
        "client_config:",
        bogus="no-such-prefix:",
        note="An in-process cache-key PREFIX, not an entity. This route can never 404, so the "
        "old literal-brace capture returned a perfectly plausible 200 with "
        "entries_invalidated=0; the real prefix invalidates 2.",
    ),
    "break_id": _blocked(
        "break_id",
        "BREAK_TIME",
        "BREAK_TIME has zero seeded rows in both the smoke and full profiles. Depends only on "
        "SHIFT, which IS seeded, so it is cheap to add -- Task 8d, not a harness workaround.",
    ),
    "coverage_id": _blocked(
        "coverage_id",
        "shift_coverage",
        "shift_coverage has zero seeded rows and is absent from both seed/coverage.py's SEEDED "
        "set and its NOT_SEEDED dict, i.e. outside the seeder's declared scope entirely.",
    ),
    "equipment_id": _blocked(
        "equipment_id",
        "EQUIPMENT",
        "EQUIPMENT has zero seeded rows; named in seed/cli.py's never-written list.",
    ),
    "filter_id": _blocked(
        "filter_id",
        "SAVED_FILTER",
        "SAVED_FILTER is user-authored state, deliberately never seeded. Unique in this "
        "codebase for being scoped by user_id rather than client_id, so every route 404s for "
        "a non-owner INCLUDING an admin -- seeding a row would not unblock it either. Only "
        "request chaining (POST a filter as the capturing identity) ever could.",
    ),
    "pool_id": _blocked(
        "pool_id",
        "FLOATING_POOL",
        "FLOATING_POOL has zero seeded rows; test_cli_derived_sets.py asserts it is not in "
        "SEEDED. Not to be confused with EMPLOYEE.is_floating_pool, a bool the seeder writes.",
    ),
    "job_id": _seeded(
        "job_id",
        "PRODUCTION_ENTRY",
        "SELECT job_id FROM PRODUCTION_ENTRY WHERE job_id IS NOT NULL ORDER BY job_id LIMIT 1",
        note="Read from PRODUCTION_ENTRY, not from JOB, and that is the whole point of the "
        "entry. S3 seeds a full routing, so most jobs are steps no shift ran; five of the six "
        "GET /api/jobs/{job_id}/* routes join PRODUCTION_ENTRY / QUALITY_ENTRY on job_id and "
        "NEVER on work_order_id, so a job taken from JOB itself captures their empty-set "
        "branch -- a 200 with fewer keys, recorded as if it were the route's answer. A job "
        "production actually ran carries quality entries for the same shift too (the emitter "
        "names one step for both), so this one id reaches every one of the six.",
    ),
    "part_number": _blocked(
        "part_number",
        "PART_OPPORTUNITIES",
        "PART_OPPORTUNITIES has zero seeded rows. Note the trap: part_number VALUES exist on "
        "PRODUCT and JOB, so a resolver that greps for the value finds a real one and gets a "
        "confident 404 -- the value is real, the table is empty.",
    ),
    "scenario_id@simulation": _blocked(
        "scenario_id@simulation",
        "SIMULATION_SCENARIO",
        "SIMULATION_SCENARIO has zero seeded rows; named in seed/cli.py among the USER-FK " "tables the seeder avoids.",
    ),
}


#: Route template -> (one SQL, the params it fills in SELECT order).
#:
#: `kpi_key` is meaningless without its paired `client_id`: they are a composite
#: PK on KPI_THRESHOLD, so resolving the two halves from two independent
#: queries could pick a `kpi_key` that does not exist for that `client_id` --
#: a 404 that looks exactly like a bad id. One query, one row, both halves.
COMPOSITES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "/api/kpi-thresholds/{client_id}/{kpi_key}": (
        "SELECT client_id, kpi_key FROM KPI_THRESHOLD ORDER BY client_id, kpi_key LIMIT 1",
        ("client_id", "kpi_key"),
    ),
}


#: Routes whose recorded 2xx is NOT evidence that the id was right.
#:
#: The brief's requirement, in its own words: "the harness must record
#: empty-body-ok per route rather than treating a 200 as proof the id was
#: right." For all but these seven, a 2xx IS that proof -- probe them with a
#: nonexistent id and the shape changes (usually to `<status:404>`, twice to a
#: thinner shape because an empty result set stops contributing nested keys).
#: For the seven below it is not: a nonexistent id yields a byte-identical
#: shape, so the golden entry would look exactly the same had resolution
#: failed completely.
#:
#: That is the enshrined-accident mechanism this task exists to close, and
#: prose in a report does not close it -- no test reads a report. It is
#: declared here and pinned TWO-SIDED by
#: `test_a_2xx_is_proof_the_id_was_right_except_where_declared`: every member
#: must still be id-insensitive, and every non-member that answered 2xx must
#: still discriminate. One-sided would pass with this set empty.
#:
#: Why each one cannot discriminate (verified by probing, not by reading):
#:   cache/invalidate  the param is a cache-key PREFIX, not an entity; the
#:                     response is a fixed envelope plus a count.
#:   capacity/workbook an envelope of 13 empty `capacity_*` lists plus
#:                     hardcoded `dashboard_inputs` defaults -- no client data
#:                     reaches it at all, so no client can change it.
#:   client-config/effective  falls back to system defaults for an unknown
#:                     client rather than 404ing.
#:   floating-pool/check-availability  answers "available" for any employee
#:                     number, with `current_assignment` and `conflict_dates`
#:                     both null -- so the recorded shape is a FLOOR, and a
#:                     response model built from it alone under-declares.
#:   inference/cycle-time  LEFT this set on 2026-08-27. It used to echo the
#:                     path input back as `product_id` and fall through to a
#:                     global average for any id. The cross-tenant fix (#238)
#:                     made it look the product up and 404 when absent, then
#:                     verify_client_access on the owner -- so it now
#:                     discriminates and must NOT be declared id-insensitive.
#:                     The two-sided gate caught this on rebase: the
#:                     declaration was true when written and stopped being
#:                     true, which is exactly what it exists to detect.
#:   workflow/.../stage-durations  echoes client_id, and `stage_durations` is
#:                     `[]` even for a real client (a seed-data gap).
#:   workflow/config   static per-status config, echoes client_id, never 404s.
NEVER_404 = frozenset(
    {
        "DELETE /api/cache/invalidate/{pattern}",
        "GET /api/capacity/workbook/{client_id}",
        "GET /api/client-config/{client_id}/effective",
        "GET /api/floating-pool/check-availability/{employee_id}",
        "GET /api/workflow/analytics/{client_id}/stage-durations",
        "GET /api/workflow/config/{client_id}",
    }
)


#: A request that can change the seeded database must not be allowed to change
#: it for every route captured after it. The capture replays these against a
#: freshly restored snapshot -- see `conftest.py`'s `harness` fixture and
#: `capture.capture_isolated`.
#: Only path-param routes qualify: the paramless mutations were already running
#: in this order before this module existed, and re-ordering them would churn
#: entries this task has no business touching.
MUTATING_METHODS = frozenset({"DELETE", "POST", "PUT", "PATCH"})

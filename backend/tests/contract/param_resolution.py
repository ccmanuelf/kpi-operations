"""Resolve a route template's path params to REAL ids from the seeded database.

`capture_all`'s docstring has always stated the hazard exactly: *"the caller
owns id resolution -- the harness deliberately does not guess ids, because a
wrong id yields a 404 whose shape is recorded as if it were the real answer."*
But nothing ever DID the resolving. `loose_routes()` hands back `(method,
route.path, {})` -- the raw template -- so every path-param route in the golden
master was captured by requesting a URL with literal braces in it, e.g.
`GET /api/workflow/statistics/%7Bclient_id%7D/status-distribution`.

Measured across the golden master's 63 path-param entries before this module
existed: 32 `<status:404>`, 22 `<status:422>`, 1 `<status:400>`, and 8 that
recorded a 200 shape for an entity whose id was the literal string
`{client_id}`. The 8 are the dangerous ones -- `status-distribution` recorded
3 keys where the real answer has 5, silently omitting an entire nested object
(`by_status[].{status,count,percentage}`). A response model built from that
entry would drop three fields from production responses.

This module is the missing half. Three code paths, not 49 special cases:

  SEEDED_ROW  one SELECT against the DB the harness just seeded; fail loudly
              if it returns nothing (that is a SEEDER regression, not a
              missing feature, and gets its own louder message).
  LITERAL     a fixed string; the param is not a row id at all (a KPI type
              name, a dataset name, a cache-key prefix).
  BLOCKED     no value can produce a meaningful answer today, because the
              backing table has zero seeded rows. Declared, with a reason,
              never guessed. Extending the seeder is Task 8d, not this module.

DERIVE, DO NOT HARDCODE. Every SEEDED_ROW value comes from executing its SQL
against the live seeded DB, never from a pasted literal, for reasons that are
not theoretical:

  * `seed/identity.py`'s `IntPkAllocator` starts every integer PK at
    `MAX(pk) + 1` of the LIVE transaction, so `employee_id`, `line_id`,
    `shift_id`, `product_id` and both `catalog_id` spaces are 1 only on a
    pristine database.
  * String PKs embed a calendar date derived from `as_of`
    (`DEMO-HOURLY-PE-2026-08-12-0-0`), and `DOWNTIME_ENTRY` / `ATTENDANCE_ENTRY`
    additionally embed internal auto-increment line/shift PKs
    (`DT-20260812-1-1`) -- those cannot be reconstructed from a format string
    at all, only read back.
  * `HOLD_ENTRY` rows exist only for particular RNG draws: smoke + seed=7
    produces ZERO holds; smoke + seed=1234 produces 5.

A stale literal on a route that cannot 404 is the worst case of all: a green
test capturing an empty body. See `capture.capture_all`'s brace guard for the
last line of defence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import Engine, text

_PARAM = re.compile(r"\{(\w+)\}")


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


#: param name -> ordered (path fragment, spec key). First match wins; a param
#: listed here whose route matches NO fragment raises rather than falling back
#: to the bare param name.
#:
#: These four names each mean two unrelated entities depending on the route
#: family, so keying the registry on the param name alone is a guaranteed
#: wrong-entity capture. `catalog_id` is the sharpest: same param name, same
#: COLUMN name, two tables (`HOLD_STATUS_CATALOG` / `HOLD_REASON_CATALOG`),
#: both plain autoincrement ints starting at 1, both fully seeded, ranges
#: overlapping. Feeding a status id to the reasons route 404s today only by
#: luck of row counts (16 vs 12); the moment the smaller table grows, it
#: returns a valid 200 for the wrong entity and the golden master enshrines
#: it. Nothing downstream can detect that.
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


def _literal(key: str, literal: str, note: Optional[str] = None) -> ParamSpec:
    return ParamSpec(key=key, kind=Kind.LITERAL, literal=literal, note=note)


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
    "job_id": _blocked(
        "job_id",
        "JOB",
        "JOB has zero seeded rows; named in seed/cli.py's never-written list. Blocks 8 of the "
        "15 blocked routes -- the highest route-count payoff of any single seeder gap.",
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


#: A request that can change the seeded database must not be allowed to change
#: it for every route captured after it. The capture replays these against a
#: freshly restored snapshot -- see test_golden_master.py's `harness` fixture.
#: Only path-param routes qualify: the paramless mutations were already running
#: in this order before this module existed, and re-ordering them would churn
#: entries this task has no business touching.
MUTATING_METHODS = frozenset({"DELETE", "POST", "PUT", "PATCH"})


class UnresolvableParam(Exception):
    """Raised when a path param cannot be resolved. Never swallowed.

    The whole defect this module repairs is that an unresolved param silently
    produced a recordable answer. Falling back to a literal-brace URL is the
    one outcome that must be impossible.
    """

    def __init__(self, key: str, route: str, reason: str) -> None:
        super().__init__(f"{route}: cannot resolve {{{key.split('@')[0]}}} -- {reason}")
        self.key = key
        self.route = route
        self.reason = reason


def spec_key(param: str, route_path: str) -> str:
    """`param@family` for a collision-prone name, the bare name otherwise."""
    routes = FAMILY_ROUTER.get(param)
    if routes is None:
        return param
    for fragment, key in routes:
        if fragment in route_path:
            return key
    raise UnresolvableParam(
        param,
        route_path,
        f"{param!r} is a collision-prone name with no FAMILY_ROUTER entry matching this route. "
        "Add the new route family explicitly -- falling back to the bare name would resolve it "
        "against another family's table and return a wrong-entity 200.",
    )


def params_of(route_path: str) -> List[str]:
    return _PARAM.findall(route_path)


def blocked_shape(key: str) -> List[str]:
    """The golden entry for a route no id can reach.

    Deliberately NOT a `<status:...>` placeholder: a status says "the route
    answered and this is what it said", which is a lie when the request was
    never sent. The reason lives in `REGISTRY[key].reason` rather than in the
    string so that editing a reason does not churn the golden file.
    """
    return [f"<blocked:{key}>"]


class Resolver:
    """Turns a route template into a concrete URL, or raises saying why not."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._cache: Dict[str, str] = {}

    def _scalar(self, sql: str) -> Optional[object]:
        with self._engine.connect() as conn:
            return conn.execute(text(sql)).scalar()

    def resolve(self, param: str, route_path: str) -> str:
        key = spec_key(param, route_path)
        spec = REGISTRY.get(key)
        if spec is None:
            raise UnresolvableParam(key, route_path, f"no ParamSpec registered for {key!r}")
        if spec.kind is Kind.BLOCKED:
            raise UnresolvableParam(key, route_path, spec.reason or "")
        if spec.kind is Kind.LITERAL:
            return str(spec.literal)
        if key not in self._cache:
            value = self._scalar(str(spec.sql))
            if value is None:
                # Deliberately a DIFFERENT, louder message than the BLOCKED
                # case. A blocked param is an expected, documented gap; a
                # SEEDED_ROW param that finds nothing means the seeder stopped
                # writing a table it is supposed to write. Collapsing the two
                # into one "not found" is how a broken seeder gets mistaken
                # for a known gap and quietly skipped for months.
                raise UnresolvableParam(
                    key,
                    route_path,
                    f"SEEDED_ROW spec found no row in {spec.table} via {spec.sql!r}. "
                    "The seed no longer populates this table -- fix the seeder, not this spec.",
                )
            self._cache[key] = str(value)
        return self._cache[key]

    def url_for(self, route_path: str) -> str:
        """The concrete URL for `route_path`, with every param substituted."""
        values: Dict[str, str] = {}
        composite = COMPOSITES.get(route_path)
        if composite is not None:
            sql, names = composite
            with self._engine.connect() as conn:
                row = conn.execute(text(sql)).first()
            if row is None:
                raise UnresolvableParam(
                    "+".join(names),
                    route_path,
                    f"composite spec found no row via {sql!r}. Fix the seeder, not this spec.",
                )
            values.update({name: str(value) for name, value in zip(names, row)})

        url = route_path
        for param in params_of(route_path):
            # `param in values`, not `values.get(param) or ...`: a composite half
            # that legitimately resolved to a falsy string would otherwise fall
            # through to the single-param path and break the atomicity the
            # composite exists to guarantee.
            value = values[param] if param in values else self.resolve(param, route_path)
            url = url.replace("{" + param + "}", value)
        return url


@dataclass(frozen=True)
class CapturePlan:
    """What to request, in what order, and what could not be requested."""

    #: (method, route template, request kwargs) for routes safe to run in one pass.
    requests: List[Tuple[str, str, dict]] = field(default_factory=list)
    #: Same, for mutating path-param routes: each is replayed against a
    #: freshly restored snapshot so it cannot poison its successors.
    isolated: List[Tuple[str, str, dict]] = field(default_factory=list)
    #: route key -> concrete URL. Never contains a brace; `capture_all` asserts it.
    urls: Dict[str, str] = field(default_factory=dict)
    #: route key -> the REGISTRY key that blocked it.
    blocked: Dict[str, str] = field(default_factory=dict)


def plan_capture(route_keys: Iterable[str], resolver: Resolver) -> CapturePlan:
    """Resolve every route key up front, before a single request is issued.

    Up front and not lazily, for two reasons. An id read back mid-capture would
    see a database an earlier mutating route had already changed; and the
    isolated phase restores a pristine snapshot before each request, which
    makes every id resolved from the pristine state valid again -- but only if
    they were resolved from it in the first place.
    """
    plan = CapturePlan()
    for route_key in route_keys:
        method, path = route_key.split(" ", 1)
        try:
            plan.urls[route_key] = resolver.url_for(path)
        except UnresolvableParam as exc:
            plan.blocked[route_key] = exc.key
            continue
        target = plan.isolated if (method in MUTATING_METHODS and "{" in path) else plan.requests
        target.append((method, path, {}))
    return plan

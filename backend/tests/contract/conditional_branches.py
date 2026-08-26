"""Routes whose response shape is CONDITIONAL: some field(s) are absent, not
null, on a branch the golden master's smoke seed cannot reach (a scope that
doesn't narrow, a client with zero matching rows). `response_model_exclude_unset=True`
is what makes those fields genuinely absent instead of an explicit `null` the
route never used to emit.

`EXCLUDE_UNSET_ROUTES` is declared here and gated TWO-SIDED by
`test_exclude_unset_flag_matches_the_declared_registry` in
`test_conditional_branches.py`: every declared member must actually carry the
flag on its route, and every route that carries the flag must be declared
here. A one-sided version (checking only that members carry the flag) would
pass with this dict empty, or with a route quietly gaining the flag without
anyone writing down why -- which is the same enshrined-accident risk
`NEVER_404` (`param_specs.py`) exists to close for id-insensitivity, applied
to this different claim.

A declaration alone is not a guarantee: registration only proves the flag is
inspectable and complete, never that the omitted branch's shape is right.
Each entry's `forcing_test` field says, AT A GLANCE, whether something
actually proves that: `None` means the branch is registered but UNFORCED --
real, disclosed debt, not silently-assumed coverage -- and a name means a
test in `test_conditional_branches.py` builds that exact branch and pins its
key set. Do not read `forcing_test` as a claim the test also checks the
right THING: a naive version of `average-times`' own forcing test round-
tripped its branch through the very model it was checking and was blind to
an added field as a result (Pydantic silently discards what a model does not
declare) -- see that test's docstring. A forcing test is only as good as
checking the RAW value before anything normalises it, not just the
validated one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from backend.tests.contract.capture import flatten_api_routes


@dataclass(frozen=True)
class ExcludeUnsetEntry:
    """`reason` names the producing function and the branch that omits keys.
    `forcing_test` is the `test_conditional_branches.py` function name that
    builds that branch and pins its exact key set, or `None` if no such test
    exists yet -- see the module docstring for what `None` does and does not
    mean.
    """

    reason: str
    forcing_test: Optional[str]


#: route -> ExcludeUnsetEntry. See the module docstring for the two-sided
#: gate this is checked against and what `forcing_test` promises.
EXCLUDE_UNSET_ROUTES: Dict[str, ExcludeUnsetEntry] = {
    "GET /api/kpi/otd": ExcludeUnsetEntry(
        reason=(
            "true_otd/standard_otd/late_counts/justified_by_reason are added only "
            "when scope resolves to exactly one client (routes/kpi/otd.py::calculate_otd_kpi) "
            "-- absent, not null, when the caller sees all clients. Task 7 -- pre-dates this "
            "registry; see OTDSummary in schemas/kpi_contracts.py for the manual verification "
            "on record."
        ),
        forcing_test=None,
    ),
    "GET /api/kpi/dashboard/aggregated": ExcludeUnsetEntry(
        reason=(
            "Each of efficiency/performance/quality/availability/absenteeism/wip_aging/otd "
            "narrows to just current/target/error on its own SQLAlchemyError/Exception "
            "fallback (routes/kpi/dashboard.py::get_aggregated_dashboard) -- the other fields "
            "are absent, not null, on that path. Task 7 -- pre-dates this registry; see "
            "AggregatedDashboard in schemas/kpi_contracts.py for the manual verification on "
            "record."
        ),
        forcing_test=None,
    ),
    "GET /api/workflow/analytics/{client_id}/average-times": ExcludeUnsetEntry(
        reason=(
            "overdue_count/overdue_percentage are absent, not null, when a client has zero "
            "matching work orders (calculations/elapsed_time.py::calculate_client_average_times). "
            "Task 9."
        ),
        forcing_test="test_average_times_empty_orders_branch_omits_overdue_keys",
    ),
}


def declared_exclude_unset_routes(app) -> frozenset:
    """The empirical side of the gate: every `/api` route that actually has
    `response_model_exclude_unset=True` set, regardless of what anyone wrote
    down. Mirrors `capture.loose_routes`'s route-walking shape, `flatten_api_routes`
    included -- see that function's docstring for why a plain `app.routes`
    walk sees zero routes under this repo's pinned FastAPI.
    """
    found = set()
    for route in flatten_api_routes(app.routes):
        if not route.path.startswith("/api"):
            continue
        if not route.response_model_exclude_unset:
            continue
        for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
            found.add(f"{method} {route.path}")
    return frozenset(found)

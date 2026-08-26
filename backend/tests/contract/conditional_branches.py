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

A declaration alone is not a guarantee: THIS module makes exclude_unset
usage inspectable and complete, but it does not by itself prove the omitted
branch's shape is right. That is `test_conditional_branches.py`'s forcing
tests' job -- see that module's docstring for which entries have one.
"""

from __future__ import annotations

from typing import Dict

from fastapi.routing import APIRoute

#: route -> why its response model needs response_model_exclude_unset=True.
#: Each reason names the producing function and the branch that omits keys.
EXCLUDE_UNSET_ROUTES: Dict[str, str] = {
    "GET /api/kpi/otd": (
        "true_otd/standard_otd/late_counts/justified_by_reason are added only "
        "when scope resolves to exactly one client (routes/kpi/otd.py::calculate_otd_kpi) "
        "-- absent, not null, when the caller sees all clients. Task 7. "
        "No forcing test yet (pre-dates this registry) -- see OTDSummary in "
        "schemas/kpi_contracts.py for the manual verification on record."
    ),
    "GET /api/kpi/dashboard/aggregated": (
        "Each of efficiency/performance/quality/availability/absenteeism/wip_aging/otd "
        "narrows to just current/target/error on its own SQLAlchemyError/Exception "
        "fallback (routes/kpi/dashboard.py::get_aggregated_dashboard) -- the other "
        "fields are absent, not null, on that path. Task 7. No forcing test yet "
        "(pre-dates this registry) -- see AggregatedDashboard in schemas/kpi_contracts.py "
        "for the manual verification on record."
    ),
    "GET /api/workflow/analytics/{client_id}/average-times": (
        "overdue_count/overdue_percentage are absent, not null, when a client has "
        "zero matching work orders (calculations/elapsed_time.py::calculate_client_average_times). "
        "Task 9. Forced by "
        "test_conditional_branches.py::test_average_times_empty_orders_branch_omits_overdue_keys."
    ),
}


def declared_exclude_unset_routes(app) -> frozenset:
    """The empirical side of the gate: every `/api` route that actually has
    `response_model_exclude_unset=True` set, regardless of what anyone wrote
    down. Mirrors `capture.loose_routes`'s route-walking shape.
    """
    found = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if not route.response_model_exclude_unset:
            continue
        for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
            found.add(f"{method} {route.path}")
    return frozenset(found)

"""Which soft-deletable tables are hidden automatically, and which are not.

A soft delete that does not hide the row is not a delete. This module is the
single declaration of *how* each soft-deletable table is hidden, so that the
answer is written down rather than inferred from whichever query happened to
remember a filter.

Three states, no fourth:

``AUTO_FILTERED_TABLES``
    Hidden by the ORM itself — ``backend/db/soft_delete_filter.py`` installs a
    session-wide ``with_loader_criteria`` so *every* ORM read excludes inactive
    rows without any query having to opt in. Seeing inactive rows requires an
    explicit opt-in (``include_inactive``).

``AD_HOC_FILTERED_TABLES``
    The pre-existing pattern: each query filters (or forgets to). Measured on
    ``main``, ``query(Employee)`` has 33 call sites and 4 nearby ``is_active``
    filters; ``query(Product)`` has 29 and 1. So these are *mostly unfiltered*
    today — a real, live defect, tracked as S1b and deliberately not fixed
    here. Moving them under the automatic filter changes what existing reads
    return (a departed employee disappearing from historical attendance would
    move KPIs silently), which needs its own verification pass.

``SOFT_DELETE_WITHOUT_COLUMN``
    CRUD paths that call ``soft_delete()`` against a model that has no
    ``is_active`` column at all. ``soft_delete()`` returns False, the route
    raises 404, and the user is told a row they can see does not exist. This is
    the same defect S1 fixes for the seven transaction tables; these four were
    invisible to the contract harness only because the seeder writes no rows
    for them. Capped by ``SOFT_DELETE_WITHOUT_COLUMN_CAP`` — the number may go
    down when they are fixed, never up.

Every entry is enforced from both sides by
``backend/tests/test_db/test_soft_delete_registry_guards.py``.
"""

from typing import Dict, FrozenSet

#: Hidden automatically by the session-level filter. Kept in lockstep with
#: alembic/versions/0007_transaction_soft_delete.py::TABLES.
AUTO_FILTERED_TABLES: FrozenSet[str] = frozenset(
    {
        "ATTENDANCE_ENTRY",
        "DEFECT_DETAIL",
        "DOWNTIME_ENTRY",
        "FLOATING_POOL",
        "HOLD_ENTRY",
        "JOB",
        "PART_OPPORTUNITIES",
        "PRODUCTION_ENTRY",
        "QUALITY_ENTRY",
        "WORK_ORDER",
        "shift_coverage",
    }
)

#: Soft-deletable, but hidden only where an individual query remembers to
#: filter. Each value says what a resurrected row costs, which is why these are
#: sequenced separately (S1b) rather than folded into a bug fix.
AD_HOC_FILTERED_TABLES: Dict[str, str] = {
    "BREAK_TIME": "S1b: reference row read through SHIFT; a stale break shifts scheduled-hours math",
    "CALCULATION_ASSUMPTION": "S1b: dual-view assumption set; a retired assumption re-entering changes derived metrics",
    "CLIENT": "S1b: tenant record; auto-hiding would strip every client-scoped join of its tenant row",
    "DEFECT_TYPE_CATALOG": "S1b: taxonomy row referenced by historical DEFECT_DETAIL rows that must stay readable",
    "EMPLOYEE": "S1b: 288 attendance rows reference employees; auto-hiding a leaver moves historical KPIs silently",
    "EMPLOYEE_CLIENT_ASSIGNMENT": "S1b: junction row already filtered in its own accessor helpers, nowhere else",
    "EQUIPMENT": "S1b: reference row joined by downtime reads; a hidden machine orphans its downtime history",
    "HOLD_REASON_CATALOG": "S1b: taxonomy row referenced by historical HOLD_ENTRY rows that must stay readable",
    "HOLD_STATUS_CATALOG": "S1b: taxonomy row referenced by historical HOLD_ENTRY rows that must stay readable",
    "PRODUCT": "S1b: 29 query sites, 1 filter; joined by every production read, so hiding rewrites history",
    "PRODUCTION_LINE": "S1b: reference row joined by line-scoped reads across production, downtime and attendance",
    "SHIFT": "S1b: reference row joined by nearly every shift-scoped read; hiding one orphans its entries",
    "SIMULATION_SCENARIO": "S1b: what-if sandbox with its own documented is_active convention in its consumers",
    "USER": "S1b: identity record; is_active already gates authentication, a second meaning would collide",
    "USER_CLIENT_ASSIGNMENT": "S1b: access-control grant read by middleware/client_auth.py with its own filtering",
    "USER_PREFERENCES": "S1b: per-user UI state; a resurrected row is cosmetic, lowest priority of the nineteen",
    "capacity_bom_header": "S1b: capacity-planning sandbox, separate from live operational KPI reads",
    "capacity_production_lines": "S1b: capacity-planning sandbox, separate from live operational KPI reads",
    "capacity_scenario": "S1b: capacity-planning sandbox, separate from live operational KPI reads",
}

#: crud module (import path suffix under backend/) -> table it soft-deletes.
#: The structural side of the gate scans backend/crud for modules importing
#: backend.utils.soft_delete; every one of them must appear here.
SOFT_DELETE_CRUD_TARGETS: Dict[str, str] = {
    "crud/attendance.py": "ATTENDANCE_ENTRY",
    "crud/coverage.py": "shift_coverage",
    "crud/defect_detail.py": "DEFECT_DETAIL",
    "crud/downtime.py": "DOWNTIME_ENTRY",
    "crud/employee/core.py": "EMPLOYEE",
    "crud/floating_pool/core.py": "FLOATING_POOL",
    "crud/hold/core.py": "HOLD_ENTRY",
    "crud/job.py": "JOB",
    "crud/part_opportunities.py": "PART_OPPORTUNITIES",
    "crud/production/core.py": "PRODUCTION_ENTRY",
    "crud/quality.py": "QUALITY_ENTRY",
    "crud/work_order.py": "WORK_ORDER",
}

#: Tables a soft-delete CRUD path writes to that have no is_active column, so
#: the DELETE endpoint answers 404 for every id. Empty, and it must stay empty:
#: this is the S1 defect itself. It held four entries for exactly one review
#: cycle — ``/api/jobs``, ``/api/coverage``, ``/api/floating-pool``,
#: ``/api/part-opportunities`` — which the contract harness had filed as a seed
#: gap rather than a 404 because the seeder writes no rows for them. Same
#: defect, different bucket, so they were folded in rather than shipped as a
#: fix for 7 of 11 instances along a boundary that reflected nothing real.
SOFT_DELETE_WITHOUT_COLUMN: Dict[str, str] = {}

#: Ratchet. May only decrease: each decrement is one endpoint that stopped
#: lying. It has reached zero, so any new entry is a regression, not a backlog
#: item — a DELETE endpoint that answers 404 for every id shipped again.
SOFT_DELETE_WITHOUT_COLUMN_CAP: int = 0

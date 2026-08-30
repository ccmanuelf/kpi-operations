"""What the seeder covers, and what it deliberately does not.

Mirrors backend/audit/registry.py's AUDITED_TABLES / EXCLUDED_TABLES pattern,
which is already guarded in tests. Nothing fails today when a feature ships
without demo data -- nine application sections have a UI, an API surface, and
zero rows. This contract is what turns that into a failing build.

S1b DECLARES ONLY WHAT S1b SEEDS. The completeness half of the gate -- every
Base.metadata table has a home in one bucket or the other -- turns on in S2,
once every table has one. Pre-declaring a table this seeder does not populate
would fail this file's own gate (spec section 8).
"""

from typing import Dict, FrozenSet

#: Every table a materialize() run actually inserts into (verified against
#: writers_master.py's and writers_operations.py's _HANDLERS dispatch tables).
SEEDED: FrozenSet[str] = frozenset(
    {
        "CLIENT",
        "CLIENT_CONFIG",
        "KPI_THRESHOLD",
        "HOLD_REASON_CATALOG",
        "HOLD_STATUS_CATALOG",
        "DEFECT_TYPE_CATALOG",
        "USER",
        "USER_CLIENT_ASSIGNMENT",
        "EMPLOYEE",
        "EMPLOYEE_CLIENT_ASSIGNMENT",
        "EMPLOYEE_LINE_ASSIGNMENT",
        "PRODUCTION_LINE",
        "SHIFT",
        "PRODUCT",
        "WORK_ORDER",
        "WORKFLOW_TRANSITION_LOG",
        "JOB",
        "HOLD_ENTRY",
        "HOLD_STATUS_TRANSITION",
        "ATTENDANCE_ENTRY",
        "PRODUCTION_ENTRY",
        "QUALITY_ENTRY",
        "DEFECT_DETAIL",
        "DOWNTIME_ENTRY",
    }
)

NOT_SEEDED: Dict[str, str] = {
    "TOKEN_BLACKLIST": (
        "JWT revocation ledger written when a user logs out. Fabricated revoked tokens "
        "would demonstrate nothing about the feature and could only mislead a reader into "
        "thinking sessions had been revoked that never existed."
    ),
}

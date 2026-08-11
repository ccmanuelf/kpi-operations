"""What the audit trail covers, and what it deliberately does not.

Scope is human decisions only (spec section 2, owner-ruled 13-table list):
work order and hold lifecycle, identity/tenant records, staffing decisions,
and the taxonomies/thresholds that reshape how history is interpreted.

Everything else in `Base.metadata` is excluded for one of a handful of
reasons: it is high-volume routine data entry rather than a decision, it is
itself an audit/event log (auditing it would double-log), it is a derived or
system-computed result, it is a separate what-if/planning sandbox that does
not touch live operational state, or it is cosmetic per-user UI state.

Both sets are enforced by guards in tests/test_audit/test_registry_guards.py:
every ORM table must appear in exactly one of them.
"""

from typing import Dict, FrozenSet

#: Tables where a person makes a decision worth attributing.
AUDITED_TABLES: FrozenSet[str] = frozenset(
    {
        "WORK_ORDER",  # status transitions, dates, quantities
        "HOLD_ENTRY",  # placing, releasing, re-reasoning holds
        "USER",  # account creation, role changes, activation
        "CLIENT",  # tenant lifecycle
        "CLIENT_CONFIG",  # per-tenant behaviour switches
        "EMPLOYEE",  # workforce record changes
        "EMPLOYEE_CLIENT_ASSIGNMENT",  # who works for which tenant
        "EMPLOYEE_LINE_ASSIGNMENT",  # line staffing decisions
        "KPI_THRESHOLD",  # the targets performance is judged against
        "HOLD_REASON_CATALOG",  # taxonomy edits reshape historical reporting
        "HOLD_STATUS_CATALOG",  # taxonomy edits reshape historical reporting
        "USER_CLIENT_ASSIGNMENT",  # access-control grant read by middleware/client_auth.py to decide tenant reach
        "DEFECT_TYPE_CATALOG",  # taxonomy edits reshape historical reporting, same rule as the hold catalogs
    }
)

#: Every other ORM table, with why it is not audited.
EXCLUDED_TABLES: Dict[str, str] = {
    # --- High-volume shift-level data entry -------------------------------
    # Routine operator input, one row per shift/day/inspection. Auditing
    # these would flood AUDIT_ENTRY with normal workflow noise rather than
    # decisions; the tables already carry entered_by/updated_by columns.
    "ATTENDANCE_ENTRY": (
        "high-volume daily shift entry, not a discretionary decision; carries its own entered_by/updated_by"
    ),
    "ATTENDANCE_HOUR_ALLOCATION": (
        "replace-on-write child of ATTENDANCE_ENTRY; whole list swapped on every save, no per-row history"
    ),
    "COVERAGE_ENTRY": "routine floating-pool coverage bookkeeping entered per shift, not a standalone decision",
    "DOWNTIME_ENTRY": "high-volume shift-level downtime logging entered by operators, not a discretionary decision",
    "PRODUCTION_ENTRY": "high-volume daily production tracking entered by operators, not a discretionary decision",
    "QUALITY_ENTRY": (
        "high-volume per-inspection quality tracking entered by inspectors, not a discretionary decision"
    ),
    "DEFECT_DETAIL": "child rows of QUALITY_ENTRY, one set per inspection; same high-volume entry pattern",
    "shift_coverage": (
        "routine per-shift staffing-coverage entry (required vs actual headcount), same pattern as COVERAGE_ENTRY"
    ),
    # --- Self-auditing tables -----------------------------------------------
    # These tables already are an audit trail for something else. Wrapping
    # them in AUDIT_ENTRY would double-log the same event.
    "WORKFLOW_TRANSITION_LOG": (
        "own append-only audit trail for WORK_ORDER status transitions; auditing it would double-log"
    ),
    "ASSUMPTION_CHANGE": (
        "own append-only audit log for CALCULATION_ASSUMPTION (mirrors WORKFLOW_TRANSITION_LOG); would double-log"
    ),
    "EVENT_STORE": ("domain-event sourcing store, itself built for audit/replay compliance per its own docstring"),
    "import_log": "dedicated CSV/batch-import audit log (rows attempted/succeeded/failed per upload); self-auditing",
    # --- Machine-written / derived / system-computed -------------------------
    "METRIC_CALCULATION_RESULT": (
        "cron-written daily by tasks/dual_view_calculation.py and already self-audits via calculated_by"
    ),
    "METRIC_ASSUMPTION_DEPENDENCY": (
        "static metric-to-assumption map populated by engineering at deploy time, not edited by users"
    ),
    "CALCULATION_ASSUMPTION": (
        "self-audits via its dedicated ASSUMPTION_CHANGE log written on every modification; would duplicate"
    ),
    "ALERT": "system-generated threshold-breach alert, not authored by a person",
    "ALERT_HISTORY": "system-computed prediction-vs-actual accuracy tracking, no human decision involved",
    "TOKEN_BLACKLIST": (
        "JWT revocation ledger written automatically on logout/expiry; a security control, not a decision"
    ),
    # --- Cosmetic / personal UI state ----------------------------------------
    "USER_PREFERENCES": "personal UI preference storage (theme, notifications), no operational or business impact",
    "DASHBOARD_WIDGET_DEFAULTS": "role-based dashboard layout defaults, purely cosmetic, no KPI or business impact",
    "SAVED_FILTER": "personal saved dashboard filter presets, a user convenience with no downstream effect",
    "FILTER_HISTORY": "ephemeral recently-applied-filter log auto-written on every filter apply, not a decision",
    "ALERT_CONFIG": (
        "per-client alert threshold/notification settings; secondary configuration, not one of the 13 tables"
    ),
    # --- Master/reference data, edited rarely during setup --------------------
    "EQUIPMENT": "machine/equipment master registry set up during client onboarding, not a recurring decision point",
    "PRODUCT": (
        "product/SKU catalog entry set up once per product; production/quality entries against it carry the activity"
    ),
    "SHIFT": "shift start/end time master definition, rarely changed after initial factory setup",
    "PRODUCTION_LINE": (
        "factory-floor topology (which lines exist and their hierarchy); infrastructure setup, not a decision"
    ),
    "JOB": "work-order line-item execution detail; the parent WORK_ORDER (audited) captures the decisions that matter",
    "FLOATING_POOL": "shared-resource availability bookkeeping updated as assignments change, not itself a decision",
    "PART_OPPORTUNITIES": (
        "DPMO calculation constant (opportunities per unit) set once per part number, an engineering value"
    ),
    "BREAK_TIME": "configurable per-shift break-period definition, infrequently changed factory-setup data",
    # --- Sandbox / what-if tools, no live operational effect ------------------
    "SIMULATION_SCENARIO": (
        "saved what-if SimPy/MiniZinc simulation config; a sandbox tool that never touches live operational data"
    ),
    # --- Capacity Planning module: a separate what-if planning subsystem ------
    # Distinct from the operational tables in AUDITED_TABLES; several of
    # these tables explicitly note in their own docstrings that they are
    # kept separate from the operational equivalents (e.g. capacity_orders
    # vs WORK_ORDER, capacity_production_lines vs PRODUCTION_LINE).
    "capacity_analysis": (
        "derived utilization/bottleneck output computed by CapacityAnalysis.calculate_metrics(), not a decision"
    ),
    "capacity_bom_detail": "bill-of-materials component reference data for MRP explosion, planning master data",
    "capacity_bom_header": "bill-of-materials parent-item reference data for MRP explosion, planning master data",
    "capacity_calendar": "working-day/holiday/shift calendar configuration for capacity math, infrastructure setup",
    "capacity_component_check": (
        "MRP explosion result computed from BOM + stock snapshot, a derived output not a decision"
    ),
    "capacity_kpi_commitment": (
        "target-vs-actual variance computed by calculate_variance(), a derived analytical record"
    ),
    "capacity_orders": (
        "capacity-planning-only order record, explicitly kept separate from the audited WORK_ORDER per its docstring"
    ),
    "capacity_production_lines": (
        "capacity-module line definition, explicitly kept separate from the operational PRODUCTION_LINE per docstring"
    ),
    "capacity_production_standards": (
        "SAM (Standard Allowed Minutes) reference data set once per style/operation, engineering configuration"
    ),
    "capacity_scenario": "what-if scenario parameters/results for capacity simulations, a planning sandbox tool",
    "capacity_schedule": (
        "draft production schedule within the capacity planning workflow, not yet a committed operational change"
    ),
    "capacity_schedule_detail": (
        "draft schedule line items within the capacity planning workflow, not yet a committed operational change"
    ),
    "capacity_stock_snapshot": "periodic inventory snapshot ingested for MRP calculations, not a user decision",
}

#: Column names whose values are never written into AUDIT_ENTRY.changes.
REDACTED_FIELDS: FrozenSet[str] = frozenset({"password_hash"})


def is_audited(table_name: str) -> bool:
    """True when changes to this table should be recorded."""
    return table_name in AUDITED_TABLES

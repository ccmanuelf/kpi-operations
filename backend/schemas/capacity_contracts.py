"""Response contract for Batch R2's single `/api/capacity` route,
`GET /api/capacity/workbook/{client_id}` -- split out from
`quality_contracts.py` purely for the 500-line limit and because it is an
unrelated area; see
docs/superpowers/plans/2026-08-25-response-model-refactor.md and
`.superpowers/sdd/2026-08-25-response-model-refactor/task-R2-brief.md`.

HAZARD -- the golden entry's 24 keys are an EMPTY ENVELOPE, not real data.
This route is in `NEVER_404` (`tests/contract/param_specs.py`): it answers
for ANY `client_id`, and the CAPACITY_* tables it reads (11 of the 13 the
seeder never writes -- `seed/cli.py`'s "13 capacity_* tables" note) hold
zero seeded rows. So the golden master records the 11 list-valued
worksheets as bare keys with no interior, and `dashboard_inputs`/
`instructions` (a hardcoded dict and a hardcoded string, neither backed by
any table) as the only worksheets with real content.

Every list item's interior below is modeled from reading
`routes/capacity/kpi_workbook.py::load_workbook` and the 11 ORM modules it
queries directly (`backend/orm/capacity/*.py`) -- NOT from any captured
example, because none exists. Two things make this safe rather than
guesswork:

1. Every `Numeric`/`Decimal`-typed column the route selects is
   `float(<column> or 0)`-cast INLINE, in the same dict-comprehension line
   that builds each item -- never forwarded raw. That is true for all 21
   Decimal-typed columns across the 11 worksheets (verified by reading
   every one; none is exempt), so there is no live Decimal-exponent hazard
   here the way `quality_contracts.py` found one in `dpmo-by-part`:
   `float(x or 0)` is `0.0` (a float literal) even when `x` is `None`,
   never a bare int `0`, so there is no int -> float widening to disclose
   either.
2. Every `Integer`-typed column is forwarded as declared in its ORM
   `Mapped[...]` annotation: `int` where the column is `nullable=False`
   (or the route applies its own `... or 0`/`... or 1` fallback), and
   `Optional[int]` where the column is nullable and the route forwards it
   bare. Cross-checked column-by-column against `backend/orm/capacity/
   *.py`, not inferred from the dict-comprehension alone.

If any table ever gains seeded rows, this module's shapes are what a real
response would look like today -- a documented model of dead code, per
spec section 6, rather than 13 opaque containers with the Decimal class
still alive inside them.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# Sheet 1: Master Calendar (orm/capacity/calendar.py::CapacityCalendarEntry)
# =============================================================================


class MasterCalendarEntry(BaseModel):
    id: int
    calendar_date: str
    is_working_day: bool
    shifts_available: int
    shift1_hours: float
    shift2_hours: float
    shift3_hours: float
    holiday_name: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# Sheet 2: Production Lines (orm/capacity/production_lines.py)
# =============================================================================


class ProductionLineEntry(BaseModel):
    id: int
    line_code: str
    line_name: str
    department: Optional[str] = None
    standard_capacity_units_per_hour: float
    max_operators: Optional[int] = None
    efficiency_factor: float
    absenteeism_factor: float
    is_active: bool
    notes: Optional[str] = None


# =============================================================================
# Sheet 3: Orders (orm/capacity/orders.py::CapacityOrder)
# =============================================================================


class WorkbookOrderEntry(BaseModel):
    """Deliberately named apart from `workorder_contracts.CapacityOrderInfo`
    (Batch R3, a different route's `capacity-order` lookup) -- same source
    table, a distinct, independently-evolving response shape."""

    id: int
    order_number: str
    customer_name: Optional[str] = None
    style_model: str
    style_description: Optional[str] = None
    order_quantity: int
    completed_quantity: Optional[int] = None
    order_date: Optional[str] = None
    required_date: str
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    order_sam_minutes: Optional[float] = None
    notes: Optional[str] = None


# =============================================================================
# Sheet 4: Production Standards (orm/capacity/standards.py)
# =============================================================================


class ProductionStandardEntry(BaseModel):
    id: int
    style_model: str
    operation_code: str
    operation_name: Optional[str] = None
    department: Optional[str] = None
    sam_minutes: float
    setup_time_minutes: float
    machine_time_minutes: float
    manual_time_minutes: float
    notes: Optional[str] = None


# =============================================================================
# Sheet 5: BOM (orm/capacity/bom.py::CapacityBOMHeader)
# =============================================================================


class BOMHeaderEntry(BaseModel):
    """`component_count` is `h.components.count()` -- a `SELECT count(*)`
    against the dynamic `components` relationship, always a native int on
    every dialect (a row-count aggregate, not a `SUM` over a numeric
    column, so the MariaDB SUM-returns-DECIMAL class does not apply)."""

    id: int
    parent_item_code: str
    parent_item_description: Optional[str] = None
    style_model: Optional[str] = None
    revision: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None
    component_count: int


# =============================================================================
# Sheet 6: Stock Snapshot (orm/capacity/stock.py)
# =============================================================================


class StockSnapshotEntry(BaseModel):
    id: int
    snapshot_date: str
    item_code: str
    item_description: Optional[str] = None
    on_hand_quantity: float
    allocated_quantity: float
    on_order_quantity: float
    available_quantity: float
    unit_of_measure: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# Sheet 7: Component Check (orm/capacity/component_check.py)
# =============================================================================


class ComponentCheckEntry(BaseModel):
    id: int
    run_date: str
    order_id: int
    order_number: Optional[str] = None
    component_item_code: str
    component_description: Optional[str] = None
    required_quantity: float
    available_quantity: float
    shortage_quantity: float
    status: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# Sheet 8: Capacity Analysis (orm/capacity/analysis.py)
# =============================================================================


class CapacityAnalysisEntry(BaseModel):
    """`demand_units`/`is_bottleneck` carry the route's own `... or 0`/
    `... or False` fallback (never `None` on the wire); `working_days`/
    `shifts_per_day`/`operators_available` do not and are forwarded bare
    from their nullable `Integer` columns."""

    id: int
    analysis_date: str
    line_id: int
    line_code: Optional[str] = None
    department: Optional[str] = None
    working_days: Optional[int] = None
    shifts_per_day: Optional[int] = None
    hours_per_shift: float
    operators_available: Optional[int] = None
    efficiency_factor: float
    absenteeism_factor: float
    gross_hours: float
    net_hours: float
    capacity_hours: float
    demand_hours: float
    demand_units: int
    utilization_percent: float
    is_bottleneck: bool
    notes: Optional[str] = None


# =============================================================================
# Sheet 9: Production Schedule (orm/capacity/schedule.py::CapacityScheduleDetail)
# =============================================================================


class ProductionScheduleEntry(BaseModel):
    """`scheduled_quantity`/`completed_quantity`/`sequence` carry the
    route's own `... or 0`/`... or 1` fallback; `schedule_name`/
    `schedule_status` are a `next(...)` lookup against the parent
    `CapacitySchedule` list, `None` if no header matches (structurally
    impossible given the FK, but the route's own default, preserved)."""

    id: int
    schedule_id: int
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    style_model: Optional[str] = None
    line_id: Optional[int] = None
    line_code: Optional[str] = None
    scheduled_date: str
    scheduled_quantity: int
    completed_quantity: int
    sequence: int
    notes: Optional[str] = None
    schedule_name: Optional[str] = None
    schedule_status: Optional[str] = None


# =============================================================================
# Sheet 10: What-If Scenarios (orm/capacity/scenario.py::CapacityScenario)
# =============================================================================


class WhatIfScenarioEntry(BaseModel):
    """`parameters`/`results` are `JSON`-typed columns (`parameters_json`/
    `results_json`), forwarded via `... or {}` -- always a dict, never
    `None`, shape otherwise unconstrained by the schema."""

    id: int
    scenario_name: str
    scenario_type: Optional[str] = None
    base_schedule_id: Optional[int] = None
    parameters: Dict[str, Any]
    results: Dict[str, Any]
    is_active: bool
    notes: Optional[str] = None


# =============================================================================
# Sheet 11: Dashboard Inputs -- a hardcoded literal dict, no table
# =============================================================================


class DashboardInputs(BaseModel):
    """`routes/capacity/kpi_workbook.py::load_workbook`'s own literal dict
    -- every value a Python `int`/`bool`/`str` constant, no ORM column
    involved at all."""

    planning_horizon_days: int
    default_efficiency: int
    bottleneck_threshold: int
    shortage_alert_days: int
    auto_schedule_enabled: bool
    target_utilization: int
    overtime_limit_percent: int
    safety_stock_days: int
    schedule_freeze_days: int
    max_shifts_per_day: int
    min_lot_size: int
    schedule_granularity: str


# =============================================================================
# Sheet 12: KPI Tracking (orm/capacity/kpi_commitment.py)
# =============================================================================


class KPITrackingEntry(BaseModel):
    """`committed_value` is `float(...)`-cast unconditionally (the column is
    `nullable=False`); `actual_value`/`variance`/`variance_percent` are
    `Optional[float]`, each guarded `if ... is not None else None`."""

    id: int
    schedule_id: int
    kpi_key: str
    kpi_name: Optional[str] = None
    period_start: str
    period_end: str
    committed_value: float
    actual_value: Optional[float] = None
    variance: Optional[float] = None
    variance_percent: Optional[float] = None
    notes: Optional[str] = None


# =============================================================================
# GET /api/capacity/workbook/{client_id}
# =============================================================================


class CapacityWorkbookResponse(BaseModel):
    """13 worksheets, matching `load_workbook`'s own docstring naming.
    `instructions` (Sheet 13) is a hardcoded markdown string, no table."""

    master_calendar: List[MasterCalendarEntry]
    production_lines: List[ProductionLineEntry]
    orders: List[WorkbookOrderEntry]
    production_standards: List[ProductionStandardEntry]
    bom: List[BOMHeaderEntry]
    stock_snapshot: List[StockSnapshotEntry]
    component_check: List[ComponentCheckEntry]
    capacity_analysis: List[CapacityAnalysisEntry]
    production_schedule: List[ProductionScheduleEntry]
    what_if_scenarios: List[WhatIfScenarioEntry]
    dashboard_inputs: DashboardInputs
    kpi_tracking: List[KPITrackingEntry]
    instructions: str

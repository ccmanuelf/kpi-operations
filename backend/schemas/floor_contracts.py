"""Response contracts for Batch R3's `/api/floating-pool` (4 of 4) and
`/api/attendance` (2 of 4) routes -- 6 of the batch's 12 total (the other 6,
for `/api/work-orders` and `/api/alerts`, live in `workorder_contracts.py`,
split out purely for the 500-line limit). New modules rather than
overloading `kpi_contracts.py` (413 lines, KPI-scoped), `workflow_contracts
.py` (workflow-scoped) or `ops_contracts.py` (498 lines, already near the
limit); see docs/superpowers/plans/2026-08-25-response-model-refactor.md.

Two named hazards (task-R3-brief.md), both closed by declared TYPES rather
than by "fixing" what looks like a bug:

1. `simulation/insights` deliberately returns numeric-looking STRINGS for
   `input_parameters.{shift_hours,cycle_time_hours,efficiency_percent}` and
   `projected_output.{hourly_rate,effective_hours}` -- explicit `str(Decimal)`
   calls in `run_staffing_simulation` (calculations/simulation.py:332-339).
   Those five fields stay `str` here; declaring `float` would coerce the
   string back into a number and silently change the wire format. The
   sibling `kpi_impact`/`comparison_to_baseline` fields are NOT part of that
   idiom -- raw `Decimal` arithmetic, never `str()`'d -- and are declared
   `float`, matching what this route ALREADY sends today (see
   `SimulationStaffingKPIImpact`'s docstring for why).
2. `check-availability/{employee_id}` is in `NEVER_404` (param_specs.py): it
   answers "available" for any employee_id, so its ONLY captured evidence is
   the narrowest branch (`current_assignment`/`conflict_dates` both null).
   `FloatingPoolCheckAvailabilityResponse` is modeled from all four of the
   producing function's return statements, not just the captured one.

Beyond those two named hazards, two more fields have real TOP-LEVEL golden
evidence for their route but an empty/bare INTERIOR at capture time -- the
same "real evidence, source-inspected interior" situation Batch R4 disclosed
for `ThresholdEntry`/`ActivityLogEntry`: `FloatingPoolSummaryResponse.
available_employees` and `FloatingPoolSimulationInsightsResponse.
recommendations` (no threshold branch fired for the captured pool's
utilization). Each is disclosed on its own model, not forced by a dedicated
test, mirroring R4's own precedent (`PlanVsActualEntry`/`ActiveShiftResponse`
also went undisclosed-but-untested by a forcing test).

int->float widening instances disclosed per-model below (never fixed, per
the plan-wide accepted-consequence rule): `AbsenteeismKPIResponse.rate`/
`.absenteeism_rate`, `AbsenteeismTrendPoint.value`, and
`FloatingPoolCurrentStatus.utilization_percent` -- each an `else 0` fallback
the smoke seed's non-empty data never exercises.

NOT modeled: `simulation/insights`' own `except Exception` fallback around
`run_staffing_simulation` returns an entirely different, incompatible
`staffing_scenarios[]` shape -- see `FloatingPoolSimulationInsightsResponse`
for why it is confirmed dead under this route rather than silently ignored.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

from backend.schemas.simulation import SimulationScenarioType

# =============================================================================
# /api/floating-pool
# =============================================================================


class FloatingPoolConflictDates(BaseModel):
    """The `conflict_dates` object in GET /api/floating-pool/check-availability/
    {employee_id} -- see FloatingPoolCheckAvailabilityResponse for the floor-
    shape disclosure this supports. `existing_start`/`existing_end` are raw
    FLOATING_POOL.available_from/available_to `DateTime` columns
    (crud/floating_pool/assignments.py::is_employee_available_for_assignment),
    never `.isoformat()`'d in the source dict -- Pydantic (and the current
    unmodeled `jsonable_encoder` path) render a bare `datetime` identically,
    so declaring `datetime` here changes nothing on the wire.
    """

    existing_start: Optional[datetime] = None
    existing_end: Optional[datetime] = None


class FloatingPoolCheckAvailabilityResponse(BaseModel):
    """GET /api/floating-pool/check-availability/{employee_id} -- HAZARD 2:
    golden evidence is a FLOOR, not the truth. This route is in `NEVER_404`
    (param_specs.py): it answers "available" for any employee_id, so the
    captured entry is always the 4-key `{is_available: true, current_
    assignment: null, conflict_dates: null, message: str}` no-existing-
    assignment branch. Modeled from ALL FOUR of `is_employee_available_for_
    assignment`'s (crud/floating_pool/assignments.py) return statements, not
    just the captured one: `current_assignment` is the other client's
    client_id string when assigned, and `conflict_dates` is populated with
    the two datetimes above on three of those branches. All 4 keys are
    unconditionally present in every branch (no `exclude_unset` needed) --
    only their VALUES vary between null and populated.
    """

    is_available: bool
    current_assignment: Optional[str] = None
    conflict_dates: Optional[FloatingPoolConflictDates] = None
    message: str


class FloatingPoolAvailableEmployee(BaseModel):
    """GET /api/floating-pool/available/list -- SOURCE INSPECTION, NO
    CAPTURED EVIDENCE (golden `[]`: no FLOATING_POOL row is unassigned under
    the smoke seed). Modeled from `get_available_floating_pool_employees`
    (crud/floating_pool/queries.py), unconditional once an employee is found
    for the entry (all 8 keys together). `available_from`/`available_to` are
    the same raw `DateTime` columns as `FloatingPoolConflictDates` above.
    """

    pool_id: int
    employee_id: int
    employee_code: str
    employee_name: str
    position: Optional[str] = None
    available_from: Optional[datetime] = None
    available_to: Optional[datetime] = None
    notes: Optional[str] = None


class FloatingPoolSummaryEmployee(BaseModel):
    """One entry of GET /api/floating-pool/summary's `available_employees`
    list -- real top-level evidence for the route (4 keys captured), but the
    smoke seed's captured pool has nobody available at the moment of
    capture, so this INTERIOR is source-inspected the same way ActivityLog
    Entry/ThresholdEntry were in Batch R4. Modeled from `get_floating_pool_
    summary` (crud/floating_pool/queries.py) -- a NARROWER 4-key shape than
    `FloatingPoolAvailableEmployee` above (no pool_id/available_from/
    available_to/notes): the two routes independently build their own dict
    literals from the same Employee row.
    """

    employee_id: int
    employee_code: str
    employee_name: str
    position: Optional[str] = None


class FloatingPoolSummaryResponse(BaseModel):
    """GET /api/floating-pool/summary -- golden evidence, 4 keys."""

    total_floating_pool_employees: int
    currently_available: int
    currently_assigned: int
    available_employees: List[FloatingPoolSummaryEmployee]


class SimulationStaffingInputParameters(BaseModel):
    """The `input_parameters` object inside one `staffing_scenarios[].result`
    -- HAZARD 1. `run_staffing_simulation` (calculations/simulation.py:
    330-335) builds this dict with `employees` as a plain `int` and the other
    three as explicit `str(Decimal)` calls -- a DELIBERATE numeric-looking-
    string idiom (task-R3-brief.md HAZARD 1), not a leak. Declaring them
    `float` would coerce the string back into a number and silently change
    the wire format; they stay `str`.
    """

    employees: int
    shift_hours: str
    cycle_time_hours: str
    efficiency_percent: str


class SimulationStaffingProjectedOutput(BaseModel):
    """The `projected_output` object -- same HAZARD 1 idiom. `units_capacity`
    is `int(...)`-cast in `calculate_production_capacity` (calculations/
    simulation.py:233); `hourly_rate`/`effective_hours` are `str(Decimal)`
    (:338-339, the exact two lines the brief's hazard names) and stay `str`
    for the same reason as above.
    """

    units_capacity: int
    hourly_rate: str
    effective_hours: str


class SimulationStaffingKPIImpact(BaseModel):
    """The `kpi_impact` object -- NOT the str idiom. These four fields are
    raw `Decimal` arithmetic results (calculations/simulation.py:341-346),
    never passed through `str()`. Today, because this route carries NO
    `response_model` at all, FastAPI serializes them via `jsonable_encoder`
    directly (no Pydantic model in the path). FastAPI's own `decimal_encoder`
    (fastapi/encoders.py) branches on the Decimal's EXPONENT, not its value:
    `int(value)` when `exponent >= 0`, `float(value)` only when `exponent <
    0` -- verified directly: `jsonable_encoder(Decimal("95"))` -> `95` (int,
    exponent 0), `jsonable_encoder(Decimal("13.60"))` -> `13.6` (float,
    exponent -2). `production_change_percent`/`employee_change_percent` are
    `.quantize(Decimal("0.01"))`'d (exponent -2, always float) and
    `efficiency` inherits `base_efficiency`'s exponent -1 (`Decimal(str(
    85.0))`) on every branch -- all three correctly stay `float`.
    `employee_change`, below, does NOT: `Decimal(employee_change)` wraps a
    plain Python `int` (`employee_count - base_employees`), which `Decimal()`
    always renders at exponent 0 -- declaring it `float` would turn today's
    JSON int into `X.0` on every response, a real wire change, not a
    no-op. Declared `int`: byte-identical to current behaviour, and still
    rejects a genuinely fractional Decimal loudly (`Decimal("95.5")` ->
    `ValidationError`, `Decimal("95")` -> `95`).
    """

    production_change_percent: float
    efficiency: float
    employee_change: int
    employee_change_percent: float


class SimulationStaffingComparison(BaseModel):
    """The `comparison_to_baseline` object. All three fields wrap
    `Decimal(<already-int>)` -- `calculate_production_capacity` `int(...)`-
    casts `units_capacity` at calculations/simulation.py:233, and `Decimal`
    subtraction of two exponent-0 operands stays exponent 0 -- so, per
    `decimal_encoder`'s exponent rule (see `SimulationStaffingKPIImpact`'s
    docstring), all three are ALWAYS integral on the wire today. Declared
    `int`, not `float`: `float` would turn every response's `baseline_units`/
    `scenario_units`/`difference` from a JSON int into `X.0` -- confirmed by
    a real A/B capture of this route's response body, not just the type
    annotation (see test_floor_contracts.py). `int` matches current
    behaviour exactly and still rejects a non-integral Decimal loudly.
    """

    baseline_units: int
    scenario_units: int
    difference: int


class SimulationStaffingResult(BaseModel):
    """The `result` object inside one `staffing_scenarios[]` entry --
    `SimulationResult` (calculations/simulation.py). `comparison_to_baseline`
    is `Optional` in the dataclass itself, though `run_staffing_simulation`'s
    only caller (this route) always populates it.
    """

    scenario_name: str
    scenario_type: SimulationScenarioType
    input_parameters: SimulationStaffingInputParameters
    projected_output: SimulationStaffingProjectedOutput
    kpi_impact: SimulationStaffingKPIImpact
    recommendations: List[str]
    confidence_score: float
    comparison_to_baseline: Optional[SimulationStaffingComparison] = None


class SimulationStaffingScenario(BaseModel):
    """One entry of GET /api/floating-pool/simulation/insights'
    `staffing_scenarios` list."""

    scenario: str
    result: SimulationStaffingResult


class FloatingPoolCurrentStatus(BaseModel):
    """The `current_status` object. `target_date` is a real `date`
    (`target_date or date.today()`, routes/floating_pool.py) -- never a pre-
    formatted string. `utilization_percent` is `round(utilization, 1)`, an
    int->float widening instance when `total_pool_size` is 0 (`utilization`
    is then the bare int `0`; not hit under the smoke seed's non-empty
    pool).
    """

    total_pool_size: int
    currently_available: int
    currently_assigned: int
    utilization_percent: float
    target_date: date


class FloatingPoolRecommendation(BaseModel):
    """One entry of GET /api/floating-pool/simulation/insights' top-level
    `recommendations` list -- real top-level evidence for the route (bare
    `recommendations` key: none of the three threshold branches fired for
    the captured pool's utilization/availability), interior source-inspected
    from the route's own literal dicts (routes/floating_pool.py), all 4 keys
    unconditional.
    """

    priority: str
    type: str
    message: str
    action: str


class FloatingPoolSimulationParameters(BaseModel):
    """The outer `simulation_parameters` object -- fixed Python float
    literals in the route (`shift_hours = 8.0`, `cycle_time_hours = 0.5`,
    `base_efficiency = 85.0`), never Decimal, never the str idiom.
    """

    base_employees: int
    shift_hours: float
    cycle_time_hours: float
    base_efficiency: float


class FloatingPoolSimulationInsightsResponse(BaseModel):
    """GET /api/floating-pool/simulation/insights -- golden evidence, 29
    keys.

    NOT modeled: the route's own `except Exception` fallback around
    `run_staffing_simulation` returns a COMPLETELY DIFFERENT
    `staffing_scenarios[]` shape (`scenario`/`employees`/`units_per_shift`/
    `efficiency`, no nested `result` at all) -- not a field subset
    `exclude_unset` could express, an entirely different key set. Confirmed
    DEAD under this specific route: every input to `run_staffing_simulation`
    here is a fixed literal (`base_employees` from an int count,
    `shift_hours=8.0`, `cycle_time_hours=0.5`, `base_efficiency=85.0`, all
    hardcoded, never user-supplied), and `calculate_production_capacity`'s
    only `raise` is `cycle_time_hours == 0` (calculations/simulation.py:210)
    -- unreachable with a hardcoded `0.5`. Left unhandled and disclosed as a
    finding rather than silently accepted.
    """

    current_status: FloatingPoolCurrentStatus
    staffing_scenarios: List[SimulationStaffingScenario]
    recommendations: List[FloatingPoolRecommendation]
    simulation_parameters: FloatingPoolSimulationParameters


# =============================================================================
# /api/attendance
# =============================================================================


class AbsenteeismByReason(BaseModel):
    """One entry of GET /api/attendance/kpi/absenteeism's `by_reason` list --
    golden evidence. `percentage` is `round(float, 1)`, true division of two
    ints."""

    reason: str
    count: int
    percentage: float


class AbsenteeismByDepartment(BaseModel):
    """One entry of `by_department` -- golden evidence."""

    department: str
    workforce: int
    absences: int
    rate: float


class AbsenteeismHighAbsenceEmployee(BaseModel):
    """One entry of `high_absence_employees` -- golden evidence.
    `last_absence` is `.strftime(...) if e.last_absence else None`, but every
    row reaching this branch is grouped from `is_absent == 1` rows with
    `having(count() >= 2)`, so `last_absence` (a `func.max` over those same
    rows) is null in source only in principle, never in practice.
    """

    employee_id: int
    department: str
    absence_count: int
    last_absence: Optional[str] = None


class AbsenteeismKPIResponse(BaseModel):
    """GET /api/attendance/kpi/absenteeism -- golden evidence, 22 keys.
    `total_scheduled_hours`/`total_hours_worked`/`total_hours_absent` are
    already `float(...)`-cast in the route (routes/attendance.py) off
    `Numeric(5, 2)` SQL `SUM()`s -- no Decimal reaches this dict. `rate`/
    `absenteeism_rate` are `round(rate, 2)`, an int->float widening instance
    when `scheduled` is 0 for the period (`rate` is then the bare int `0`;
    not hit under the smoke seed's non-zero scheduled hours).
    """

    shift_id: int
    start_date: str
    end_date: str
    total_scheduled_hours: float
    total_hours_worked: float
    total_hours_absent: float
    rate: float
    absenteeism_rate: float
    total_employees: int
    total_absences: int
    calculation_timestamp: str
    by_reason: List[AbsenteeismByReason]
    by_department: List[AbsenteeismByDepartment]
    high_absence_employees: List[AbsenteeismHighAbsenceEmployee]


class AbsenteeismTrendPoint(BaseModel):
    """GET /api/attendance/kpi/absenteeism/trend -- golden evidence, 2 keys.
    The route returns a bare list, not a wrapped object (`-> list[dict]`).
    `value` is `round(rate, 2)`, the same int->float widening as
    `AbsenteeismKPIResponse.rate` when a day's scheduled hours are 0.
    """

    date: str
    value: float

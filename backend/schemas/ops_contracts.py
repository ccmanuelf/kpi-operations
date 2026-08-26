"""Response contracts for Batch R4: `/api/cache`, `/api/kpi-thresholds`,
`/api/predictions`, `/api/data-completeness`, `/api/my-shift`, `/api/shifts`,
`/api/plan-vs-actual` -- 18 routes total. New module rather than overloading
`kpi_contracts.py` (413 lines, KPI-scoped) or `workflow_contracts.py`
(workflow-scoped); see docs/superpowers/plans/2026-08-25-response-model-refactor.md.

Declared types are what close the Decimal class: MariaDB's `SUM()` over an
INTEGER column returns DECIMAL at the driver level even though the column
itself is a plain integer, Pydantic renders a `Decimal` field as a JSON
*string* under `Any`/`Dict`, and a declared `int`/`float` coerces the value
instead of forwarding it as-is. `MyShiftStatsResponse.units_produced` and
`.efficiency` are the one live instance of this in this batch -- see that
model's docstring for the exact code path and
`backend/tests/contract/test_ops_contracts.py` for the mutation-tested proof.

Most of this batch has real golden-master evidence (`backend/tests/contract/
golden/api_shapes.json`). Three models -- `ActiveShiftResponse`,
`KPIHealthAssessmentResponse`, and `PlanVsActualEntry` (+ nested
`LineBreakdownEntry`) -- carry NO captured evidence: their routes' golden
entries are placeholders (`<status:404>`, `<status:400>`, `[]`), so they are
built from reading the producing function directly, exactly as Task 9's
`StageDurationEntry` was. `ThresholdEntry` and `ActivityLogEntry` are a
narrower version of the same gap: their routes have real captured top-level
evidence, but the smoke seed never populates the collection each lives
inside, so each interior is source-inspected the same way.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# /api/cache -- golden evidence for all 4 routes.
# =============================================================================


class CacheHealthResponse(BaseModel):
    """GET /api/cache/health -- golden evidence, 4 keys.

    `cache_health()` (routes/cache.py) wraps its body in a bare
    `try/except Exception`: on the (never-seen-in-capture, defensive-only)
    exception path it returns a 3-key dict -- `status`, `timestamp`, `error`
    -- with `entries`/`hit_rate` absent entirely, not null. Without
    `response_model_exclude_unset=True`, `Optional[int] = None` fields would
    emit `entries: null`/`hit_rate: null` on that branch (a key the original
    route never sent), and without `Optional` at all the missing keys would
    fail response validation outright, turning a graceful in-band error into
    a 500. Registered in `EXCLUDE_UNSET_ROUTES`; forced directly in
    `test_conditional_branches.py::test_cache_health_error_branch_omits_entries_and_hit_rate`.
    """

    status: str
    timestamp: str
    entries: Optional[int] = None
    hit_rate: Optional[float] = None
    error: Optional[str] = None


class CacheStatistics(BaseModel):
    """The `statistics` object nested in GET /api/cache/stats.

    `KPICache.get_stats()` (backend/cache/kpi_cache.py) is a plain in-memory
    dict of Python ints plus one `round(float, 2)` -- no SQL, no Decimal.
    """

    entries: int
    hits: int
    misses: int
    hit_rate: float
    sets: int
    evictions: int


class CacheStatsResponse(BaseModel):
    """GET /api/cache/stats -- golden evidence, 8 keys (2 top-level + 6 nested)."""

    status: str
    timestamp: str
    statistics: CacheStatistics


class CacheClearResponse(BaseModel):
    """POST /api/cache/clear -- golden evidence, 4 keys."""

    status: str
    message: str
    entries_cleared: int
    timestamp: str


class CacheInvalidateResponse(BaseModel):
    """DELETE /api/cache/invalidate/{pattern} -- golden evidence, 4 keys.

    `pattern` is an in-process cache-key prefix, not an id -- see
    `param_specs.py`'s `NEVER_404` entry for this route.
    """

    status: str
    pattern: str
    entries_invalidated: int
    timestamp: str


# =============================================================================
# /api/kpi-thresholds -- golden evidence for the GET and the composite DELETE.
# PUT is untouched (Task 16, needs a request body).
# =============================================================================


class ThresholdEntry(BaseModel):
    """One value of the `thresholds` map in GET /api/kpi-thresholds.

    NOT captured: the smoke seed carries zero KPI_THRESHOLD rows, so the
    golden entry's `thresholds` key is bare with no dotted children.
    Modeled from `get_kpi_thresholds` (routes/kpi/thresholds.py), which
    builds this exact 8-key dict per threshold from the KPI_THRESHOLD ORM
    row (`target_value`/`warning_threshold`/`critical_threshold` are plain
    `Float` columns, never `Numeric` -- no Decimal risk here).
    """

    threshold_id: str
    kpi_key: str
    target_value: float
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    unit: Optional[str] = None
    higher_is_better: Optional[str] = None
    is_global: bool


class KPIThresholdsResponse(BaseModel):
    """GET /api/kpi-thresholds -- golden evidence, 3 keys.

    `thresholds`'s VALUES are data-shaped (see `ThresholdEntry`), but its
    KEYS are `kpi_key` strings -- data, not fixed field names, the same
    reason `capture.py`'s `MAP_FIELDS` treats `by_severity`/`by_category`
    specially. An empty dict serializes identically either way, so typing
    the value side costs nothing today and is correct once a row exists.
    """

    client_id: Optional[str] = None
    client_name: Optional[str] = None
    thresholds: Dict[str, ThresholdEntry]


class KPIThresholdDeleteResponse(BaseModel):
    """DELETE /api/kpi-thresholds/{client_id}/{kpi_key} -- golden evidence, 1
    key. `delete_client_threshold` (routes/kpi/thresholds.py) has exactly
    one success return, a single-key message dict; the 404-on-missing path
    never reaches this model."""

    message: str


# =============================================================================
# /api/predictions -- golden evidence for benchmarks and demo/seed;
# health/{kpi_type} is source-inspected (see below).
# =============================================================================


class KPIBenchmarkEntry(BaseModel):
    """One KPI's benchmark block in GET /api/predictions/benchmarks.
    `get_kpi_benchmarks()` (generators/sample_data_phase5.py) is a single
    hardcoded literal dict -- no branches, no DB, no Decimal."""

    target: float
    excellent: float
    good: float
    fair: float
    unit: str
    description: str


class KPIBenchmarksResponse(BaseModel):
    """GET /api/predictions/benchmarks -- golden evidence, 60 keys (10 x 6).
    Field order matches `get_kpi_benchmarks()`'s dict literal; the 10 names
    are exactly `KPITypePhase5`'s members, verified against the function
    body directly (a mismatch there would 500, not silently mis-serialize)."""

    efficiency: KPIBenchmarkEntry
    performance: KPIBenchmarkEntry
    availability: KPIBenchmarkEntry
    oee: KPIBenchmarkEntry
    ppm: KPIBenchmarkEntry
    dpmo: KPIBenchmarkEntry
    fpy: KPIBenchmarkEntry
    rty: KPIBenchmarkEntry
    absenteeism: KPIBenchmarkEntry
    otd: KPIBenchmarkEntry


class PredictionsDemoSeedResponse(BaseModel):
    """POST /api/predictions/demo/seed -- golden evidence, 5 keys.

    Only capturable with pytest's cwd at `backend/` -- see
    `test_golden_master.py`'s module docstring for the pre-existing
    lazy-import bug that 500s otherwise. `total_records`/`clients`/`kpis`/
    `days_per_kpi` are all plain Python `len()`/loop-counter ints
    (`seed_demo_predictions`, generators/sample_data_phase5.py) -- no SQL
    aggregate, no Decimal.
    """

    message: str
    total_records: int
    clients: int
    kpis: int
    days_per_kpi: int


class KPIHealthAssessmentResponse(BaseModel):
    """GET /api/predictions/health/{kpi_type} -- SOURCE INSPECTION, NO
    CAPTURED EVIDENCE. Golden entry is `<status:400>`: `get_kpi_health`
    (routes/predictions.py) queries a 7-day window and requires >= 3 points,
    but `get_historical_kpi_data` returns `[]` under this smoke seed (its
    query raises internally and is swallowed by a broad `except Exception`),
    so the 400 fires every time. Pre-existing; not fixed here, per the brief.

    Modeled from `get_kpi_health`'s own literal return dict, unconditional
    once construction begins -- all 9 keys always present together, so no
    `exclude_unset` is needed for the route's own dict. (Separately,
    `health_data["current_vs_target"]` can `KeyError` for an unknown
    `kpi_type`, since -- unlike sibling route `/predictions/{kpi_type}` --
    this route never validates `kpi_type` first; a pre-existing latent bug,
    also not fixed here.) `assessed_at` is a real `datetime` object
    (`datetime.now(tz=timezone.utc)`), not a pre-formatted string.
    """

    kpi_type: str
    client_id: str
    current_value: float
    health_score: float
    trend: str
    target: float
    current_vs_target: float
    recommendations: List[str]
    assessed_at: datetime


# =============================================================================
# /api/data-completeness -- golden evidence for all 3 routes.
# =============================================================================


class CompletenessCategory(BaseModel):
    """One of production/downtime/attendance/quality/hold in GET
    /api/data-completeness -- a `func.count()` scalar (BIGINT, never
    Decimal) and a `round(float, 1)`, never a SQL `SUM()`."""

    entered: int
    expected: int
    percentage: float
    status: str


class CompletenessOverall(BaseModel):
    percentage: float
    status: str


class DataCompletenessResponse(BaseModel):
    """GET /api/data-completeness -- golden evidence, 26 keys."""

    date: str
    shift_id: Optional[int] = None
    client_id: Optional[str] = None
    production: CompletenessCategory
    downtime: CompletenessCategory
    attendance: CompletenessCategory
    quality: CompletenessCategory
    hold: CompletenessCategory
    overall: CompletenessOverall
    calculation_timestamp: str


class CompletenessCategoryDetail(BaseModel):
    """One entry of `categories` in GET /api/data-completeness/categories --
    `get_completeness_by_category` merges 5 nav-hint keys with the same
    4-key shape as `CompletenessCategory` into one flat dict."""

    id: str
    name: str
    icon: str
    color: str
    route: str
    entered: int
    expected: int
    percentage: float
    status: str


class DataCompletenessCategoriesResponse(BaseModel):
    """GET /api/data-completeness/categories -- golden evidence, 13 keys."""

    date: str
    overall: CompletenessOverall
    categories: List[CompletenessCategoryDetail]
    calculation_timestamp: str


class DailyCompletenessEntry(BaseModel):
    """One entry of GET /api/data-completeness/summary's `daily` list."""

    date: str
    overall_percentage: float
    status: str
    production: float
    downtime: float
    attendance: float
    quality: float


class DataCompletenessSummaryResponse(BaseModel):
    """GET /api/data-completeness/summary -- golden evidence, 11 keys."""

    start_date: str
    end_date: str
    average_completeness: float
    daily: List[DailyCompletenessEntry]
    calculation_timestamp: str


# =============================================================================
# /api/my-shift -- golden evidence for both routes; per-item interiors of
# `activity` are source-inspected (smoke seed has none dated `date.today()`).
# =============================================================================


class MyShiftStatsResponse(BaseModel):
    """GET /api/my-shift/stats -- golden evidence, 8 keys.

    THE LIVE DECIMAL HAZARD in this batch. `get_my_shift_stats`
    (routes/my_shift.py) reads `total_units` off
    `func.sum(ProductionEntry.units_produced)`; MariaDB's `SUM()` returns
    DECIMAL regardless of the summed column's own `Integer` type (the
    SUM-Integer-to-Decimal class from `e2e-sweep-remediation`).
    `downtime_minutes`/`defect_count` are already `int(...)`-cast in the
    route, but `units_produced` (`total_units`, unmodified) is not, and
    `efficiency = total_units / total_target * 100` can inherit the same
    Decimal. Declaring both fields here (`int`, `float`) closes it: Pydantic
    coerces `Decimal` on validation instead of forwarding it. See
    `test_ops_contracts.py` for the mutation-tested proof.
    """

    date: str
    shift_id: Optional[int] = None
    units_produced: int
    efficiency: float
    downtime_incidents: int
    downtime_minutes: int
    quality_checks: int
    defect_count: int


class ActivityLogEntry(BaseModel):
    """One entry of GET /api/my-shift/activity's `activity` list.

    NOT captured: the golden entry's `activity` key is bare (no `[].`
    children) because the smoke seed has no production/downtime/quality rows
    dated `date.today()` (seed is anchored to a fixed past `as_of` date).
    Modeled from `get_my_recent_activity` (routes/my_shift.py), whose three
    branches (production/downtime/quality) each build this identical 6-key
    dict, with `value` always a plain `Integer` column read directly
    (`units_produced`/`downtime_duration_minutes`/`units_inspected`, none
    `Numeric`).
    """

    id: str
    type: str
    description: str
    timestamp: str
    work_order_id: Optional[str] = None
    value: int


class MyShiftActivityResponse(BaseModel):
    """GET /api/my-shift/activity -- golden evidence, 3 keys."""

    date: str
    shift_id: Optional[int] = None
    activity: List[ActivityLogEntry]


# =============================================================================
# /api/shifts -- golden evidence for the list; `/active` is source-inspected.
# =============================================================================


class ShiftListEntry(BaseModel):
    """One entry of GET /api/shifts -- golden evidence, 4 keys per item.
    `list_shifts` (routes/reference.py) builds a plain dict literal;
    `start_time`/`end_time` are `.strftime("%H:%M")` strings."""

    shift_id: int
    shift_name: str
    start_time: str
    end_time: str


class ActiveShiftResponse(BaseModel):
    """GET /api/shifts/active -- SOURCE INSPECTION, NO CAPTURED EVIDENCE.

    Golden entry is `<status:404>`: the capture pins the clock to 15:00 UTC
    (`ShiftActivePin`, capture.py), a deliberate dead zone between the smoke
    seed's two shift windows, so a 200 is never recorded. Do NOT change the
    pin. Modeled from `get_active_shift`'s (routes/reference.py) two return
    statements -- identical 5-key dicts; the no-match branch raises
    `HTTPException(404)` instead of returning a dict at all.
    """

    shift_id: int
    shift_name: str
    start_time: str
    end_time: str
    is_active: bool


# =============================================================================
# /api/plan-vs-actual -- `/summary` has golden evidence for its top level;
# `/plan-vs-actual` and the `orders`/`line_breakdown` interiors are source-
# inspected (smoke seed's scoped capacity orders are empty either way).
# =============================================================================


class LineBreakdownEntry(BaseModel):
    """One entry of a PlanVsActualEntry's `line_breakdown` list --
    source-inspected, see `PlanVsActualEntry`."""

    line_id: str
    units_produced: int
    entry_count: int


class PlanVsActualEntry(BaseModel):
    """GET /api/plan-vs-actual -- SOURCE INSPECTION, NO CAPTURED EVIDENCE
    (golden entry is `[]`: the smoke seed's capacity orders don't clear this
    route's default active-status filter). Also reused for the `orders`
    field of GET /api/plan-vs-actual/summary, whose `orders` is empty for
    the identical reason (a bare key with no `[].` children).

    Modeled from `_build_plan_vs_actual_entry` (services/plan_vs_actual_service.py),
    unconditional -- always the same 18 keys -- and never touching a SQL
    aggregate: `wo_actual_total`/`production_total` are Python `sum()` over
    already-fetched ORM rows (`WorkOrder.actual_quantity` and
    `ProductionEntry.units_produced` are both `Integer`, not `Numeric`), so
    no Decimal hazard reaches this path despite the arithmetic.
    """

    capacity_order_id: int
    order_number: str
    customer_name: Optional[str] = None
    style_model: str
    status: Optional[str] = None
    priority: Optional[str] = None
    planned_quantity: int
    actual_completed: int
    variance_quantity: int
    variance_percentage: float
    completion_percentage: float
    required_date: Optional[str] = None
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    projected_completion: Optional[str] = None
    on_time_risk: str
    linked_work_orders: int
    line_breakdown: List[LineBreakdownEntry]


class RiskDistribution(BaseModel):
    """The `risk_distribution` object in GET /api/plan-vs-actual/summary.

    Field names are the literal dict keys `get_plan_vs_actual_summary`
    (services/plan_vs_actual_service.py) initializes and increments --
    upper-case because `_calculate_risk`'s return values are, not a styling
    choice.
    """

    LOW: int
    MEDIUM: int
    HIGH: int
    OVERDUE: int
    COMPLETED: int
    UNKNOWN: int


class PlanVsActualSummaryResponse(BaseModel):
    """GET /api/plan-vs-actual/summary -- golden evidence, 12 keys (top
    level + `risk_distribution.*`; `orders`' interior is source-inspected,
    see `PlanVsActualEntry`, whose reasoning also covers why no Decimal
    reaches `overall_variance` or the two quantity totals below.
    """

    total_orders: int
    total_planned_quantity: int
    total_actual_completed: int
    overall_variance: int
    overall_completion_pct: float
    risk_distribution: RiskDistribution
    orders: List[PlanVsActualEntry]

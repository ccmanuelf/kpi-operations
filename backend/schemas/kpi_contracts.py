"""Response contracts for /api/kpi.

Declared types are what close the Decimal class: MariaDB hands back Decimal,
Pydantic renders Decimal as a JSON string under `Any`, and a declared `float`
coerces it instead. See docs/superpowers/specs/2026-08-25-response-model-refactor-design.md.
"""

from datetime import date as date_type, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """One point on any KPI trend series.

    Shared by 9 endpoints (absenteeism, availability, efficiency, oee,
    on-time-delivery, performance, quality, throughput-time, wip-aging) --
    measured, not assumed: 8 of the 9 returned exactly ("date", "value") on
    2026-08-25 against the committed golden master; on-time-delivery/trend
    returned no rows under that seed (empty capture carries no shape), so its
    membership is confirmed by reading backend/routes/kpi/trends.py::get_otd_trend
    instead, which returns the identical `{"date": str(r.date), "value": ...}`
    shape as its siblings.
    """

    date: str
    value: float


# =============================================================================
# Task 7: the remaining 15 /api/kpi routes (measured 2026-08-25).
#
# Every model below is keyed one-to-one to a single route -- the brief for
# this task is explicit that the by-shift/by-product and efficiency/
# performance pairs must NOT share a model even though they look similar:
# efficiency carries actual_output/expected_output, performance carries
# units/rate. Forcing a shared model would make fields optional on both
# sides, which defeats the point of a typed contract.
# =============================================================================


class AvailabilityKPI(BaseModel):
    """GET /api/kpi/availability -- golden evidence, 12 keys (Group A)."""

    work_order_id: Optional[str] = None
    shift_id: Optional[str] = None
    target_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_scheduled_hours: float
    total_downtime_hours: float
    available_hours: float
    availability_percentage: float
    average_availability: float
    downtime_events: int
    calculation_timestamp: str


class DailyProductionSummary(BaseModel):
    """GET /api/kpi/dashboard -- golden evidence, list of 5 keys (Group A)."""

    date: datetime
    total_units: int
    avg_efficiency: float
    avg_performance: float
    entry_count: int


class DashboardDateRange(BaseModel):
    start_date: str
    end_date: str


class DashboardEfficiency(BaseModel):
    """Fields beyond current/target are absent, not null, on the
    SQLAlchemyError/Exception fallback path in get_aggregated_dashboard --
    they are Optional here (not required) so that fallback dict still
    validates instead of 500ing. `error` is declared so it survives
    serialization on that path; the route sets
    `response_model_exclude_unset=True` so a field absent from the source
    dict (the normal case: none of these sub-dicts ever contain "error" on
    the success path) is omitted from the JSON rather than emitted as an
    explicit `null` -- without that flag every declared-Optional field would
    appear as `null` on EVERY response, which is itself a golden-master
    regression (a key that used to be entirely absent now always exists)."""

    current: float
    target: float
    total_units: Optional[int] = None
    total_hours: Optional[float] = None
    error: Optional[str] = None


class DashboardPerformance(BaseModel):
    current: float
    target: float
    error: Optional[str] = None


class DashboardQuality(BaseModel):
    fpy: float
    fpy_target: Optional[float] = None
    ppm: float
    dpmo: float
    total_inspected: int
    total_passed: Optional[int] = None
    total_defective: Optional[int] = None
    total_defects: Optional[int] = None
    opportunities_per_unit: Optional[int] = None
    error: Optional[str] = None


class DashboardAvailability(BaseModel):
    current: float
    target: float
    downtime_hours: Optional[float] = None
    scheduled_hours: Optional[float] = None
    error: Optional[str] = None


class DashboardAbsenteeism(BaseModel):
    rate: float
    target: float
    total_scheduled_hours: Optional[float] = None
    total_absent_hours: Optional[float] = None
    employee_count: Optional[int] = None
    error: Optional[str] = None


class DashboardWipAging(BaseModel):
    total_active: int
    within_target: int
    overdue: int
    avg_aging_days: Optional[float] = None
    error: Optional[str] = None


class DashboardOtd(BaseModel):
    rate: float
    target: float
    total_orders: Optional[int] = None
    on_time_orders: Optional[int] = None
    late_orders: Optional[int] = None
    error: Optional[str] = None


class DashboardTrends(BaseModel):
    efficiency: List[TrendPoint] = []
    performance: List[TrendPoint] = []


class AggregatedDashboard(BaseModel):
    """GET /api/kpi/dashboard/aggregated -- golden evidence, 40 nested keys
    (Group A). "The hard one": spec Sec6 requires nested sub-models, not a
    flat Dict[str, Any], or the Decimal leak survives in the interior. The
    route sets `response_model_exclude_unset=True` -- see DashboardEfficiency
    for why."""

    date_range: DashboardDateRange
    client_id: Optional[str] = None
    efficiency: DashboardEfficiency
    performance: DashboardPerformance
    quality: DashboardQuality
    availability: DashboardAvailability
    absenteeism: DashboardAbsenteeism
    wip_aging: DashboardWipAging
    otd: DashboardOtd
    trends: DashboardTrends


class EfficiencyByProduct(BaseModel):
    """GET /api/kpi/efficiency/by-product -- golden evidence (Group A)."""

    product_id: int
    product_name: str
    actual_output: int
    efficiency: float


class EfficiencyByShift(BaseModel):
    """GET /api/kpi/efficiency/by-shift -- golden evidence (Group A)."""

    shift_id: int
    shift_name: str
    actual_output: int
    expected_output: int
    efficiency: float


class LateOrder(BaseModel):
    """GET /api/kpi/late-orders -- golden evidence (Group A)."""

    work_order: str
    product_id: int
    start_date: datetime
    days_pending: int
    total_units: int


class TrueOTDBreakdown(BaseModel):
    on_time: int
    late: int
    early: int
    total: int
    percentage: float
    net_percentage: float
    description: str
    inferred_dates_count: int
    skipped_no_date: int


class StandardOTDBreakdown(BaseModel):
    on_time: int
    total: int
    percentage: float
    net_percentage: float
    description: str
    inferred_dates_count: int
    skipped_no_date: int


class LateOrderCounts(BaseModel):
    total: int
    justified: int
    unjustified: int
    unclassified: int


class OTDSummary(BaseModel):
    """GET /api/kpi/otd -- golden evidence covers the 7 base keys (Group A).

    true_otd/standard_otd/late_counts/justified_by_reason are added by the
    route ONLY when scope resolves to exactly one client (source inspection,
    calculate_otd_kpi in routes/kpi/otd.py). Measured 2026-08-25: the smoke
    seed's admin fixture actually DOES resolve to a single client, so this
    branch fires under the very auth the golden master was captured with --
    but the committed golden entry for GET /api/kpi/otd only has the 7 base
    keys, meaning it was captured before this branch existed or under a
    different scope resolution. Declared Optional, with the route also
    setting `response_model_exclude_unset=True`, so: (a) when the branch
    does NOT fire, these 4 keys are genuinely absent from the JSON (matching
    the golden entry exactly, not emitted as `null`), and (b) when it DOES
    fire, all 4 keys serialize with real content. Either way nothing the
    endpoint used to return is silently dropped -- the alternative (plain
    Optional fields with no exclude_unset) would have added 4 extra `null`
    keys to the committed golden shape, which is a real regression, not the
    intended "4 becomes 4.0" kind of change this refactor allows.
    """

    start_date: date_type
    end_date: date_type
    client_id: Optional[str] = None
    otd_percentage: float
    on_time_count: int
    total_orders: int
    calculation_timestamp: datetime
    true_otd: Optional[TrueOTDBreakdown] = None
    standard_otd: Optional[StandardOTDBreakdown] = None
    late_counts: Optional[LateOrderCounts] = None
    justified_by_reason: Optional[Dict[str, int]] = None


class PerformanceByProduct(BaseModel):
    """GET /api/kpi/performance/by-product -- golden evidence (Group A)."""

    product_id: int
    product_name: str
    units: int
    rate: float
    performance: float


class PerformanceByShift(BaseModel):
    """GET /api/kpi/performance/by-shift -- golden evidence (Group A)."""

    shift_id: int
    shift_name: str
    units: int
    rate: float
    performance: float


class WipAgingTopItem(BaseModel):
    """GET /api/kpi/wip-aging/top -- golden evidence (Group A)."""

    work_order: str
    product: str
    age: int
    quantity: int


class ChronicHold(BaseModel):
    """GET /api/kpi/chronic-holds -- Group B: golden entry is `[]` (no rows
    under the smoke seed). Model derived from source inspection of
    identify_chronic_holds in backend/calculations/wip_aging.py, not from
    captured evidence."""

    hold_id: str
    work_order: str
    product_id: Optional[int] = None
    quantity: int
    aging_days: int
    hold_reason: Optional[str] = None
    hold_category: Optional[str] = None
    threshold_days_used: int


class OTDByClient(BaseModel):
    """GET /api/kpi/otd/by-client -- Group B: golden entry is `[]` (no rows).
    Model derived from source inspection of get_otd_by_client in
    backend/routes/kpi/otd.py, not from captured evidence."""

    client_id: str
    client_name: str
    total_deliveries: int
    on_time: int
    otd_percentage: float


class LateDelivery(BaseModel):
    """GET /api/kpi/otd/late-deliveries -- Group B: golden entry is `[]` (no
    rows). Model derived from source inspection of get_late_deliveries in
    backend/routes/kpi/otd.py, not from captured evidence."""

    delivery_date: str
    work_order: str
    client: str
    delay_hours: int
    style_model: Optional[str] = None


class LaborTotals(BaseModel):
    scheduled: float
    actual: float
    normal: float
    double: float
    triple: float
    unsplit_actual: float
    billed: float
    available_for_efficiency: float


class LaborClassBucket(BaseModel):
    actual: float
    billed: float
    available_for_efficiency: float


class LaborByLaborClass(BaseModel):
    direct: LaborClassBucket
    indirect: LaborClassBucket
    unclassified: LaborClassBucket


class LaborEntryCounts(BaseModel):
    total: int
    with_split: int
    with_allocations: int


class LaborHoursSummary(BaseModel):
    """GET /api/kpi/labor-hours -- Group B: golden entry is `<status:422>`
    (requires start_date/end_date query params the capture harness does not
    supply). Model derived from source inspection of summarize_labor_hours
    in backend/calculations/labor_hours.py and the route's own
    _coerce_nested/earned_hours/excluded_entries/efficiency_available_basis
    additions in backend/routes/kpi/labor_hours.py, not from captured
    evidence. `by_category` is a value-keyed map (dynamic allocation-category
    strings as keys -- same treatment capture.py's MAP_FIELDS already gives
    the identically-named field on /api/alerts/dashboard), typed as
    Dict[str, float] rather than a fixed submodel."""

    totals: LaborTotals
    by_labor_class: LaborByLaborClass
    by_category: Dict[str, float]
    entry_counts: LaborEntryCounts
    earned_hours: float
    excluded_entries: int
    efficiency_available_basis: Optional[float] = None


class KPICauseResponse(BaseModel):
    """GET /api/kpi/{metric}/cause -- Group B: golden entry is
    `<status:422>` (path param + required `date` query param). Model derived
    from source inspection of get_kpi_cause in backend/routes/kpi/cause.py
    and every driver function in backend/services/kpi_cause_service.py
    (top_downtime_reason, top_defect_type, top_absence_type,
    late_work_orders, oldest_active_hold, oee_dominant_loss) plus the two
    fallback branches (unknown driver, driver returns None): all seven
    driver functions and both fallbacks return exactly this same key set --
    {date, metric, kind, factor, value, unit, share} -- so despite the
    route's docstring warning that per-metric payloads vary, the key SET is
    provably invariant across every metric this route accepts. `kind` and
    `factor` are None only on the two fallback paths; `unit` is never None
    (empty string "" on fallback, a real unit otherwise); `value`/`share`
    are `float | None` on CauseResult itself. A precise model is therefore
    correct here, not a mis-fit -- this is NOT the allowlisted exception
    spec Sec6 anticipates for a genuinely variable shape.
    """

    date: str
    metric: str
    kind: Optional[str] = None
    factor: Optional[str] = None
    value: Optional[float] = None
    unit: str
    share: Optional[float] = None

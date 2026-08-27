"""Response contracts for Batch R3's `/api/work-orders` (3 of 5) and
`/api/alerts` (2 of 2) routes -- 6 of the batch's 12 total (the other 6, for
`/api/floating-pool` and `/api/attendance`, live in `floor_contracts.py`,
split out purely for the 500-line limit; see that module's docstring for the
batch-wide hazard/disclosure summary). `POST /api/work-orders/{id}/approve-qc`
lives here (not in the split-off /floating-pool module) because it shares
this module's `EXCLUDE_UNSET_ROUTES` pattern with `AlertsHistoryAccuracy
Response` below.

Three source-inspected interiors, real top-level golden evidence but an
empty/bare INTERIOR at capture time (the same treatment Batch R4 gave
`ThresholdEntry`/`ActivityLogEntry`): `WorkOrderProgressResponse.
hold_history` (no HOLD_ENTRY rows on the captured work order) and
`WorkOrderCapacityOrderResponse.capacity_order` (no linked CAPACITY_ORDERS
row on that same work order).

Two routes have a genuinely CONDITIONAL shape -- a field present on one
branch, absent (not null) on another -- registered in `EXCLUDE_UNSET_ROUTES`
(tests/contract/conditional_branches.py) and forced in
test_conditional_branches.py: `AlertsHistoryAccuracyResponse` (GET
/api/alerts/history/accuracy, whose two branches share only `period_days`/
`total_predictions`) and `WorkOrderApproveQCResponse` (POST /api/work-
orders/{id}/approve-qc, whose already-approved branch omits `message`).
"""

from typing import Any, List, Optional

from pydantic import BaseModel

from backend.schemas.alert import AlertResponse

# =============================================================================
# /api/work-orders
# =============================================================================


class CapacityOrderInfo(BaseModel):
    """The `capacity_order` object in GET /api/work-orders/{work_order_id}/
    capacity-order -- source-inspected: golden evidence is the not-linked
    branch (`{"linked": false, "capacity_order": null}`, 2 bare keys), the
    seeded work order used for capture has no linked CAPACITY_ORDERS row.
    Modeled from `orm/capacity/orders.py`'s `CapacityOrder` columns, as
    `get_work_order_capacity_order` (routes/work_orders.py) forwards them
    verbatim.
    """

    id: int
    order_number: str
    customer_name: Optional[str] = None
    style_model: str
    order_quantity: int
    completed_quantity: Optional[int] = None
    required_date: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class WorkOrderCapacityOrderResponse(BaseModel):
    """GET /api/work-orders/{work_order_id}/capacity-order -- golden
    evidence, 2 keys (the not-linked branch; see `CapacityOrderInfo`).
    """

    linked: bool
    capacity_order: Optional[CapacityOrderInfo] = None


class ProductionEntryProgressItem(BaseModel):
    """One entry of GET /api/work-orders/{work_order_id}/progress's
    `production_entries` list -- golden evidence. `run_time_hours` is
    already `float(...)`-cast in the route off a `Numeric(10, 2)` column;
    `units_produced`/`employees_assigned`/`defect_count`/`scrap_count` are
    plain `Integer` columns.
    """

    production_entry_id: str
    production_date: Optional[str] = None
    units_produced: int
    run_time_hours: Optional[float] = None
    employees_assigned: int
    defect_count: int
    scrap_count: int
    shift_name: Optional[str] = None
    product_name: Optional[str] = None


class QualityInspectionProgressItem(BaseModel):
    """One entry of `quality_inspections` -- golden evidence."""

    inspection_id: str
    inspection_date: Optional[str] = None
    inspection_type: Optional[str] = None
    result: Optional[str] = None
    defects_found: int
    notes: Optional[str] = None


class HoldHistoryItem(BaseModel):
    """One entry of `hold_history` -- real top-level evidence for `progress`
    (bare `hold_history` key: the captured work order has no HOLD_ENTRY
    rows), interior source-inspected from the route's own dict literal
    (routes/work_orders.py). `quantity` is a hardcoded `None` literal in
    EVERY branch -- never assigned a real value anywhere in this route -- so
    its true type is unconstrained; kept `Optional[Any]` rather than
    guessing one.
    """

    hold_id: str
    hold_date: Optional[str] = None
    resume_date: Optional[str] = None
    reason: Optional[str] = None
    quantity: Optional[Any] = None
    status: Optional[str] = None


class WorkOrderProgressResponse(BaseModel):
    """GET /api/work-orders/{work_order_id}/progress -- golden evidence, 27
    keys. `progress_percentage` is always a `float` (Python true division of
    two `Integer` columns, or the `0.0` literal default) -- no widening.
    `remaining_quantity` is `max(0, int - int)`, plain `int`.
    """

    work_order_id: str
    style_model: str
    status: str
    planned_quantity: int
    actual_quantity: Optional[int] = None
    progress_percentage: float
    remaining_quantity: int
    is_on_track: bool
    production_entries: List[ProductionEntryProgressItem]
    quality_inspections: List[QualityInspectionProgressItem]
    hold_history: List[HoldHistoryItem]
    total_production_entries: int
    total_defects: int
    total_scrap: int


class WorkOrderTimelineEvent(BaseModel):
    """One entry of GET /api/work-orders/{work_order_id}/timeline's `events`
    list -- golden evidence. Every one of the route's 6 append sites
    (routes/work_orders.py) builds this identical 6-key dict.
    """

    event_type: str
    title: str
    description: str
    timestamp: str
    icon: str
    color: str


class WorkOrderTimelineResponse(BaseModel):
    """GET /api/work-orders/{work_order_id}/timeline -- golden evidence, 8
    keys."""

    work_order_id: str
    events: List[WorkOrderTimelineEvent]
    total_events: int


class WorkOrderApproveQCResponse(BaseModel):
    """POST /api/work-orders/{work_order_id}/approve-qc -- golden evidence,
    6 keys (the freshly-approved branch -- the isolated-capture harness
    always calls this exactly once per restored snapshot, landing here
    first). `message` is absent, not null, on the OTHER branch
    (`work_order.qc_approved` already true) -- registered in
    `EXCLUDE_UNSET_ROUTES`, forced in test_conditional_branches.py.
    `qc_approved` is a hardcoded Python `bool` literal in BOTH branches
    (routes/work_orders.py), never the raw `Optional[int]` WORK_ORDER.
    qc_approved column.
    """

    status: str
    work_order_id: str
    qc_approved: bool
    qc_approved_date: Optional[str] = None
    qc_approved_by: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# /api/alerts
# =============================================================================


class AlertsHistoryAccuracyResponse(BaseModel):
    """GET /api/alerts/history/accuracy -- golden evidence, 4 keys, but only
    for ONE of two entirely disjoint branches. `get_prediction_accuracy`
    (routes/alerts/config_history.py) returns EITHER a 4-key `{period_days,
    total_predictions, accuracy_metrics: null, message}` dict when the
    lookback window has zero ALERT_HISTORY rows with a non-null actual_value
    (the smoke seed's captured branch), OR an entirely different 6-key
    `{period_days, total_predictions, accurate_predictions, accuracy_rate_
    percent, average_error_percent, category}` dict once such rows exist --
    the two branches share only `period_days`/`total_predictions`.
    Registered in `EXCLUDE_UNSET_ROUTES` (all 6 non-shared fields Optional);
    forced in test_conditional_branches.py, which also proves the golden
    branch's `accuracy_metrics`/`message` are correctly ABSENT on the other
    side. `accuracy_metrics` is a hardcoded `None` literal, never assigned a
    real value anywhere in the route -- kept `Optional[Any]`, same reasoning
    as `HoldHistoryItem.quantity`. `average_error_percent` is an int->float
    widening instance when every `error_percent` in the window is falsy
    (`errors` is then `[]` and `avg_error` the bare int `0`).
    """

    period_days: int
    total_predictions: int
    accuracy_metrics: Optional[Any] = None
    message: Optional[str] = None
    accurate_predictions: Optional[int] = None
    accuracy_rate_percent: Optional[float] = None
    average_error_percent: Optional[float] = None
    category: Optional[str] = None


class AlertsCheckAllResponse(BaseModel):
    """POST /api/alerts/generate/check-all -- golden evidence, 26 keys.
    `alerts` reuses the pre-existing `schemas.alert.AlertResponse` directly
    (already typed `float`, never `Decimal`, for current_value/threshold_
    value/predicted_value/confidence) rather than a duplicate -- the same
    reuse Task 9 applied to `WorkflowConfigResponse`. `errors` is `errors if
    errors else None` (routes/alerts/generate.py) -- always a PRESENT
    `null`, never an omitted key (the 4 internal checks are wrapped in a
    narrow `except (SQLAlchemyError, ValueError)`, not a bare `except
    Exception`, so there is no `exclude_unset` case here).
    """

    status: str
    alerts_generated: int
    alerts: List[AlertResponse]
    errors: Optional[List[str]] = None

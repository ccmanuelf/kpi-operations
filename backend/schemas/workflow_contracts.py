"""Response contracts for the 9 `/api/workflow` GET routes converted in Task 9.

Declared types are what close the Decimal class on the routes that need it:
MariaDB hands back Decimal for some aggregates, Pydantic renders Decimal as a
JSON string under `Any`, and a declared numeric type coerces it instead. See
docs/superpowers/specs/2026-08-25-response-model-refactor-design.md.

`backend.schemas.workflow.WorkflowConfigResponse` already matches
`GET /api/workflow/config/{client_id}` field-for-field (client_id,
workflow_statuses, workflow_transitions, workflow_optional_statuses,
workflow_closure_trigger, workflow_version -- verified against
`get_workflow_config` in backend/calculations/workflow_engine.py) and is
reused directly from routes/workflow.py rather than duplicated here.
`WorkflowTemplate` and `AllowedTransitionsResponse` in that same module were
considered and rejected for their similarly-named routes below -- see each
class's docstring for why.
"""

from typing import List, Optional

from pydantic import BaseModel


class TemplateSummary(BaseModel):
    """One entry of GET /api/workflow/templates's `templates` list --
    golden evidence, 5 keys.

    NOT backend.schemas.workflow.WorkflowTemplate: that model also requires
    workflow_transitions and workflow_optional_statuses, which the route's
    own per-template dict (routes/workflow.py::list_workflow_templates)
    never includes -- using it here would 500 on every call.
    """

    template_id: str
    name: str
    description: str
    workflow_statuses: List[str]
    workflow_closure_trigger: str


class TemplatesListResponse(BaseModel):
    """GET /api/workflow/templates -- golden evidence, 6 keys."""

    templates: List[TemplateSummary]
    count: int


class AverageTimesBreakdown(BaseModel):
    lifecycle_hours: Optional[float] = None
    lifecycle_days: Optional[float] = None
    lead_time_hours: Optional[float] = None
    lead_time_days: Optional[float] = None
    processing_time_hours: Optional[float] = None
    processing_time_days: Optional[float] = None


class AverageTimesSummary(BaseModel):
    """GET /api/workflow/analytics/{client_id}/average-times -- golden
    evidence, 10 keys.

    `calculate_client_average_times` (backend/calculations/elapsed_time.py)
    returns a SHORTER dict -- `{client_id, count: 0, averages: None}` -- when
    the client has zero matching work orders: `overdue_count` and
    `overdue_percentage` are absent from that dict entirely, not present as
    null. `Optional[...] = None` alone would still emit them as explicit
    `null` on that path (a real regression the golden master's captured
    client, which has work orders, cannot see); the route pairs this model
    with `response_model_exclude_unset=True` to keep them genuinely absent
    when the source dict never set them. `averages: None` on that same path
    is a real key with a null value, which `Optional[...]` alone already
    reproduces correctly.
    """

    client_id: str
    count: int
    overdue_count: Optional[int] = None
    overdue_percentage: Optional[float] = None
    averages: Optional[AverageTimesBreakdown] = None


class StageDurationEntry(BaseModel):
    """One row of `stage_durations` in GET
    /api/workflow/analytics/{client_id}/stage-durations.

    NOT captured: the golden entry's `stage_durations` key has no dotted
    children because the smoke seed produced zero grouped rows for it
    (`calculate_stage_duration_summary` groups WORKFLOW_TRANSITION_LOG by
    (from_status, to_status)). Modeled from reading
    backend/calculations/elapsed_time.py::calculate_stage_duration_summary
    directly, exactly as Task 7 did for its Group B routes (chronic-holds,
    otd/by-client, otd/late-deliveries) -- there is no captured evidence for
    this interior. `elapsed_from_previous_hours` is an Integer column
    (backend/orm/workflow.py), so `avg`/`min`/`max` never actually carry a
    live Decimal on either SQL dialect regardless of the type declared here;
    this model exists to satisfy spec Sec6's nested-structure requirement (a
    List[StageDurationEntry], not Dict[str, Any]) rather than to close a
    Decimal leak this particular field never had.
    """

    from_status: Optional[str] = None
    to_status: str
    avg_hours: Optional[float] = None
    avg_days: Optional[float] = None
    min_hours: Optional[int] = None
    max_hours: Optional[int] = None
    transition_count: int


class StageDurationsFilter(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class StageDurationsResponse(BaseModel):
    client_id: str
    stage_durations: List[StageDurationEntry]
    filter: StageDurationsFilter


class StatusDistributionItem(BaseModel):
    status: str
    count: int
    percentage: float


class StatusDistributionResponse(BaseModel):
    """GET /api/workflow/statistics/{client_id}/status-distribution."""

    client_id: str
    total_work_orders: int
    by_status: List[StatusDistributionItem]


class TransitionByStatus(BaseModel):
    from_status: Optional[str] = None
    to_status: str
    count: int
    avg_elapsed_hours: Optional[float] = None


class TransitionBySource(BaseModel):
    trigger_source: Optional[str] = None
    count: int


class TransitionStatisticsResponse(BaseModel):
    """GET /api/workflow/statistics/{client_id}/transitions."""

    client_id: str
    total_transitions: int
    by_transition: List[TransitionByStatus]
    by_source: List[TransitionBySource]


class WorkOrderAllowedTransitions(BaseModel):
    """GET /api/workflow/work-orders/{work_order_id}/allowed-transitions.

    NOT backend.schemas.workflow.AllowedTransitionsResponse: that model is
    missing `work_order_id`, one of the four keys
    `get_allowed_transitions_for_work_order`
    (backend/crud/workflow/operations.py) always returns -- using it here
    would silently drop that field from every response.
    """

    work_order_id: str
    client_id: str
    current_status: str
    allowed_next_statuses: List[str]


class ElapsedTimeLifecycle(BaseModel):
    total_hours: Optional[int] = None
    total_days: Optional[float] = None
    is_overdue: bool
    days_early_or_late: Optional[int] = None


class ElapsedTimeStages(BaseModel):
    lead_time_hours: Optional[int] = None
    lead_time_days: Optional[float] = None
    processing_time_hours: Optional[int] = None
    processing_time_days: Optional[float] = None
    shipping_time_hours: Optional[int] = None


class ElapsedTimeForecast(BaseModel):
    time_to_expected_hours: Optional[int] = None
    expected_date: Optional[str] = None


class ElapsedTimeDates(BaseModel):
    received_date: Optional[str] = None
    dispatch_date: Optional[str] = None
    shipped_date: Optional[str] = None
    closure_date: Optional[str] = None


class WorkOrderElapsedTimeResponse(BaseModel):
    """GET /api/workflow/work-orders/{work_order_id}/elapsed-time -- golden
    evidence, 17 keys across 4 fixed nested groups.

    `WorkOrderElapsedTime.get_all_metrics`
    (backend/calculations/elapsed_time.py) always emits all 4 groups and
    every one of their keys as a single dict literal -- each leaf is a real
    (possibly null) value, never an omitted key. Checked against the source
    directly: this route does NOT need `response_model_exclude_unset`, unlike
    the brief's hint that it was a likely candidate.
    """

    work_order_id: str
    status: str
    lifecycle: ElapsedTimeLifecycle
    stages: ElapsedTimeStages
    forecast: ElapsedTimeForecast
    dates: ElapsedTimeDates


class TransitionTimeEntry(BaseModel):
    """One item of GET
    /api/workflow/work-orders/{work_order_id}/transition-times.

    `get_transition_elapsed_times` (backend/calculations/elapsed_time.py)
    builds each dict as a literal with all 8 keys always present, so this
    route needs no `response_model_exclude_unset` either.
    """

    transition_id: int
    from_status: Optional[str] = None
    to_status: str
    transitioned_at: Optional[str] = None
    elapsed_from_previous_hours: Optional[int] = None
    elapsed_from_received_hours: Optional[int] = None
    trigger_source: Optional[str] = None
    notes: Optional[str] = None

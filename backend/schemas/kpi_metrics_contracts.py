"""Response contracts for Batch R5, part 2: the batch's two Decimal/floor
hazards and its one exclude_unset case -- `GET /api/jobs/kpi/rty-summary`,
`GET /api/inference/cycle-time/{product_id}`, `GET /api/client-config/
{client_id}/effective`, `POST /api/metrics/calculate/run-nightly`. The
batch's remaining 7 typed routes and its JSON-Schema-document exception live
in `reference_contracts.py`; see
docs/superpowers/plans/2026-08-25-response-model-refactor.md and
`.superpowers/sdd/2026-08-25-response-model-refactor/task-R5-brief.md`.

HAZARD 1 -- `GET /api/client-config/{client_id}/effective` is a `NEVER_404`
member (`tests/contract/param_specs.py`): "falls back to system defaults for
an unknown client rather than 404ing". `crud/client_config.py::
get_client_config_or_defaults` has two branches -- a real `ClientConfig` row
(`otd_mode`/etc, all `Float`/`Integer` ORM columns, orm/client_config.py) or
the literal `GLOBAL_DEFAULTS` dict -- and the golden master's 13 keys cannot
tell which one it captured. Modeled from BOTH branches, not just the
captured one: reading `get_client_config_or_defaults` line by line, both
share the identical 13-key set, and neither can carry a Decimal --
`ClientConfig`'s numeric columns are `Float`/`Integer`, never `Numeric`. So
this route's own `-> Any` annotation (which WOULD stringify a Decimal if one
existed, per the corrected exponent rule) never actually leaks one; there is
nothing to fix here, only to model honestly. `otd_mode` is a string enum
value (`.value`); `is_default` is the one field that tells the two branches
apart, and it IS in the captured 13.

HAZARD 2 -- `GET /api/inference/cycle-time/{product_id}` carries a LIVE
Decimal-string leak, measured directly against a fresh seeded SQLite DB this
session (smoke profile, seed_value=1234, product_id=1, which resolves to the
`historical_30day_avg` branch):

    BEFORE: {"ideal_cycle_time":"0.034260326879026824", ...}   (JSON string)
    AFTER:  {"ideal_cycle_time":0.034260326879026824, ...}     (JSON number)

`calculations/inference.py::InferenceEngine.infer_ideal_cycle_time` is
declared `-> Tuple[Decimal, float, str, bool]` and builds `Decimal(str(...))`
in every one of its 6 return branches -- dialect-independent (the Decimal is
constructed in Python, not read off a `Numeric` column), so this leak is
live on SQLite today, including the current demo deployment, not only on
MariaDB. The route itself carries no `response_model` and is annotated
`-> Any` (`routes/reference.py:136`), so FastAPI's inferred model already
renders the bare `Decimal` as a JSON string, per the corrected exponent
rule (`def f() -> Any:` is the ANNOTATED case, not the immune one).
Declaring `ideal_cycle_time: float` closes it -- a per-unit cycle time is
genuinely fractional, never `int`, and never `Decimal`.
`confidence_score`/`confidence` are already-native `float`
(`InferenceEngine`'s own confidence constants, e.g. `0.6`, `1.0`, never
Decimal); `warning`/`recommendation` are `Optional[str]`,
`needs_review`/`is_estimated` are `bool` -- all four of the last group
sourced from `InferenceEngine.flag_low_confidence`, which returns the SAME
4 keys on both of its branches (never an omission -- no exclude_unset
needed on this route).

This route's `NEVER_404` entry was removed in `7ba8c0a`: the cross-tenant
security fix (#238) added a product lookup that 404s on an unknown id, then
calls `verify_client_access` on the product's owning client, so the route
now discriminates. That call is UNTOUCHED by this batch -- every route diff
below is a pure decorator/import change, verified with
`git diff --unified=0` per file.

EXCLUDE_UNSET -- `GET /api/jobs/kpi/rty-summary`: `calculations/fpy_rty.py::
calculate_job_rty_summary`'s zero-completed-jobs branch (the smoke seed's
captured shape, 9 keys) omits three keys the populated branch always sends
-- `total_good_units`, `jobs_meeting_target`, `interpretation` (forced with
a real completed job below; measured directly, not assumed). Registered in
`EXCLUDE_UNSET_ROUTES` (`tests/contract/conditional_branches.py`); forced in
`test_conditional_branches.py::
test_jobs_rty_summary_populated_branch_pins_the_extra_keys`.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# GET /api/client-config/{client_id}/effective -- HAZARD 1, a NEVER_404 floor
# =============================================================================


class ClientConfigEffectiveResponse(BaseModel):
    """See the module docstring's HAZARD 1. Field types cross-checked
    against BOTH `crud/client_config.py::get_client_config_or_defaults`
    branches: the real-config branch (`orm/client_config.py`'s `Float`/
    `Integer`, all `Optional`-typed, columns) and the literal
    `GLOBAL_DEFAULTS` dict -- both share this exact 13-key set."""

    otd_mode: str
    default_cycle_time_hours: Optional[float] = None
    efficiency_target_percent: Optional[float] = None
    quality_target_ppm: Optional[float] = None
    fpy_target_percent: Optional[float] = None
    dpmo_opportunities_default: Optional[int] = None
    availability_target_percent: Optional[float] = None
    performance_target_percent: Optional[float] = None
    oee_target_percent: Optional[float] = None
    absenteeism_target_percent: Optional[float] = None
    wip_aging_threshold_days: Optional[int] = None
    wip_critical_threshold_days: Optional[int] = None
    is_default: bool


# =============================================================================
# GET /api/inference/cycle-time/{product_id} -- HAZARD 2, live Decimal-string leak
# =============================================================================


class InferenceCycleTimeResponse(BaseModel):
    """See the module docstring's HAZARD 2 for the measured before/after."""

    product_id: int
    shift_id: Optional[int] = None
    ideal_cycle_time: float
    confidence_score: float
    source_level: str
    is_estimated: bool
    warning: Optional[str] = None
    confidence: float
    recommendation: Optional[str] = None
    needs_review: bool


# =============================================================================
# GET /api/jobs/kpi/rty-summary -- exclude_unset
# =============================================================================


class JobRTYPeriod(BaseModel):
    start_date: str
    end_date: str


class TopScrapOperation(BaseModel):
    """`calculations/fpy_rty.py::calculate_job_rty_summary`'s
    `operation_scrap` accumulator -- Python `+=` over `Job.quantity_scrapped
    or 0` (an `Integer` column, orm/job.py), never a SQL aggregate."""

    operation: str
    units_scrapped: int


class JobRTYSummaryResponse(BaseModel):
    """`routes/jobs.py::get_job_rty_summary` ->
    `calculations/fpy_rty.py::calculate_job_rty_summary`. All Python-summed
    `int`s off `Integer` ORM columns (`Job.completed_quantity`/
    `quantity_scrapped`, orm/job.py) read as row attributes, never a SQL
    `func.sum` -- no MariaDB SUM-Decimal exposure. `average_job_yield`/
    `overall_yield` are `float(...)`-cast on both branches (the empty
    branch uses the float literal `0.0`, never a bare int `0` -- no
    widening to disclose). `total_good_units`/`jobs_meeting_target`/
    `interpretation` are absent, not null, on the zero-completed-jobs
    branch -- see the module docstring's EXCLUDE_UNSET note;
    `response_model_exclude_unset` is set on this route."""

    period: JobRTYPeriod
    total_jobs_completed: int
    total_units_completed: int
    total_units_scrapped: int
    total_good_units: Optional[int] = None
    average_job_yield: float
    overall_yield: float
    jobs_below_target: int
    jobs_meeting_target: Optional[int] = None
    top_scrap_operations: List[TopScrapOperation]
    interpretation: Optional[str] = None


# =============================================================================
# POST /api/metrics/calculate/run-nightly
# =============================================================================


class NightlyMetricResults(BaseModel):
    """`tasks/dual_view_calculation.py::run_for_client` -- each value is a
    persisted `METRIC_CALCULATION_RESULT.result_id` (`Integer` primary key,
    orm/metric_calculation_result.py), or `None` if that metric's own
    calculation raised. All three keys are always present (`results =
    {"oee": None, "otd": None, "fpy": None}` initialized before any
    calculation runs, then selectively overwritten) -- never an omission."""

    oee: Optional[int] = None
    otd: Optional[int] = None
    fpy: Optional[int] = None


class RunNightlyResponse(BaseModel):
    """`routes/dual_view_calculate.py::trigger_nightly_run`. `summary` is
    keyed by `client_id` -- a genuine data-keyed map (one entry per active
    client, `tasks/dual_view_calculation.py::
    run_nightly_dual_view_calculations`), modeled as `Dict[str, ...]`
    rather than enumerated fields, the same reasoning as
    `reference_contracts.FilterStatisticsResponse.filters_by_type`.
    Admin-only (`get_current_admin`, untouched by this batch); reached by
    the write-capture harness with no request body, per
    task-R5-brief.md."""

    status: str
    summary: Dict[str, NightlyMetricResults]

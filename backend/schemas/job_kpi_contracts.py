"""Response contracts for the six `GET /api/jobs/{job_id}/*` KPI routes --
`yield`, `efficiency`, `performance`, `ppm`, `dpmo`, `kpi-summary`. This is
the last increment of the response-model refactor; `ALLOWLIST` goes 35 -> 29
with it. See docs/superpowers/plans/2026-08-25-response-model-refactor.md.

These six were UNREACHABLE until #244 seeded JOB rows, which is the only
reason they can be modelled from measured evidence rather than from reading
the handlers. `param_specs.py`'s `job_id` spec resolves the id from
PRODUCTION_ENTRY, not from JOB, precisely so the capture lands on the
POPULATED branch of all six -- read that spec's `note` before touching
anything here.

THE LEAK, measured against the harness's seeded SQLite DB
(`GET /api/jobs/DEMO-HOURLY-WO-0001-OP1/yield`, seed as_of 2026-08-25):

    BEFORE: {..., "yield_percentage":"99.00", "completed_quantity":500, ...}
    AFTER:  {..., "yield_percentage":99.0,    "completed_quantity":500, ...}

`calculations/fpy_rty.py::calculate_job_yield` returns `yield_pct` as a bare
`Decimal` (`:617` -- `(Decimal(str(good)) / Decimal(str(completed))) * 100`),
and `routes/jobs.py::get_job_yield` is annotated `-> Any`, which is the
ANNOTATED case, not the encoder-reached one, so FastAPI's inferred model
renders that Decimal as a JSON STRING. Dialect-independent -- the Decimal is
constructed in Python from two `Integer` columns, never read off a `Numeric`
one -- so this is live on SQLite today, not only on MariaDB.

The sharpest evidence that the MODEL is the right place to declare this, and
not the handler's casting discipline, is inside the same capture: the SAME
number, for the SAME job, is a JSON number on `kpi-summary`
(`"yield":{"yield_percentage":99.0,...}`) and a JSON string on `yield`
(`"yield_percentage":"99.00"`). `get_job_kpi_summary` happens to call
`float(...)` on its copy and `calculate_job_yield` happens not to. A
consumer of both endpoints sees one metric in two types, decided by which
handler last remembered to cast. The other five routes cast every numeric
value they emit, so none of them leaks today -- what they lack is anything
that would NOTICE if a future edit stopped casting. That is what these
models are for.

EXCLUDE_UNSET -- four of the six (`efficiency`, `performance`, `ppm`,
`dpmo`) return a SHORTER dict, with a `message` key the populated branch
never sends, when the job has no PRODUCTION_ENTRY / QUALITY_ENTRY rows
joined to it. That branch is real and ordinary (S3 seeds a full routing, so
most JOB rows are steps no shift ever ran -- `param_specs.py`'s `job_id`
note), it is simply not the one any capture reaches. Modelling only the
captured branch would make those routes STOP SENDING `message` -- exactly
the regression the golden master exists to catch, on the one branch it
cannot see. All four are registered in `EXCLUDE_UNSET_ROUTES`
(`tests/contract/conditional_branches.py`) and forced by
`test_job_kpi_empty_entries_branches_keep_their_own_shape`
(`test_conditional_branches.py`), which pins both key sets on the RAW dict
before the model normalises it.

`kpi-summary` needs no such treatment: it has ONE return, and its three
nested objects are built unconditionally.

`yield` needs none either, and its second branch is a different case worth
being explicit about rather than silently omitting.
`calculate_job_yield` has a "Job not found" branch (`fpy_rty.py:604-611`)
that omits `operation_name`/`sequence_number`/`part_number` and adds
`error`. It is UNREACHABLE through this route: `get_job_yield` calls
`crud/job.py::get_job` first and raises 404 when it returns None, and
`get_job` is the SAME `db.query(Job).filter(Job.job_id == job_id)` lookup
narrowed by a client filter (both go through the soft-delete filter). A
lookup that survives the narrower query cannot fail the wider one, so a
request that reaches `calculate_job_yield` always finds its row. The branch
is therefore modelled out, not modelled as optional: declaring `error` and
`Optional` operation fields would emit three nulls on every real response
and silently swallow the "Job not found" message if it ever did fire.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# GET /api/jobs/{job_id}/yield -- the measured Decimal-string leak
# =============================================================================


class JobYieldResponse(BaseModel):
    """`routes/jobs.py::get_job_yield` ->
    `calculations/fpy_rty.py::calculate_job_yield`. See the module docstring
    for the measured before/after and for why the function's second branch is
    not modelled.

    `yield_percentage` is the leak: a bare `Decimal`, `float` here.
    `completed_quantity`/`quantity_scrapped` are `Integer` columns
    (orm/job.py) read as row attributes with an `or 0` guard, and
    `good_quantity` is their Python difference -- `int`, never a SQL
    aggregate, so no MariaDB SUM-Decimal exposure. `operation_name`
    (`String`, NOT NULL) and `sequence_number` (`Integer`, NOT NULL) are
    required; `part_number` is a nullable column and really can be null.
    """

    job_id: str
    operation_name: str
    sequence_number: int
    part_number: Optional[str] = None
    yield_percentage: float
    completed_quantity: int
    quantity_scrapped: int
    good_quantity: int


# =============================================================================
# GET /api/jobs/{job_id}/efficiency -- exclude_unset
# =============================================================================


class JobEfficiencyEntry(BaseModel):
    """One PRODUCTION_ENTRY row in `get_job_efficiency`'s `entries` list.
    `production_entry_id` is a `String` primary key (orm/production_entry.py),
    `units_produced` an `Integer` NOT NULL column, and
    `efficiency_percentage` a `Numeric(8, 4)` column the handler already
    casts with `float(e.efficiency_percentage or 0)` -- `float` is what keeps
    it a JSON number if that cast is ever dropped.
    """

    production_entry_id: str
    units_produced: int
    efficiency_percentage: float


class JobEfficiencyResponse(BaseModel):
    """`routes/jobs.py::get_job_efficiency`. `part_number`, `entries` are
    absent -- not null -- on the no-entries branch, and `message` is present
    only there; see the module docstring's EXCLUDE_UNSET note.

    `efficiency_percentage` averages `ProductionKPIService.
    calculate_efficiency_only`'s `Decimal` results and `total_labor_hours`
    sums `Numeric(10, 2)` `run_time_hours`; both are `float` for that reason.
    `total_units_produced`/`entry_count` are Python sums/counts over
    `Integer` columns.
    """

    job_id: str
    part_number: Optional[str] = None
    efficiency_percentage: float
    total_units_produced: int
    total_labor_hours: float
    entry_count: int
    entries: Optional[List[JobEfficiencyEntry]] = None
    message: Optional[str] = None


# =============================================================================
# GET /api/jobs/{job_id}/performance -- exclude_unset
# =============================================================================


class JobPerformanceResponse(BaseModel):
    """`routes/jobs.py::get_job_performance`. `total_run_time_hours` is
    absent -- not null -- on the no-entries branch, which is also the only
    branch that sends `message`; see the module docstring's EXCLUDE_UNSET
    note.

    `performance_percentage` averages `ProductionKPIService.
    calculate_performance_only`'s `Decimal` results, `total_run_time_hours`
    sums `Numeric(10, 2)` `run_time_hours` -- `float` both.
    """

    job_id: str
    performance_percentage: float
    total_units_produced: int
    total_run_time_hours: Optional[float] = None
    entry_count: int
    message: Optional[str] = None


# =============================================================================
# GET /api/jobs/{job_id}/ppm -- exclude_unset
# =============================================================================


class JobPPMResponse(BaseModel):
    """`routes/jobs.py::get_job_ppm`. Every field except `message` is sent on
    both branches -- `message` alone is what makes this an exclude_unset
    route; see the module docstring's EXCLUDE_UNSET note.

    `ppm` is `calculations/ppm.py::calculate_ppm_pure`'s quantized `Decimal`
    -- `float`. `total_inspected`/`total_defects` are Python `sum()`s over
    `Integer` QUALITY_ENTRY columns (orm/quality_entry.py), never
    `func.sum`.
    """

    job_id: str
    ppm: float
    total_inspected: int
    total_defects: int
    entry_count: int
    message: Optional[str] = None


# =============================================================================
# GET /api/jobs/{job_id}/dpmo -- exclude_unset
# =============================================================================


class JobDPMOResponse(BaseModel):
    """`routes/jobs.py::get_job_dpmo`. `total_inspected`, `total_defects`,
    `opportunities_per_unit` and `using_part_specific_opportunities` are
    absent -- not null -- on the no-entries branch, which is also the only
    branch that sends `message`; see the module docstring's EXCLUDE_UNSET
    note.

    `dpmo` and `sigma_level` are `calculations/dpmo.py`'s `Decimal` returns
    (`calculate_dpmo_pure`, `calculate_sigma_level_pure`) -- `float`.
    `total_opportunities` is the second half of `calculate_dpmo_pure`'s
    tuple, declared `int` there, and `opportunities_per_unit` is
    `get_opportunities_for_part`/`get_client_opportunities_default`'s `int`.
    `using_part_specific_opportunities` reports whether the JOB row carried a
    part number at all, not whether a PART_OPPORTUNITIES row was found --
    pre-existing, and left exactly as it is.
    """

    job_id: str
    dpmo: float
    sigma_level: float
    total_inspected: Optional[int] = None
    total_defects: Optional[int] = None
    total_opportunities: int
    opportunities_per_unit: Optional[int] = None
    using_part_specific_opportunities: Optional[bool] = None
    entry_count: int
    message: Optional[str] = None


# =============================================================================
# GET /api/jobs/{job_id}/kpi-summary -- one branch, three nested objects
# =============================================================================


class JobSummaryProductionKPIs(BaseModel):
    """`get_job_kpi_summary`'s `production_kpis`. `efficiency_percentage`/
    `performance_percentage` average `ProductionKPIService`'s `Decimal`
    results and `quality_rate` is a `Decimal` ratio computed in the handler
    -- `float` all three. `total_units_produced`/`defect_count`/`scrap_count`
    are Python sums over `Integer` columns; `entry_count` is a `len()`.
    """

    efficiency_percentage: float
    performance_percentage: float
    quality_rate: float
    total_units_produced: int
    defect_count: int
    scrap_count: int
    entry_count: int


class JobSummaryQualityKPIs(BaseModel):
    """`get_job_kpi_summary`'s `quality_kpis`. Same provenance as
    `JobPPMResponse`/`JobDPMOResponse` above, minus `total_opportunities`
    and `using_part_specific_opportunities`, which this route computes but
    does not send. `total_defects` here is `units_defective` (the PPM
    numerator), NOT the `total_defects_count` the DPMO numerator uses --
    the two names differ by design in the handler.
    """

    ppm: float
    dpmo: float
    sigma_level: float
    total_inspected: int
    total_defects: int
    opportunities_per_unit: int
    entry_count: int


class JobSummaryYield(BaseModel):
    """`get_job_kpi_summary`'s `yield`. `yield_percentage` comes from
    `calculate_job_yield_pure`, which returns a `Decimal` the handler casts
    to `float` -- unlike `calculate_job_yield` on the `/yield` route, which
    does not. See the module docstring: that divergence is the reason these
    models exist.
    """

    yield_percentage: float
    completed_quantity: int
    quantity_scrapped: int


class JobKPISummaryResponse(BaseModel):
    """`routes/jobs.py::get_job_kpi_summary`. One return, no branch.

    `yield` is a Python keyword, so the field is `yield_` with an alias.
    FastAPI serialises response models with `response_model_by_alias=True` by
    default, so the wire key stays `yield` -- pinned by the golden master's
    `yield.*` leaf paths, which would move the moment that stopped being
    true.

    `status` is `getattr(job, "status", None)` and JOB has NO `status`
    column (orm/job.py), so it is ALWAYS null -- captured as a key with a
    null value, which is why it appears in the golden master. Modelled as
    the `Optional[str]` the handler's `getattr` default implies rather than
    quietly deleted: dropping it would change the shape.
    """

    job_id: str
    part_number: Optional[str] = None
    status: Optional[str] = None
    production_kpis: JobSummaryProductionKPIs
    quality_kpis: JobSummaryQualityKPIs
    yield_: JobSummaryYield = Field(alias="yield")

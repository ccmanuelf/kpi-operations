"""Response contracts for Batch R5, part 1: static/lookup-style routes with
no conditional branching and no live Decimal hazard -- `GET /api/defect-types
/constants`, `GET /api/defect-types/template/download`, `GET /api/products`,
`GET /api/downtime-reasons`, `GET /api/filters/statistics`, `GET /api/v2/
simulation/`, `GET /api/import-logs`. The batch's two Decimal/floor hazards
and its exclude_unset case (`client-config/effective`, `inference/cycle-time`,
`jobs/kpi/rty-summary`) live in `kpi_metrics_contracts.py`; see
docs/superpowers/plans/2026-08-25-response-model-refactor.md and
`.superpowers/sdd/2026-08-25-response-model-refactor/task-R5-brief.md`.

`GET /api/v2/simulation/schema` -- the batch's third hazard, 229 keys -- is
NOT modeled here or anywhere: it returns `SimulationConfig.model_json_schema()`
(`routes/simulation_v2.py::get_input_schema`) verbatim, Pydantic's own
JSON-Schema serialization of that model, not a payload this route composes.
Declared out of the refactor's scope via `backend/tests/contract/
schema_document_routes.py` instead -- see that module for the two-sided gate
and the byte-identical proof
(`shape_of(SimulationConfig.model_json_schema()) ==
golden["GET /api/v2/simulation/schema"]`, 229/229 keys).

DISCLOSED, NOT A REGRESSION: every `int` field declared across this module
and `kpi_metrics_contracts.py` is a new validation boundary the old
`-> Any`/`-> dict`/`List[dict]` routes never had. A fractional value stored
under one of these columns (SQLite's weak typing lets an `INTEGER` column
hold a float; a raw-SQL seeder or migration bypass could write one) used to
pass through untyped and serialize as whatever it was; it now fails Pydantic
validation and the route 500s. Unreachable via this app's own write paths
today (every mutating schema for these tables declares the field `int`, and
the underlying DDL is `sa.Integer`), but it is a new failure mode for a
direct-DB write or a future seeder change, not present before this batch.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# GET /api/defect-types/constants
# =============================================================================


class DefectTypeConstantsResponse(BaseModel):
    """`routes/defect_type_catalog.py::get_constants` -- `GLOBAL_CLIENT_ID`
    is the literal string constant (`crud/defect_type_catalog.py::
    GLOBAL_CLIENT_ID = "GLOBAL"`), never a DB value."""

    GLOBAL_CLIENT_ID: str


# =============================================================================
# GET /api/defect-types/template/download -- returns JSON despite the name
# =============================================================================


class DefectTypeExampleRow(BaseModel):
    """One of `download_csv_template`'s two hardcoded example rows
    (`routes/defect_type_catalog.py`). `sort_order` is a literal Python int
    (`1`, `2`) in the source, never a DB value."""

    defect_code: str
    defect_name: str
    description: str
    category: str
    severity_default: str
    industry_standard_code: str
    sort_order: int


class DefectTypeTemplate(BaseModel):
    columns: List[str]
    example_rows: List[DefectTypeExampleRow]


class DefectTypeTemplateResponse(BaseModel):
    """`routes/defect_type_catalog.py::download_csv_template`. CONFIRMED
    despite its `/template/download` path and `download_csv_template` name:
    the handler returns a plain dict (annotated `-> Any`, no
    `FileResponse`/`StreamingResponse` anywhere in its body) -- a real JSON
    body, not a file. `notes` is a hardcoded list of 7 strings."""

    template: DefectTypeTemplate
    notes: List[str]


# =============================================================================
# GET /api/products
# =============================================================================


class ProductListEntry(BaseModel):
    """`routes/reference.py::list_products`. `ideal_cycle_time` is the ORM
    column `Product.ideal_cycle_time` (`Mapped[Optional[Decimal]]`,
    orm/product.py:30), but the route itself already `float(...)`-casts it
    (`float(p.ideal_cycle_time) if p.ideal_cycle_time else None`) before
    building the dict -- so this route carries no live Decimal hazard: the
    cast happens before this model ever sees the value, or the value is
    `None` (a route-level literal, not a raw column read).

    FLAGGED, NOT FIXED (pre-existing, this batch's response model cannot
    see it either way): that same ternary is a truthiness test, not a
    None-check, so a real product with `ideal_cycle_time = Decimal("0")`
    -- a genuinely zero cycle time, not "unset" -- renders `ideal_cycle_time:
    null` instead of `0.0`. Out of scope for a response-model batch: the
    value never reaches this model in the first place, it is already `None`
    by the time the route builds its dict."""

    product_id: int
    product_code: str
    product_name: str
    ideal_cycle_time: Optional[float] = None


# =============================================================================
# GET /api/downtime-reasons
# =============================================================================


class DowntimeCategoryEntry(BaseModel):
    id: str
    label_key: str


class DowntimeReasonEntry(BaseModel):
    id: str
    label_key: str
    default_category: str


class DowntimeReasonsResponse(BaseModel):
    """`routes/reference.py::list_downtime_reasons`. Both lists are built
    from static Python registries (`orm/downtime_taxonomy.py`'s
    `SELECTABLE_CATEGORIES`/`DowntimeReasonEnum`), never a DB query -- the
    key set cannot vary by client, user, or seed state."""

    categories: List[DowntimeCategoryEntry]
    reasons: List[DowntimeReasonEntry]


# =============================================================================
# GET /api/filters/statistics
# =============================================================================


class MostUsedFilterEntry(BaseModel):
    """`crud/saved_filter/utilities.py::get_filter_statistics`'s
    `most_used` branch. NO CAPTURED EVIDENCE for this interior -- the
    smoke seed's capturing user owns zero saved filters, so golden's
    `most_used_filter` entry is a bare `null` leaf (see
    `FilterStatisticsResponse` below) -- same disclosure class as
    `ImportLogEntry`. Modeled purely from source: `filter_id`/`usage_count`
    are bare `SavedFilter` row attributes (`Integer` columns,
    orm/saved_filter.py), never a computed aggregate."""

    filter_id: int
    filter_name: str
    usage_count: int


class FilterStatisticsResponse(BaseModel):
    """`crud/saved_filter/utilities.py::get_filter_statistics`.

    GOLDEN EVIDENCE IS THIN: the smoke seed's capturing user owns zero
    saved filters, so golden's entry is `{total_filters, filters_by_type,
    most_used_filter, total_usage_count}` with `filters_by_type` and
    `most_used_filter` recorded as BARE LEAVES (`{}` and `null` -- no
    nested keys captured at all). `MostUsedFilterEntry`'s 3-field interior
    is therefore source-inspection-only, the same disclosure class as
    `ImportLogEntry` (see that model). `filters_by_type` and
    `RunNightlyResponse.summary` (`kpi_metrics_contracts.py`) are the SAME
    shape class as `by_severity`/`by_category`
    (`tests/contract/capture.py`'s MAP_FIELDS) -- a genuine value-keyed
    map, not a fixed field set -- but DELIBERATELY NOT REGISTERED there:
    `shape_of` only recurses a MAP_FIELDS key as `key.*`, which would
    change BOTH golden entries' recorded key strings
    (`filters_by_type` -> `filters_by_type.*`; the four
    `summary.<client_id>.<metric>` leaf paths -> `summary.*.<metric>`) --
    exactly the golden-master edit this batch is forbidden to make.
    `test_map_fields_are_exactly_the_known_five` pins the registry at
    5 for this reason: the omission here is deliberate, not an oversight.
    Live consequence worth flagging: golden's `run-nightly` entry bakes in
    the smoke seed's 4 specific active client ids as literal key
    fragments, so a future reseed that changes the active client SET (not
    merely their data) would churn that one golden entry -- the same
    fragility `MAP_FIELDS`'s own docstring describes for `by_severity`,
    just not remediable here without touching the golden file.

    `total_filters` is `func.count(...)` -- COUNT, unlike SUM, never
    returns a MariaDB DECIMAL on any dialect (it counts rows, not values),
    so no cast is needed for correctness; `filters_by_type`'s values are
    the same `func.count(...).label("count")` aggregate, COUNT-backed, so
    the same reasoning covers `Dict[str, int]`. `total_usage_count` is
    `func.sum(SavedFilter.usage_count) or 0` -- UNLIKE `total_filters`,
    this IS a SUM over an `Integer` column (`usage_count`,
    orm/saved_filter.py), the same MariaDB SUM-returns-DECIMAL shape this
    codebase has hit before, and the route never casts it; declaring `int`
    closes that class of leak the same way HAZARD 2 closes it for
    `inference/cycle-time`. But the capture never exercised the SUM path
    at all: with zero filters for this user, `func.sum(...)` returns
    `None` and `or 0` supplies the literal `0` -- so, like
    `most_used_filter`, this is disclosed on the strength of the source,
    not a measured before/after. Correcting an earlier draft of this
    docstring: `or 0` does NOT catch only a `None` scalar -- `Decimal("0")`
    is falsy in Python, so a genuine zero-sum (rows exist, all
    `usage_count` values are 0) takes the same `or 0` arm as no rows at
    all. The conclusion is unaffected (declaring `int` is correct either
    way), but the reasoning in that earlier version was wrong.
    """

    total_filters: int
    filters_by_type: Dict[str, int]
    most_used_filter: Optional[MostUsedFilterEntry] = None
    total_usage_count: int


# =============================================================================
# GET /api/v2/simulation/
# =============================================================================


class SimulationConstraints(BaseModel):
    max_products: int
    max_operations_per_product: int
    max_total_operations: int
    max_horizon_days: int


class SimulationDefaultValues(BaseModel):
    grade_pct: float
    fpd_pct: float
    rework_pct: float
    operators: int
    variability: str


class SimulationInfoResponse(BaseModel):
    """`routes/simulation_v2.py::simulation_info` -- a fully static literal
    dict; every value is a Python constant from `simulation_v2/constants.py`
    (`MAX_PRODUCTS=5`, `DEFAULT_GRADE_PCT=85.0`, ...) or an inline string
    literal, never a DB read. Deliberately unauthenticated -- see the
    route's own docstring."""

    name: str
    version: str
    description: str
    capabilities: List[str]
    limitations: List[str]
    constraints: SimulationConstraints
    default_values: SimulationDefaultValues


# =============================================================================
# GET /api/import-logs -- NO CAPTURED EVIDENCE, source inspection only
# =============================================================================


class ImportLogEntry(BaseModel):
    """`routes/production.py::get_import_logs`. Golden entry is `[]` -- the
    smoke seed's capturing user has zero `import_log` rows -- so every
    field below is modeled from `orm/import_log.py` alone, with no captured
    example to cross-check against. All `Integer`/`String`/`DateTime`
    columns, no `Numeric`/`Decimal` anywhere in the table, so there is no
    Decimal hazard to disclose even without live evidence."""

    log_id: int
    user_id: str
    import_timestamp: datetime
    file_name: Optional[str] = None
    rows_attempted: int
    rows_succeeded: int
    rows_failed: int
    error_details: Optional[str] = None
    import_type: str

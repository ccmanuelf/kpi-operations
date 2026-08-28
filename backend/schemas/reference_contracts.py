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
    `None` (a route-level literal, not a raw column read)."""

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
    `most_used` branch -- `filter_id`/`usage_count` are bare `SavedFilter`
    row attributes (`Integer` columns, orm/saved_filter.py), never a
    computed aggregate."""

    filter_id: int
    filter_name: str
    usage_count: int


class FilterStatisticsResponse(BaseModel):
    """`crud/saved_filter/utilities.py::get_filter_statistics`.
    `total_filters` is `func.count(...)` -- COUNT, unlike SUM, never
    returns a MariaDB DECIMAL on any dialect (it counts rows, not values),
    so no cast is needed for correctness. `filters_by_type` is a genuine
    value-keyed map (filter type -> count), the same shape class as
    `by_severity`/`by_category` (`tests/contract/capture.py`'s MAP_FIELDS)
    but modeled here as the `Dict[str, int]` it actually is rather than
    enumerated fields -- COUNT-backed, same no-Decimal reasoning as
    `total_filters`. `most_used_filter` is `None` when the user owns zero
    filters (present as JSON `null`, never omitted -- not an exclude_unset
    case). `total_usage_count` is `func.sum(SavedFilter.usage_count) or 0`
    -- UNLIKE `total_filters`, this IS a SUM over an `Integer` column
    (`usage_count`, orm/saved_filter.py), the same MariaDB
    SUM-returns-DECIMAL shape this codebase has hit before, and the route
    never casts it. Declaring `int` here closes that live-on-MariaDB leak
    the same class as HAZARD 2 closes for `inference/cycle-time`
    (`kpi_metrics_contracts.py`) -- undetectable on SQLite, where `SUM`
    already returns a Python `int`/`float`, so there is no before/after to
    measure on this repo's test database; disclosed on the strength of the
    source (`or 0` catches only a `None` scalar -- zero matching rows --
    never a populated dialect-specific `Decimal`).
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

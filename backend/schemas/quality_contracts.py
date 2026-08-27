"""Response contracts for Batch R2's `/api/quality` routes -- 6 of the
batch's 7 total (the 7th, `GET /api/capacity/workbook/{client_id}`, lives in
`capacity_contracts.py`, split out purely for the 500-line limit and because
it is an unrelated area; see
docs/superpowers/plans/2026-08-25-response-model-refactor.md and
`.superpowers/sdd/2026-08-25-response-model-refactor/task-R2-brief.md`).

Two Decimal exponent hazards found by reading the producers, not by
sampling a value (the brief's own central warning: FastAPI's
`decimal_encoder` returns `int()` for a Decimal with exponent >= 0 and
`float()` only for a negative exponent):

1. `GET /api/quality/kpi/dpmo-by-part` -- `calculations/dpmo.py::
   calculate_dpmo_with_part_lookup`'s zero-quality-entries branch returns
   raw, un-`float()`-cast `Decimal("0")` for `overall_dpmo`/
   `overall_sigma_level` (exponent 0 -- a JSON INTEGER `0` on the wire
   today, via `jsonable_encoder`, since this route carries no
   `response_model` yet). The populated branch already `float(...)`-casts
   both. Declaring both fields `float` here means every response is a
   consistent JSON float regardless of branch -- a genuine, disclosed
   int -> float widening on the zero-entries branch (`0` -> `0.0`), the
   same accepted-consequence class as Batch R4's `cache/health` `hit_rate`.
   No captured evidence exists for this branch (the golden entry reflects
   the populated one); `test_quality_capacity_contracts.py` feeds the
   model the exact raw `Decimal("0")` the empty branch produces and proves
   it serializes as a JSON number, never a Decimal-as-string.

2. `GET /api/quality/kpi/top-defects` -- golden entry is `[]` (the smoke
   seed has no QUALITY_ENTRY row with `process_step` set); modeled purely
   from `calculations/ppm.py::identify_top_defects`, which is NEVER
   `float()`-cast: `percentage`/`cumulative_percentage` are raw Decimal
   division results. Declared `float` (never `Decimal`) here. Disclosed,
   not fixed: when a single item holds 100% of the total (`Decimal(str(n))
   / Decimal(str(n)) * 100` reduces to `Decimal('100')`, exponent 0), this
   route would render that share as a JSON int TODAY -- declaring `float`
   widens that one case to `100.0`, the same accepted class as (1).
   Also disclosed, not fixed (out of scope -- a response model cannot
   affect code that raises before serialization is ever reached):
   `identify_top_defects` unconditionally reads `item["percentage"]` in its
   cumulative-percentage loop, but only ever WRITES that key when
   `total_defects > 0`. If `inspections` is non-empty while every matched
   row's `units_defective` is 0, the second loop raises `KeyError` --  a
   pre-existing 500, not a shape the response model ever sees, and
   unreachable by definition whenever this route actually returns 200 with
   a non-empty list. `TopDefectItem` therefore declares `percentage`/
   `cumulative_percentage` as always-present, matching every response this
   route can actually produce without crashing first.

One plain-int widening (the SIMPLER mechanism from Batch R4's own note --
`else 0`, a literal, not a Decimal at all), disclosed per the plan-wide
accepted-consequence rule, no dedicated test: `GET /api/quality/kpi/
by-product`'s `fpy` and `GET /api/quality/kpi/defects-by-type`'s
`percentage` are `round(float, 1)` on their populated branch but a bare
int `0` when the divisor is 0 or absent (`by-product`: no product group
has any inspected units; `defects-by-type`: `total_defects` sums to 0).
Declaring both `float` is correct -- a rate cannot be `int` -- and widens
only that unreached-in-capture edge to `0.0`.

Every other numeric field below is either always a native Python `int`
(summed in Python over `Integer`-typed ORM columns, or `func.sum(...)`
results the route itself `int(...)`-casts before building the response --
neutralising the MariaDB SUM-returns-DECIMAL class this repo has hit
before) or always `float()`-cast at the point of construction
(`calculations/fpy_rty.py`'s repair/rework/scrap rates, `ppm_dpmo.py`'s
`ppm/trend` series) -- verified by reading each producing function, not by
probing one sample.
"""

from typing import List, Optional

from pydantic import BaseModel

# =============================================================================
# GET /api/quality/kpi/by-product
# =============================================================================


class QualityByProductItem(BaseModel):
    """`routes/quality/pareto.py::get_quality_by_product`. `inspected`/
    `defects` are `int(...)`-cast in the route off `func.sum(...)` over
    `Integer` columns (QualityEntry.units_inspected/units_defective).
    `fpy` is `round(float(...)/float(...)*100, 1)` on the populated branch,
    bare int `0` when `r.inspected` is falsy -- see the module docstring's
    plain-int widening disclosure.
    """

    product_name: str
    inspected: int
    defects: int
    fpy: float


# =============================================================================
# GET /api/quality/kpi/defects-by-type
# =============================================================================


class DefectsByTypeItem(BaseModel):
    """`routes/quality/pareto.py::get_defects_by_type`. `count` is
    `int(...)`-cast off `func.sum(DefectDetail.defect_count)`. `percentage`
    is `round(int/int*100, 1)` on the populated branch, bare int `0` when
    `total_defects` is 0 -- see the module docstring's plain-int widening
    disclosure.
    """

    defect_type: str
    count: int
    percentage: float


# =============================================================================
# GET /api/quality/kpi/ppm/trend
# =============================================================================


class PPMTrendPoint(BaseModel):
    """`routes/quality/ppm_dpmo.py::get_ppm_trend`. `value` is
    `round(float(ppm), 2)` on BOTH branches (the zero-inspected branch is
    the float literal `0.0`, not an int) -- no widening, unlike its
    siblings above.
    """

    date: str
    value: float


# =============================================================================
# GET /api/quality/kpi/dpmo-by-part
# =============================================================================


class DPMOPeriod(BaseModel):
    start_date: str
    end_date: str


class DPMOByPartItem(BaseModel):
    """One entry of `by_part` -- `calculations/dpmo.py::
    calculate_dpmo_with_part_lookup`. `opportunities_per_unit` is always a
    native int: either `PartOpportunities.opportunities_per_unit`
    (`Integer`, orm/part_opportunities.py:28) or a client/global default
    that is itself `int(...)`-cast (`get_client_opportunities_default`).
    `units_inspected`/`defects_found` are summed in Python over
    `QualityEntry.units_inspected`/`total_defects_count`/`units_defective`
    (`Integer` columns) read as ORM row attributes, never a SQL-level
    `func.sum` -- so never subject to the MariaDB SUM-returns-DECIMAL
    class. `total_opportunities` is `units_inspected * opportunities_per_unit`,
    int * int. `dpmo`/`sigma_level` are `float(...)`-cast unconditionally.
    """

    part_number: str
    units_inspected: int
    defects_found: int
    opportunities_per_unit: int
    total_opportunities: int
    dpmo: float
    sigma_level: float


class DPMOByPartResponse(BaseModel):
    """`routes/quality/ppm_dpmo.py::calculate_dpmo_by_part`. `client_id` is
    the raw incoming query param (never scope-resolved by this route --
    pre-existing, unrelated to this task, not touched). `overall_dpmo`/
    `overall_sigma_level` carry the module docstring's HAZARD (1): the
    zero-quality-entries branch returns raw `Decimal("0")`, never
    `float()`-cast. `total_units`/`total_defects`/`total_opportunities` are
    plain Python ints on every branch (`0` int literals in the empty
    branch, Python-summed ints in the populated one).
    """

    period: DPMOPeriod
    client_id: Optional[str] = None
    overall_dpmo: float
    overall_sigma_level: float
    total_units: int
    total_defects: int
    total_opportunities: int
    by_part: List[DPMOByPartItem]
    using_part_specific_opportunities: bool
    calculation_timestamp: str


# =============================================================================
# GET /api/quality/kpi/fpy-rty-breakdown
# =============================================================================


class FPYRTYPeriod(BaseModel):
    start_date: str
    end_date: str


class FPYBreakdown(BaseModel):
    """`calculations/fpy_rty.py::calculate_fpy_with_repair_breakdown`.
    `first_pass_good`/`total_inspected`/`units_reworked`/
    `units_requiring_repair`/`units_scrapped`/`recovered_units` are
    Python `sum(...)` over `Integer`-typed `QualityEntry` columns read as
    ORM row attributes (never a SQL-level aggregate) -- always native int,
    on both the empty (`0` literals) and populated branch.
    `fpy_percentage`/`rework_rate`/`repair_rate`/`scrap_rate`/
    `recovery_rate` are `float(...)`-cast unconditionally by the route
    (`routes/quality/fpy_rty.py::get_fpy_rty_breakdown`), regardless of
    which branch of the producer set the underlying Decimal.
    """

    fpy_percentage: float
    first_pass_good: int
    total_inspected: int
    units_reworked: int
    units_requiring_repair: int
    units_scrapped: int
    rework_rate: float
    repair_rate: float
    scrap_rate: float
    recovered_units: int
    recovery_rate: float


class RTYStepDetail(BaseModel):
    """One entry of `rty_breakdown.step_details` -- same int/float split as
    `FPYBreakdown` (the route re-derives each step via the same
    `calculate_fpy_with_repair_breakdown`, `float(...)`-casting the two
    rate fields it forwards)."""

    step: str
    fpy_percentage: float
    first_pass_good: int
    total_inspected: int
    units_reworked: int
    units_requiring_repair: int
    units_scrapped: int
    rework_rate: float
    repair_rate: float


class RTYBreakdown(BaseModel):
    """`calculations/fpy_rty.py::calculate_rty_with_repair_impact`.
    `total_rework`/`total_repair`/`total_scrap` are Python-accumulated ints
    (`+=` over `FPYBreakdown`'s own already-int fields). `rty_percentage`/
    `rework_impact_percentage`/`repair_impact_percentage`/
    `throughput_loss_percentage` are `float(...)`-cast unconditionally by
    the route. `interpretation` is one of `get_rty_interpretation`'s fixed
    string literals.
    """

    rty_percentage: float
    step_details: List[RTYStepDetail]
    total_rework: int
    total_repair: int
    total_scrap: int
    rework_impact_percentage: float
    repair_impact_percentage: float
    throughput_loss_percentage: float
    interpretation: str


class FPYRTYBreakdownResponse(BaseModel):
    """`routes/quality/fpy_rty.py::get_fpy_rty_breakdown` -- 34 keys, the
    largest in this batch. `product_id`/`client_id`/`inspection_stage_filter`
    are the raw incoming query params, echoed unconditionally (never
    scope-resolved, never omitted)."""

    period: FPYRTYPeriod
    product_id: Optional[int] = None
    client_id: Optional[str] = None
    inspection_stage_filter: Optional[str] = None
    fpy_breakdown: FPYBreakdown
    rty_breakdown: RTYBreakdown
    calculation_timestamp: str


# =============================================================================
# GET /api/quality/kpi/top-defects -- SOURCE INSPECTION, NO CAPTURED EVIDENCE
# =============================================================================


class TopDefectItem(BaseModel):
    """`calculations/ppm.py::identify_top_defects` -- golden entry is `[]`;
    modeled entirely from the producing function, no captured evidence for
    a non-empty response. See the module docstring's HAZARD (2) for the
    Decimal-exponent widening disclosure and the confirmed, unfixed,
    out-of-scope `KeyError` this route's own code can raise before a
    response model is ever consulted.
    """

    defect_type: str
    count: int
    category: Optional[str] = None
    percentage: float
    cumulative_percentage: float

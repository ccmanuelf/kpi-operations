"""Batch R2's two live Decimal hazards (task-R2-brief.md), both found by
reading the producer rather than by sampling a value -- see
`schemas/quality_contracts.py`'s module docstring for the full disclosure.

1. `GET /api/quality/kpi/dpmo-by-part`: `calculate_dpmo_with_part_lookup`'s
   (calculations/dpmo.py) zero-quality-entries branch returns raw,
   un-`float()`-cast `Decimal("0")` for `overall_dpmo`/
   `overall_sigma_level` -- the same Decimal-serializes-as-a-JSON-string
   defect this whole refactor exists to close, applied to this batch's own
   live use of `Decimal`.
2. `GET /api/quality/kpi/top-defects`: `identify_top_defects`
   (calculations/ppm.py) never `float()`-casts `percentage`/
   `cumulative_percentage` -- raw Decimal division results, on the only
   branch this route can return without crashing first (see
   `TopDefectItem`'s docstring for the confirmed, unfixed, out-of-scope
   `KeyError` on the other one).

The golden master cannot check either: it compares key sets, never value
types, by design (`capture.py`'s `is_loose` docstring), so a field silently
reverted to `Decimal` would leave the whole contract suite green -- the
identical gap `test_ops_contracts.py`/`test_floor_contracts.py` close for
their own tasks' hazards.
"""

import json
from decimal import Decimal

from backend.schemas.quality_contracts import DPMOByPartResponse, TopDefectItem


def test_dpmo_by_part_empty_branch_decimal_fields_serialize_as_numbers():
    """Feeds `DPMOByPartResponse` the EXACT raw `Decimal("0")` values
    `calculate_dpmo_with_part_lookup`'s zero-quality-entries branch returns
    for `overall_dpmo`/`overall_sigma_level` -- unlike the populated
    branch, which already `float(...)`-casts both before returning.
    """
    raw = dict(
        period=dict(start_date="2026-07-01", end_date="2026-07-31"),
        client_id="C1",
        overall_dpmo=Decimal("0"),
        overall_sigma_level=Decimal("0"),
        total_units=0,
        total_defects=0,
        total_opportunities=0,
        by_part=[],
        using_part_specific_opportunities=False,
        calculation_timestamp="2026-07-31T00:00:00+00:00",
    )

    dumped = json.loads(DPMOByPartResponse(**raw).model_dump_json())

    assert dumped["overall_dpmo"] == 0.0
    assert type(dumped["overall_dpmo"]) is float
    assert dumped["overall_sigma_level"] == 0.0
    assert type(dumped["overall_sigma_level"]) is float


def test_top_defects_raw_decimal_percentage_fields_serialize_as_numbers():
    """Feeds `TopDefectItem` a raw Decimal division result -- the exact
    shape `identify_top_defects` produces for `percentage`/
    `cumulative_percentage` (never `float()`-cast by the producer, unlike
    every other numeric field this batch converts).
    """
    raw = dict(
        defect_type="Stitching",
        count=12,
        category="Final",
        percentage=Decimal("60.416666666666666666666667"),
        cumulative_percentage=Decimal("60.416666666666666666666667"),
    )

    dumped = json.loads(TopDefectItem(**raw).model_dump_json())

    assert dumped["percentage"] == 60.416666666666664
    assert type(dumped["percentage"]) is float


def test_top_defects_exact_100_percent_share_serializes_as_a_number():
    """`GET /api/quality/kpi/top-defects` is annotated `-> list`
    (`pareto.py:40`), so FastAPI already infers a response model from that
    annotation and Pydantic's inferred-model serializer renders a bare
    `Decimal` as a JSON STRING regardless of its exponent -- see the module
    docstring's corrected mechanism. When a single item holds 100% of
    `total_defects`, `Decimal(str(n)) / Decimal(str(n)) * 100` reduces to
    `Decimal('100')` -- `"100"` (a JSON string) on the wire TODAY, not
    `100` the int an exponent-based rule would predict. Declaring `float`
    fixes the leak to `100.0`. Unlike the fractional-share case above,
    `Decimal('100')` has no fractional digits, so this case is
    string -> number only, with no precision truncation to disclose.
    """
    raw = dict(
        defect_type="Solo",
        count=5,
        category=None,
        percentage=Decimal("100"),
        cumulative_percentage=Decimal("100"),
    )

    dumped = json.loads(TopDefectItem(**raw).model_dump_json())

    assert dumped["percentage"] == 100.0
    assert type(dumped["percentage"]) is float
    assert dumped["cumulative_percentage"] == 100.0

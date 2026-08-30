"""Batch R1's live Decimal hazard (`schemas/job_kpi_contracts.py`), and the
narrow value-type assertion every batch owes.

`GET /api/jobs/{job_id}/yield` was serving `"yield_percentage":"99.00"` -- a
JSON STRING -- measured against the harness's own seeded database before this
batch. `calculations/fpy_rty.py::calculate_job_yield` returns `yield_pct` as a
bare, un-`float()`-cast `Decimal`, and the route is annotated `-> Any`, which
is the ANNOTATED case: FastAPI's inferred model routes it through Pydantic's
serializer, which stringifies a `Decimal` regardless of its exponent. The
other five R1 routes cast every numeric value they emit and so leak nothing
today -- what they lacked is anything that would NOTICE if an edit stopped
casting, which is what the family test below supplies.

The golden master cannot check any of this: it compares key sets, never value
types, BY DESIGN (`capture.py`'s `is_loose` docstring), so a field silently
re-typed `Decimal` would leave the whole contract suite green -- the identical
gap `test_ops_contracts.py` / `test_quality_contracts.py` /
`test_floor_contracts.py` close for their own batches.

The sharpest single fact on record here: the same metric, for the same job, in
the same capture, was a JSON string on `/yield` and a JSON number on
`/kpi-summary` (`"yield":{"yield_percentage":99.0,...}`), because one producer
called `float()` and the other did not. Casting discipline in six handlers is
not a contract; a declared type is.
"""

import json
from decimal import Decimal
from typing import Any, Iterator, Tuple

import pytest

from backend.schemas.job_kpi_contracts import (
    JobDPMOResponse,
    JobEfficiencyResponse,
    JobKPISummaryResponse,
    JobPPMResponse,
    JobPerformanceResponse,
    JobYieldResponse,
)


def test_job_yield_raw_decimal_percentage_serializes_as_a_number():
    """The measured leak, with the exact `Decimal` the producer builds.

    495 good of 500 completed: `Decimal("495") / Decimal("500") * 100` is
    `Decimal("99.00")` -- no `.quantize()` involved, that is simply what the
    division yields -- and `"99.00"` is what the route put on the wire.
    Declaring `float` is what makes it `99.0`.
    """
    raw = dict(
        job_id="DEMO-HOURLY-WO-0001-OP1",
        operation_name="Preparation",
        sequence_number=1,
        part_number="HR-BRKT",
        yield_percentage=Decimal("495") / Decimal("500") * 100,
        completed_quantity=500,
        quantity_scrapped=5,
        good_quantity=495,
    )
    assert raw["yield_percentage"] == Decimal("99.00")

    dumped = json.loads(JobYieldResponse(**raw).model_dump_json())

    assert dumped["yield_percentage"] == 99.0
    assert type(dumped["yield_percentage"]) is float


def test_job_yield_zero_scrap_whole_number_percentage_serializes_as_a_number():
    """A job with no scrap reduces to `Decimal("100")` -- exponent 0, which
    an exponent-based reading of the bug would predict renders as the int
    `100`. It does not: the route is annotated, so the pre-conversion wire was
    the STRING `"100"`, the same leak as the fractional case. Pinned
    separately because the two look different and only one of them is what a
    reviewer would think to sample.
    """
    raw = dict(
        job_id="J1",
        operation_name="Assembly",
        sequence_number=2,
        part_number=None,
        yield_percentage=Decimal("500") / Decimal("500") * 100,
        completed_quantity=500,
        quantity_scrapped=0,
        good_quantity=500,
    )
    assert raw["yield_percentage"] == Decimal("100")

    dumped = json.loads(JobYieldResponse(**raw).model_dump_json())

    assert dumped["yield_percentage"] == 100.0
    assert type(dumped["yield_percentage"]) is float


def test_kpi_summary_nested_yield_keeps_its_reserved_word_wire_name():
    """`yield` is a Python keyword, so the field is `yield_` with an alias.
    The golden master's `yield.*` leaf paths depend on FastAPI's
    `response_model_by_alias=True` default holding; this pins the model half
    of that directly, so a `populate_by_name` / alias edit fails here with the
    reason visible rather than as a wide golden diff.
    """
    dumped = json.loads(JobKPISummaryResponse(**_SUMMARY_RAW).model_dump_json(by_alias=True))

    assert "yield" in dumped
    assert "yield_" not in dumped


_SUMMARY_RAW = dict(
    job_id="J1",
    part_number="HR-BRKT",
    status=None,
    production_kpis=dict(
        efficiency_percentage=Decimal("150.00"),
        performance_percentage=Decimal("150.00"),
        quality_rate=Decimal("99.77678571428571428571428571"),
        total_units_produced=Decimal("448"),
        defect_count=Decimal("0"),
        scrap_count=Decimal("1"),
        entry_count=2,
    ),
    quality_kpis=dict(
        ppm=Decimal("11160.71"),
        dpmo=Decimal("1116.07"),
        sigma_level=Decimal("4.0"),
        total_inspected=Decimal("448"),
        total_defects=Decimal("5"),
        opportunities_per_unit=10,
        entry_count=2,
    ),
    **{
        "yield": dict(
            yield_percentage=Decimal("99.00"),
            completed_quantity=Decimal("500"),
            quantity_scrapped=Decimal("5"),
        )
    },
)


#: (model, a raw dict feeding a `Decimal` to every numeric field, the leaf
#: paths that are legitimately text). Every numeric field is fed a `Decimal`
#: including the `int`-declared ones, because a MariaDB `SUM()` returns
#: DECIMAL whatever the summed column's own type is -- the SUM-Integer-to-
#: Decimal class -- and an `int` declaration has to coerce it, not forward it.
DECIMAL_FED_MODELS: Tuple[Tuple[str, Any, dict, frozenset], ...] = (
    (
        "yield",
        JobYieldResponse,
        dict(
            job_id="J1",
            operation_name="Preparation",
            sequence_number=Decimal("1"),
            part_number="HR-BRKT",
            yield_percentage=Decimal("99.00"),
            completed_quantity=Decimal("500"),
            quantity_scrapped=Decimal("5"),
            good_quantity=Decimal("495"),
        ),
        frozenset({"job_id", "operation_name", "part_number"}),
    ),
    (
        "efficiency",
        JobEfficiencyResponse,
        dict(
            job_id="J1",
            part_number="HR-BRKT",
            efficiency_percentage=Decimal("150.00"),
            total_units_produced=Decimal("448"),
            total_labor_hours=Decimal("21.66"),
            entry_count=Decimal("2"),
            entries=[
                dict(
                    production_entry_id="PE-1",
                    units_produced=Decimal("231"),
                    efficiency_percentage=Decimal("0.0000"),
                )
            ],
        ),
        frozenset({"job_id", "part_number", "entries[].production_entry_id"}),
    ),
    (
        "performance",
        JobPerformanceResponse,
        dict(
            job_id="J1",
            performance_percentage=Decimal("150.00"),
            total_units_produced=Decimal("448"),
            total_run_time_hours=Decimal("14.46"),
            entry_count=Decimal("2"),
        ),
        frozenset({"job_id"}),
    ),
    (
        "ppm",
        JobPPMResponse,
        dict(
            job_id="J1",
            ppm=Decimal("11160.71"),
            total_inspected=Decimal("448"),
            total_defects=Decimal("5"),
            entry_count=Decimal("2"),
        ),
        frozenset({"job_id"}),
    ),
    (
        "dpmo",
        JobDPMOResponse,
        dict(
            job_id="J1",
            dpmo=Decimal("1116.07"),
            sigma_level=Decimal("4.0"),
            total_inspected=Decimal("448"),
            total_defects=Decimal("5"),
            total_opportunities=Decimal("4480"),
            opportunities_per_unit=Decimal("10"),
            using_part_specific_opportunities=True,
            entry_count=Decimal("2"),
        ),
        frozenset({"job_id"}),
    ),
    (
        "kpi-summary",
        JobKPISummaryResponse,
        _SUMMARY_RAW,
        frozenset({"job_id", "part_number", "status"}),
    ),
)


def _leaves(value: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Every scalar in a decoded JSON body, by dotted path -- the same
    `a.b`/`a[].b` notation the golden master records, so a failure names a
    path a reader can find in `golden/api_shapes.json`.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{prefix}{key}.")
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item, f"{prefix[:-1]}[].")
    else:
        yield prefix.rstrip("."), value


@pytest.mark.parametrize(
    "model, raw, text_paths",
    [case[1:] for case in DECIMAL_FED_MODELS],
    ids=[case[0] for case in DECIMAL_FED_MODELS],
)
def test_every_r1_model_renders_a_decimal_as_a_json_number(model, raw, text_paths):
    """Feeds a `Decimal` to EVERY numeric field of all six R1 models and
    asserts nothing but the declared text fields comes back as a JSON string.

    Only `/yield` leaks today; the other five are one dropped `float(...)`
    away from leaking, and this is what would notice. It is also the check
    that survives a MariaDB deployment: `func.sum()` there returns DECIMAL
    whatever the summed column's own type is, so an `int`-declared field must
    coerce a `Decimal` rather than forward it.

    Asserting `not isinstance(str)` rather than a per-field type is
    deliberate: the defect is Decimal-as-string, and a type-per-field table
    would have to be kept in step with every model change or it would start
    failing for reasons that are not this one.
    """
    dumped = json.loads(model(**raw).model_dump_json(by_alias=True))

    for path, value in _leaves(dumped):
        if value is None or path in text_paths:
            continue
        assert not isinstance(value, str), (
            f"{model.__name__}.{path} serialized as {value!r} -- expected a JSON number. "
            "A Decimal-typed field, or a dropped coercion, regressed back in."
        )


def test_yield_answers_404_before_its_response_model_can_see_the_miss(harness) -> None:
    """`JobYieldResponse` deliberately does not model a "Job not found" shape.

    That is safe only because `get_job()` runs first and raises an
    HTTPException, which bypasses the response model entirely — the handler's
    own not-found dict is unreachable. Cross-model review pointed out that
    nothing pinned the ORDERING, so a refactor moving the lookup after the
    happy path would force that branch through the model and either 500 or
    silently drop `detail`, and no test would notice.

    This is that test. It asserts the status AND that the body still carries
    `detail`: a 404 whose payload had been reshaped by the response model would
    still be a 404.
    """
    response = harness.client.get("/api/jobs/NO-SUCH-JOB-ID/yield")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body, f"404 body lost its detail key: {body}"
    assert "yield_percentage" not in body, "the response model shaped an error payload"

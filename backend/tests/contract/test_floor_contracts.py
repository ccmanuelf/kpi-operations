"""HAZARD 1 (task-R3-brief.md): GET /api/floating-pool/simulation/insights
returns numeric-looking STRINGS on purpose in `input_parameters`/
`projected_output` (explicit `str(Decimal)` calls, calculations/
simulation.py:332-339) but raw `Decimal` arithmetic -- never `str()`'d -- in
`kpi_impact`/`comparison_to_baseline`. Two mutation-provable properties, one
class of test each. The golden master cannot check either: it compares key
sets, never value types, by design (`capture.py`'s `is_loose` docstring), so
a field silently mistyped either direction would leave the whole contract
suite green.

1. The deliberate `str` fields must NOT be declared `float`: feeding the
   model the exact numeric-looking strings the producing function emits
   must round-trip as a JSON STRING, never a coerced number -- declaring
   `float` instead is the exact mistake the hazard warns against.
2. The fields that are NOT part of that idiom (`kpi_impact`/
   `comparison_to_baseline`) are raw `Decimal` arithmetic and must serialize
   as JSON NUMBERS, never Decimal-as-string -- the same guarantee
   `test_ops_contracts.py` proves for `MyShiftStatsResponse`, applied here
   to this batch's own live use of `Decimal`.
"""

import json
from decimal import Decimal

from backend.schemas.floor_contracts import (
    SimulationStaffingComparison,
    SimulationStaffingInputParameters,
    SimulationStaffingKPIImpact,
    SimulationStaffingProjectedOutput,
)


def test_simulation_input_parameters_keep_the_deliberate_str_idiom():
    """`shift_hours`/`cycle_time_hours`/`efficiency_percent` are `str(Decimal)`
    in `run_staffing_simulation` (calculations/simulation.py:332-334) --
    feeding the model the SAME string values it already produces must yield
    a JSON string, not a number silently coerced from it.
    """
    raw = dict(employees=12, shift_hours="8.0", cycle_time_hours="0.50", efficiency_percent="85.00")

    dumped = json.loads(SimulationStaffingInputParameters(**raw).model_dump_json())

    assert dumped["employees"] == 12
    assert dumped["shift_hours"] == "8.0"
    assert dumped["cycle_time_hours"] == "0.50"
    assert dumped["efficiency_percent"] == "85.00"
    assert type(dumped["cycle_time_hours"]) is str


def test_simulation_projected_output_keeps_the_deliberate_str_idiom():
    """`hourly_rate`/`effective_hours` are `str(Decimal)` in
    `calculate_production_capacity` (calculations/simulation.py:338-339) --
    the exact two lines the brief's HAZARD 1 names. `units_capacity` is
    `int(...)`-cast (:233), never part of the str idiom.
    """
    raw = dict(units_capacity=48, hourly_rate="6.00", effective_hours="48.00")

    dumped = json.loads(SimulationStaffingProjectedOutput(**raw).model_dump_json())

    assert dumped["units_capacity"] == 48
    assert dumped["hourly_rate"] == "6.00"
    assert type(dumped["hourly_rate"]) is str
    assert dumped["effective_hours"] == "48.00"
    assert type(dumped["effective_hours"]) is str


def test_simulation_kpi_impact_decimal_fields_serialize_as_numbers():
    """`kpi_impact` is raw `Decimal` arithmetic (calculations/simulation.py:
    341-346), never `str()`'d -- feeding the model `Decimal` input, exactly
    as the calculation layer produces, must yield JSON numbers.
    """
    raw = dict(
        production_change_percent=Decimal("13.60"),
        efficiency=Decimal("85.00"),
        employee_change=Decimal("2"),
        employee_change_percent=Decimal("16.67"),
    )

    dumped = json.loads(SimulationStaffingKPIImpact(**raw).model_dump_json())

    assert dumped["production_change_percent"] == 13.6
    assert type(dumped["production_change_percent"]) is float
    assert dumped["efficiency"] == 85.0
    assert dumped["employee_change"] == 2.0
    assert dumped["employee_change_percent"] == 16.67


def test_simulation_comparison_to_baseline_decimal_fields_serialize_as_numbers():
    """`comparison_to_baseline` -- same reasoning as `kpi_impact`: raw
    `Decimal`, never `str()`'d."""
    raw = dict(baseline_units=Decimal("100"), scenario_units=Decimal("120"), difference=Decimal("20"))

    dumped = json.loads(SimulationStaffingComparison(**raw).model_dump_json())

    assert dumped["baseline_units"] == 100.0
    assert type(dumped["baseline_units"]) is float
    assert dumped["scenario_units"] == 120.0
    assert dumped["difference"] == 20.0

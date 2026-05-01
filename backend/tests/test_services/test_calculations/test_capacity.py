"""Phase 1 dual-view orchestrators: Capacity Requirements, Production Capacity."""

from decimal import Decimal

from backend.services.calculations.capacity import (
    CapacityRequirementsInputs,
    ComponentCoverageInputs,
    ProductionCapacityInputs,
    calculate_capacity_requirements,
    calculate_component_coverage,
    calculate_production_capacity,
)


class TestCapacityRequirements:
    def test_standard_mode_textbook_no_buffer(self):
        # (1000 × 0.25) / (8 × 0.85) = 250 / 6.8 ≈ 36.76 → ceil to 37
        inputs = CapacityRequirementsInputs(
            target_units=1000,
            cycle_time_hours=Decimal("0.25"),
            shift_hours=Decimal("8"),
            target_efficiency_pct=Decimal("85"),
            absenteeism_buffer_pct=Decimal("0"),
        )
        result = calculate_capacity_requirements(inputs)
        assert result.metric_name == "capacity_requirements"
        assert result.value.required_employees == 37
        assert result.value.buffer_employees == 0
        assert result.value.total_recommended == 37

    def test_with_buffer(self):
        # 37 employees × 5% buffer = 1.85 → 2
        inputs = CapacityRequirementsInputs(
            target_units=1000,
            cycle_time_hours=Decimal("0.25"),
            shift_hours=Decimal("8"),
            target_efficiency_pct=Decimal("85"),
            absenteeism_buffer_pct=Decimal("5"),
        )
        result = calculate_capacity_requirements(inputs)
        assert result.value.required_employees == 37
        assert result.value.buffer_employees == 2
        assert result.value.total_recommended == 39

    def test_minimum_one_buffer_when_buffer_pct_set(self):
        # 68 × 0.1 / (8 × 0.85) = 1 required; 1 × 1% = 0.01 → forced to 1 minimum
        inputs = CapacityRequirementsInputs(
            target_units=68,
            cycle_time_hours=Decimal("0.1"),
            shift_hours=Decimal("8"),
            target_efficiency_pct=Decimal("85"),
            absenteeism_buffer_pct=Decimal("1"),
        )
        result = calculate_capacity_requirements(inputs)
        assert result.value.required_employees == 1
        assert result.value.buffer_employees >= 1


class TestProductionCapacity:
    def test_standard_mode_textbook(self):
        # (10 × 8 × 0.85) / 0.25 = 68 / 0.25 = 272
        inputs = ProductionCapacityInputs(
            employees=10,
            shift_hours=Decimal("8"),
            cycle_time_hours=Decimal("0.25"),
            efficiency_pct=Decimal("85"),
        )
        result = calculate_production_capacity(inputs)
        assert result.value == Decimal("272.00")

    def test_zero_employees_yields_zero(self):
        inputs = ProductionCapacityInputs(
            employees=0,
            shift_hours=Decimal("8"),
            cycle_time_hours=Decimal("0.25"),
            efficiency_pct=Decimal("85"),
        )
        assert calculate_production_capacity(inputs).value == Decimal("0")


class TestComponentCoverage:
    def test_standard_mode_textbook(self):
        inputs = ComponentCoverageInputs(
            available_quantity=Decimal("80"),
            required_quantity=Decimal("100"),
        )
        assert calculate_component_coverage(inputs).value == Decimal("80.00")

    def test_zero_required_yields_100(self):
        inputs = ComponentCoverageInputs(
            available_quantity=Decimal("0"),
            required_quantity=Decimal("0"),
        )
        assert calculate_component_coverage(inputs).value == Decimal("100.00")

    def test_over_supplied(self):
        inputs = ComponentCoverageInputs(
            available_quantity=Decimal("150"),
            required_quantity=Decimal("100"),
        )
        assert calculate_component_coverage(inputs).value == Decimal("150.00")

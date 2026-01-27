"""
Tests for the Simulation & Capacity Planning Core Engine
Tests cover: capacity calculations, staffing simulations, efficiency simulations,
shift coverage, and floating pool optimization.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from backend.calculations.simulation import (
    calculate_capacity_requirements,
    calculate_production_capacity,
    run_staffing_simulation,
    run_efficiency_simulation,
    simulate_shift_coverage,
    simulate_multi_shift_coverage,
    optimize_floating_pool_allocation,
    run_capacity_simulation,
    SimulationScenarioType,
    OptimizationGoal,
    CapacityRequirement,
    SimulationResult,
    ShiftCoverageSimulation,
    FloatingPoolOptimization
)


class TestProductionCapacity:
    """Tests for calculate_production_capacity function (standalone, no db required)"""

    def test_basic_production_calculation(self):
        """Test basic production capacity calculation"""
        result = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("85.0")
        )

        assert "units_capacity" in result
        assert "hourly_rate" in result
        assert "effective_production_hours" in result
        assert result["units_capacity"] > 0
        assert result["employees"] == 10

    def test_production_scales_with_employees(self):
        """Test that production scales linearly with employees"""
        result_10 = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("100.0")
        )

        result_20 = calculate_production_capacity(
            employees=20,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("100.0")
        )

        # Double employees should double output
        assert result_20["units_capacity"] == 2 * result_10["units_capacity"]

    def test_production_efficiency_impact(self):
        """Test efficiency impact on production"""
        result_100 = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("100.0")
        )

        result_50 = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("50.0")
        )

        # 50% efficiency should halve output
        assert result_50["units_capacity"] == result_100["units_capacity"] // 2

    def test_zero_cycle_time_raises_error(self):
        """Test that zero cycle time raises ValueError"""
        with pytest.raises(ValueError, match="Cycle time cannot be zero"):
            calculate_production_capacity(
                employees=10,
                shift_hours=Decimal("8.0"),
                cycle_time_hours=Decimal("0.0"),
                efficiency_percent=Decimal("85.0")
            )

    def test_zero_employees_returns_zero_capacity(self):
        """Test that zero employees returns zero capacity"""
        result = calculate_production_capacity(
            employees=0,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("85.0")
        )

        assert result["units_capacity"] == 0

    def test_longer_shift_increases_capacity(self):
        """Test that longer shifts increase capacity"""
        result_8h = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("100.0")
        )

        result_12h = calculate_production_capacity(
            employees=10,
            shift_hours=Decimal("12.0"),
            cycle_time_hours=Decimal("0.5"),
            efficiency_percent=Decimal("100.0")
        )

        # 12h shift should produce 1.5x more than 8h shift
        assert result_12h["units_capacity"] > result_8h["units_capacity"]
        ratio = result_12h["units_capacity"] / result_8h["units_capacity"]
        assert abs(ratio - 1.5) < 0.01


class TestStaffingSimulation:
    """Tests for run_staffing_simulation function"""

    def test_basic_staffing_simulation(self):
        """Test basic staffing simulation"""
        scenarios = [15, 20, 25]

        result = run_staffing_simulation(
            base_employees=20,
            scenarios=scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0")
        )

        assert len(result) == 3
        for sim_result in result:
            assert isinstance(sim_result, SimulationResult)
            assert sim_result.scenario_type == SimulationScenarioType.STAFFING
            assert "employees" in sim_result.input_parameters

    def test_staffing_scenarios_ordering(self):
        """Test that more employees produce more units"""
        scenarios = [15, 20, 25]

        result = run_staffing_simulation(
            base_employees=20,
            scenarios=scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0"),
            efficiency_scaling=False
        )

        outputs = sorted(result, key=lambda x: x.input_parameters["employees"])

        # Higher employee count should mean higher output
        for i in range(len(outputs) - 1):
            assert outputs[i].projected_output["units_capacity"] < outputs[i + 1].projected_output["units_capacity"]

    def test_staffing_simulation_with_efficiency_scaling(self):
        """Test that efficiency scaling affects very different staffing levels"""
        # Severely understaffed scenario
        result = run_staffing_simulation(
            base_employees=20,
            scenarios=[5],  # Very understaffed
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0"),
            efficiency_scaling=True
        )

        # Should have recommendations about efficiency adjustment
        assert len(result) == 1
        # With scaling, efficiency should be adjusted
        efficiency_str = result[0].input_parameters["efficiency_percent"]
        adjusted_efficiency = Decimal(efficiency_str)
        # Understaffed scenarios get efficiency penalty
        assert adjusted_efficiency < Decimal("85.0")

    def test_staffing_simulation_recommendations(self):
        """Test that recommendations are generated"""
        scenarios = [18, 22]  # Less and more than base

        result = run_staffing_simulation(
            base_employees=20,
            scenarios=scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0")
        )

        for sim_result in result:
            assert len(sim_result.recommendations) > 0


class TestEfficiencySimulation:
    """Tests for run_efficiency_simulation function"""

    def test_basic_efficiency_simulation(self):
        """Test basic efficiency simulation"""
        efficiency_scenarios = [Decimal("70.0"), Decimal("80.0"), Decimal("90.0")]

        result = run_efficiency_simulation(
            employees=20,
            efficiency_scenarios=efficiency_scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0")
        )

        assert len(result) == 3
        for sim_result in result:
            assert isinstance(sim_result, SimulationResult)
            assert sim_result.scenario_type == SimulationScenarioType.EFFICIENCY

    def test_efficiency_output_ordering(self):
        """Test that higher efficiency produces more units"""
        efficiency_scenarios = [Decimal("50.0"), Decimal("75.0"), Decimal("100.0")]

        result = run_efficiency_simulation(
            employees=20,
            efficiency_scenarios=efficiency_scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5")
        )

        outputs = sorted(result, key=lambda x: Decimal(x.input_parameters["efficiency_percent"]))

        # Higher efficiency should mean higher output
        for i in range(len(outputs) - 1):
            assert outputs[i].projected_output["units_capacity"] <= outputs[i + 1].projected_output["units_capacity"]

    def test_efficiency_recommendations_for_improvement(self):
        """Test recommendations for efficiency improvement"""
        efficiency_scenarios = [Decimal("95.0")]  # Higher than base

        result = run_efficiency_simulation(
            employees=20,
            efficiency_scenarios=efficiency_scenarios,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5"),
            base_efficiency=Decimal("85.0")
        )

        assert len(result) == 1
        # Should have recommendations about improvement
        recs = result[0].recommendations
        assert any("Improving" in r or "increases" in r.lower() for r in recs)


class TestShiftCoverage:
    """Tests for simulate_shift_coverage function"""

    def test_basic_shift_coverage(self):
        """Test basic shift coverage simulation"""
        result = simulate_shift_coverage(
            regular_employees=15,
            floating_pool_available=5,
            required_employees=20,
            shift_name="Morning",
            shift_id=1
        )

        assert isinstance(result, ShiftCoverageSimulation)
        assert result.shift_name == "Morning"
        assert result.shift_id == 1
        assert result.required_employees == 20

    def test_shift_fully_covered(self):
        """Test shift is fully covered when enough employees"""
        result = simulate_shift_coverage(
            regular_employees=20,
            floating_pool_available=5,
            required_employees=20
        )

        assert result.coverage_gap == 0
        assert result.coverage_percent == Decimal("100.0")

    def test_shift_understaffed(self):
        """Test shift understaffed detection"""
        result = simulate_shift_coverage(
            regular_employees=10,
            floating_pool_available=5,
            required_employees=20
        )

        assert result.coverage_gap == 5  # 20 - (10 + 5) = 5
        assert result.coverage_percent < Decimal("100.0")

    def test_floating_pool_fills_gap(self):
        """Test that floating pool fills coverage gap"""
        result = simulate_shift_coverage(
            regular_employees=15,
            floating_pool_available=10,
            required_employees=20
        )

        # Total available = 25, required = 20, gap = 0
        assert result.coverage_gap == 0
        assert result.coverage_percent == Decimal("100.0")

    def test_overstaffed_recommendations(self):
        """Test recommendations when overstaffed"""
        result = simulate_shift_coverage(
            regular_employees=25,
            floating_pool_available=5,
            required_employees=20
        )

        assert result.coverage_gap == 0
        # Should have overstaffing recommendation
        assert any("Overstaffed" in r for r in result.recommendations)

    def test_coverage_warning_below_threshold(self):
        """Test warning when coverage is below 90%"""
        result = simulate_shift_coverage(
            regular_employees=10,
            floating_pool_available=5,
            required_employees=20
        )

        # Coverage = 15/20 = 75%
        assert result.coverage_percent < Decimal("90.0")
        assert any("WARNING" in r for r in result.recommendations)


class TestMultiShiftCoverage:
    """Tests for simulate_multi_shift_coverage function"""

    def test_multi_shift_simulation(self):
        """Test multi-shift coverage simulation"""
        shifts = [
            {"shift_id": 1, "shift_name": "Morning", "regular_employees": 15, "required": 20},
            {"shift_id": 2, "shift_name": "Afternoon", "regular_employees": 16, "required": 18},
            {"shift_id": 3, "shift_name": "Night", "regular_employees": 12, "required": 15}
        ]

        results, summary = simulate_multi_shift_coverage(
            shifts=shifts,
            floating_pool_total=10
        )

        assert len(results) == 3
        assert "total_shifts" in summary
        assert "overall_coverage_percent" in summary
        assert summary["floating_pool_total"] == 10

    def test_pool_allocation_priority(self):
        """Test that pool is allocated to most understaffed shifts first"""
        shifts = [
            {"shift_id": 1, "shift_name": "Low Gap", "regular_employees": 18, "required": 20},  # gap=2
            {"shift_id": 2, "shift_name": "High Gap", "regular_employees": 10, "required": 20},  # gap=10
        ]

        results, summary = simulate_multi_shift_coverage(
            shifts=shifts,
            floating_pool_total=5
        )

        # High gap shift should receive more allocation
        allocations = summary["allocations"]
        high_gap_alloc = next((a for a in allocations if a["shift_name"] == "High Gap"), None)
        assert high_gap_alloc is not None
        assert high_gap_alloc["pool_employees_assigned"] > 0

    def test_pool_not_overallocated(self):
        """Test that pool is not over-allocated"""
        shifts = [
            {"shift_id": 1, "shift_name": "S1", "regular_employees": 10, "required": 20},
            {"shift_id": 2, "shift_name": "S2", "regular_employees": 10, "required": 20},
        ]

        results, summary = simulate_multi_shift_coverage(
            shifts=shifts,
            floating_pool_total=5
        )

        assert summary["floating_pool_allocated"] <= 5
        assert summary["floating_pool_remaining"] >= 0


class TestCapacityRequirementsWithMock:
    """Tests for calculate_capacity_requirements function (requires db mock)"""

    @patch("backend.calculations.simulation.get_client_config_or_defaults")
    def test_basic_capacity_calculation(self, mock_config):
        """Test basic capacity requirement calculation"""
        mock_config.return_value = {"default_cycle_time_hours": "0.25"}
        mock_db = MagicMock()

        result = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=1000,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0"),
            target_efficiency=Decimal("85.0"),
            absenteeism_rate=Decimal("5.0"),
            include_buffer=False
        )

        assert isinstance(result, CapacityRequirement)
        assert result.target_units == 1000
        assert result.required_employees > 0

    @patch("backend.calculations.simulation.get_client_config_or_defaults")
    def test_capacity_with_buffer(self, mock_config):
        """Test capacity calculation includes buffer when requested"""
        mock_config.return_value = {"default_cycle_time_hours": "0.25"}
        mock_db = MagicMock()

        result_no_buffer = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=1000,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0"),
            target_efficiency=Decimal("85.0"),
            include_buffer=False
        )

        result_with_buffer = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=1000,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0"),
            target_efficiency=Decimal("85.0"),
            include_buffer=True
        )

        # Buffer should add employees
        assert result_with_buffer.buffer_employees > 0
        assert result_with_buffer.total_recommended > result_no_buffer.required_employees

    @patch("backend.calculations.simulation.get_client_config_or_defaults")
    def test_capacity_absenteeism_impact(self, mock_config):
        """Test that higher absenteeism adds more buffer"""
        mock_config.return_value = {"default_cycle_time_hours": "0.25"}
        mock_db = MagicMock()

        result_low_absence = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=1000,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0"),
            absenteeism_rate=Decimal("2.0"),
            include_buffer=True
        )

        result_high_absence = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=1000,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0"),
            absenteeism_rate=Decimal("15.0"),
            include_buffer=True
        )

        assert result_high_absence.buffer_employees >= result_low_absence.buffer_employees

    @patch("backend.calculations.simulation.get_client_config_or_defaults")
    def test_capacity_zero_target(self, mock_config):
        """Test handling of zero target units"""
        mock_config.return_value = {"default_cycle_time_hours": "0.25"}
        mock_db = MagicMock()

        result = calculate_capacity_requirements(
            db=mock_db,
            client_id="test_client",
            target_units=0,
            target_date=date.today() + timedelta(days=10),
            cycle_time_hours=Decimal("0.5"),
            shift_hours=Decimal("8.0")
        )

        assert result.required_employees == 0 or result.target_units == 0


class TestFloatingPoolOptimizationWithMock:
    """Tests for optimize_floating_pool_allocation function (requires db mock)"""

    def test_basic_optimization_balance_workload(self):
        """Test basic floating pool optimization with balance workload goal"""
        mock_db = MagicMock()

        available_employees = [
            {"employee_id": f"E{i}"} for i in range(10)
        ]

        shift_requirements = [
            {"shift_id": 1, "shift_name": "Morning", "required": 20, "regular_employees": 15},
            {"shift_id": 2, "shift_name": "Afternoon", "required": 18, "regular_employees": 16},
            {"shift_id": 3, "shift_name": "Night", "required": 15, "regular_employees": 12}
        ]

        result = optimize_floating_pool_allocation(
            db=mock_db,
            client_id="test_client",
            target_date=date.today(),
            available_pool_employees=available_employees,
            shift_requirements=shift_requirements,
            optimization_goal=OptimizationGoal.BALANCE_WORKLOAD
        )

        assert isinstance(result, FloatingPoolOptimization)
        assert result.total_available == 10
        assert len(result.allocation_suggestions) > 0

    def test_optimization_meet_target_goal(self):
        """Test optimization with meet target goal"""
        mock_db = MagicMock()

        available_employees = [{"employee_id": f"E{i}"} for i in range(5)]

        shift_requirements = [
            {"shift_id": 1, "shift_name": "S1", "required": 20, "regular_employees": 10},  # gap=10
            {"shift_id": 2, "shift_name": "S2", "required": 15, "regular_employees": 12},  # gap=3
        ]

        result = optimize_floating_pool_allocation(
            db=mock_db,
            client_id="test_client",
            target_date=date.today(),
            available_pool_employees=available_employees,
            shift_requirements=shift_requirements,
            optimization_goal=OptimizationGoal.MEET_TARGET
        )

        # Should prioritize highest gap
        assert result.allocation_suggestions[0]["shift_id"] == 1

    def test_optimization_respects_pool_size(self):
        """Test that optimization doesn't over-allocate"""
        mock_db = MagicMock()

        available_employees = [{"employee_id": f"E{i}"} for i in range(5)]

        shift_requirements = [
            {"shift_id": 1, "shift_name": "S1", "required": 30, "regular_employees": 10},
            {"shift_id": 2, "shift_name": "S2", "required": 30, "regular_employees": 10}
        ]

        result = optimize_floating_pool_allocation(
            db=mock_db,
            client_id="test_client",
            target_date=date.today(),
            available_pool_employees=available_employees,
            shift_requirements=shift_requirements,
            optimization_goal=OptimizationGoal.BALANCE_WORKLOAD
        )

        total_allocated = sum(a["employees_assigned"] for a in result.allocation_suggestions)
        assert total_allocated <= 5

    def test_optimization_no_shortage(self):
        """Test optimization when no shortage exists"""
        mock_db = MagicMock()

        available_employees = [{"employee_id": f"E{i}"} for i in range(5)]

        shift_requirements = [
            {"shift_id": 1, "shift_name": "S1", "required": 10, "regular_employees": 15},
            {"shift_id": 2, "shift_name": "S2", "required": 10, "regular_employees": 12}
        ]

        result = optimize_floating_pool_allocation(
            db=mock_db,
            client_id="test_client",
            target_date=date.today(),
            available_pool_employees=available_employees,
            shift_requirements=shift_requirements,
            optimization_goal=OptimizationGoal.BALANCE_WORKLOAD
        )

        # No allocation needed
        assert len(result.allocation_suggestions) == 0


class TestRunCapacitySimulationWithMock:
    """Tests for run_capacity_simulation function (requires db mock)"""

    @patch("backend.calculations.simulation.get_client_config_or_defaults")
    def test_comprehensive_simulation(self, mock_config):
        """Test comprehensive capacity simulation"""
        mock_config.return_value = {"default_cycle_time_hours": "0.25"}
        mock_db = MagicMock()

        simulation_config = {
            "target_units": 1000,
            "current_employees": 20,
            "shift_hours": "8.0",
            "cycle_time_hours": "0.5",
            "efficiency": "85.0",
            "staffing_scenarios": [18, 20, 22],
            "efficiency_scenarios": [80.0, 85.0, 90.0]
        }

        result = run_capacity_simulation(
            db=mock_db,
            client_id="test_client",
            simulation_config=simulation_config
        )

        assert "simulation_date" in result
        assert "capacity_requirements" in result
        assert "current_capacity" in result
        assert "gap_analysis" in result
        assert "staffing_simulations" in result
        assert "efficiency_simulations" in result
        assert "recommendations" in result


class TestDataclassesAndEnums:
    """Tests for dataclasses and enums"""

    def test_simulation_scenario_types(self):
        """Test SimulationScenarioType enum values"""
        assert SimulationScenarioType.STAFFING.value == "staffing"
        assert SimulationScenarioType.PRODUCTION.value == "production"
        assert SimulationScenarioType.CAPACITY.value == "capacity"
        assert SimulationScenarioType.EFFICIENCY.value == "efficiency"
        assert SimulationScenarioType.FLOATING_POOL.value == "floating_pool"
        assert SimulationScenarioType.SHIFT_COVERAGE.value == "shift_coverage"

    def test_optimization_goal_enum(self):
        """Test OptimizationGoal enum values"""
        assert OptimizationGoal.MINIMIZE_COST.value == "minimize_cost"
        assert OptimizationGoal.MAXIMIZE_PRODUCTION.value == "maximize_production"
        assert OptimizationGoal.BALANCE_WORKLOAD.value == "balance_workload"
        assert OptimizationGoal.MEET_TARGET.value == "meet_target"

    def test_capacity_requirement_dataclass(self):
        """Test CapacityRequirement dataclass"""
        req = CapacityRequirement(
            target_units=1000,
            required_employees=10,
            required_hours=Decimal("250"),
            required_shifts=2,
            estimated_efficiency=Decimal("85.0"),
            buffer_employees=1,
            total_recommended=11
        )

        assert req.target_units == 1000
        assert req.required_employees == 10
        assert req.total_recommended == 11
        assert req.confidence_score == Decimal("85.0")  # default


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_very_large_numbers(self):
        """Test handling of very large numbers"""
        result = calculate_production_capacity(
            employees=1000,
            shift_hours=Decimal("24.0"),
            cycle_time_hours=Decimal("0.001"),
            efficiency_percent=Decimal("99.9")
        )

        assert result is not None
        assert result["units_capacity"] > 0

    def test_decimal_precision(self):
        """Test that decimal precision is maintained"""
        result = calculate_production_capacity(
            employees=7,
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.33"),
            efficiency_percent=Decimal("87.5")
        )

        assert isinstance(result["hourly_rate"], Decimal)
        assert isinstance(result["effective_production_hours"], Decimal)

    def test_empty_scenarios(self):
        """Test handling of empty scenario lists"""
        result = run_staffing_simulation(
            base_employees=20,
            scenarios=[],
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5")
        )

        assert result == []

    def test_single_scenario(self):
        """Test simulation with single scenario"""
        result = run_efficiency_simulation(
            employees=20,
            efficiency_scenarios=[Decimal("85.0")],
            shift_hours=Decimal("8.0"),
            cycle_time_hours=Decimal("0.5")
        )

        assert len(result) == 1

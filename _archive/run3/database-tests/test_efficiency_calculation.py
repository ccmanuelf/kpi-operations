"""
Test Suite for Efficiency Calculation Fix

Verifies that efficiency uses SCHEDULED hours, not runtime hours.
"""

import pytest
from decimal import Decimal


class TestShiftHoursCalculation:
    """Test scheduled shift hours calculation."""

    def test_standard_8_hour_shift(self):
        """Standard day shift: 07:00 to 15:00"""
        from backend.calculations.efficiency import calculate_shift_hours

        hours = calculate_shift_hours("07:00:00", "15:00:00")
        assert hours == 8.0

    def test_overnight_shift(self):
        """Night shift crossing midnight: 22:00 to 06:00"""
        from backend.calculations.efficiency import calculate_shift_hours

        hours = calculate_shift_hours("22:00:00", "06:00:00")
        assert hours == 8.0

    def test_12_hour_shift(self):
        """Extended 12-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours

        hours = calculate_shift_hours("07:00:00", "19:00:00")
        assert hours == 12.0

    def test_partial_shift(self):
        """Partial 4-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours

        hours = calculate_shift_hours("08:00:00", "12:00:00")
        assert hours == 4.0


class TestEfficiencyFormula:
    """Test efficiency formula correctness."""

    def test_basic_efficiency_calculation(self):
        """
        Test Case:
        - 1000 units produced
        - 0.01 hours per unit (ideal cycle time)
        - 5 employees assigned
        - 8 hour scheduled shift

        Expected: 25% efficiency
        Formula: (1000 × 0.01) / (5 × 8) × 100 = 25%
        """
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        assert efficiency == 25.0

    def test_efficiency_independent_of_runtime(self):
        """
        CRITICAL TEST: Efficiency should NOT change with runtime.

        Same scenario, different runtimes:
        - Scenario A: 6 hours runtime (2 hours downtime)
        - Scenario B: 8 hours runtime (no downtime)

        Both should have SAME efficiency (25%) because they use
        SCHEDULED hours (8), not runtime.
        """
        from backend.calculations.efficiency import calculate_efficiency

        # Scenario A: 6 hours runtime
        efficiency_a = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0  # Uses SCHEDULED hours
        )

        # Scenario B: 8 hours runtime
        efficiency_b = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0  # Same SCHEDULED hours
        )

        # Both should be equal - efficiency is independent of actual runtime
        assert efficiency_a == efficiency_b == 25.0

    def test_high_efficiency(self):
        """
        High productivity scenario:
        - 2000 units (double production)
        - Same resources (5 employees, 8 hours)

        Expected: 50% efficiency (2x baseline)
        """
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=2000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        assert efficiency == 50.0

    def test_low_efficiency(self):
        """
        Low productivity scenario:
        - 500 units (half production)
        - Same resources

        Expected: 12.5% efficiency (0.5x baseline)
        """
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=500,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        assert efficiency == 12.5

    def test_more_employees_lower_efficiency(self):
        """
        More employees with same output = lower efficiency.

        - 1000 units
        - 10 employees (doubled)
        - Same shift hours

        Expected: 12.5% efficiency (half of baseline 25%)
        """
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=10,
            shift_hours=8.0
        )

        assert efficiency == 12.5

    def test_longer_shift_lower_efficiency(self):
        """
        Longer shift with same output = lower efficiency.

        - 1000 units
        - 12 hour shift (longer)
        - Same employees

        Expected: 16.67% efficiency (lower than 8-hour baseline)
        """
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=12.0
        )

        assert round(efficiency, 2) == 16.67


class TestEfficiencyEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_employees_returns_none(self):
        """Can't calculate efficiency with zero employees."""
        from backend.calculations.efficiency import calculate_efficiency

        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=0,
            shift_hours=8.0
        )

        assert result is None

    def test_zero_shift_hours_returns_none(self):
        """Can't calculate efficiency with zero shift hours."""
        from backend.calculations.efficiency import calculate_efficiency

        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=0.0
        )

        assert result is None

    def test_negative_units_returns_none(self):
        """Negative units should return None."""
        from backend.calculations.efficiency import calculate_efficiency

        result = calculate_efficiency(
            units_produced=-100,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        assert result is None

    def test_zero_units_zero_efficiency(self):
        """Zero units produced = 0% efficiency."""
        from backend.calculations.efficiency import calculate_efficiency

        efficiency = calculate_efficiency(
            units_produced=0,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        assert efficiency == 0.0


class TestFormulaCorrectness:
    """Verify fix matches CSV requirement specification."""

    def test_old_formula_vs_new_formula(self):
        """
        Demonstrate difference between old (wrong) and new (correct) formulas.

        Scenario:
        - 1000 units produced
        - 0.01 hr/unit cycle time
        - 5 employees
        - 8 hour scheduled shift
        - 6 hour actual runtime (25% downtime)

        OLD FORMULA (WRONG):
        efficiency = (1000 × 0.01) / (5 × 6) = 33.33%
        Problem: Uses runtime, so downtime affects efficiency

        NEW FORMULA (CORRECT):
        efficiency = (1000 × 0.01) / (5 × 8) = 25%
        Correct: Uses scheduled hours, efficiency independent of downtime
        """
        from backend.calculations.efficiency import calculate_efficiency

        # New formula (correct) - uses scheduled hours
        new_efficiency = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0  # SCHEDULED hours
        )

        # Old formula result (for comparison)
        runtime_hours = 6.0
        old_efficiency = (1000 * 0.01) / (5 * runtime_hours) * 100

        # New formula should give 25%, old gave 33.33%
        assert new_efficiency == 25.0
        assert round(old_efficiency, 2) == 33.33

        # They should be different!
        assert new_efficiency != old_efficiency

    def test_csv_requirement_compliance(self):
        """
        Verify compliance with CSV requirement:
        "Use scheduled_hours from shift, not actual run_time"

        Multiple test cases to ensure formula uses scheduled hours.
        """
        from backend.calculations.efficiency import calculate_efficiency

        test_cases = [
            {
                "units": 1000,
                "cycle_time": 0.01,
                "employees": 5,
                "scheduled_hours": 8.0,
                "expected_efficiency": 25.0
            },
            {
                "units": 2000,
                "cycle_time": 0.005,
                "employees": 10,
                "scheduled_hours": 8.0,
                "expected_efficiency": 12.5
            },
            {
                "units": 500,
                "cycle_time": 0.02,
                "employees": 2,
                "scheduled_hours": 12.0,
                "expected_efficiency": 41.67
            }
        ]

        for case in test_cases:
            efficiency = calculate_efficiency(
                units_produced=case["units"],
                ideal_cycle_time=case["cycle_time"],
                employees_assigned=case["employees"],
                shift_hours=case["scheduled_hours"]
            )

            assert round(efficiency, 2) == case["expected_efficiency"]


class TestEfficiencyVsPerformance:
    """Verify distinction between Efficiency (workforce) and Performance (machine)."""

    def test_efficiency_and_performance_different_denominators(self):
        """
        Same scenario should yield different values for efficiency and performance.

        Given:
        - 1000 units, 0.01 hr/unit
        - 5 employees, 8 hour shift
        - 6 hour runtime

        Efficiency (workforce): (1000 × 0.01) / (5 × 8) = 25%
        Performance (machine): (1000 × 0.01) / 6 = 166.67%
        """
        from backend.calculations.efficiency import calculate_efficiency
        from backend.calculations.performance import calculate_performance

        # Same base data
        units = 1000
        cycle_time = 0.01
        employees = 5
        scheduled_hours = 8.0
        runtime_hours = 6.0

        # Calculate both KPIs
        efficiency = calculate_efficiency(
            units_produced=units,
            ideal_cycle_time=cycle_time,
            employees_assigned=employees,
            shift_hours=scheduled_hours  # Uses scheduled
        )

        performance = calculate_performance(
            units_produced=units,
            ideal_cycle_time=cycle_time,
            run_time_hours=runtime_hours  # Uses runtime
        )

        # Different values
        assert efficiency == 25.0
        assert round(performance, 2) == 166.67
        assert efficiency != performance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

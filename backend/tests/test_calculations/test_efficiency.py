"""
Test Suite for Efficiency KPI (KPI #3)

Tests efficiency calculation formula:
Efficiency = (Units × Cycle Time) / (Employees × Scheduled Hours) × 100

Covers:
- Basic calculation with known inputs
- Edge cases (zero employees, zero hours)
- Boundary conditions
- Database integration
- Shift hour calculations
"""
import pytest
from decimal import Decimal
from datetime import time

from calculations.efficiency import (
    calculate_efficiency,
    calculate_shift_hours,
    calculate_efficiency_from_db,
)


class TestEfficiencyCalculation:
    """Test efficiency calculation with known inputs/outputs"""

    def test_basic_efficiency_calculation(self, expected_efficiency):
        """Test basic efficiency with standard values"""
        # Given: 1000 units, 0.01 hr cycle time, 5 employees, 8 hour shift
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Should calculate 25% efficiency
        assert result == expected_efficiency
        assert result == 25.0

    def test_high_efficiency_scenario(self):
        """Test scenario with >100% efficiency (overproduction)"""
        # Given: High production with same resources
        result = calculate_efficiency(
            units_produced=5000,  # 5x more units
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 125%
        assert result == 125.0

    def test_low_efficiency_scenario(self):
        """Test scenario with low efficiency"""
        # Given: Low production
        result = calculate_efficiency(
            units_produced=400,  # Less units
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 10%
        assert result == 10.0

    def test_efficiency_as_ratio(self):
        """Test efficiency returned as ratio instead of percentage"""
        # Given: Same scenario, but ratio format
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0,
            as_percentage=False
        )

        # Then: Should return 0.25 (25% as ratio)
        assert result == 0.25

    def test_zero_production(self):
        """Test efficiency with zero units produced"""
        # Given: No production
        result = calculate_efficiency(
            units_produced=0,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 0%
        assert result == 0.0

    def test_invalid_zero_employees(self):
        """Test that zero employees returns None"""
        # Given: Invalid zero employees
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=0,
            shift_hours=8.0
        )

        # Then: Should return None (invalid)
        assert result is None

    def test_invalid_zero_shift_hours(self):
        """Test that zero shift hours returns None"""
        # Given: Invalid zero shift hours
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=0
        )

        # Then: Should return None (invalid)
        assert result is None

    def test_negative_units_produced(self):
        """Test that negative units returns None"""
        # Given: Invalid negative units
        result = calculate_efficiency(
            units_produced=-100,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Should return None (invalid)
        assert result is None

    def test_very_small_cycle_time(self):
        """Test efficiency with very fast cycle time (seconds)"""
        # Given: 10 second cycle time = 0.00278 hours
        result = calculate_efficiency(
            units_produced=10000,
            ideal_cycle_time=0.00278,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Calculate expected efficiency
        # (10000 × 0.00278) / (5 × 8) × 100 = 27.8 / 40 × 100 = 69.5%
        assert abs(result - 69.5) < 0.1

    def test_single_employee(self):
        """Test efficiency with single employee"""
        # Given: One employee producing 80 units
        result = calculate_efficiency(
            units_produced=80,
            ideal_cycle_time=0.1,  # 6 minutes per unit
            employees_assigned=1,
            shift_hours=8.0
        )

        # Then: (80 × 0.1) / (1 × 8) × 100 = 8 / 8 × 100 = 100%
        assert result == 100.0

    def test_decimal_precision(self):
        """Test that efficiency is calculated with proper precision"""
        # Given: Values that result in repeating decimal
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=3,
            shift_hours=8.0
        )

        # Then: Should round to 4 decimal places
        # (1000 × 0.01) / (3 × 8) × 100 = 10 / 24 × 100 = 41.6667%
        assert result == 41.6667


class TestShiftHoursCalculation:
    """Test shift hours calculation from start/end times"""

    def test_standard_day_shift(self):
        """Test 8-hour day shift calculation"""
        # Given: 7 AM to 3 PM
        hours = calculate_shift_hours("07:00:00", "15:00:00")

        # Then: Should be 8 hours
        assert hours == 8.0

    def test_night_shift_overnight(self):
        """Test overnight shift calculation"""
        # Given: 10 PM to 6 AM (crosses midnight)
        hours = calculate_shift_hours("22:00:00", "06:00:00")

        # Then: Should be 8 hours
        assert hours == 8.0

    def test_12_hour_shift(self):
        """Test 12-hour shift"""
        # Given: 7 AM to 7 PM
        hours = calculate_shift_hours("07:00:00", "19:00:00")

        # Then: Should be 12 hours
        assert hours == 12.0

    def test_partial_hour_shift(self):
        """Test shift with minutes"""
        # Given: 7:30 AM to 3:45 PM
        hours = calculate_shift_hours("07:30:00", "15:45:00")

        # Then: Should be 8.25 hours
        assert hours == 8.25

    def test_very_short_shift(self):
        """Test very short shift (2 hours)"""
        # Given: 1 PM to 3 PM
        hours = calculate_shift_hours("13:00:00", "15:00:00")

        # Then: Should be 2 hours
        assert hours == 2.0


class TestEfficiencyEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_maximum_theoretical_efficiency(self):
        """Test scenario achieving maximum theoretical efficiency"""
        # Given: Perfect conditions - all time is productive
        # 8 employees × 8 hours = 64 available hours
        # 6400 units × 0.01 hrs = 64 production hours
        result = calculate_efficiency(
            units_produced=6400,
            ideal_cycle_time=0.01,
            employees_assigned=8,
            shift_hours=8.0
        )

        # Then: Should achieve 100% efficiency
        assert result == 100.0

    def test_overproduction_efficiency(self):
        """Test efficiency when production exceeds capacity (overtime/faster work)"""
        # Given: More production than theoretical capacity
        result = calculate_efficiency(
            units_produced=8000,  # Would need 80 hours
            ideal_cycle_time=0.01,
            employees_assigned=8,
            shift_hours=8.0  # Only 64 hours available
        )

        # Then: Efficiency > 100% indicates overtime or faster-than-standard work
        assert result == 125.0

    def test_very_large_numbers(self):
        """Test with very large production numbers"""
        # Given: Large batch production
        result = calculate_efficiency(
            units_produced=1000000,
            ideal_cycle_time=0.001,
            employees_assigned=50,
            shift_hours=8.0
        )

        # Then: (1000000 × 0.001) / (50 × 8) × 100 = 1000 / 400 × 100 = 250%
        assert result == 250.0

    def test_rounding_consistency(self):
        """Test that rounding is consistent"""
        # Given: Same calculation multiple times
        results = [
            calculate_efficiency(1000, 0.01, 5, 8.0)
            for _ in range(10)
        ]

        # Then: All results should be identical
        assert len(set(results)) == 1
        assert results[0] == 25.0


class TestEfficiencyBusinessScenarios:
    """Test real-world business scenarios"""

    def test_understaffed_shift(self):
        """Test efficiency when understaffed"""
        # Given: Same production with fewer employees
        normal = calculate_efficiency(1000, 0.01, 5, 8.0)
        understaffed = calculate_efficiency(1000, 0.01, 3, 8.0)

        # Then: Understaffed should show higher efficiency
        # (same output with fewer resources)
        assert understaffed > normal
        assert understaffed == pytest.approx(41.67, rel=0.01)

    def test_overstaffed_shift(self):
        """Test efficiency when overstaffed"""
        # Given: Same production with more employees
        normal = calculate_efficiency(1000, 0.01, 5, 8.0)
        overstaffed = calculate_efficiency(1000, 0.01, 8, 8.0)

        # Then: Overstaffed should show lower efficiency
        assert overstaffed < normal
        assert overstaffed == 15.625

    def test_shortened_shift_high_productivity(self):
        """Test efficiency in shortened shift with high output"""
        # Given: 6-hour shift with normal daily production
        result = calculate_efficiency(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=6.0  # Shortened shift
        )

        # Then: (1000 × 0.01) / (5 × 6) × 100 = 10 / 30 × 100 = 33.33%
        assert result == pytest.approx(33.33, rel=0.01)

    def test_double_shift_scenario(self):
        """Test efficiency across double shift"""
        # Given: 16-hour shift (2 shifts)
        result = calculate_efficiency(
            units_produced=2000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=16.0
        )

        # Then: (2000 × 0.01) / (5 × 16) × 100 = 20 / 80 × 100 = 25%
        assert result == 25.0

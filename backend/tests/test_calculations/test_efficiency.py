"""
Test Suite for Efficiency KPI (KPI #3)

Tests efficiency calculation formula:
Efficiency = (Units x Cycle Time) / (Employees x Scheduled Hours) x 100

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
from unittest.mock import Mock, MagicMock

from backend.calculations.efficiency import (
    calculate_efficiency,
    calculate_shift_hours,
    update_efficiency_for_entry,
    DEFAULT_CYCLE_TIME,
    DEFAULT_SHIFT_HOURS,
)


# ===== Helper Functions for Standalone Calculations =====

def simple_efficiency_calc(
    units_produced: int,
    ideal_cycle_time: float,
    employees_assigned: int,
    shift_hours: float,
    as_percentage: bool = True
) -> float | None:
    """
    Simple standalone efficiency calculation without DB dependency.
    Formula: (units x cycle_time) / (employees x shift_hours) x 100

    Args:
        units_produced: Number of units produced
        ideal_cycle_time: Hours per unit
        employees_assigned: Number of employees
        shift_hours: Duration of shift in hours
        as_percentage: Return as percentage (True) or ratio (False)

    Returns:
        Efficiency percentage/ratio or None if invalid inputs
    """
    if units_produced < 0 or employees_assigned <= 0 or shift_hours <= 0:
        return None

    if units_produced == 0:
        return 0.0

    efficiency = (units_produced * ideal_cycle_time) / (employees_assigned * shift_hours)

    if as_percentage:
        return round(efficiency * 100, 4)
    return round(efficiency, 4)


# ===== Test Classes =====

@pytest.mark.unit
class TestEfficiencyCalculation:
    """Test efficiency calculation with known inputs/outputs"""

    @pytest.mark.unit
    def test_basic_efficiency_calculation(self, expected_efficiency):
        """Test basic efficiency with standard values"""
        # Given: 1000 units, 0.01 hr cycle time, 5 employees, 8 hour shift
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Should calculate 25% efficiency
        assert result == expected_efficiency
        assert result == 25.0

    @pytest.mark.unit
    def test_high_efficiency_scenario(self):
        """Test scenario with >100% efficiency (overproduction)"""
        # Given: High production with same resources
        result = simple_efficiency_calc(
            units_produced=5000,  # 5x more units
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 125%
        assert result == 125.0

    @pytest.mark.unit
    def test_low_efficiency_scenario(self):
        """Test scenario with low efficiency"""
        # Given: Low production
        result = simple_efficiency_calc(
            units_produced=400,  # Less units
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 10%
        assert result == 10.0

    @pytest.mark.unit
    def test_efficiency_as_ratio(self):
        """Test efficiency returned as ratio instead of percentage"""
        # Given: Same scenario, but ratio format
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0,
            as_percentage=False
        )

        # Then: Should return 0.25 (25% as ratio)
        assert result == 0.25

    @pytest.mark.unit
    def test_zero_production(self):
        """Test efficiency with zero units produced"""
        # Given: No production
        result = simple_efficiency_calc(
            units_produced=0,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Efficiency should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_invalid_zero_employees(self):
        """Test that zero employees returns None"""
        # Given: Invalid zero employees
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=0,
            shift_hours=8.0
        )

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_invalid_zero_shift_hours(self):
        """Test that zero shift hours returns None"""
        # Given: Invalid zero shift hours
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=0
        )

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_negative_units_produced(self):
        """Test that negative units returns None"""
        # Given: Invalid negative units
        result = simple_efficiency_calc(
            units_produced=-100,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_very_small_cycle_time(self):
        """Test efficiency with very fast cycle time (seconds)"""
        # Given: 10 second cycle time = 0.00278 hours
        result = simple_efficiency_calc(
            units_produced=10000,
            ideal_cycle_time=0.00278,
            employees_assigned=5,
            shift_hours=8.0
        )

        # Then: Calculate expected efficiency
        # (10000 x 0.00278) / (5 x 8) x 100 = 27.8 / 40 x 100 = 69.5%
        assert abs(result - 69.5) < 0.1

    @pytest.mark.unit
    def test_single_employee(self):
        """Test efficiency with single employee"""
        # Given: One employee producing 80 units
        result = simple_efficiency_calc(
            units_produced=80,
            ideal_cycle_time=0.1,  # 6 minutes per unit
            employees_assigned=1,
            shift_hours=8.0
        )

        # Then: (80 x 0.1) / (1 x 8) x 100 = 8 / 8 x 100 = 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_decimal_precision(self):
        """Test that efficiency is calculated with proper precision"""
        # Given: Values that result in repeating decimal
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=3,
            shift_hours=8.0
        )

        # Then: Should round to 4 decimal places
        # (1000 x 0.01) / (3 x 8) x 100 = 10 / 24 x 100 = 41.6667%
        assert result == 41.6667


@pytest.mark.unit
class TestShiftHoursCalculation:
    """Test shift hours calculation from start/end times"""

    @pytest.mark.unit
    def test_standard_day_shift(self):
        """Test 8-hour day shift calculation"""
        # Given: 7 AM to 3 PM
        hours = calculate_shift_hours(time(7, 0), time(15, 0))

        # Then: Should be 8 hours
        assert hours == Decimal("8.0")

    @pytest.mark.unit
    def test_night_shift_overnight(self):
        """Test overnight shift calculation"""
        # Given: 10 PM to 6 AM (crosses midnight)
        hours = calculate_shift_hours(time(22, 0), time(6, 0))

        # Then: Should be 8 hours
        assert hours == Decimal("8.0")

    @pytest.mark.unit
    def test_12_hour_shift(self):
        """Test 12-hour shift"""
        # Given: 7 AM to 7 PM
        hours = calculate_shift_hours(time(7, 0), time(19, 0))

        # Then: Should be 12 hours
        assert hours == Decimal("12.0")

    @pytest.mark.unit
    def test_partial_hour_shift(self):
        """Test shift with minutes"""
        # Given: 7:30 AM to 3:45 PM
        hours = calculate_shift_hours(time(7, 30), time(15, 45))

        # Then: Should be 8.25 hours
        assert hours == Decimal("8.25")

    @pytest.mark.unit
    def test_very_short_shift(self):
        """Test very short shift (2 hours)"""
        # Given: 1 PM to 3 PM
        hours = calculate_shift_hours(time(13, 0), time(15, 0))

        # Then: Should be 2 hours
        assert hours == Decimal("2.0")


@pytest.mark.unit
class TestEfficiencyEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.unit
    def test_maximum_theoretical_efficiency(self):
        """Test scenario achieving maximum theoretical efficiency"""
        # Given: Perfect conditions - all time is productive
        # 8 employees x 8 hours = 64 available hours
        # 6400 units x 0.01 hrs = 64 production hours
        result = simple_efficiency_calc(
            units_produced=6400,
            ideal_cycle_time=0.01,
            employees_assigned=8,
            shift_hours=8.0
        )

        # Then: Should achieve 100% efficiency
        assert result == 100.0

    @pytest.mark.unit
    def test_overproduction_efficiency(self):
        """Test efficiency when production exceeds capacity (overtime/faster work)"""
        # Given: More production than theoretical capacity
        result = simple_efficiency_calc(
            units_produced=8000,  # Would need 80 hours
            ideal_cycle_time=0.01,
            employees_assigned=8,
            shift_hours=8.0  # Only 64 hours available
        )

        # Then: Efficiency > 100% indicates overtime or faster-than-standard work
        assert result == 125.0

    @pytest.mark.unit
    def test_very_large_numbers(self):
        """Test with very large production numbers"""
        # Given: Large batch production
        result = simple_efficiency_calc(
            units_produced=1000000,
            ideal_cycle_time=0.001,
            employees_assigned=50,
            shift_hours=8.0
        )

        # Then: (1000000 x 0.001) / (50 x 8) x 100 = 1000 / 400 x 100 = 250%
        assert result == 250.0

    @pytest.mark.unit
    def test_rounding_consistency(self):
        """Test that rounding is consistent"""
        # Given: Same calculation multiple times
        results = [
            simple_efficiency_calc(1000, 0.01, 5, 8.0)
            for _ in range(10)
        ]

        # Then: All results should be identical
        assert len(set(results)) == 1
        assert results[0] == 25.0


@pytest.mark.unit
class TestEfficiencyBusinessScenarios:
    """Test real-world business scenarios"""

    @pytest.mark.unit
    def test_understaffed_shift(self):
        """Test efficiency when understaffed"""
        # Given: Same production with fewer employees
        normal = simple_efficiency_calc(1000, 0.01, 5, 8.0)
        understaffed = simple_efficiency_calc(1000, 0.01, 3, 8.0)

        # Then: Understaffed should show higher efficiency
        # (same output with fewer resources)
        assert understaffed > normal
        assert understaffed == pytest.approx(41.67, rel=0.01)

    @pytest.mark.unit
    def test_overstaffed_shift(self):
        """Test efficiency when overstaffed"""
        # Given: Same production with more employees
        normal = simple_efficiency_calc(1000, 0.01, 5, 8.0)
        overstaffed = simple_efficiency_calc(1000, 0.01, 8, 8.0)

        # Then: Overstaffed should show lower efficiency
        assert overstaffed < normal
        assert overstaffed == 15.625

    @pytest.mark.unit
    def test_shortened_shift_high_productivity(self):
        """Test efficiency in shortened shift with high output"""
        # Given: 6-hour shift with normal daily production
        result = simple_efficiency_calc(
            units_produced=1000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=6.0  # Shortened shift
        )

        # Then: (1000 x 0.01) / (5 x 6) x 100 = 10 / 30 x 100 = 33.33%
        assert result == pytest.approx(33.33, rel=0.01)

    @pytest.mark.unit
    def test_double_shift_scenario(self):
        """Test efficiency across double shift"""
        # Given: 16-hour shift (2 shifts)
        result = simple_efficiency_calc(
            units_produced=2000,
            ideal_cycle_time=0.01,
            employees_assigned=5,
            shift_hours=16.0
        )

        # Then: (2000 x 0.01) / (5 x 16) x 100 = 20 / 80 x 100 = 25%
        assert result == 25.0


@pytest.mark.integration
class TestEfficiencyDatabaseIntegration:
    """Test efficiency calculation with database integration"""

    @pytest.mark.integration
    def test_calculate_efficiency_with_mock_db(self, db_session):
        """Test calculate_efficiency function with mock database"""
        from backend.schemas.client import Client, ClientType
        from backend.schemas.product import Product
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.shift import Shift

        # Create client first (required FK for product and shift)
        client = Client(
            client_id="TEST-CLIENT",
            client_name="Test Client",
            client_type=ClientType.HOURLY_RATE,
            is_active=1,
        )
        db_session.add(client)
        db_session.flush()

        # Create mock shift
        shift = Shift(
            shift_id=1,
            client_id="TEST-CLIENT",
            shift_name="Day Shift",
            start_time=time(7, 0),
            end_time=time(15, 0),
            is_active=True
        )
        db_session.add(shift)

        # Create mock product
        product = Product(
            product_id=1,
            client_id="TEST-CLIENT",
            product_code="TEST-001",
            product_name="Test Product",
            ideal_cycle_time=Decimal("0.01"),
            is_active=True
        )
        db_session.add(product)
        db_session.commit()

        # Create mock production entry - use mock since table might not exist
        mock_entry = Mock()
        mock_entry.entry_id = 1
        mock_entry.product_id = 1
        mock_entry.shift_id = 1
        mock_entry.units_produced = 1000
        mock_entry.employees_assigned = 5
        mock_entry.run_time_hours = Decimal("8.0")

        # Calculate efficiency
        efficiency, cycle_time, was_inferred = calculate_efficiency(
            db_session, mock_entry, product
        )

        # Verify result
        assert efficiency == Decimal("25.00")
        assert cycle_time == Decimal("0.01")
        assert was_inferred is False


@pytest.mark.unit
class TestDefaultConstants:
    """Test default constants used in efficiency calculations"""

    @pytest.mark.unit
    def test_default_cycle_time_value(self):
        """Test that DEFAULT_CYCLE_TIME is reasonable"""
        assert DEFAULT_CYCLE_TIME == Decimal("0.25")  # 15 minutes per unit

    @pytest.mark.unit
    def test_default_shift_hours_value(self):
        """Test that DEFAULT_SHIFT_HOURS is standard 8-hour shift"""
        assert DEFAULT_SHIFT_HOURS == Decimal("8.0")

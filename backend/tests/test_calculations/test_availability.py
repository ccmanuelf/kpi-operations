"""
Test Suite for Availability KPI (KPI #8)

Tests equipment/line availability calculations:
- Availability = (Scheduled Time - Downtime) / Scheduled Time * 100
- MTBF (Mean Time Between Failures)
- MTTR (Mean Time To Repair)

Covers:
- Basic availability calculation
- Zero downtime (100% availability)
- Full downtime (0% availability)
- Edge cases and boundary conditions
- OEE integration scenarios
"""

import pytest
from decimal import Decimal
from datetime import date, time, datetime
from unittest.mock import Mock, MagicMock


# ===== Helper Functions for Standalone Calculations =====


def calculate_availability_simple(scheduled_hours: float, downtime_hours: float) -> float | None:
    """
    Calculate availability percentage.

    Formula: ((Scheduled - Downtime) / Scheduled) * 100

    Args:
        scheduled_hours: Total scheduled production hours
        downtime_hours: Total downtime hours

    Returns:
        Availability percentage or None if invalid inputs
    """
    if scheduled_hours <= 0:
        return None
    if downtime_hours < 0:
        return None
    if downtime_hours > scheduled_hours:
        # Downtime cannot exceed scheduled time
        return 0.0

    available = scheduled_hours - downtime_hours
    availability = (available / scheduled_hours) * 100
    return round(availability, 4)


def calculate_mtbf(operating_hours: float, failure_count: int) -> float | None:
    """
    Calculate Mean Time Between Failures.

    Formula: Total Operating Time / Number of Failures

    Args:
        operating_hours: Total hours of operation
        failure_count: Number of failure events

    Returns:
        MTBF in hours or None if no failures
    """
    if failure_count <= 0:
        return None
    if operating_hours < 0:
        return None

    mtbf = operating_hours / failure_count
    return round(mtbf, 4)


def calculate_mttr(total_repair_hours: float, repair_count: int) -> float | None:
    """
    Calculate Mean Time To Repair.

    Formula: Total Repair Time / Number of Repairs

    Args:
        total_repair_hours: Total hours spent on repairs
        repair_count: Number of repair events

    Returns:
        MTTR in hours or None if no repairs
    """
    if repair_count <= 0:
        return None
    if total_repair_hours < 0:
        return None

    mttr = total_repair_hours / repair_count
    return round(mttr, 4)


def calculate_oee_availability_component(scheduled_hours: float, downtime_hours: float) -> float:
    """
    Calculate availability as decimal for OEE calculation.

    Args:
        scheduled_hours: Total scheduled hours
        downtime_hours: Total downtime hours

    Returns:
        Availability as decimal (0-1)
    """
    availability_pct = calculate_availability_simple(scheduled_hours, downtime_hours)
    if availability_pct is None:
        return 0.0
    return availability_pct / 100


# ===== Test Classes =====


@pytest.mark.unit
class TestAvailabilityBasicCalculation:
    """Test basic availability calculation"""

    @pytest.mark.unit
    def test_full_availability(self, expected_availability=None):
        """Test 100% availability when no downtime"""
        # Given: 8-hour shift with no downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=0.0)

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_standard_availability_scenario(self, expected_availability):
        """Test typical availability with some downtime"""
        # Given: 8-hour shift with 0.5 hours downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=0.5)

        # Then: Should be 93.75%
        # (8 - 0.5) / 8 * 100 = 7.5 / 8 * 100 = 93.75%
        assert result == expected_availability
        assert result == 93.75

    @pytest.mark.unit
    def test_50_percent_availability(self):
        """Test 50% availability (half shift downtime)"""
        # Given: 8-hour shift with 4 hours downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=4.0)

        # Then: Should be 50%
        assert result == 50.0

    @pytest.mark.unit
    def test_zero_availability(self):
        """Test 0% availability (full downtime)"""
        # Given: Entire shift is downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=8.0)

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_partial_hour_downtime(self):
        """Test availability with partial hour downtime"""
        # Given: 8-hour shift with 1.25 hours downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=1.25)

        # Then: (8 - 1.25) / 8 * 100 = 6.75 / 8 * 100 = 84.375%
        assert result == 84.375

    @pytest.mark.unit
    def test_12_hour_shift_availability(self):
        """Test availability for 12-hour shift"""
        # Given: 12-hour shift with 1.5 hours downtime
        result = calculate_availability_simple(scheduled_hours=12.0, downtime_hours=1.5)

        # Then: (12 - 1.5) / 12 * 100 = 10.5 / 12 * 100 = 87.5%
        assert result == 87.5

    @pytest.mark.unit
    def test_short_shift_availability(self):
        """Test availability for short (4-hour) shift"""
        # Given: 4-hour shift with 30 minutes downtime
        result = calculate_availability_simple(scheduled_hours=4.0, downtime_hours=0.5)

        # Then: (4 - 0.5) / 4 * 100 = 3.5 / 4 * 100 = 87.5%
        assert result == 87.5


@pytest.mark.unit
class TestAvailabilityEdgeCases:
    """Test edge cases for availability calculation"""

    @pytest.mark.unit
    def test_zero_scheduled_hours(self):
        """Test that zero scheduled hours returns None"""
        # Given: No scheduled time
        result = calculate_availability_simple(scheduled_hours=0.0, downtime_hours=0.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_negative_scheduled_hours(self):
        """Test that negative scheduled hours returns None"""
        # Given: Invalid negative scheduled time
        result = calculate_availability_simple(scheduled_hours=-8.0, downtime_hours=1.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_negative_downtime_hours(self):
        """Test that negative downtime returns None"""
        # Given: Invalid negative downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=-1.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_downtime_exceeds_scheduled(self):
        """Test when downtime exceeds scheduled time"""
        # Given: More downtime than scheduled (data error)
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=10.0)

        # Then: Should return 0% (capped, not negative)
        assert result == 0.0

    @pytest.mark.unit
    def test_very_small_downtime(self):
        """Test with very small downtime (seconds)"""
        # Given: 1 minute downtime = 0.0167 hours
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=0.0167)

        # Then: Should be close to 100%
        # (8 - 0.0167) / 8 * 100 = 99.79%
        assert result == pytest.approx(99.79, rel=0.01)

    @pytest.mark.unit
    def test_precision_rounding(self):
        """Test decimal precision in availability"""
        # Given: Values that produce repeating decimal
        result = calculate_availability_simple(scheduled_hours=12.0, downtime_hours=2.0)

        # Then: (12 - 2) / 12 * 100 = 10/12 * 100 = 83.3333%
        assert result == 83.3333


@pytest.mark.unit
class TestMTBFCalculation:
    """Test Mean Time Between Failures calculation"""

    @pytest.mark.unit
    def test_basic_mtbf(self):
        """Test basic MTBF calculation"""
        # Given: 100 hours operating time, 5 failures
        result = calculate_mtbf(operating_hours=100.0, failure_count=5)

        # Then: MTBF = 100 / 5 = 20 hours
        assert result == 20.0

    @pytest.mark.unit
    def test_high_mtbf_reliable_machine(self):
        """Test high MTBF (very reliable machine)"""
        # Given: 1000 hours with only 2 failures
        result = calculate_mtbf(operating_hours=1000.0, failure_count=2)

        # Then: MTBF = 1000 / 2 = 500 hours
        assert result == 500.0

    @pytest.mark.unit
    def test_low_mtbf_unreliable_machine(self):
        """Test low MTBF (unreliable machine)"""
        # Given: 40 hours with 8 failures
        result = calculate_mtbf(operating_hours=40.0, failure_count=8)

        # Then: MTBF = 40 / 8 = 5 hours
        assert result == 5.0

    @pytest.mark.unit
    def test_no_failures_returns_none(self):
        """Test MTBF with no failures"""
        # Given: No failures recorded
        result = calculate_mtbf(operating_hours=1000.0, failure_count=0)

        # Then: Should return None (cannot calculate)
        assert result is None

    @pytest.mark.unit
    def test_single_failure(self):
        """Test MTBF with single failure"""
        # Given: 168 hours (1 week) with 1 failure
        result = calculate_mtbf(operating_hours=168.0, failure_count=1)

        # Then: MTBF = 168 hours
        assert result == 168.0


@pytest.mark.unit
class TestMTTRCalculation:
    """Test Mean Time To Repair calculation"""

    @pytest.mark.unit
    def test_basic_mttr(self):
        """Test basic MTTR calculation"""
        # Given: 10 hours total repair time, 5 repairs
        result = calculate_mttr(total_repair_hours=10.0, repair_count=5)

        # Then: MTTR = 10 / 5 = 2 hours
        assert result == 2.0

    @pytest.mark.unit
    def test_quick_repairs(self):
        """Test MTTR with quick repairs"""
        # Given: 3 hours total, 6 repairs
        result = calculate_mttr(total_repair_hours=3.0, repair_count=6)

        # Then: MTTR = 0.5 hours (30 minutes)
        assert result == 0.5

    @pytest.mark.unit
    def test_slow_repairs(self):
        """Test MTTR with slow/complex repairs"""
        # Given: 24 hours total, 2 repairs
        result = calculate_mttr(total_repair_hours=24.0, repair_count=2)

        # Then: MTTR = 12 hours
        assert result == 12.0

    @pytest.mark.unit
    def test_no_repairs_returns_none(self):
        """Test MTTR with no repairs"""
        # Given: No repairs recorded
        result = calculate_mttr(total_repair_hours=0.0, repair_count=0)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_mttr_minutes_precision(self):
        """Test MTTR with minutes precision"""
        # Given: 2.5 hours total, 3 repairs
        result = calculate_mttr(total_repair_hours=2.5, repair_count=3)

        # Then: MTTR = 0.8333 hours (50 minutes)
        assert result == pytest.approx(0.8333, rel=0.01)


@pytest.mark.unit
class TestOEEAvailabilityComponent:
    """Test availability as OEE component"""

    @pytest.mark.unit
    def test_oee_availability_decimal(self):
        """Test availability returned as decimal for OEE"""
        # Given: Standard availability scenario
        result = calculate_oee_availability_component(scheduled_hours=8.0, downtime_hours=0.5)

        # Then: Should return 0.9375 (93.75%)
        assert result == 0.9375

    @pytest.mark.unit
    def test_oee_full_availability(self):
        """Test 100% availability for OEE"""
        # Given: No downtime
        result = calculate_oee_availability_component(scheduled_hours=8.0, downtime_hours=0.0)

        # Then: Should return 1.0
        assert result == 1.0

    @pytest.mark.unit
    def test_oee_low_availability(self):
        """Test low availability for OEE"""
        # Given: 25% downtime
        result = calculate_oee_availability_component(scheduled_hours=8.0, downtime_hours=2.0)

        # Then: Should return 0.75
        assert result == 0.75

    @pytest.mark.unit
    def test_oee_calculation_integration(self):
        """Test availability integrates with full OEE calculation"""
        # Given: Typical manufacturing scenario
        availability = calculate_oee_availability_component(scheduled_hours=8.0, downtime_hours=0.5)  # 0.9375

        performance = 0.85  # 85% performance
        quality = 0.98  # 98% quality

        # When: Calculate OEE
        oee = availability * performance * quality

        # Then: OEE = 0.9375 * 0.85 * 0.98 = 0.7806
        assert oee == pytest.approx(0.7806, rel=0.01)


@pytest.mark.unit
class TestAvailabilityBusinessScenarios:
    """Test real-world availability scenarios"""

    @pytest.mark.unit
    def test_planned_maintenance_impact(self):
        """Test availability with planned maintenance"""
        # Given: 8-hour shift with 1 hour planned maintenance
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=1.0)

        # Then: Should be 87.5%
        assert result == 87.5

    @pytest.mark.unit
    def test_unplanned_breakdown(self):
        """Test availability after unplanned breakdown"""
        # Given: 8-hour shift with 2.5 hours breakdown
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=2.5)

        # Then: Should be 68.75%
        assert result == 68.75

    @pytest.mark.unit
    def test_multiple_downtime_events(self):
        """Test availability with multiple downtime events"""
        # Given: Multiple downtime events totaling 1.5 hours
        downtime_events = [0.25, 0.5, 0.25, 0.5]  # 4 events
        total_downtime = sum(downtime_events)

        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=total_downtime)

        # Then: (8 - 1.5) / 8 * 100 = 81.25%
        assert result == 81.25

    @pytest.mark.unit
    def test_world_class_availability_target(self):
        """Test against world-class availability target (>=90%)"""
        # Given: Minimal downtime
        result = calculate_availability_simple(scheduled_hours=8.0, downtime_hours=0.6)  # 36 minutes

        # Then: Should exceed 90%
        # (8 - 0.6) / 8 * 100 = 92.5%
        assert result >= 90.0
        assert result == 92.5

    @pytest.mark.unit
    def test_availability_trend_improvement(self):
        """Test availability improvement over time"""
        # Given: Monthly availability data showing improvement
        month1 = calculate_availability_simple(8.0, 2.0)  # 75%
        month2 = calculate_availability_simple(8.0, 1.5)  # 81.25%
        month3 = calculate_availability_simple(8.0, 1.0)  # 87.5%
        month4 = calculate_availability_simple(8.0, 0.5)  # 93.75%

        # Then: Should show progressive improvement
        assert month1 < month2 < month3 < month4
        assert month4 > 90.0  # Achieved world-class

    @pytest.mark.unit
    def test_machine_reliability_metrics(self):
        """Test combined MTBF and MTTR analysis"""
        # Given: Machine reliability data
        operating_hours = 720  # 1 month continuous
        failures = 3
        total_repair_time = 12  # hours

        # When: Calculate metrics
        mtbf = calculate_mtbf(operating_hours, failures)
        mttr = calculate_mttr(total_repair_time, failures)

        # Then: Good machine should have high MTBF, low MTTR
        assert mtbf == 240.0  # Fails every 240 hours (10 days)
        assert mttr == 4.0  # Average 4-hour repair time

        # Calculate implied availability
        # A = MTBF / (MTBF + MTTR)
        implied_availability = mtbf / (mtbf + mttr) * 100
        assert implied_availability == pytest.approx(98.36, rel=0.01)

    @pytest.mark.unit
    def test_24_7_operation_availability(self):
        """Test availability for 24/7 operation"""
        # Given: Weekly 24/7 operation (168 hours)
        result = calculate_availability_simple(scheduled_hours=168.0, downtime_hours=8.0)  # 8 hours total downtime

        # Then: (168 - 8) / 168 * 100 = 95.24%
        assert result == pytest.approx(95.24, rel=0.01)


@pytest.mark.unit
class TestAvailabilityCategories:
    """Test availability categorization by downtime type"""

    @pytest.mark.unit
    def test_categorize_availability_level(self):
        """Test categorizing availability into performance levels"""
        # Given: Various availability percentages
        test_cases = [
            (98.0, "World Class"),
            (92.0, "Excellent"),
            (85.0, "Good"),
            (75.0, "Average"),
            (60.0, "Poor"),
        ]

        def categorize(availability: float) -> str:
            if availability >= 95:
                return "World Class"
            elif availability >= 90:
                return "Excellent"
            elif availability >= 80:
                return "Good"
            elif availability >= 70:
                return "Average"
            else:
                return "Poor"

        for availability, expected_category in test_cases:
            result = categorize(availability)
            assert result == expected_category, f"Expected {expected_category} for {availability}%"

    @pytest.mark.unit
    def test_downtime_pareto_analysis(self):
        """Test identifying major downtime contributors"""
        # Given: Downtime by category
        downtime_categories = {
            "Equipment Failure": 2.5,
            "Changeover": 1.5,
            "Material Shortage": 0.5,
            "Operator Error": 0.3,
            "Other": 0.2,
        }
        scheduled_hours = 40.0  # Weekly

        # When: Calculate availability impact of each
        total_downtime = sum(downtime_categories.values())
        availability = calculate_availability_simple(scheduled_hours, total_downtime)

        # Then: Total should be 87.5%
        # (40 - 5) / 40 * 100 = 87.5%
        assert total_downtime == 5.0
        assert availability == 87.5

        # Equipment Failure is biggest contributor (50% of downtime)
        equipment_pct = (downtime_categories["Equipment Failure"] / total_downtime) * 100
        assert equipment_pct == 50.0

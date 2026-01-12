"""
Test Suite for On-Time Delivery (OTD) KPI (KPI #2)

Tests delivery performance calculations:
- OTD% = (Orders Delivered On Time / Total Orders) * 100
- Lead Time calculation
- Cycle Time analysis
- Late order identification

Covers:
- Basic OTD calculation
- Lead time tracking
- Delivery variance analysis
- Edge cases and business scenarios
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta


# ===== Helper Functions for Standalone Calculations =====

def calculate_otd(
    on_time_count: int,
    total_count: int
) -> float | None:
    """
    Calculate On-Time Delivery percentage.

    Formula: (On-Time Orders / Total Orders) * 100

    Args:
        on_time_count: Number of orders delivered on time
        total_count: Total number of orders

    Returns:
        OTD percentage or None if invalid inputs
    """
    if total_count <= 0:
        return None
    if on_time_count < 0:
        return None
    if on_time_count > total_count:
        on_time_count = total_count  # Cap at 100%

    otd = (on_time_count / total_count) * 100
    return round(otd, 4)


def calculate_lead_time(
    start_date: date,
    end_date: date
) -> int | None:
    """
    Calculate lead time in days.

    Lead Time = End Date - Start Date (inclusive)

    Args:
        start_date: Order/production start date
        end_date: Completion/delivery date

    Returns:
        Lead time in days or None if invalid
    """
    if start_date is None or end_date is None:
        return None
    if end_date < start_date:
        return None  # Invalid: end before start

    lead_time = (end_date - start_date).days + 1  # Inclusive
    return lead_time


def calculate_delivery_variance(
    planned_date: date,
    actual_date: date
) -> int:
    """
    Calculate delivery variance in days.

    Positive = late, Negative = early

    Args:
        planned_date: Planned delivery date
        actual_date: Actual delivery date

    Returns:
        Variance in days (+ late, - early)
    """
    variance = (actual_date - planned_date).days
    return variance


def is_on_time(
    planned_date: date,
    actual_date: date,
    tolerance_days: int = 0
) -> bool:
    """
    Check if delivery was on time (within tolerance).

    Args:
        planned_date: Planned delivery date
        actual_date: Actual delivery date
        tolerance_days: Days of tolerance (default 0)

    Returns:
        True if on time, False if late
    """
    variance = calculate_delivery_variance(planned_date, actual_date)
    return variance <= tolerance_days


def calculate_cycle_time_hours(
    production_entries: list[dict]
) -> float:
    """
    Calculate total cycle time from production entries.

    Args:
        production_entries: List of entries with run_time_hours

    Returns:
        Total cycle time in hours
    """
    if not production_entries:
        return 0.0

    total_hours = sum(
        entry.get("run_time_hours", 0)
        for entry in production_entries
    )
    return round(total_hours, 2)


def categorize_delivery_status(
    variance: int
) -> str:
    """
    Categorize delivery based on variance.

    Args:
        variance: Days variance (+ late, - early)

    Returns:
        Status category string
    """
    if variance < -3:
        return "Very Early"
    elif variance < 0:
        return "Early"
    elif variance == 0:
        return "On Time"
    elif variance <= 3:
        return "Slightly Late"
    elif variance <= 7:
        return "Late"
    else:
        return "Very Late"


def calculate_otd_by_category(
    orders: list[dict]
) -> dict:
    """
    Calculate OTD statistics by category.

    Args:
        orders: List of orders with planned_date and actual_date

    Returns:
        Dictionary with OTD breakdown
    """
    if not orders:
        return {
            "total": 0,
            "on_time": 0,
            "early": 0,
            "late": 0,
            "otd_percentage": 0.0
        }

    on_time = 0
    early = 0
    late = 0

    for order in orders:
        variance = calculate_delivery_variance(
            order["planned_date"],
            order["actual_date"]
        )
        if variance < 0:
            early += 1
        elif variance == 0:
            on_time += 1
        else:
            late += 1

    total = len(orders)
    otd_count = on_time + early  # Early counts as on-time
    otd_pct = (otd_count / total) * 100 if total > 0 else 0.0

    return {
        "total": total,
        "on_time": on_time,
        "early": early,
        "late": late,
        "otd_percentage": round(otd_pct, 2)
    }


# ===== Test Classes =====

@pytest.mark.unit
class TestOTDBasicCalculation:
    """Test basic OTD calculation"""

    @pytest.mark.unit
    def test_perfect_otd(self):
        """Test 100% OTD (all orders on time)"""
        # Given: All orders delivered on time
        result = calculate_otd(
            on_time_count=100,
            total_count=100
        )

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_basic_otd_calculation(self):
        """Test basic OTD with some late orders"""
        # Given: 95 on-time out of 100 total
        result = calculate_otd(
            on_time_count=95,
            total_count=100
        )

        # Then: Should be 95%
        assert result == 95.0

    @pytest.mark.unit
    def test_50_percent_otd(self):
        """Test 50% OTD"""
        # Given: Half orders late
        result = calculate_otd(
            on_time_count=50,
            total_count=100
        )

        # Then: Should be 50%
        assert result == 50.0

    @pytest.mark.unit
    def test_zero_otd(self):
        """Test 0% OTD (all orders late)"""
        # Given: All orders late
        result = calculate_otd(
            on_time_count=0,
            total_count=100
        )

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_single_order_on_time(self):
        """Test single order delivered on time"""
        # Given: One order, on time
        result = calculate_otd(
            on_time_count=1,
            total_count=1
        )

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_single_order_late(self):
        """Test single order delivered late"""
        # Given: One order, late
        result = calculate_otd(
            on_time_count=0,
            total_count=1
        )

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_precision_otd(self):
        """Test OTD with decimal precision"""
        # Given: 33 on-time out of 100
        result = calculate_otd(
            on_time_count=33,
            total_count=100
        )

        # Then: Should be 33%
        assert result == 33.0

        # Test with repeating decimal
        result2 = calculate_otd(
            on_time_count=1,
            total_count=3
        )
        # 1/3 * 100 = 33.3333%
        assert result2 == 33.3333


@pytest.mark.unit
class TestOTDEdgeCases:
    """Test OTD edge cases"""

    @pytest.mark.unit
    def test_zero_total_orders(self):
        """Test OTD with no orders"""
        # Given: No orders
        result = calculate_otd(
            on_time_count=0,
            total_count=0
        )

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_negative_total_orders(self):
        """Test OTD with negative total"""
        # Given: Invalid negative total
        result = calculate_otd(
            on_time_count=0,
            total_count=-10
        )

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_negative_on_time_count(self):
        """Test OTD with negative on-time count"""
        # Given: Invalid negative on-time
        result = calculate_otd(
            on_time_count=-5,
            total_count=100
        )

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_on_time_exceeds_total(self):
        """Test when on-time exceeds total (data error)"""
        # Given: More on-time than total
        result = calculate_otd(
            on_time_count=120,
            total_count=100
        )

        # Then: Should cap at 100%
        assert result == 100.0


@pytest.mark.unit
class TestLeadTimeCalculation:
    """Test lead time calculation"""

    @pytest.mark.unit
    def test_same_day_lead_time(self):
        """Test lead time when completed same day"""
        # Given: Start and end same day
        result = calculate_lead_time(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15)
        )

        # Then: Should be 1 day (inclusive)
        assert result == 1

    @pytest.mark.unit
    def test_one_week_lead_time(self):
        """Test one-week lead time"""
        # Given: Monday to Friday
        result = calculate_lead_time(
            start_date=date(2024, 1, 15),  # Monday
            end_date=date(2024, 1, 19)     # Friday
        )

        # Then: Should be 5 days
        assert result == 5

    @pytest.mark.unit
    def test_one_month_lead_time(self):
        """Test one-month lead time"""
        # Given: Month start to end
        result = calculate_lead_time(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        # Then: Should be 31 days
        assert result == 31

    @pytest.mark.unit
    def test_invalid_lead_time_end_before_start(self):
        """Test invalid lead time (end before start)"""
        # Given: End date before start
        result = calculate_lead_time(
            start_date=date(2024, 1, 20),
            end_date=date(2024, 1, 15)
        )

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_lead_time_with_none_dates(self):
        """Test lead time with None dates"""
        # Given: None dates
        result = calculate_lead_time(
            start_date=None,
            end_date=date(2024, 1, 15)
        )

        # Then: Should return None
        assert result is None


@pytest.mark.unit
class TestDeliveryVariance:
    """Test delivery variance calculation"""

    @pytest.mark.unit
    def test_on_time_delivery(self):
        """Test exactly on-time delivery"""
        # Given: Delivered exactly on planned date
        result = calculate_delivery_variance(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 15)
        )

        # Then: Variance should be 0
        assert result == 0

    @pytest.mark.unit
    def test_early_delivery(self):
        """Test early delivery (negative variance)"""
        # Given: Delivered 2 days early
        result = calculate_delivery_variance(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 13)
        )

        # Then: Variance should be -2
        assert result == -2

    @pytest.mark.unit
    def test_late_delivery(self):
        """Test late delivery (positive variance)"""
        # Given: Delivered 3 days late
        result = calculate_delivery_variance(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 18)
        )

        # Then: Variance should be +3
        assert result == 3

    @pytest.mark.unit
    def test_very_late_delivery(self):
        """Test very late delivery"""
        # Given: Delivered 2 weeks late
        result = calculate_delivery_variance(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 29)
        )

        # Then: Variance should be +14
        assert result == 14


@pytest.mark.unit
class TestOnTimeCheck:
    """Test on-time delivery check"""

    @pytest.mark.unit
    def test_exact_on_time(self):
        """Test delivery exactly on planned date"""
        # Given: Exact on-time delivery
        result = is_on_time(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 15)
        )

        # Then: Should be True
        assert result is True

    @pytest.mark.unit
    def test_early_is_on_time(self):
        """Test early delivery counts as on-time"""
        # Given: Delivered early
        result = is_on_time(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 13)
        )

        # Then: Should be True
        assert result is True

    @pytest.mark.unit
    def test_late_is_not_on_time(self):
        """Test late delivery is not on-time"""
        # Given: Delivered 1 day late
        result = is_on_time(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 16)
        )

        # Then: Should be False
        assert result is False

    @pytest.mark.unit
    def test_within_tolerance(self):
        """Test delivery within tolerance window"""
        # Given: 1 day late but 2-day tolerance
        result = is_on_time(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 16),
            tolerance_days=2
        )

        # Then: Should be True (within tolerance)
        assert result is True

    @pytest.mark.unit
    def test_outside_tolerance(self):
        """Test delivery outside tolerance window"""
        # Given: 3 days late with 2-day tolerance
        result = is_on_time(
            planned_date=date(2024, 1, 15),
            actual_date=date(2024, 1, 18),
            tolerance_days=2
        )

        # Then: Should be False (outside tolerance)
        assert result is False


@pytest.mark.unit
class TestDeliveryStatusCategorization:
    """Test delivery status categorization"""

    @pytest.mark.unit
    def test_very_early_status(self):
        """Test very early delivery status"""
        # Given: 5 days early
        result = categorize_delivery_status(-5)

        # Then: Should be "Very Early"
        assert result == "Very Early"

    @pytest.mark.unit
    def test_early_status(self):
        """Test early delivery status"""
        # Given: 2 days early
        result = categorize_delivery_status(-2)

        # Then: Should be "Early"
        assert result == "Early"

    @pytest.mark.unit
    def test_on_time_status(self):
        """Test on-time delivery status"""
        # Given: Exact on-time
        result = categorize_delivery_status(0)

        # Then: Should be "On Time"
        assert result == "On Time"

    @pytest.mark.unit
    def test_slightly_late_status(self):
        """Test slightly late delivery status"""
        # Given: 2 days late
        result = categorize_delivery_status(2)

        # Then: Should be "Slightly Late"
        assert result == "Slightly Late"

    @pytest.mark.unit
    def test_late_status(self):
        """Test late delivery status"""
        # Given: 5 days late
        result = categorize_delivery_status(5)

        # Then: Should be "Late"
        assert result == "Late"

    @pytest.mark.unit
    def test_very_late_status(self):
        """Test very late delivery status"""
        # Given: 10 days late
        result = categorize_delivery_status(10)

        # Then: Should be "Very Late"
        assert result == "Very Late"


@pytest.mark.unit
class TestCycleTimeCalculation:
    """Test cycle time calculation"""

    @pytest.mark.unit
    def test_single_entry_cycle_time(self):
        """Test cycle time with single production entry"""
        # Given: Single entry
        entries = [{"run_time_hours": 8.0}]

        result = calculate_cycle_time_hours(entries)

        # Then: Should be 8 hours
        assert result == 8.0

    @pytest.mark.unit
    def test_multiple_entries_cycle_time(self):
        """Test cycle time with multiple production entries"""
        # Given: Multiple entries
        entries = [
            {"run_time_hours": 8.0},
            {"run_time_hours": 6.5},
            {"run_time_hours": 7.25},
        ]

        result = calculate_cycle_time_hours(entries)

        # Then: Should be total of all hours
        assert result == 21.75

    @pytest.mark.unit
    def test_empty_entries_cycle_time(self):
        """Test cycle time with no entries"""
        # Given: Empty list
        entries = []

        result = calculate_cycle_time_hours(entries)

        # Then: Should be 0
        assert result == 0.0


@pytest.mark.unit
class TestOTDByCategory:
    """Test OTD breakdown by category"""

    @pytest.mark.unit
    def test_all_on_time(self):
        """Test all orders on time"""
        # Given: All orders exactly on time
        orders = [
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 15)},
            {"planned_date": date(2024, 1, 16), "actual_date": date(2024, 1, 16)},
            {"planned_date": date(2024, 1, 17), "actual_date": date(2024, 1, 17)},
        ]

        result = calculate_otd_by_category(orders)

        # Then: 100% OTD
        assert result["total"] == 3
        assert result["on_time"] == 3
        assert result["early"] == 0
        assert result["late"] == 0
        assert result["otd_percentage"] == 100.0

    @pytest.mark.unit
    def test_mixed_delivery_status(self):
        """Test mixed delivery statuses"""
        # Given: Mix of early, on-time, and late
        orders = [
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 13)},  # Early
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 15)},  # On time
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 18)},  # Late
            {"planned_date": date(2024, 1, 16), "actual_date": date(2024, 1, 14)},  # Early
        ]

        result = calculate_otd_by_category(orders)

        # Then: 75% OTD (early + on-time)
        assert result["total"] == 4
        assert result["on_time"] == 1
        assert result["early"] == 2
        assert result["late"] == 1
        assert result["otd_percentage"] == 75.0

    @pytest.mark.unit
    def test_empty_orders(self):
        """Test with no orders"""
        # Given: No orders
        orders = []

        result = calculate_otd_by_category(orders)

        # Then: All zeros
        assert result["total"] == 0
        assert result["otd_percentage"] == 0.0


@pytest.mark.unit
class TestOTDBusinessScenarios:
    """Test real-world OTD scenarios"""

    @pytest.mark.unit
    def test_monthly_otd_report(self):
        """Test monthly OTD report calculation"""
        # Given: Monthly order data
        orders = [
            {"planned_date": date(2024, 1, i), "actual_date": date(2024, 1, i)}
            if i <= 28  # 28 on-time
            else {"planned_date": date(2024, 1, i), "actual_date": date(2024, 2, 1)}  # Late delivery into Feb
            for i in range(1, 31)  # 30 orders total
        ]

        result = calculate_otd_by_category(orders)

        # Then: ~93.3% OTD (28/30)
        assert result["otd_percentage"] == pytest.approx(93.33, rel=0.01)

    @pytest.mark.unit
    def test_customer_priority_impact(self):
        """Test OTD for priority vs standard customers"""
        # Given: Priority customers get better OTD
        priority_orders = [
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 14)},
            {"planned_date": date(2024, 1, 16), "actual_date": date(2024, 1, 16)},
            {"planned_date": date(2024, 1, 17), "actual_date": date(2024, 1, 17)},
        ]
        standard_orders = [
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 17)},
            {"planned_date": date(2024, 1, 16), "actual_date": date(2024, 1, 18)},
            {"planned_date": date(2024, 1, 17), "actual_date": date(2024, 1, 17)},
        ]

        priority_result = calculate_otd_by_category(priority_orders)
        standard_result = calculate_otd_by_category(standard_orders)

        # Then: Priority should have better OTD
        assert priority_result["otd_percentage"] == 100.0
        assert standard_result["otd_percentage"] == pytest.approx(33.33, rel=0.01)

    @pytest.mark.unit
    def test_world_class_otd_target(self):
        """Test against world-class OTD target (>=98%)"""
        # Given: High-performing delivery
        on_time = 98
        total = 100

        result = calculate_otd(on_time, total)

        # Then: Should meet world-class target
        assert result >= 98.0

    @pytest.mark.unit
    def test_otd_trend_improvement(self):
        """Test OTD improvement over quarters"""
        # Given: Quarterly OTD data showing improvement
        q1_otd = calculate_otd(85, 100)  # 85%
        q2_otd = calculate_otd(90, 100)  # 90%
        q3_otd = calculate_otd(95, 100)  # 95%
        q4_otd = calculate_otd(98, 100)  # 98%

        # Then: Should show progressive improvement
        assert q1_otd < q2_otd < q3_otd < q4_otd
        assert q4_otd == 98.0

    @pytest.mark.unit
    def test_lead_time_vs_otd_correlation(self):
        """Test that shorter lead times often correlate with better OTD"""
        # Given: Orders with various lead times
        short_lead_orders = [
            {"planned_date": date(2024, 1, 10), "actual_date": date(2024, 1, 10)},  # On time
            {"planned_date": date(2024, 1, 11), "actual_date": date(2024, 1, 11)},  # On time
        ]
        long_lead_orders = [
            {"planned_date": date(2024, 1, 30), "actual_date": date(2024, 2, 2)},   # Late
            {"planned_date": date(2024, 1, 31), "actual_date": date(2024, 2, 3)},   # Late
        ]

        short_otd = calculate_otd_by_category(short_lead_orders)
        long_otd = calculate_otd_by_category(long_lead_orders)

        # Then: Short lead time orders have better OTD
        assert short_otd["otd_percentage"] == 100.0
        assert long_otd["otd_percentage"] == 0.0

    @pytest.mark.unit
    def test_late_order_cost_impact(self):
        """Test calculating cost impact of late orders"""
        # Given: Late order data with penalty costs
        total_orders = 100
        late_orders = 8
        penalty_per_late_order = 500.0  # $500 penalty per late order

        # When: Calculate OTD and costs
        otd = calculate_otd(total_orders - late_orders, total_orders)
        total_penalties = late_orders * penalty_per_late_order

        # Then: Calculate impact
        assert otd == 92.0
        assert total_penalties == 4000.0  # $4000 in penalties

    @pytest.mark.unit
    def test_delivery_variance_distribution(self):
        """Test analyzing delivery variance distribution"""
        # Given: Orders with various variances
        orders = [
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 10)},  # -5 (Very Early)
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 14)},  # -1 (Early)
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 15)},  # 0 (On Time)
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 16)},  # +1 (Slightly Late)
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 20)},  # +5 (Late)
            {"planned_date": date(2024, 1, 15), "actual_date": date(2024, 1, 25)},  # +10 (Very Late)
        ]

        # When: Categorize each
        categories = [
            categorize_delivery_status(
                calculate_delivery_variance(o["planned_date"], o["actual_date"])
            )
            for o in orders
        ]

        # Then: Verify distribution
        assert categories.count("Very Early") == 1
        assert categories.count("Early") == 1
        assert categories.count("On Time") == 1
        assert categories.count("Slightly Late") == 1
        assert categories.count("Late") == 1
        assert categories.count("Very Late") == 1

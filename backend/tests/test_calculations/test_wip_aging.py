"""
Test Suite for WIP Aging KPI (KPI #1)

Tests WIP (Work-in-Progress) aging calculations:
- Aging bucket categorization (0-7, 8-14, 15-30, 30+ days)
- Hold resolution rate calculation
- Chronic hold identification
- Average aging calculation

Covers:
- Basic aging calculation
- Bucket distribution
- Edge cases (negative dates, zero quantities)
- Hold resolution tracking
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch


# ===== Helper Functions for Standalone Calculations =====

def calculate_aging_days(hold_date: date, as_of_date: date = None) -> int:
    """
    Calculate aging days from hold date to as-of date.

    Args:
        hold_date: Date when item was put on hold
        as_of_date: Date to calculate aging against (default: today)

    Returns:
        Number of days in aging
    """
    if as_of_date is None:
        as_of_date = date.today()

    aging = (as_of_date - hold_date).days
    return max(0, aging)


def categorize_aging_bucket(aging_days: int) -> str:
    """
    Categorize aging days into standard buckets.

    Args:
        aging_days: Number of days in aging

    Returns:
        Bucket category string
    """
    if aging_days <= 7:
        return "0-7"
    elif aging_days <= 14:
        return "8-14"
    elif aging_days <= 30:
        return "15-30"
    else:
        return "over_30"


def calculate_average_wip_age(
    holds: list[dict],
    as_of_date: date = None
) -> Decimal:
    """
    Calculate weighted average WIP age.

    Args:
        holds: List of hold records with hold_date and quantity
        as_of_date: Date to calculate against

    Returns:
        Weighted average aging in days
    """
    if as_of_date is None:
        as_of_date = date.today()

    if not holds:
        return Decimal("0")

    total_weighted_days = 0
    total_quantity = 0

    for hold in holds:
        aging_days = (as_of_date - hold["hold_date"]).days
        quantity = hold.get("quantity", 1)
        total_weighted_days += aging_days * quantity
        total_quantity += quantity

    if total_quantity == 0:
        return Decimal("0")

    return Decimal(str(total_weighted_days)) / Decimal(str(total_quantity))


def calculate_hold_resolution_rate(
    holds: list[dict],
    target_days: int = 7
) -> Decimal:
    """
    Calculate percentage of holds resolved within target time.

    Args:
        holds: List of hold records with hold_date and release_date
        target_days: Target resolution time in days

    Returns:
        Resolution rate as percentage
    """
    if not holds:
        return Decimal("0")

    released_holds = [h for h in holds if h.get("release_date") is not None]
    if not released_holds:
        return Decimal("0")

    on_time = 0
    for hold in released_holds:
        resolution_days = (hold["release_date"] - hold["hold_date"]).days
        if resolution_days <= target_days:
            on_time += 1

    return (Decimal(str(on_time)) / Decimal(str(len(released_holds)))) * 100


# ===== Test Classes =====

@pytest.mark.unit
class TestWIPAgingBasicCalculation:
    """Test basic WIP aging calculation"""

    @pytest.mark.unit
    def test_basic_aging_calculation(self):
        """Test basic aging days calculation"""
        # Given: Item held 15 days ago
        hold_date = date(2024, 1, 1)
        as_of_date = date(2024, 1, 16)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)

        # Then: Should be 15 days
        assert aging_days == 15

    @pytest.mark.unit
    def test_same_day_aging(self):
        """Test aging when held today"""
        # Given: Item held today
        today = date.today()

        # When: Calculate aging
        aging_days = calculate_aging_days(today, today)

        # Then: Should be 0 days
        assert aging_days == 0

    @pytest.mark.unit
    def test_one_day_aging(self):
        """Test aging of exactly 1 day"""
        # Given: Item held yesterday
        hold_date = date(2024, 1, 1)
        as_of_date = date(2024, 1, 2)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)

        # Then: Should be 1 day
        assert aging_days == 1

    @pytest.mark.unit
    def test_negative_aging_returns_zero(self):
        """Test that future hold dates return 0 (edge case)"""
        # Given: Future hold date (data error scenario)
        hold_date = date(2024, 1, 20)
        as_of_date = date(2024, 1, 15)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)

        # Then: Should return 0 (not negative)
        assert aging_days == 0


@pytest.mark.unit
class TestWIPAgingBuckets:
    """Test WIP aging bucket categorization"""

    @pytest.mark.unit
    def test_bucket_0_7_days(self):
        """Test items in 0-7 day bucket"""
        # Given: Various aging within first week
        test_cases = [0, 1, 3, 5, 7]

        for days in test_cases:
            # When: Categorize
            bucket = categorize_aging_bucket(days)

            # Then: Should be in 0-7 bucket
            assert bucket == "0-7", f"Day {days} should be in 0-7 bucket"

    @pytest.mark.unit
    def test_bucket_8_14_days(self):
        """Test items in 8-14 day bucket"""
        # Given: Aging in second week
        test_cases = [8, 10, 12, 14]

        for days in test_cases:
            # When: Categorize
            bucket = categorize_aging_bucket(days)

            # Then: Should be in 8-14 bucket
            assert bucket == "8-14", f"Day {days} should be in 8-14 bucket"

    @pytest.mark.unit
    def test_bucket_15_30_days(self):
        """Test items in 15-30 day bucket"""
        # Given: Aging in weeks 3-4
        test_cases = [15, 20, 25, 30]

        for days in test_cases:
            # When: Categorize
            bucket = categorize_aging_bucket(days)

            # Then: Should be in 15-30 bucket
            assert bucket == "15-30", f"Day {days} should be in 15-30 bucket"

    @pytest.mark.unit
    def test_bucket_over_30_days(self):
        """Test items in over 30 day bucket"""
        # Given: Aging over 30 days
        test_cases = [31, 45, 60, 90, 365]

        for days in test_cases:
            # When: Categorize
            bucket = categorize_aging_bucket(days)

            # Then: Should be in over_30 bucket
            assert bucket == "over_30", f"Day {days} should be in over_30 bucket"

    @pytest.mark.unit
    def test_bucket_boundary_day_7(self):
        """Test boundary at day 7"""
        # Given: Exactly 7 days
        bucket_7 = categorize_aging_bucket(7)
        bucket_8 = categorize_aging_bucket(8)

        # Then: Day 7 should be in 0-7, day 8 in 8-14
        assert bucket_7 == "0-7"
        assert bucket_8 == "8-14"

    @pytest.mark.unit
    def test_bucket_boundary_day_14(self):
        """Test boundary at day 14"""
        # Given: Days 14 and 15
        bucket_14 = categorize_aging_bucket(14)
        bucket_15 = categorize_aging_bucket(15)

        # Then: Day 14 should be in 8-14, day 15 in 15-30
        assert bucket_14 == "8-14"
        assert bucket_15 == "15-30"

    @pytest.mark.unit
    def test_bucket_boundary_day_30(self):
        """Test boundary at day 30"""
        # Given: Days 30 and 31
        bucket_30 = categorize_aging_bucket(30)
        bucket_31 = categorize_aging_bucket(31)

        # Then: Day 30 should be in 15-30, day 31 in over_30
        assert bucket_30 == "15-30"
        assert bucket_31 == "over_30"


@pytest.mark.unit
class TestWIPAverageAging:
    """Test weighted average WIP aging calculation"""

    @pytest.mark.unit
    def test_single_item_average(self):
        """Test average with single item"""
        # Given: One hold
        as_of_date = date(2024, 1, 16)
        holds = [{"hold_date": date(2024, 1, 1), "quantity": 100}]

        # When: Calculate average
        avg = calculate_average_wip_age(holds, as_of_date)

        # Then: Should be exactly 15 days
        assert float(avg) == 15.0

    @pytest.mark.unit
    def test_multiple_items_same_quantity(self):
        """Test average with multiple items, same quantity"""
        # Given: Multiple holds with equal quantities
        as_of_date = date(2024, 1, 20)
        holds = [
            {"hold_date": date(2024, 1, 10), "quantity": 100},  # 10 days
            {"hold_date": date(2024, 1, 15), "quantity": 100},  # 5 days
            {"hold_date": date(2024, 1, 18), "quantity": 100},  # 2 days
        ]

        # When: Calculate average
        avg = calculate_average_wip_age(holds, as_of_date)

        # Then: Average should be (10+5+2)/3 = 5.67 days
        # Weighted: (10*100 + 5*100 + 2*100) / 300 = 1700/300 = 5.67
        assert float(avg) == pytest.approx(5.67, rel=0.01)

    @pytest.mark.unit
    def test_weighted_average_different_quantities(self):
        """Test weighted average with different quantities"""
        # Given: Holds with different quantities
        as_of_date = date(2024, 1, 20)
        holds = [
            {"hold_date": date(2024, 1, 10), "quantity": 1000},  # 10 days, large qty
            {"hold_date": date(2024, 1, 15), "quantity": 100},   # 5 days, small qty
        ]

        # When: Calculate weighted average
        avg = calculate_average_wip_age(holds, as_of_date)

        # Then: Weighted toward the larger quantity
        # (10*1000 + 5*100) / (1000+100) = 10500/1100 = 9.545
        assert float(avg) == pytest.approx(9.55, rel=0.01)

    @pytest.mark.unit
    def test_empty_holds_list(self):
        """Test average with no holds"""
        # Given: Empty list
        holds = []

        # When: Calculate average
        avg = calculate_average_wip_age(holds)

        # Then: Should be 0
        assert float(avg) == 0.0

    @pytest.mark.unit
    def test_zero_quantity_holds(self):
        """Test average when all quantities are zero"""
        # Given: Holds with zero quantities
        holds = [
            {"hold_date": date(2024, 1, 1), "quantity": 0},
            {"hold_date": date(2024, 1, 5), "quantity": 0},
        ]

        # When: Calculate average
        avg = calculate_average_wip_age(holds, date(2024, 1, 20))

        # Then: Should be 0 (avoid division by zero)
        assert float(avg) == 0.0


@pytest.mark.unit
class TestHoldResolutionRate:
    """Test hold resolution rate calculation"""

    @pytest.mark.unit
    def test_all_holds_resolved_on_time(self):
        """Test 100% on-time resolution"""
        # Given: All holds resolved within 7 days
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 5)},   # 4 days
            {"hold_date": date(2024, 1, 3), "release_date": date(2024, 1, 8)},   # 5 days
            {"hold_date": date(2024, 1, 5), "release_date": date(2024, 1, 12)},  # 7 days
        ]

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds, target_days=7)

        # Then: Should be 100%
        assert float(rate) == 100.0

    @pytest.mark.unit
    def test_no_holds_resolved_on_time(self):
        """Test 0% on-time resolution"""
        # Given: All holds resolved late
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 15)},  # 14 days
            {"hold_date": date(2024, 1, 3), "release_date": date(2024, 1, 20)},  # 17 days
            {"hold_date": date(2024, 1, 5), "release_date": date(2024, 1, 25)},  # 20 days
        ]

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds, target_days=7)

        # Then: Should be 0%
        assert float(rate) == 0.0

    @pytest.mark.unit
    def test_partial_on_time_resolution(self):
        """Test partial on-time resolution"""
        # Given: Mix of on-time and late resolutions
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 5)},   # 4 days - on time
            {"hold_date": date(2024, 1, 3), "release_date": date(2024, 1, 15)},  # 12 days - late
            {"hold_date": date(2024, 1, 5), "release_date": date(2024, 1, 10)},  # 5 days - on time
        ]

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds, target_days=7)

        # Then: Should be 66.67% (2 out of 3)
        assert float(rate) == pytest.approx(66.67, rel=0.01)

    @pytest.mark.unit
    def test_unreleased_holds_excluded(self):
        """Test that unreleased holds are excluded from calculation"""
        # Given: Mix of released and unreleased holds
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 5)},   # Released on time
            {"hold_date": date(2024, 1, 3), "release_date": None},               # Not released
            {"hold_date": date(2024, 1, 5), "release_date": None},               # Not released
        ]

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds, target_days=7)

        # Then: Should be 100% (only 1 released, and it was on time)
        assert float(rate) == 100.0

    @pytest.mark.unit
    def test_no_released_holds(self):
        """Test with no released holds"""
        # Given: All holds unreleased
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": None},
            {"hold_date": date(2024, 1, 3), "release_date": None},
        ]

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds, target_days=7)

        # Then: Should be 0%
        assert float(rate) == 0.0

    @pytest.mark.unit
    def test_empty_holds_list_resolution(self):
        """Test resolution rate with empty list"""
        # Given: No holds
        holds = []

        # When: Calculate resolution rate
        rate = calculate_hold_resolution_rate(holds)

        # Then: Should be 0%
        assert float(rate) == 0.0

    @pytest.mark.unit
    def test_custom_target_days(self):
        """Test with custom target days"""
        # Given: Holds with various resolution times
        holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 4)},   # 3 days
            {"hold_date": date(2024, 1, 3), "release_date": date(2024, 1, 8)},   # 5 days
            {"hold_date": date(2024, 1, 5), "release_date": date(2024, 1, 12)},  # 7 days
        ]

        # When: Calculate with 3-day target
        rate_3day = calculate_hold_resolution_rate(holds, target_days=3)

        # When: Calculate with 5-day target
        rate_5day = calculate_hold_resolution_rate(holds, target_days=5)

        # Then: Different targets should yield different rates
        assert float(rate_3day) == pytest.approx(33.33, rel=0.01)  # 1 of 3
        assert float(rate_5day) == pytest.approx(66.67, rel=0.01)  # 2 of 3


@pytest.mark.unit
class TestWIPAgingEdgeCases:
    """Test edge cases for WIP aging calculations"""

    @pytest.mark.unit
    def test_very_old_hold(self):
        """Test hold that is very old (over 1 year)"""
        # Given: Hold from over a year ago
        hold_date = date(2023, 1, 1)
        as_of_date = date(2024, 6, 1)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)
        bucket = categorize_aging_bucket(aging_days)

        # Then: Should be over 30 bucket and ~517 days
        assert aging_days == 517
        assert bucket == "over_30"

    @pytest.mark.unit
    def test_leap_year_boundary(self):
        """Test aging across leap year boundary"""
        # Given: Hold spanning Feb 29
        hold_date = date(2024, 2, 28)
        as_of_date = date(2024, 3, 1)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)

        # Then: Should be 2 days (Feb 28 -> Feb 29 -> Mar 1)
        assert aging_days == 2

    @pytest.mark.unit
    def test_year_boundary(self):
        """Test aging across year boundary"""
        # Given: Hold spanning Dec 31 to Jan 1
        hold_date = date(2023, 12, 31)
        as_of_date = date(2024, 1, 1)

        # When: Calculate aging
        aging_days = calculate_aging_days(hold_date, as_of_date)

        # Then: Should be 1 day
        assert aging_days == 1

    @pytest.mark.unit
    def test_large_quantity_weighting(self):
        """Test that large quantities properly weight the average"""
        # Given: One small old hold, one large new hold
        as_of_date = date(2024, 1, 30)
        holds = [
            {"hold_date": date(2024, 1, 1), "quantity": 10},      # 29 days, small
            {"hold_date": date(2024, 1, 29), "quantity": 10000},  # 1 day, large
        ]

        # When: Calculate weighted average
        avg = calculate_average_wip_age(holds, as_of_date)

        # Then: Should be heavily weighted toward 1 day
        # (29*10 + 1*10000) / (10 + 10000) = 10290/10010 = 1.028 days
        assert float(avg) == pytest.approx(1.03, rel=0.01)


@pytest.mark.unit
class TestWIPAgingBusinessScenarios:
    """Test real-world WIP aging scenarios"""

    @pytest.mark.unit
    def test_quality_hold_scenario(self):
        """Test typical quality hold scenario"""
        # Given: Quality inspection hold
        hold_date = date(2024, 1, 10)
        inspection_date = date(2024, 1, 15)  # 5 days later
        release_date = date(2024, 1, 16)     # Released next day

        holds = [{"hold_date": hold_date, "release_date": release_date, "quantity": 500}]

        # When: Check resolution
        rate = calculate_hold_resolution_rate(holds, target_days=7)
        aging_at_inspection = calculate_aging_days(hold_date, inspection_date)
        final_aging = calculate_aging_days(hold_date, release_date)

        # Then: Should be resolved on time
        assert float(rate) == 100.0
        assert aging_at_inspection == 5
        assert final_aging == 6

    @pytest.mark.unit
    def test_chronic_hold_identification(self):
        """Test identifying chronic holds (>30 days)"""
        # Given: Mix of holds
        as_of_date = date(2024, 2, 15)
        holds = [
            {"hold_date": date(2024, 2, 10), "quantity": 100},   # 5 days - OK
            {"hold_date": date(2024, 1, 25), "quantity": 200},   # 21 days - Warning
            {"hold_date": date(2024, 1, 1), "quantity": 50},     # 45 days - Chronic
            {"hold_date": date(2023, 12, 1), "quantity": 30},    # 76 days - Chronic
        ]

        # When: Identify chronic holds
        chronic_count = 0
        for hold in holds:
            aging = calculate_aging_days(hold["hold_date"], as_of_date)
            if categorize_aging_bucket(aging) == "over_30":
                chronic_count += 1

        # Then: Should identify 2 chronic holds
        assert chronic_count == 2

    @pytest.mark.unit
    def test_monthly_aging_report(self):
        """Test monthly aging distribution report"""
        # Given: Various holds at month end
        as_of_date = date(2024, 1, 31)
        holds = [
            {"hold_date": date(2024, 1, 28), "quantity": 100},   # 3 days
            {"hold_date": date(2024, 1, 25), "quantity": 150},   # 6 days
            {"hold_date": date(2024, 1, 20), "quantity": 200},   # 11 days
            {"hold_date": date(2024, 1, 10), "quantity": 80},    # 21 days
            {"hold_date": date(2023, 12, 15), "quantity": 50},   # 47 days
        ]

        # When: Build distribution report
        distribution = {"0-7": 0, "8-14": 0, "15-30": 0, "over_30": 0}
        for hold in holds:
            aging = calculate_aging_days(hold["hold_date"], as_of_date)
            bucket = categorize_aging_bucket(aging)
            distribution[bucket] += hold["quantity"]

        # Then: Validate distribution
        assert distribution["0-7"] == 250     # 100 + 150
        assert distribution["8-14"] == 200    # 200
        assert distribution["15-30"] == 80    # 80
        assert distribution["over_30"] == 50  # 50

    @pytest.mark.unit
    def test_resolution_time_trend(self):
        """Test resolution time trend analysis"""
        # Given: Holds over multiple months showing improvement
        month1_holds = [
            {"hold_date": date(2024, 1, 1), "release_date": date(2024, 1, 12)},   # 11 days
            {"hold_date": date(2024, 1, 5), "release_date": date(2024, 1, 14)},   # 9 days
        ]
        month2_holds = [
            {"hold_date": date(2024, 2, 1), "release_date": date(2024, 2, 6)},    # 5 days
            {"hold_date": date(2024, 2, 5), "release_date": date(2024, 2, 10)},   # 5 days
        ]

        # When: Calculate resolution rates
        rate_m1 = calculate_hold_resolution_rate(month1_holds, target_days=7)
        rate_m2 = calculate_hold_resolution_rate(month2_holds, target_days=7)

        # Then: Month 2 should show improvement
        assert float(rate_m1) == 0.0   # Neither resolved in 7 days
        assert float(rate_m2) == 100.0  # Both resolved in 7 days

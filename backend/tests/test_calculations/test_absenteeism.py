"""
Test Suite for Absenteeism KPI (KPI #10)

Tests employee attendance/absenteeism calculations:
- Absenteeism Rate = (Hours Absent / Scheduled Hours) * 100
- Attendance Rate = (Days Present / Total Days) * 100
- Bradford Factor for absence pattern analysis

Covers:
- Basic absenteeism calculation
- Attendance rate tracking
- Chronic absentee identification
- Bradford Factor scoring
- Edge cases and boundary conditions
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock


# ===== Helper Functions for Standalone Calculations =====


def calculate_absenteeism_rate(hours_absent: float, scheduled_hours: float) -> float | None:
    """
    Calculate absenteeism rate as percentage.

    Formula: (Hours Absent / Scheduled Hours) * 100

    Args:
        hours_absent: Total hours of absence
        scheduled_hours: Total scheduled work hours

    Returns:
        Absenteeism rate percentage or None if invalid
    """
    if scheduled_hours <= 0:
        return None
    if hours_absent < 0:
        return None

    rate = (hours_absent / scheduled_hours) * 100
    return round(rate, 4)


def calculate_attendance_rate(days_present: int, total_days: int) -> float | None:
    """
    Calculate attendance rate as percentage.

    Formula: (Days Present / Total Scheduled Days) * 100

    Args:
        days_present: Number of days employee was present
        total_days: Total scheduled work days

    Returns:
        Attendance rate percentage or None if invalid
    """
    if total_days <= 0:
        return None
    if days_present < 0:
        return None
    if days_present > total_days:
        days_present = total_days  # Cap at 100%

    rate = (days_present / total_days) * 100
    return round(rate, 4)


def calculate_bradford_factor(spell_count: int, total_days_absent: int) -> int:
    """
    Calculate Bradford Factor score.

    Formula: S^2 * D
    Where S = number of spells (absence instances)
          D = total days of absence

    Interpretation:
    - 0-50: Low risk
    - 51-125: Monitor
    - 126-250: Formal action
    - 251+: Final warning/termination

    Args:
        spell_count: Number of separate absence instances
        total_days_absent: Total days of all absences

    Returns:
        Bradford Factor score
    """
    if spell_count < 0 or total_days_absent < 0:
        return 0

    return (spell_count**2) * total_days_absent


def count_absence_spells(absence_dates: list[date]) -> int:
    """
    Count number of absence spells (consecutive days count as 1 spell).

    Args:
        absence_dates: List of dates when employee was absent

    Returns:
        Number of separate absence spells
    """
    if not absence_dates:
        return 0

    # Sort dates
    sorted_dates = sorted(absence_dates)

    spells = 1
    for i in range(1, len(sorted_dates)):
        # If gap > 1 day, it's a new spell
        gap = (sorted_dates[i] - sorted_dates[i - 1]).days
        if gap > 1:
            spells += 1

    return spells


def interpret_bradford_factor(score: int) -> str:
    """
    Interpret Bradford Factor score.

    Args:
        score: Bradford Factor score

    Returns:
        Risk interpretation string
    """
    if score <= 50:
        return "Low risk"
    elif score <= 125:
        return "Monitor - pattern emerging"
    elif score <= 250:
        return "Formal action recommended"
    else:
        return "Final warning/termination level"


# ===== Test Classes =====


@pytest.mark.unit
class TestAbsenteeismRateCalculation:
    """Test basic absenteeism rate calculation"""

    @pytest.mark.unit
    def test_basic_absenteeism_calculation(self):
        """Test basic absenteeism with known values"""
        # Given: 2 hours absent, 40 hours scheduled (1 week)
        result = calculate_absenteeism_rate(hours_absent=2.0, scheduled_hours=40.0)

        # Then: (2 / 40) * 100 = 5%
        assert result == 5.0

    @pytest.mark.unit
    def test_zero_absenteeism(self):
        """Test perfect attendance (0% absenteeism)"""
        # Given: No absence
        result = calculate_absenteeism_rate(hours_absent=0.0, scheduled_hours=40.0)

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_full_absence(self):
        """Test complete absence (100% absenteeism)"""
        # Given: Full week absent
        result = calculate_absenteeism_rate(hours_absent=40.0, scheduled_hours=40.0)

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_half_day_absence(self):
        """Test half-day absence"""
        # Given: 4 hours absent from 8-hour day
        result = calculate_absenteeism_rate(hours_absent=4.0, scheduled_hours=8.0)

        # Then: Should be 50%
        assert result == 50.0

    @pytest.mark.unit
    def test_partial_hour_absence(self):
        """Test partial hour absence (late arrival)"""
        # Given: 30 minutes late (0.5 hours)
        result = calculate_absenteeism_rate(hours_absent=0.5, scheduled_hours=8.0)

        # Then: (0.5 / 8) * 100 = 6.25%
        assert result == 6.25

    @pytest.mark.unit
    def test_monthly_absenteeism(self):
        """Test monthly absenteeism calculation"""
        # Given: 8 hours absent in 160-hour month
        result = calculate_absenteeism_rate(hours_absent=8.0, scheduled_hours=160.0)

        # Then: (8 / 160) * 100 = 5%
        assert result == 5.0

    @pytest.mark.unit
    def test_industry_average_comparison(self):
        """Test against industry average (~3-5%)"""
        # Given: Industry average absenteeism
        result = calculate_absenteeism_rate(hours_absent=6.4, scheduled_hours=160.0)

        # Then: Should be 4% (within industry average)
        assert result == 4.0


@pytest.mark.unit
class TestAbsenteeismEdgeCases:
    """Test edge cases for absenteeism calculation"""

    @pytest.mark.unit
    def test_zero_scheduled_hours(self):
        """Test that zero scheduled hours returns None"""
        # Given: No scheduled time
        result = calculate_absenteeism_rate(hours_absent=0.0, scheduled_hours=0.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_negative_scheduled_hours(self):
        """Test that negative scheduled hours returns None"""
        # Given: Invalid negative scheduled time
        result = calculate_absenteeism_rate(hours_absent=2.0, scheduled_hours=-40.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_negative_absent_hours(self):
        """Test that negative absent hours returns None"""
        # Given: Invalid negative absence
        result = calculate_absenteeism_rate(hours_absent=-2.0, scheduled_hours=40.0)

        # Then: Should return None (invalid)
        assert result is None

    @pytest.mark.unit
    def test_over_100_percent_absenteeism(self):
        """Test when absent hours exceed scheduled (data error)"""
        # Given: More absent than scheduled (impossible but handle gracefully)
        result = calculate_absenteeism_rate(hours_absent=50.0, scheduled_hours=40.0)

        # Then: Should return >100% (indicates data error)
        assert result == 125.0

    @pytest.mark.unit
    def test_precision_rounding(self):
        """Test decimal precision in absenteeism"""
        # Given: Values producing repeating decimal
        result = calculate_absenteeism_rate(hours_absent=2.0, scheduled_hours=3.0)

        # Then: Should round to 4 decimal places
        # (2 / 3) * 100 = 66.6667%
        assert result == 66.6667


@pytest.mark.unit
class TestAttendanceRateCalculation:
    """Test attendance rate calculation"""

    @pytest.mark.unit
    def test_perfect_attendance(self):
        """Test perfect attendance (100%)"""
        # Given: Present every day
        result = calculate_attendance_rate(days_present=20, total_days=20)

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_90_percent_attendance(self):
        """Test 90% attendance"""
        # Given: 18 out of 20 days present
        result = calculate_attendance_rate(days_present=18, total_days=20)

        # Then: Should be 90%
        assert result == 90.0

    @pytest.mark.unit
    def test_low_attendance(self):
        """Test low attendance (chronic absentee)"""
        # Given: Only 15 out of 20 days present
        result = calculate_attendance_rate(days_present=15, total_days=20)

        # Then: Should be 75%
        assert result == 75.0

    @pytest.mark.unit
    def test_single_absence(self):
        """Test single day absence"""
        # Given: 1 day absent out of 5
        result = calculate_attendance_rate(days_present=4, total_days=5)

        # Then: Should be 80%
        assert result == 80.0

    @pytest.mark.unit
    def test_zero_attendance(self):
        """Test complete absence"""
        # Given: Never present
        result = calculate_attendance_rate(days_present=0, total_days=20)

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_invalid_zero_days(self):
        """Test with zero total days"""
        # Given: No scheduled days
        result = calculate_attendance_rate(days_present=0, total_days=0)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_present_exceeds_total(self):
        """Test when present exceeds total (data error)"""
        # Given: More present than scheduled (error)
        result = calculate_attendance_rate(days_present=25, total_days=20)

        # Then: Should cap at 100%
        assert result == 100.0


@pytest.mark.unit
class TestBradfordFactorCalculation:
    """Test Bradford Factor calculation"""

    @pytest.mark.unit
    def test_basic_bradford_factor(self):
        """Test basic Bradford Factor calculation"""
        # Given: 3 spells, 5 total days
        result = calculate_bradford_factor(spell_count=3, total_days_absent=5)

        # Then: 3^2 * 5 = 9 * 5 = 45
        assert result == 45

    @pytest.mark.unit
    def test_single_spell_many_days(self):
        """Test one long absence (low Bradford Factor)"""
        # Given: 1 spell of 10 days (single illness)
        result = calculate_bradford_factor(spell_count=1, total_days_absent=10)

        # Then: 1^2 * 10 = 1 * 10 = 10
        assert result == 10

    @pytest.mark.unit
    def test_many_spells_few_days(self):
        """Test many short absences (high Bradford Factor)"""
        # Given: 5 spells of 1 day each (pattern of single days off)
        result = calculate_bradford_factor(spell_count=5, total_days_absent=5)

        # Then: 5^2 * 5 = 25 * 5 = 125
        assert result == 125

    @pytest.mark.unit
    def test_no_absences(self):
        """Test zero absences"""
        # Given: No absences
        result = calculate_bradford_factor(spell_count=0, total_days_absent=0)

        # Then: Should be 0
        assert result == 0

    @pytest.mark.unit
    def test_high_bradford_critical(self):
        """Test critical Bradford Factor level"""
        # Given: 6 spells, 8 days total
        result = calculate_bradford_factor(spell_count=6, total_days_absent=8)

        # Then: 6^2 * 8 = 36 * 8 = 288
        assert result == 288


@pytest.mark.unit
class TestBradfordFactorInterpretation:
    """Test Bradford Factor interpretation"""

    @pytest.mark.unit
    def test_low_risk_interpretation(self):
        """Test low risk interpretation"""
        # Given: Score <= 50
        test_scores = [0, 25, 45, 50]

        for score in test_scores:
            result = interpret_bradford_factor(score)
            assert result == "Low risk"

    @pytest.mark.unit
    def test_monitor_interpretation(self):
        """Test monitor level interpretation"""
        # Given: Score 51-125
        test_scores = [51, 75, 100, 125]

        for score in test_scores:
            result = interpret_bradford_factor(score)
            assert result == "Monitor - pattern emerging"

    @pytest.mark.unit
    def test_formal_action_interpretation(self):
        """Test formal action level interpretation"""
        # Given: Score 126-250
        test_scores = [126, 175, 200, 250]

        for score in test_scores:
            result = interpret_bradford_factor(score)
            assert result == "Formal action recommended"

    @pytest.mark.unit
    def test_critical_interpretation(self):
        """Test critical level interpretation"""
        # Given: Score > 250
        test_scores = [251, 300, 500, 1000]

        for score in test_scores:
            result = interpret_bradford_factor(score)
            assert result == "Final warning/termination level"


@pytest.mark.unit
class TestAbsenceSpellCounting:
    """Test counting of absence spells"""

    @pytest.mark.unit
    def test_single_day_spells(self):
        """Test counting single-day absences as separate spells"""
        # Given: Separate single-day absences
        absences = [
            date(2024, 1, 5),  # Friday
            date(2024, 1, 10),  # Wednesday
            date(2024, 1, 15),  # Monday
        ]

        # When: Count spells
        result = count_absence_spells(absences)

        # Then: Should be 3 spells
        assert result == 3

    @pytest.mark.unit
    def test_consecutive_days_single_spell(self):
        """Test consecutive days count as one spell"""
        # Given: Three consecutive days absent
        absences = [
            date(2024, 1, 15),  # Monday
            date(2024, 1, 16),  # Tuesday
            date(2024, 1, 17),  # Wednesday
        ]

        # When: Count spells
        result = count_absence_spells(absences)

        # Then: Should be 1 spell
        assert result == 1

    @pytest.mark.unit
    def test_mixed_spells(self):
        """Test mix of single and consecutive absences"""
        # Given: Mixed pattern
        absences = [
            date(2024, 1, 5),  # Single day (spell 1)
            date(2024, 1, 10),  # Start of 3-day (spell 2)
            date(2024, 1, 11),
            date(2024, 1, 12),
            date(2024, 1, 20),  # Single day (spell 3)
        ]

        # When: Count spells
        result = count_absence_spells(absences)

        # Then: Should be 3 spells
        assert result == 3

    @pytest.mark.unit
    def test_no_absences(self):
        """Test empty absence list"""
        # Given: No absences
        absences = []

        # When: Count spells
        result = count_absence_spells(absences)

        # Then: Should be 0
        assert result == 0

    @pytest.mark.unit
    def test_unsorted_dates(self):
        """Test that unsorted dates are handled correctly"""
        # Given: Unsorted consecutive dates
        absences = [
            date(2024, 1, 17),
            date(2024, 1, 15),
            date(2024, 1, 16),
        ]

        # When: Count spells
        result = count_absence_spells(absences)

        # Then: Should still count as 1 spell
        assert result == 1


@pytest.mark.unit
class TestAbsenteeismBusinessScenarios:
    """Test real-world absenteeism scenarios"""

    @pytest.mark.unit
    def test_quarterly_absenteeism_report(self):
        """Test quarterly absenteeism calculation"""
        # Given: Quarter with 65 working days, 8-hour shifts
        scheduled_hours = 65 * 8  # 520 hours
        absent_hours = 24  # 3 days absent

        # When: Calculate rate
        rate = calculate_absenteeism_rate(absent_hours, scheduled_hours)

        # Then: Should be ~4.6% (acceptable for most industries)
        assert rate == pytest.approx(4.62, rel=0.01)

    @pytest.mark.unit
    def test_chronic_absentee_identification(self):
        """Test identifying chronic absentee (>10% rate)"""
        # Given: High absenteeism
        scheduled_hours = 160.0  # 1 month
        absent_hours = 20.0  # 2.5 days

        # When: Calculate rate
        rate = calculate_absenteeism_rate(absent_hours, scheduled_hours)

        # Then: Should identify as chronic (>10%)
        assert rate == 12.5
        assert rate > 10.0  # Chronic threshold

    @pytest.mark.unit
    def test_team_absenteeism_summary(self):
        """Test calculating team absenteeism average"""
        # Given: Team of 5 employees
        team_data = [
            {"hours_absent": 4.0, "scheduled": 160.0},  # 2.5%
            {"hours_absent": 8.0, "scheduled": 160.0},  # 5%
            {"hours_absent": 2.0, "scheduled": 160.0},  # 1.25%
            {"hours_absent": 0.0, "scheduled": 160.0},  # 0%
            {"hours_absent": 16.0, "scheduled": 160.0},  # 10%
        ]

        # When: Calculate individual rates
        rates = [calculate_absenteeism_rate(e["hours_absent"], e["scheduled"]) for e in team_data]

        # Then: Calculate team average
        avg_rate = sum(rates) / len(rates)
        assert avg_rate == pytest.approx(3.75, rel=0.01)

    @pytest.mark.unit
    def test_bradford_factor_comparison(self):
        """Test comparing two employees with same total days"""
        # Employee A: One long illness (1 spell, 5 days)
        emp_a_bradford = calculate_bradford_factor(1, 5)

        # Employee B: Five single-day absences (5 spells, 5 days)
        emp_b_bradford = calculate_bradford_factor(5, 5)

        # Then: Employee B has much higher Bradford Factor
        assert emp_a_bradford == 5  # 1^2 * 5 = 5
        assert emp_b_bradford == 125  # 5^2 * 5 = 125

        # Employee B is 25x higher risk despite same total days
        assert emp_b_bradford / emp_a_bradford == 25

    @pytest.mark.unit
    def test_seasonal_absenteeism_pattern(self):
        """Test seasonal variation in absenteeism"""
        # Given: Winter months typically have higher absenteeism
        winter_rate = calculate_absenteeism_rate(12.0, 160.0)  # 7.5%
        summer_rate = calculate_absenteeism_rate(5.0, 160.0)  # 3.125%

        # Then: Winter should be higher
        assert winter_rate > summer_rate
        assert winter_rate == 7.5
        assert summer_rate == 3.125

    @pytest.mark.unit
    def test_cost_of_absenteeism(self):
        """Test estimating cost impact of absenteeism"""
        # Given: Absenteeism rate and cost assumptions
        scheduled_hours = 160.0
        absent_hours = 8.0
        hourly_rate = 25.0  # $25/hour

        # When: Calculate absenteeism rate and cost
        rate = calculate_absenteeism_rate(absent_hours, scheduled_hours)
        direct_cost = absent_hours * hourly_rate
        indirect_cost = direct_cost * 1.5  # 1.5x indirect costs
        total_cost = direct_cost + indirect_cost

        # Then: Calculate totals
        assert rate == 5.0
        assert direct_cost == 200.0
        assert indirect_cost == 300.0
        assert total_cost == 500.0

    @pytest.mark.unit
    def test_absenteeism_trend_improvement(self):
        """Test absenteeism improvement over time"""
        # Given: Monthly rates showing improvement
        month1 = calculate_absenteeism_rate(16.0, 160.0)  # 10%
        month2 = calculate_absenteeism_rate(12.0, 160.0)  # 7.5%
        month3 = calculate_absenteeism_rate(8.0, 160.0)  # 5%
        month4 = calculate_absenteeism_rate(4.8, 160.0)  # 3%

        # Then: Should show progressive improvement
        assert month1 > month2 > month3 > month4
        improvement = ((month1 - month4) / month1) * 100
        assert improvement == 70.0  # 70% improvement


@pytest.mark.unit
class TestAbsenteeismThresholds:
    """Test absenteeism threshold categorization"""

    @pytest.mark.unit
    def test_excellent_absenteeism(self):
        """Test excellent absenteeism (<2%)"""
        result = calculate_absenteeism_rate(2.0, 160.0)
        assert result == 1.25
        assert result < 2.0

    @pytest.mark.unit
    def test_good_absenteeism(self):
        """Test good absenteeism (2-4%)"""
        result = calculate_absenteeism_rate(5.0, 160.0)
        assert result == 3.125
        assert 2.0 <= result < 4.0

    @pytest.mark.unit
    def test_average_absenteeism(self):
        """Test average absenteeism (4-6%)"""
        result = calculate_absenteeism_rate(8.0, 160.0)
        assert result == 5.0
        assert 4.0 <= result < 6.0

    @pytest.mark.unit
    def test_concerning_absenteeism(self):
        """Test concerning absenteeism (6-10%)"""
        result = calculate_absenteeism_rate(12.0, 160.0)
        assert result == 7.5
        assert 6.0 <= result < 10.0

    @pytest.mark.unit
    def test_critical_absenteeism(self):
        """Test critical absenteeism (>10%)"""
        result = calculate_absenteeism_rate(20.0, 160.0)
        assert result == 12.5
        assert result >= 10.0

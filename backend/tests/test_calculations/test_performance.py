"""
Test Suite for Performance KPI (KPI #9)

Tests performance calculation formula:
Performance = (Ideal Cycle Time × Units) / Run Time × 100

Covers:
- Basic calculation with known inputs
- Edge cases (zero runtime, downtime)
- OEE integration scenarios
- Machine speed vs. ideal speed
"""
import pytest
from decimal import Decimal

from calculations.performance import (
    calculate_performance,
    update_performance_for_entry,
)


class TestPerformanceCalculation:
    """Test performance calculation with known inputs/outputs"""

    def test_basic_performance_calculation(self, expected_performance):
        """Test basic performance with standard values"""
        # Given: 1000 units, 0.01 hr cycle time, 8 hrs runtime
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Should calculate 125% performance
        # (0.01 × 1000) / 8.0 × 100 = 10 / 8 × 100 = 125%
        assert result == expected_performance
        assert result == 125.0

    def test_perfect_performance_100_percent(self):
        """Test scenario achieving exactly 100% performance"""
        # Given: Production exactly matches ideal cycle time
        result = calculate_performance(
            units_produced=800,
            ideal_cycle_time=0.01,  # 36 seconds per unit
            run_time_hours=8.0
        )

        # Then: (0.01 × 800) / 8.0 × 100 = 8 / 8 × 100 = 100%
        assert result == 100.0

    def test_low_performance_scenario(self):
        """Test scenario with low performance (slow production)"""
        # Given: Low production rate
        result = calculate_performance(
            units_produced=500,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: (0.01 × 500) / 8.0 × 100 = 5 / 8 × 100 = 62.5%
        assert result == 62.5

    def test_high_performance_scenario(self):
        """Test scenario with high performance (faster than ideal)"""
        # Given: Production faster than ideal
        result = calculate_performance(
            units_produced=2000,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: (0.01 × 2000) / 8.0 × 100 = 20 / 8 × 100 = 250%
        assert result == 250.0

    def test_performance_as_ratio(self):
        """Test performance returned as ratio instead of percentage"""
        # Given: Same scenario, but ratio format
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=8.0,
            as_percentage=False
        )

        # Then: Should return 1.25 (125% as ratio)
        assert result == 1.25

    def test_zero_production(self):
        """Test performance with zero units (line stopped)"""
        # Given: No production during runtime
        result = calculate_performance(
            units_produced=0,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Performance should be 0%
        assert result == 0.0

    def test_invalid_zero_runtime(self):
        """Test that zero runtime returns None"""
        # Given: Invalid zero runtime
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=0
        )

        # Then: Should return None (invalid)
        assert result is None

    def test_invalid_negative_runtime(self):
        """Test that negative runtime returns None"""
        # Given: Invalid negative runtime
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=-5.0
        )

        # Then: Should return None (invalid)
        assert result is None

    def test_invalid_negative_units(self):
        """Test that negative units returns None"""
        # Given: Invalid negative units
        result = calculate_performance(
            units_produced=-100,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Should return None (invalid)
        assert result is None


class TestPerformanceVsEfficiency:
    """Test difference between Performance and Efficiency KPIs"""

    def test_performance_uses_runtime_not_scheduled(self):
        """
        CRITICAL TEST: Performance uses ACTUAL runtime, not scheduled hours
        This is the key difference from Efficiency
        """
        # Given: Line ran only 6 hours (2 hours downtime)
        performance = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=6.0  # ACTUAL runtime
        )

        # Then: (0.01 × 1000) / 6.0 × 100 = 10 / 6 × 100 = 166.67%
        # Higher because less time was used
        assert performance == pytest.approx(166.67, rel=0.01)

    def test_performance_measures_machine_speed(self):
        """Performance measures how fast the machine ran, not workforce efficiency"""
        # Scenario 1: Slow machine operation
        slow_performance = calculate_performance(
            units_produced=600,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Scenario 2: Fast machine operation
        fast_performance = calculate_performance(
            units_produced=1200,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Fast performance should be double slow performance
        assert fast_performance == 2 * slow_performance
        assert slow_performance == 75.0
        assert fast_performance == 150.0


class TestPerformanceEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_very_fast_cycle_time(self):
        """Test with very fast cycle time (seconds)"""
        # Given: 5 second cycle time = 0.00139 hours
        result = calculate_performance(
            units_produced=20000,
            ideal_cycle_time=0.00139,
            run_time_hours=8.0
        )

        # Then: (0.00139 × 20000) / 8.0 × 100 = 27.8 / 8 × 100 = 347.5%
        assert result == pytest.approx(347.5, rel=0.1)

    def test_very_slow_cycle_time(self):
        """Test with very slow cycle time (hours)"""
        # Given: 1 hour cycle time (complex assembly)
        result = calculate_performance(
            units_produced=10,
            ideal_cycle_time=1.0,
            run_time_hours=8.0
        )

        # Then: (1.0 × 10) / 8.0 × 100 = 10 / 8 × 100 = 125%
        assert result == 125.0

    def test_very_short_runtime(self):
        """Test with very short runtime period"""
        # Given: 30 minute runtime = 0.5 hours
        result = calculate_performance(
            units_produced=100,
            ideal_cycle_time=0.005,  # 18 seconds
            run_time_hours=0.5
        )

        # Then: (0.005 × 100) / 0.5 × 100 = 0.5 / 0.5 × 100 = 100%
        assert result == 100.0

    def test_decimal_precision(self):
        """Test that performance is calculated with proper precision"""
        # Given: Values that result in repeating decimal
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=6.0
        )

        # Then: Should round to 4 decimal places
        # (0.01 × 1000) / 6.0 × 100 = 166.6667%
        assert result == 166.6667


class TestPerformanceBusinessScenarios:
    """Test real-world business scenarios"""

    def test_machine_running_faster_than_standard(self):
        """Test when machine operates faster than standard cycle time"""
        # Given: Machine running at 150% of standard speed
        result = calculate_performance(
            units_produced=1200,  # 50% more than standard
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Performance should be 150%
        assert result == 150.0

    def test_machine_running_slower_than_standard(self):
        """Test when machine operates slower than standard cycle time"""
        # Given: Machine running at 75% of standard speed
        result = calculate_performance(
            units_produced=600,  # 25% less than standard
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Performance should be 75%
        assert result == 75.0

    def test_performance_with_micro_stops(self):
        """Test performance accounting for minor stoppages"""
        # Given: Total shift time vs. actual runtime
        # 8 hour shift, but only 7.5 hours actual runtime (micro-stops)
        result = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=7.5  # Actual runtime after micro-stops
        )

        # Then: (0.01 × 1000) / 7.5 × 100 = 133.33%
        assert result == pytest.approx(133.33, rel=0.01)

    def test_batch_changeover_impact(self):
        """Test performance during batch changeovers"""
        # Given: Reduced runtime due to changeover
        result = calculate_performance(
            units_produced=700,  # Reduced due to changeover
            ideal_cycle_time=0.01,
            run_time_hours=6.0  # 2 hours for changeover
        )

        # Then: (0.01 × 700) / 6.0 × 100 = 116.67%
        assert result == pytest.approx(116.67, rel=0.01)

    def test_multi_product_average_performance(self):
        """Test calculating average performance across products"""
        # Given: Multiple products with different cycle times
        product_a_perf = calculate_performance(500, 0.01, 4.0)
        product_b_perf = calculate_performance(1000, 0.005, 4.0)

        # Then: Calculate weighted average
        # Product A: (0.01 × 500) / 4.0 × 100 = 125%
        # Product B: (0.005 × 1000) / 4.0 × 100 = 125%
        assert product_a_perf == 125.0
        assert product_b_perf == 125.0

        avg_performance = (product_a_perf + product_b_perf) / 2
        assert avg_performance == 125.0


class TestPerformanceOEEIntegration:
    """Test performance as part of OEE (Overall Equipment Effectiveness)"""

    def test_performance_component_of_oee(self):
        """
        OEE = Availability × Performance × Quality
        Test that performance integrates correctly with OEE
        """
        # Given: Performance calculation
        performance_pct = calculate_performance(
            units_produced=1000,
            ideal_cycle_time=0.01,
            run_time_hours=8.0,
            as_percentage=False  # Get as ratio for OEE
        )

        # Given: Mock availability and quality
        availability = 0.95  # 95% uptime
        quality = 0.98  # 98% good units

        # Then: Calculate OEE
        oee = availability * performance_pct * quality

        # OEE = 0.95 × 1.25 × 0.98 = 1.16375 (116.375%)
        # High OEE indicates excellent overall performance
        assert oee == pytest.approx(1.164, rel=0.01)

    def test_world_class_performance_target(self):
        """Test against world-class performance target (≥95%)"""
        # Given: Production achieving world-class target
        result = calculate_performance(
            units_produced=760,  # Optimized for 95%
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Should achieve 95% performance
        assert result == 95.0

    def test_performance_below_acceptable_threshold(self):
        """Test identifying performance below acceptable threshold"""
        # Given: Poor performance (< 60%)
        result = calculate_performance(
            units_produced=400,
            ideal_cycle_time=0.01,
            run_time_hours=8.0
        )

        # Then: Should be flagged as requiring intervention
        assert result == 50.0
        assert result < 60.0  # Below acceptable threshold

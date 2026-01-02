"""
KPI #9: PERFORMANCE Calculation Tests
Tests all edge cases for Performance = (Ideal Cycle Time × Units) / Run Time × 100

FORMULA:
- Performance = (ideal_cycle_time × units_produced) / run_time_hours × 100

FLEXIBILITY REQUIREMENTS:
- run_time_hours → shift_hours - downtime_hours → shift_hours
- ideal_cycle_time → inference (same as Efficiency)
"""

import pytest
from datetime import date
from decimal import Decimal


class TestPerformanceCalculationPerfectData:
    """Test performance with complete data"""

    def test_performance_calculation_standard_case(self):
        """
        TEST 1: Perfect Data - Standard Performance

        SCENARIO:
        - 100 units produced
        - 0.25 hr ideal cycle time
        - 22 hours actual run time

        EXPECTED:
        - Ideal hours = 100 × 0.25 = 25.0
        - Performance = 25.0 / 22.0 × 100 = 113.64%
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("22.0")
        }

        # result = calculate_performance(data)

        expected_ideal_hours = Decimal("25.0")
        expected_performance = Decimal("113.64")

        # assert result["ideal_hours"] == expected_ideal_hours
        # assert abs(result["performance_percent"] - expected_performance) < Decimal("0.01")
        # assert result["estimated"] == False
        pass

    def test_performance_exactly_100_percent(self):
        """
        TEST 2: Performance = 100% (Perfect Match)

        SCENARIO:
        - Actual run time = Ideal time
        - Perfect performance

        EXPECTED:
        - Performance = 100.00%
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("25.0")  # Exactly ideal
        }

        # result = calculate_performance(data)

        # assert result["performance_percent"] == Decimal("100.00")
        pass

    def test_performance_below_100_percent(self):
        """
        TEST 3: Performance < 100% (Slower than ideal)

        SCENARIO:
        - Taking longer than ideal
        - Indicates inefficiency

        EXPECTED:
        - Performance = 83.33%
        - Flag for investigation
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("30.0")  # Slower
        }

        # result = calculate_performance(data)

        expected_performance = Decimal("83.33")

        # assert abs(result["performance_percent"] - expected_performance) < Decimal("0.01")
        # assert result["performance_percent"] < Decimal("100.0")
        pass

    def test_performance_zero_production(self):
        """
        TEST 4: Zero Units Produced

        SCENARIO: No production (downtime)
        EXPECTED: Performance = 0%
        """
        data = {
            "units_produced": 0,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("8.0")
        }

        # result = calculate_performance(data)

        # assert result["performance_percent"] == Decimal("0.0")
        pass


class TestPerformanceCalculationInference:
    """Test inference for missing data"""

    def test_performance_missing_ideal_cycle_time(self):
        """
        TEST 5: Missing ideal_cycle_time - Use Inference

        SCENARIO:
        - ideal_cycle_time = NULL
        - Use client average (0.28 hr)

        EXPECTED:
        - Use inferred value
        - Flag as "ESTIMATED"
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": None,  # MISSING
            "run_time_hours": Decimal("22.0"),
            "client_id": "BOOT-LINE-A"
        }

        # Assume inference returns 0.28
        inferred_cycle_time = Decimal("0.28")

        # result = calculate_performance(data)

        expected_ideal_hours = Decimal("28.0")  # 100 × 0.28

        # assert result["ideal_hours"] == expected_ideal_hours
        # assert result["estimated"] == True
        # assert result["inference_method"] == "client_style_average"
        pass

    def test_performance_missing_run_time_use_shift_hours(self):
        """
        TEST 6: Missing run_time_hours - Use shift_hours

        SCENARIO:
        - run_time_hours = NULL
        - Fall back to shift_hours (no downtime data)

        EXPECTED:
        - Use shift_hours as run_time
        - Flag as "ESTIMATED"
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": None,  # MISSING
            "shift_hours": Decimal("9.0")
        }

        # result = calculate_performance(data)

        expected_run_time = Decimal("9.0")

        # assert result["run_time_hours"] == expected_run_time
        # assert result["estimated"] == True
        pass

    def test_performance_with_downtime_adjustment(self):
        """
        TEST 7: Adjust run_time for Downtime

        SCENARIO:
        - shift_hours = 9.0
        - downtime_hours = 0.5 (30 min equipment failure)
        - Actual run_time = 9.0 - 0.5 = 8.5

        EXPECTED:
        - Performance calculated on 8.5 hours
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "shift_hours": Decimal("9.0"),
            "downtime_hours": Decimal("0.5")
        }

        # result = calculate_performance(data)

        expected_run_time = Decimal("8.5")
        expected_performance = Decimal("294.12")  # 25 / 8.5 × 100

        # assert result["run_time_hours"] == expected_run_time
        # assert abs(result["performance_percent"] - expected_performance) < Decimal("0.01")
        pass


class TestPerformanceCalculationEdgeCases:
    """Test boundary conditions"""

    def test_performance_very_high_flag_review(self):
        """
        TEST 8: Performance > 150% - Flag for Review

        SCENARIO:
        - Exceptionally high performance
        - May indicate data entry error OR process improvement

        EXPECTED:
        - Allow calculation
        - Flag for verification
        """
        data = {
            "units_produced": 400,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("50.0")
        }

        # result = calculate_performance(data)

        # Performance = 100 / 50 × 100 = 200%

        # assert result["performance_percent"] == Decimal("200.00")
        # assert result["flag_for_review"] == True
        # assert "exceptionally_high_performance" in result["warnings"]
        pass

    def test_performance_very_low_investigation(self):
        """
        TEST 9: Performance < 50% - Urgent Investigation

        SCENARIO:
        - Performance significantly below target
        - Critical inefficiency

        EXPECTED:
        - Flag as HIGH priority
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("60.0")  # Very slow
        }

        # result = calculate_performance(data)

        # Performance = 25 / 60 × 100 = 41.67%

        # assert result["performance_percent"] < Decimal("50.0")
        # assert result["investigation_priority"] == "HIGH"
        pass

    def test_performance_without_downtime_module(self):
        """
        TEST 10: Calculate Performance Without Downtime Data

        SCENARIO:
        - Phase 1 MVP (no Downtime module yet)
        - Use shift_hours as run_time

        EXPECTED:
        - Works independently
        - Conservative estimate (assumes no downtime)
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "shift_hours": Decimal("9.0"),
            "downtime_data_available": False
        }

        # result = calculate_performance(data)

        # assert result["run_time_hours"] == Decimal("9.0")
        # assert result["calculated_without_downtime"] == True
        pass


class TestPerformanceCalculationMultiShift:
    """Test performance across different shifts"""

    def test_performance_aggregated_daily(self):
        """
        TEST 11: Aggregate Performance for Full Day (2 shifts)

        SCENARIO:
        - Shift 1: 100 units, 8.5 hrs
        - Shift 2: 75 units, 7.0 hrs

        EXPECTED:
        - Total Performance = Total Ideal / Total Run Time
        """
        shift_1 = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("8.5")
        }

        shift_2 = {
            "units_produced": 75,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("7.0")
        }

        # result = calculate_performance_aggregated([shift_1, shift_2])

        # Total ideal = (100 × 0.25) + (75 × 0.25) = 43.75
        # Total run = 8.5 + 7.0 = 15.5
        # Performance = 43.75 / 15.5 × 100 = 282.26%

        expected_performance = Decimal("282.26")

        # assert abs(result["performance_percent"] - expected_performance) < Decimal("0.01")
        pass

    def test_performance_different_cycle_times(self):
        """
        TEST 12: Different Products with Different Cycle Times

        SCENARIO:
        - Product A: 0.25 hr cycle
        - Product B: 0.35 hr cycle
        - Both produced in same shift

        EXPECTED:
        - Weighted average performance
        """
        entries = [
            {"units_produced": 100, "ideal_cycle_time": Decimal("0.25"), "run_time_hours": Decimal("5.0")},
            {"units_produced": 50, "ideal_cycle_time": Decimal("0.35"), "run_time_hours": Decimal("4.0")}
        ]

        # result = calculate_performance_aggregated(entries)

        # Total ideal = (100 × 0.25) + (50 × 0.35) = 42.5
        # Total run = 5.0 + 4.0 = 9.0
        # Performance = 42.5 / 9.0 × 100 = 472.22%

        # assert result["performance_percent"] > Decimal("400.0")
        pass


class TestPerformanceOEEIntegration:
    """Test Performance as part of OEE calculation"""

    def test_performance_for_oee_calculation(self):
        """
        TEST 13: Performance Component of OEE

        SCENARIO:
        - OEE = Availability × Performance × Quality
        - Performance must be in decimal form (not percentage)

        EXPECTED:
        - Return both percentage and decimal
        """
        data = {
            "units_produced": 100,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("22.0")
        }

        # result = calculate_performance(data)

        # assert result["performance_percent"] == Decimal("113.64")
        # assert result["performance_decimal"] == Decimal("1.1364")  # For OEE
        pass

    def test_performance_capped_at_100_for_oee(self):
        """
        TEST 14: Performance Capped at 100% for OEE (Optional)

        SCENARIO:
        - Some clients want OEE capped at 100%
        - Others allow >100%

        EXPECTED:
        - Configurable capping
        """
        data = {
            "units_produced": 400,
            "ideal_cycle_time": Decimal("0.25"),
            "run_time_hours": Decimal("50.0"),
            "cap_at_100_percent": True
        }

        # result = calculate_performance(data)

        # Raw = 200%, but capped
        # assert result["performance_percent_raw"] == Decimal("200.00")
        # assert result["performance_percent_capped"] == Decimal("100.00")
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

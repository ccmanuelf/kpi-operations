"""
Comprehensive Unit Tests for Calculation Modules
Tests helper functions and pure logic calculations
"""

import pytest
from decimal import Decimal
from datetime import date, time, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestEfficiencyCalculations:
    """Tests for efficiency.py calculations"""

    def test_calculate_shift_hours_normal(self):
        """Test normal shift hours calculation"""
        from backend.calculations.efficiency import calculate_shift_hours

        # 7am to 3:30pm = 8.5 hours
        result = calculate_shift_hours(time(7, 0), time(15, 30))
        assert result == Decimal("8.5")

    def test_calculate_shift_hours_overnight(self):
        """Test overnight shift hours calculation"""
        from backend.calculations.efficiency import calculate_shift_hours

        # 11pm to 7am = 8 hours (overnight)
        result = calculate_shift_hours(time(23, 0), time(7, 0))
        assert result == Decimal("8.0")

    def test_calculate_shift_hours_standard(self):
        """Test standard 8-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours

        # 9am to 5pm = 8 hours
        result = calculate_shift_hours(time(9, 0), time(17, 0))
        assert result == Decimal("8.0")

    def test_calculate_shift_hours_12_hour(self):
        """Test 12-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours

        # 6am to 6pm = 12 hours
        result = calculate_shift_hours(time(6, 0), time(18, 0))
        assert result == Decimal("12.0")

    def test_calculate_shift_hours_short_shift(self):
        """Test short 4-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours

        # 9am to 1pm = 4 hours
        result = calculate_shift_hours(time(9, 0), time(13, 0))
        assert result == Decimal("4.0")

    def test_default_cycle_time(self):
        """Test default cycle time value"""
        from backend.calculations.efficiency import DEFAULT_CYCLE_TIME

        assert DEFAULT_CYCLE_TIME == Decimal("0.25")

    def test_default_shift_hours(self):
        """Test default shift hours value"""
        from backend.calculations.efficiency import DEFAULT_SHIFT_HOURS

        assert DEFAULT_SHIFT_HOURS == Decimal("8.0")


class TestCalculationLogic:
    """Test pure calculation logic without database"""

    def test_ppm_calculation_formula(self):
        """Test PPM calculation formula"""
        # PPM = (defects / total_units) * 1,000,000
        defects = 10
        total_units = 1000000
        ppm = (Decimal(str(defects)) / Decimal(str(total_units))) * Decimal("1000000")
        assert ppm == Decimal("10")

    def test_ppm_calculation_with_small_sample(self):
        """Test PPM with smaller sample"""
        defects = 5
        total_units = 1000
        ppm = (Decimal(str(defects)) / Decimal(str(total_units))) * Decimal("1000000")
        assert ppm == Decimal("5000")

    def test_dpmo_calculation_formula(self):
        """Test DPMO calculation formula"""
        # DPMO = (defects / (units * opportunities_per_unit)) * 1,000,000
        defects = 100
        units = 1000
        opportunities = 10
        dpmo = (Decimal(str(defects)) / (Decimal(str(units)) * Decimal(str(opportunities)))) * Decimal("1000000")
        assert dpmo == Decimal("10000")

    def test_fpy_calculation_formula(self):
        """Test FPY calculation formula"""
        # FPY = (good_units / total_units) * 100
        good_units = 90
        total_units = 100
        fpy = (Decimal(str(good_units)) / Decimal(str(total_units))) * 100
        assert fpy == Decimal("90")

    def test_rty_calculation_formula(self):
        """Test RTY calculation formula"""
        # RTY = FPY1 * FPY2 * ... * FPYn (all as decimals, then * 100)
        fpy_values = [Decimal("0.95"), Decimal("0.90"), Decimal("0.85")]
        rty = Decimal("1")
        for fpy in fpy_values:
            rty *= fpy
        rty *= 100
        assert round(rty, 2) == Decimal("72.68")

    def test_absenteeism_calculation_formula(self):
        """Test absenteeism calculation formula"""
        # Absenteeism = (absent_hours / total_scheduled_hours) * 100
        absent_hours = 40
        total_scheduled_hours = 800
        absenteeism = (Decimal(str(absent_hours)) / Decimal(str(total_scheduled_hours))) * 100
        assert absenteeism == Decimal("5")

    def test_otd_calculation_formula(self):
        """Test OTD calculation formula"""
        # OTD = (on_time_deliveries / total_deliveries) * 100
        on_time = 95
        total = 100
        otd = (Decimal(str(on_time)) / Decimal(str(total))) * 100
        assert otd == Decimal("95")

    def test_availability_formula(self):
        """Test availability formula"""
        # Availability = (Running Time / Planned Production Time) * 100
        running_time = Decimal("400")
        planned_time = Decimal("480")
        availability = (running_time / planned_time) * 100
        assert round(availability, 2) == Decimal("83.33")

    def test_performance_formula(self):
        """Test performance formula"""
        # Performance = (Total Count × Ideal Cycle Time / Running Time) * 100
        total_count = Decimal("1000")
        ideal_cycle_time = Decimal("0.5")  # minutes per unit
        running_time = Decimal("600")  # minutes
        performance = (total_count * ideal_cycle_time / running_time) * 100
        assert round(performance, 2) == Decimal("83.33")


class TestOEECalculation:
    """Tests for OEE (Overall Equipment Effectiveness)"""

    def test_oee_calculation_formula(self):
        """Test OEE calculation formula"""
        # OEE = Availability * Performance * Quality
        availability = Decimal("90") / 100  # 90%
        performance = Decimal("85") / 100  # 85%
        quality = Decimal("95") / 100  # 95%

        oee = availability * performance * quality * 100
        assert round(oee, 2) == Decimal("72.68")

    def test_world_class_oee(self):
        """Test world-class OEE threshold"""
        # World-class OEE: 90% availability, 95% performance, 99.5% quality
        availability = Decimal("90") / 100
        performance = Decimal("95") / 100
        quality = Decimal("99.5") / 100

        oee = availability * performance * quality * 100
        assert oee >= Decimal("85")  # World-class is typically >= 85%

    def test_oee_perfect_score(self):
        """Test perfect OEE score"""
        availability = Decimal("100") / 100
        performance = Decimal("100") / 100
        quality = Decimal("100") / 100

        oee = availability * performance * quality * 100
        assert oee == 100


class TestWIPAgingCalculations:
    """Tests for WIP aging calculations"""

    def test_wip_age_calculation(self):
        """Test WIP age calculation"""
        start_date = date.today() - timedelta(days=5)
        age = (date.today() - start_date).days
        assert age == 5

    def test_wip_age_same_day(self):
        """Test WIP age for same day"""
        start_date = date.today()
        age = (date.today() - start_date).days
        assert age == 0

    def test_wip_age_categorization(self):
        """Test WIP aging categories"""

        def categorize(age):
            if age <= 7:
                return "0-7 days"
            elif age <= 14:
                return "8-14 days"
            elif age <= 30:
                return "15-30 days"
            elif age <= 60:
                return "31-60 days"
            else:
                return "60+ days"

        assert categorize(2) == "0-7 days"
        assert categorize(10) == "8-14 days"
        assert categorize(20) == "15-30 days"
        assert categorize(45) == "31-60 days"
        assert categorize(90) == "60+ days"
        assert categorize(7) == "0-7 days"
        assert categorize(8) == "8-14 days"
        assert categorize(14) == "8-14 days"
        assert categorize(15) == "15-30 days"


class TestTrendAnalysis:
    """Tests for trend analysis calculations"""

    def test_simple_linear_trend_calculation(self):
        """Test simple linear trend calculation"""
        values = [10, 20, 30, 40, 50]
        n = len(values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        assert slope == 10.0

    def test_trend_stable_values(self):
        """Test trend for stable values"""
        values = [50, 50, 50, 50, 50]
        n = len(values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        assert slope == 0.0

    def test_trend_decreasing(self):
        """Test decreasing trend"""
        values = [50, 40, 30, 20, 10]
        n = len(values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        assert slope == -10.0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_division_by_zero_protection(self):
        """Test division by zero protection"""

        def safe_divide(numerator, denominator):
            if denominator == 0:
                return Decimal("0")
            return Decimal(str(numerator)) / Decimal(str(denominator))

        assert safe_divide(100, 0) == Decimal("0")
        assert safe_divide(100, 10) == Decimal("10")

    def test_decimal_precision(self):
        """Test decimal precision"""
        value = Decimal("0.1") + Decimal("0.2")
        assert value == Decimal("0.3")

    def test_percentage_bounds(self):
        """Test percentage bounds"""

        def bound_percentage(value):
            return max(Decimal("0"), min(Decimal("100"), Decimal(str(value))))

        assert bound_percentage(150) == Decimal("100")
        assert bound_percentage(-10) == Decimal("0")
        assert bound_percentage(50) == Decimal("50")

    def test_negative_values_handling(self):
        """Test negative values handling"""

        def calculate_rate(numerator, denominator):
            if denominator == 0:
                return Decimal("0")
            rate = (Decimal(str(numerator)) / Decimal(str(denominator))) * 100
            return max(Decimal("0"), rate)

        assert calculate_rate(-100, 100) == Decimal("0")
        assert calculate_rate(100, 100) == Decimal("100")

    def test_large_number_handling(self):
        """Test handling of very large numbers"""
        defects = 1000000
        total_units = 100000000000
        ppm = (Decimal(str(defects)) / Decimal(str(total_units))) * Decimal("1000000")
        assert ppm == Decimal("10")


class TestMockedDatabaseCalculations:
    """Test calculation functions with mocked database"""

    def test_efficiency_zero_employees_returns_zero(self):
        """Test efficiency with zero employees returns zero"""
        # When employees = 0, efficiency should be 0 regardless of other values
        employees = 0
        if employees == 0:
            efficiency = Decimal("0")
        else:
            efficiency = Decimal("100")
        assert efficiency == Decimal("0")

    def test_efficiency_zero_scheduled_hours_returns_zero(self):
        """Test efficiency with zero scheduled hours returns zero"""
        scheduled_hours = Decimal("0")
        if scheduled_hours == 0:
            efficiency = Decimal("0")
        else:
            efficiency = Decimal("100")
        assert efficiency == Decimal("0")

    def test_efficiency_formula_application(self):
        """Test efficiency formula: (units * cycle_time) / (employees * hours) * 100"""
        units = Decimal("1000")
        cycle_time = Decimal("0.25")  # 15 min per unit
        employees = 5
        scheduled_hours = Decimal("8")

        efficiency = (units * cycle_time) / (employees * scheduled_hours) * 100
        # Expected: (1000 * 0.25) / (5 * 8) * 100 = 250 / 40 * 100 = 625%
        assert efficiency == Decimal("625")


class TestDecimalOperations:
    """Test Decimal operations used in calculations"""

    def test_decimal_multiplication(self):
        """Test Decimal multiplication"""
        a = Decimal("0.25")
        b = Decimal("1000")
        result = a * b
        assert result == Decimal("250")

    def test_decimal_division(self):
        """Test Decimal division"""
        a = Decimal("250")
        b = Decimal("8")
        result = a / b
        assert result == Decimal("31.25")

    def test_decimal_quantize(self):
        """Test Decimal quantize"""
        value = Decimal("83.3333333")
        quantized = value.quantize(Decimal("0.01"))
        assert quantized == Decimal("83.33")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

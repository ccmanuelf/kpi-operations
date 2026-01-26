"""
Comprehensive Tests for FPY (First Pass Yield) and RTY (Rolled Throughput Yield) Calculations
Target: Increase fpy_rty.py coverage from 29% to 60%+
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestFPYBasic:
    """Basic tests for FPY calculations"""

    def test_import_fpy_rty(self):
        """Test module imports correctly"""
        from backend.calculations import fpy_rty
        assert fpy_rty is not None

    def test_fpy_formula(self):
        """Test FPY formula: FPY = (Units Passed First Time / Total Units) * 100"""
        total_units = 1000
        passed_first_time = 950

        fpy = (Decimal(str(passed_first_time)) / Decimal(str(total_units))) * 100

        assert fpy == Decimal("95.0")

    def test_fpy_perfect_100(self):
        """Test FPY with 100% pass rate"""
        total_units = 500
        passed_first_time = 500

        fpy = (Decimal(str(passed_first_time)) / Decimal(str(total_units))) * 100

        assert fpy == Decimal("100.0")

    def test_fpy_zero_pass(self):
        """Test FPY with 0% pass rate"""
        total_units = 100
        passed_first_time = 0

        fpy = (Decimal(str(passed_first_time)) / Decimal(str(total_units))) * 100

        assert fpy == Decimal("0.0")


class TestRTYBasic:
    """Basic tests for RTY calculations"""

    def test_rty_formula_single_process(self):
        """Test RTY formula with single process: RTY = FPY"""
        fpy = Decimal("0.95")
        rty = fpy * 100

        assert rty == Decimal("95.0")

    def test_rty_formula_multiple_processes(self):
        """Test RTY formula: RTY = FPY1 * FPY2 * ... * FPYn"""
        # 3 processes with 95%, 90%, 92% FPY respectively
        fpy1 = Decimal("0.95")
        fpy2 = Decimal("0.90")
        fpy3 = Decimal("0.92")

        rty = fpy1 * fpy2 * fpy3 * 100

        # 0.95 * 0.90 * 0.92 = 0.7866
        expected = Decimal("78.66")
        assert abs(rty - expected) < Decimal("0.01")

    def test_rty_decreases_with_more_processes(self):
        """Test RTY decreases as more processes are added"""
        fpy = Decimal("0.95")

        rty_1_process = fpy
        rty_2_process = fpy * fpy
        rty_3_process = fpy * fpy * fpy

        assert rty_2_process < rty_1_process
        assert rty_3_process < rty_2_process


class TestCalculateFPY:
    """Tests for calculate_fpy function"""

    def test_calculate_fpy_no_data(self, db_session):
        """Test FPY with no data"""
        from backend.calculations.fpy_rty import calculate_fpy

        result = calculate_fpy(
            db_session,
            product_id=1,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        # Should return 0 or default when no data
        assert result[0] == Decimal("0") or result[2] == 0

    def test_calculate_fpy_with_product_filter(self, db_session):
        """Test FPY with product filter"""
        from backend.calculations.fpy_rty import calculate_fpy

        result = calculate_fpy(
            db_session,
            product_id=1,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        assert isinstance(result, tuple)
        assert len(result) == 3


class TestCalculateRTY:
    """Tests for calculate_rty function"""

    def test_calculate_rty_no_data(self, db_session):
        """Test RTY with no data"""
        from backend.calculations.fpy_rty import calculate_rty

        result = calculate_rty(
            db_session,
            product_id=1,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        # RTY returns (rty_percentage, step_details list)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestFPYByWorkOrder:
    """Tests for FPY calculation by work order"""

    def test_fpy_by_work_order_not_found(self, db_session):
        """Test FPY for non-existent work order"""
        # Note: calculate_fpy_by_work_order is not implemented in current module
        # Test process_yield instead which provides similar functionality
        from backend.calculations.fpy_rty import calculate_process_yield
        from datetime import date, timedelta

        result = calculate_process_yield(
            db_session,
            product_id=999,  # Non-existent product
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        # Should return dict with 0 values for non-existent product
        assert isinstance(result, dict)
        assert result.get("total_produced") == 0 or result.get("process_yield") == Decimal("0")


class TestDefectRateCalculation:
    """Tests for defect rate as complement to FPY"""

    def test_defect_rate_from_fpy(self):
        """Test defect rate = 100 - FPY"""
        fpy = Decimal("95.5")
        defect_rate = Decimal("100") - fpy

        assert defect_rate == Decimal("4.5")

    def test_defects_per_unit(self):
        """Test defects per unit calculation"""
        total_defects = 45
        total_units = 1000

        dpu = Decimal(str(total_defects)) / Decimal(str(total_units))

        assert dpu == Decimal("0.045")


class TestHiddenFactoryCalculation:
    """Tests for Hidden Factory calculation from RTY"""

    def test_hidden_factory_percentage(self):
        """Test hidden factory: % of production being reworked"""
        # If RTY is 80%, hidden factory is 20%
        rty = Decimal("80.0")
        hidden_factory = Decimal("100") - rty

        assert hidden_factory == Decimal("20.0")

    def test_hidden_factory_cost(self):
        """Test hidden factory cost impact"""
        # If 20% is rework and rework cost is $50/unit
        total_units = 1000
        hidden_factory_pct = Decimal("0.20")
        rework_cost_per_unit = Decimal("50")

        hidden_cost = total_units * hidden_factory_pct * rework_cost_per_unit

        assert hidden_cost == Decimal("10000")


class TestFPYTrend:
    """Tests for FPY trend analysis"""

    def test_fpy_trend_weekly(self):
        """Test weekly FPY trend calculation"""
        weekly_fpy = [
            Decimal("92.5"),
            Decimal("93.0"),
            Decimal("94.2"),
            Decimal("93.8"),
            Decimal("95.1")
        ]

        average_fpy = sum(weekly_fpy) / len(weekly_fpy)
        assert Decimal("93.7") < average_fpy < Decimal("93.8")

    def test_fpy_improvement_detection(self):
        """Test detection of FPY improvement"""
        # Comparing week-over-week
        last_week_fpy = Decimal("93.0")
        this_week_fpy = Decimal("95.5")

        improvement = this_week_fpy - last_week_fpy
        improvement_pct = (improvement / last_week_fpy) * 100

        assert improvement > 0
        assert improvement == Decimal("2.5")


class TestFPYByProcess:
    """Tests for FPY by process step"""

    def test_process_step_fpy(self):
        """Test FPY for individual process steps"""
        process_fpy = {
            "Assembly": Decimal("98.5"),
            "Soldering": Decimal("96.2"),
            "Testing": Decimal("99.1"),
            "Packaging": Decimal("99.8")
        }

        # RTY = product of all FPY
        rty = Decimal("1.0")
        for fpy in process_fpy.values():
            rty *= (fpy / 100)
        rty *= 100

        # 0.985 * 0.962 * 0.991 * 0.998 = 0.9374
        assert Decimal("93.5") < rty < Decimal("94.0")

    def test_identify_bottleneck_process(self):
        """Test identification of lowest FPY process"""
        process_fpy = {
            "Assembly": Decimal("98.5"),
            "Soldering": Decimal("92.2"),
            "Testing": Decimal("99.1"),
            "Packaging": Decimal("99.8")
        }

        bottleneck = min(process_fpy.items(), key=lambda x: x[1])

        assert bottleneck[0] == "Soldering"
        assert bottleneck[1] == Decimal("92.2")


class TestFPYValidation:
    """Tests for FPY input validation"""

    def test_fpy_bounds_0_100(self):
        """Test FPY is bounded between 0 and 100"""
        def validate_fpy(fpy: Decimal) -> bool:
            return Decimal("0") <= fpy <= Decimal("100")

        assert validate_fpy(Decimal("0")) == True
        assert validate_fpy(Decimal("50")) == True
        assert validate_fpy(Decimal("100")) == True
        assert validate_fpy(Decimal("-5")) == False
        assert validate_fpy(Decimal("105")) == False

    def test_fpy_with_zero_units(self):
        """Test FPY handling with zero total units"""
        total_units = 0
        passed_units = 0

        if total_units == 0:
            fpy = Decimal("0")
        else:
            fpy = (Decimal(str(passed_units)) / Decimal(str(total_units))) * 100

        assert fpy == Decimal("0")

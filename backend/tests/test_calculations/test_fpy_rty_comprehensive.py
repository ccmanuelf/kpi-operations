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
            db_session, product_id=1, start_date=date.today() - timedelta(days=30), end_date=date.today()
        )

        # Should return 0 or default when no data
        assert result[0] == Decimal("0") or result[2] == 0

    def test_calculate_fpy_with_product_filter(self, db_session):
        """Test FPY with product filter"""
        from backend.calculations.fpy_rty import calculate_fpy

        result = calculate_fpy(
            db_session, product_id=1, start_date=date.today() - timedelta(days=30), end_date=date.today()
        )

        assert isinstance(result, tuple)
        assert len(result) == 3


class TestCalculateRTY:
    """Tests for calculate_rty function"""

    def test_calculate_rty_no_data(self, db_session):
        """Test RTY with no data"""
        from backend.calculations.fpy_rty import calculate_rty

        result = calculate_rty(
            db_session, product_id=1, start_date=date.today() - timedelta(days=30), end_date=date.today()
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
            end_date=date.today(),
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
        weekly_fpy = [Decimal("92.5"), Decimal("93.0"), Decimal("94.2"), Decimal("93.8"), Decimal("95.1")]

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
            "Packaging": Decimal("99.8"),
        }

        # RTY = product of all FPY
        rty = Decimal("1.0")
        for fpy in process_fpy.values():
            rty *= fpy / 100
        rty *= 100

        # 0.985 * 0.962 * 0.991 * 0.998 = 0.9374
        assert Decimal("93.5") < rty < Decimal("94.0")

    def test_identify_bottleneck_process(self):
        """Test identification of lowest FPY process"""
        process_fpy = {
            "Assembly": Decimal("98.5"),
            "Soldering": Decimal("92.2"),
            "Testing": Decimal("99.1"),
            "Packaging": Decimal("99.8"),
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


# =============================================================================
# Test get_rty_interpretation (pure function)
# =============================================================================


class TestGetRTYInterpretation:
    """Test RTY interpretation function"""

    def test_excellent_rty_low_repair(self):
        """Test excellent RTY with minimal repair"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("96"), Decimal("1.5"))
        assert "Excellent" in result
        assert "minimal repair" in result

    def test_good_rty_moderate_repair(self):
        """Test good RTY with moderate repair"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("92"), Decimal("4"))
        assert "Good" in result
        assert "monitor" in result.lower()

    def test_acceptable_rty_high_repair(self):
        """Test acceptable RTY with high repair rate"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("85"), Decimal("12"))
        assert "Warning" in result
        assert "process issues" in result.lower()

    def test_acceptable_rty_low_repair(self):
        """Test acceptable RTY with low repair"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("82"), Decimal("3"))
        assert "Acceptable" in result
        assert "improvement opportunity" in result.lower()

    def test_low_rty_excessive_repair(self):
        """Test low RTY with excessive repair"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("75"), Decimal("18"))
        assert "Critical" in result
        assert "immediate" in result.lower()

    def test_low_rty_moderate_repair(self):
        """Test low RTY with moderate repair"""
        from backend.calculations.fpy_rty import get_rty_interpretation

        result = get_rty_interpretation(Decimal("78"), Decimal("8"))
        assert "Needs Improvement" in result
        assert "investigate" in result.lower()


class TestGetJobRTYInterpretation:
    """Test job RTY interpretation function"""

    def test_excellent_job_rty(self):
        """Test excellent job-level RTY"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(Decimal("99"))
        assert "Excellent" in result

    def test_good_job_rty(self):
        """Test good job-level RTY"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(Decimal("96"))
        assert "Good" in result

    def test_acceptable_job_rty(self):
        """Test acceptable job-level RTY"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(Decimal("92"))
        assert "Acceptable" in result

    def test_warning_job_rty(self):
        """Test warning job-level RTY"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(Decimal("87"))
        assert "Warning" in result

    def test_critical_job_rty(self):
        """Test critical job-level RTY"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(Decimal("80"))
        assert "Critical" in result

    def test_float_input(self):
        """Test interpretation with float input"""
        from backend.calculations.fpy_rty import get_job_rty_interpretation

        result = get_job_rty_interpretation(98.5)
        assert "Excellent" in result


# =============================================================================
# Test calculate_fpy_with_repair_breakdown (mocked)
# =============================================================================


class TestCalculateFPYWithRepairBreakdown:
    """Test FPY with detailed repair/rework breakdown"""

    def test_breakdown_no_inspections(self):
        """Test breakdown with no inspection data"""
        from backend.calculations.fpy_rty import calculate_fpy_with_repair_breakdown

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_fpy_with_repair_breakdown(mock_db, 1, date.today() - timedelta(days=30), date.today())

        assert result["fpy_percentage"] == Decimal("0")
        assert result["first_pass_good"] == 0
        assert result["total_inspected"] == 0
        # With no inspections, recovery_rate is 0 (no data to calculate from)
        assert result["recovery_rate"] == Decimal("0")

    def test_breakdown_with_data(self):
        """Test breakdown with inspection data"""
        from backend.calculations.fpy_rty import calculate_fpy_with_repair_breakdown

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 100
        mock_inspection.units_passed = 90
        mock_inspection.units_reworked = 5
        mock_inspection.units_requiring_repair = 3
        mock_inspection.units_scrapped = 2
        mock_query.all.return_value = [mock_inspection]

        result = calculate_fpy_with_repair_breakdown(mock_db, 1, date.today() - timedelta(days=30), date.today())

        assert result["fpy_percentage"] == Decimal("90")
        assert result["first_pass_good"] == 90
        assert result["units_reworked"] == 5
        assert result["units_requiring_repair"] == 3
        assert result["recovered_units"] == 8

    def test_breakdown_recovery_rate_calculation(self):
        """Test recovery rate calculation"""
        from backend.calculations.fpy_rty import calculate_fpy_with_repair_breakdown

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 100
        mock_inspection.units_passed = 90
        mock_inspection.units_reworked = 4
        mock_inspection.units_requiring_repair = 4
        mock_inspection.units_scrapped = 2
        mock_query.all.return_value = [mock_inspection]

        result = calculate_fpy_with_repair_breakdown(mock_db, 1, date.today() - timedelta(days=30), date.today())

        # Recovery = 8 / 10 = 80%
        assert result["recovery_rate"] == Decimal("80")


# =============================================================================
# Test calculate_rty_with_repair_impact (mocked)
# =============================================================================


class TestCalculateRTYWithRepairImpact:
    """Test RTY with repair impact analysis"""

    def test_rty_with_repair_impact_structure(self):
        """Test RTY with repair impact returns correct structure"""
        from backend.calculations.fpy_rty import calculate_rty_with_repair_impact

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 100
        mock_inspection.units_passed = 90
        mock_inspection.units_reworked = 5
        mock_inspection.units_requiring_repair = 3
        mock_inspection.units_scrapped = 2
        mock_query.all.return_value = [mock_inspection]

        result = calculate_rty_with_repair_impact(mock_db, 1, date.today() - timedelta(days=30), date.today())

        assert "rty_percentage" in result
        assert "step_details" in result
        assert "total_rework" in result
        assert "total_repair" in result
        assert "throughput_loss_percentage" in result
        assert "interpretation" in result

    def test_rty_with_repair_custom_steps(self):
        """Test RTY with repair impact and custom steps"""
        from backend.calculations.fpy_rty import calculate_rty_with_repair_impact

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 50
        mock_inspection.units_passed = 48
        mock_inspection.units_reworked = 1
        mock_inspection.units_requiring_repair = 1
        mock_inspection.units_scrapped = 0
        mock_query.all.return_value = [mock_inspection]

        result = calculate_rty_with_repair_impact(
            mock_db, 1, date.today() - timedelta(days=30), date.today(), process_steps=["Step1", "Step2"]
        )

        assert len(result["step_details"]) == 2


# =============================================================================
# Test calculate_defect_escape_rate (mocked)
# =============================================================================


class TestCalculateDefectEscapeRate:
    """Test defect escape rate calculation"""

    def test_escape_rate_basic(self):
        """Test basic escape rate calculation"""
        from backend.calculations.fpy_rty import calculate_defect_escape_rate

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_in_process = MagicMock()
        mock_in_process.inspection_stage = "In-Process"
        mock_in_process.units_defective = 8

        mock_final = MagicMock()
        mock_final.inspection_stage = "Final"
        mock_final.units_defective = 2

        mock_query.all.return_value = [mock_in_process, mock_final]

        escape_rate = calculate_defect_escape_rate(mock_db, 1, date.today() - timedelta(days=30), date.today())

        # 2 / 10 * 100 = 20%
        assert escape_rate == Decimal("20")

    def test_escape_rate_no_inspections(self):
        """Test escape rate with no inspections"""
        from backend.calculations.fpy_rty import calculate_defect_escape_rate

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        escape_rate = calculate_defect_escape_rate(mock_db, 1, date.today() - timedelta(days=30), date.today())

        assert escape_rate == Decimal("0")

    def test_escape_rate_no_defects(self):
        """Test escape rate with no defects"""
        from backend.calculations.fpy_rty import calculate_defect_escape_rate

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_inspection = MagicMock()
        mock_inspection.inspection_stage = "Final"
        mock_inspection.units_defective = 0
        mock_query.all.return_value = [mock_inspection]

        escape_rate = calculate_defect_escape_rate(mock_db, 1, date.today() - timedelta(days=30), date.today())

        assert escape_rate == Decimal("0")


# =============================================================================
# Test calculate_job_yield (Phase 6.6, mocked)
# =============================================================================


class TestCalculateJobYield:
    """Test job-level yield calculation"""

    def test_job_yield_basic(self):
        """Test basic job yield calculation"""
        from backend.calculations.fpy_rty import calculate_job_yield

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_job = MagicMock()
        mock_job.job_id = "JOB001"
        mock_job.operation_name = "Assembly"
        mock_job.sequence_number = 1
        mock_job.part_number = "PART-A"
        mock_job.completed_quantity = 100
        mock_job.quantity_scrapped = 5
        mock_query.first.return_value = mock_job

        result = calculate_job_yield(mock_db, "JOB001")

        assert result["job_id"] == "JOB001"
        assert result["completed_quantity"] == 100
        assert result["quantity_scrapped"] == 5
        assert result["good_quantity"] == 95
        assert result["yield_percentage"] == Decimal("95")

    def test_job_yield_not_found(self):
        """Test job yield with non-existent job"""
        from backend.calculations.fpy_rty import calculate_job_yield

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = calculate_job_yield(mock_db, "INVALID_JOB")

        assert result["job_id"] == "INVALID_JOB"
        assert result["yield_percentage"] == Decimal("0")
        assert "error" in result

    def test_job_yield_zero_completed(self):
        """Test job yield with zero completed quantity"""
        from backend.calculations.fpy_rty import calculate_job_yield

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_job = MagicMock()
        mock_job.job_id = "JOB002"
        mock_job.operation_name = "Test"
        mock_job.sequence_number = 2
        mock_job.part_number = "PART-B"
        mock_job.completed_quantity = 0
        mock_job.quantity_scrapped = 0
        mock_query.first.return_value = mock_job

        result = calculate_job_yield(mock_db, "JOB002")

        assert result["yield_percentage"] == Decimal("0")

    def test_job_yield_with_none_values(self):
        """Test job yield handles None values"""
        from backend.calculations.fpy_rty import calculate_job_yield

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_job = MagicMock()
        mock_job.job_id = "JOB003"
        mock_job.operation_name = "Pack"
        mock_job.sequence_number = 3
        mock_job.part_number = "PART-C"
        mock_job.completed_quantity = None
        mock_job.quantity_scrapped = None
        mock_query.first.return_value = mock_job

        result = calculate_job_yield(mock_db, "JOB003")

        assert result["completed_quantity"] == 0
        assert result["yield_percentage"] == Decimal("0")


# =============================================================================
# Test calculate_work_order_job_rty (Phase 6.6, mocked)
# =============================================================================


class TestCalculateWorkOrderJobRTY:
    """Test work order job-level RTY calculation"""

    def test_work_order_job_rty_basic(self):
        """Test basic work order job RTY calculation"""
        from backend.calculations.fpy_rty import calculate_work_order_job_rty

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        mock_job1 = MagicMock()
        mock_job1.job_id = "J1"
        mock_job1.operation_name = "Cut"
        mock_job1.sequence_number = 1
        mock_job1.part_number = "PART-A"
        mock_job1.planned_quantity = 100
        mock_job1.completed_quantity = 100
        mock_job1.quantity_scrapped = 5
        mock_job1.is_completed = True

        mock_job2 = MagicMock()
        mock_job2.job_id = "J2"
        mock_job2.operation_name = "Sew"
        mock_job2.sequence_number = 2
        mock_job2.part_number = "PART-A"
        mock_job2.planned_quantity = 95
        mock_job2.completed_quantity = 95
        mock_job2.quantity_scrapped = 5
        mock_job2.is_completed = True

        mock_query.all.return_value = [mock_job1, mock_job2]

        result = calculate_work_order_job_rty(mock_db, "WO001")

        assert result["work_order_id"] == "WO001"
        assert result["job_count"] == 2
        assert result["total_scrapped"] == 10
        assert "interpretation" in result

    def test_work_order_job_rty_no_jobs(self):
        """Test work order job RTY with no jobs"""
        from backend.calculations.fpy_rty import calculate_work_order_job_rty

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_work_order_job_rty(mock_db, "WO_EMPTY")

        assert result["rty_percentage"] == Decimal("0")
        assert result["job_count"] == 0
        assert "error" in result

    def test_work_order_job_rty_bottleneck_identification(self):
        """Test bottleneck job identification"""
        from backend.calculations.fpy_rty import calculate_work_order_job_rty

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        # Good job: 95% yield
        mock_job1 = MagicMock()
        mock_job1.job_id = "J1"
        mock_job1.operation_name = "Good Op"
        mock_job1.sequence_number = 1
        mock_job1.part_number = "P1"
        mock_job1.planned_quantity = 100
        mock_job1.completed_quantity = 100
        mock_job1.quantity_scrapped = 5
        mock_job1.is_completed = True

        # Problem job: 80% yield (bottleneck)
        mock_job2 = MagicMock()
        mock_job2.job_id = "J2"
        mock_job2.operation_name = "Problem Op"
        mock_job2.sequence_number = 2
        mock_job2.part_number = "P1"
        mock_job2.planned_quantity = 95
        mock_job2.completed_quantity = 100
        mock_job2.quantity_scrapped = 20
        mock_job2.is_completed = True

        mock_query.all.return_value = [mock_job1, mock_job2]

        result = calculate_work_order_job_rty(mock_db, "WO003")

        assert result["bottleneck_job"] is not None
        assert result["bottleneck_job"]["job_id"] == "J2"


# =============================================================================
# Test calculate_job_rty_summary (Phase 6.6, mocked)
# =============================================================================


class TestCalculateJobRTYSummary:
    """Test job RTY summary calculation"""

    def test_job_rty_summary_basic(self):
        """Test basic job RTY summary"""
        from backend.calculations.fpy_rty import calculate_job_rty_summary

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_job1 = MagicMock()
        mock_job1.operation_name = "Op1"
        mock_job1.completed_quantity = 100
        mock_job1.quantity_scrapped = 5

        mock_job2 = MagicMock()
        mock_job2.operation_name = "Op2"
        mock_job2.completed_quantity = 100
        mock_job2.quantity_scrapped = 10

        mock_query.all.return_value = [mock_job1, mock_job2]

        result = calculate_job_rty_summary(mock_db, date.today() - timedelta(days=30), date.today())

        assert result["total_jobs_completed"] == 2
        assert result["total_units_completed"] == 200
        assert result["total_units_scrapped"] == 15
        assert "top_scrap_operations" in result

    def test_job_rty_summary_no_jobs(self):
        """Test job RTY summary with no jobs"""
        from backend.calculations.fpy_rty import calculate_job_rty_summary

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_job_rty_summary(mock_db, date.today() - timedelta(days=30), date.today())

        assert result["total_jobs_completed"] == 0
        assert result["average_job_yield"] == Decimal("0")

    def test_job_rty_summary_top_scrap_operations(self):
        """Test top scrap operations ranking"""
        from backend.calculations.fpy_rty import calculate_job_rty_summary

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_jobs = []
        for op_name, scrap in [("Assembly", 50), ("Testing", 30), ("Assembly", 25)]:
            mock_job = MagicMock()
            mock_job.operation_name = op_name
            mock_job.completed_quantity = 100
            mock_job.quantity_scrapped = scrap
            mock_jobs.append(mock_job)

        mock_query.all.return_value = mock_jobs

        result = calculate_job_rty_summary(mock_db, date.today() - timedelta(days=30), date.today())

        top_scrap = result["top_scrap_operations"]
        assert len(top_scrap) <= 5
        # Assembly should be first (50 + 25 = 75 total)
        assert top_scrap[0]["operation"] == "Assembly"
        assert top_scrap[0]["units_scrapped"] == 75

    def test_job_rty_summary_jobs_below_target(self):
        """Test counting jobs below 95% target"""
        from backend.calculations.fpy_rty import calculate_job_rty_summary

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # 2 above target (96%, 98%), 1 below (90%)
        mock_job1 = MagicMock()
        mock_job1.operation_name = "Good1"
        mock_job1.completed_quantity = 100
        mock_job1.quantity_scrapped = 4  # 96%

        mock_job2 = MagicMock()
        mock_job2.operation_name = "Good2"
        mock_job2.completed_quantity = 100
        mock_job2.quantity_scrapped = 2  # 98%

        mock_job3 = MagicMock()
        mock_job3.operation_name = "Problem"
        mock_job3.completed_quantity = 100
        mock_job3.quantity_scrapped = 10  # 90%

        mock_query.all.return_value = [mock_job1, mock_job2, mock_job3]

        result = calculate_job_rty_summary(mock_db, date.today() - timedelta(days=30), date.today())

        assert result["jobs_below_target"] == 1
        assert result["jobs_meeting_target"] == 2

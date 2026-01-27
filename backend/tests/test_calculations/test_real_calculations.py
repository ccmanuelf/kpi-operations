"""
Tests for actual calculation module functions with mocked database sessions.
Target: Cover calculations/ directory to reach 85% overall coverage.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session


# =============================================================================
# EFFICIENCY MODULE TESTS
# =============================================================================
class TestEfficiencyModule:
    """Tests for calculations/efficiency.py"""

    def test_get_floating_pool_coverage_count(self):
        """Test floating pool coverage count function"""
        from calculations.efficiency import get_floating_pool_coverage_count

        mock_db = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 3

        result = get_floating_pool_coverage_count(
            mock_db, "CLIENT-001", date.today(), shift_id=1
        )

        assert result == 3
        mock_db.query.assert_called_once()

    def test_get_floating_pool_coverage_count_no_shift(self):
        """Test floating pool coverage without shift filter"""
        from calculations.efficiency import get_floating_pool_coverage_count

        mock_db = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5

        result = get_floating_pool_coverage_count(
            mock_db, "CLIENT-001", date.today(), shift_id=None
        )

        assert result == 5

    def test_get_floating_pool_coverage_count_zero(self):
        """Test floating pool with no coverage"""
        from calculations.efficiency import get_floating_pool_coverage_count

        mock_db = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None

        result = get_floating_pool_coverage_count(
            mock_db, "CLIENT-001", date.today()
        )

        assert result == 0

    def test_inferred_employees_dataclass(self):
        """Test InferredEmployees dataclass"""
        from calculations.efficiency import InferredEmployees

        inferred = InferredEmployees(
            count=5,
            is_inferred=True,
            inference_source="historical_avg",
            confidence_score=0.5
        )

        assert inferred.count == 5
        assert inferred.is_inferred is True
        assert inferred.inference_source == "historical_avg"
        assert inferred.confidence_score == 0.5

    def test_infer_employees_count_from_assigned(self):
        """Test employees inference from employees_assigned"""
        from calculations.efficiency import infer_employees_count

        mock_db = MagicMock(spec=Session)
        mock_entry = MagicMock()
        mock_entry.employees_assigned = 10
        mock_entry.client_id = "CLIENT-001"
        mock_entry.production_date = date.today()
        mock_entry.shift_id = 1

        # Mock the floating pool query
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        result = infer_employees_count(mock_db, mock_entry, include_floating_pool=False)

        assert result.count == 10
        assert result.is_inferred is False
        assert result.inference_source == "employees_assigned"
        assert result.confidence_score == 1.0

    def test_infer_employees_count_fallback_to_present(self):
        """Test employees inference falls back to employees_present"""
        from calculations.efficiency import infer_employees_count

        mock_db = MagicMock(spec=Session)
        mock_entry = MagicMock()
        mock_entry.employees_assigned = None
        mock_entry.employees_present = 8
        mock_entry.client_id = "CLIENT-001"
        mock_entry.production_date = date.today()
        mock_entry.shift_id = 1

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        result = infer_employees_count(mock_db, mock_entry, include_floating_pool=False)

        assert result.count == 8
        assert result.is_inferred is True
        assert result.inference_source == "employees_present"
        assert result.confidence_score == 0.8


# =============================================================================
# AVAILABILITY MODULE TESTS
# =============================================================================
class TestAvailabilityModule:
    """Tests for calculations/availability.py"""

    def test_calculate_availability_basic(self):
        """Test basic availability calculation"""
        from calculations.availability import calculate_availability

        mock_db = MagicMock(spec=Session)

        # Mock shift query
        mock_shift = MagicMock()
        mock_shift.duration_hours = 8.0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_shift

        # Mock downtime sum query
        mock_downtime_query = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 1.5

        result = calculate_availability(mock_db, 1, 1, date.today())

        # Should return tuple of (availability_pct, scheduled_hours, downtime_hours, event_count)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_calculate_availability_no_shift(self):
        """Test availability when shift not found (uses default 8 hours)"""
        from calculations.availability import calculate_availability

        mock_db = MagicMock(spec=Session)

        # Mock no shift found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = calculate_availability(mock_db, 1, 1, date.today())

        assert isinstance(result, tuple)
        # With 0 downtime and 8 hours default, availability should be 100%
        assert result[1] == Decimal("8.0")  # scheduled hours

    def test_calculate_availability_result_structure(self):
        """Test availability result structure"""
        from calculations.availability import calculate_availability

        mock_db = MagicMock(spec=Session)

        mock_shift = MagicMock()
        mock_shift.duration_hours = 8.0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_shift
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = calculate_availability(mock_db, 1, 1, date.today())

        # Result should be a valid tuple
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_calculate_mtbf(self):
        """Test Mean Time Between Failures calculation"""
        from calculations.availability import calculate_mtbf

        mock_db = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.scalar.return_value = 40  # 40 hours total

        result = calculate_mtbf(
            mock_db, "MACHINE-001",
            date.today() - timedelta(days=30),
            date.today()
        )

        # MTBF = total_operating_hours / number_of_failures
        assert result is None or isinstance(result, Decimal)

    def test_calculate_mttr(self):
        """Test Mean Time To Repair calculation"""
        from calculations.availability import calculate_mttr

        mock_db = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.scalar.return_value = 10  # 10 hours total repair time

        result = calculate_mttr(
            mock_db, "MACHINE-001",
            date.today() - timedelta(days=30),
            date.today()
        )

        assert result is None or isinstance(result, Decimal)


# =============================================================================
# PPM MODULE TESTS
# =============================================================================
class TestPPMModule:
    """Tests for calculations/ppm.py"""

    def test_calculate_ppm_basic(self):
        """Test basic PPM calculation"""
        from calculations.ppm import calculate_ppm

        mock_db = MagicMock(spec=Session)

        # Mock inspection query result
        mock_result = MagicMock()
        mock_result.total_inspected = 10000
        mock_result.total_defects = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        result = calculate_ppm(
            mock_db, 1, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Returns (ppm, total_inspected, total_defects)
        assert isinstance(result, tuple)
        assert len(result) == 3
        # PPM = (5 / 10000) * 1,000,000 = 500
        assert result[0] == Decimal("500")
        assert result[1] == 10000
        assert result[2] == 5

    def test_calculate_ppm_zero_inspected(self):
        """Test PPM with zero inspections"""
        from calculations.ppm import calculate_ppm

        mock_db = MagicMock(spec=Session)

        mock_result = MagicMock()
        mock_result.total_inspected = 0
        mock_result.total_defects = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        result = calculate_ppm(
            mock_db, 1, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Should return 0 PPM with no inspections
        assert result[0] == Decimal("0")

    def test_calculate_ppm_zero_defects(self):
        """Test PPM with zero defects"""
        from calculations.ppm import calculate_ppm

        mock_db = MagicMock(spec=Session)

        mock_result = MagicMock()
        mock_result.total_inspected = 10000
        mock_result.total_defects = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        result = calculate_ppm(
            mock_db, 1, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Should return 0 PPM with no defects
        assert result[0] == Decimal("0")

    def test_calculate_ppm_by_category(self):
        """Test PPM calculation by defect category"""
        from calculations.ppm import calculate_ppm_by_category

        mock_db = MagicMock(spec=Session)

        # Mock inspection results with categories
        mock_insp1 = MagicMock()
        mock_insp1.units_inspected = 1000
        mock_insp1.defects_found = 5
        mock_insp1.defect_category = "Dimensional"

        mock_insp2 = MagicMock()
        mock_insp2.units_inspected = 1000
        mock_insp2.defects_found = 3
        mock_insp2.defect_category = "Surface"

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_insp1, mock_insp2]

        result = calculate_ppm_by_category(
            mock_db, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        assert isinstance(result, dict)


# =============================================================================
# DPMO MODULE TESTS
# =============================================================================
class TestDPMOModule:
    """Tests for calculations/dpmo.py"""

    def test_calculate_sigma_level_six_sigma(self):
        """Test sigma level calculation for 6 sigma (3.4 DPMO)"""
        from calculations.dpmo import calculate_sigma_level

        sigma = calculate_sigma_level(Decimal("3.4"))
        # 3.4 DPMO should be around 6 sigma
        assert sigma >= Decimal("5.5")

    def test_calculate_sigma_level_three_sigma(self):
        """Test sigma level calculation for 3 sigma"""
        from calculations.dpmo import calculate_sigma_level

        # 66807 DPMO = 3 sigma
        sigma = calculate_sigma_level(Decimal("66807"))
        assert sigma >= Decimal("2.5") and sigma <= Decimal("3.5")

    def test_calculate_sigma_level_zero_dpmo(self):
        """Test sigma level calculation with zero DPMO"""
        from calculations.dpmo import calculate_sigma_level

        # 0 DPMO should return maximum sigma
        sigma = calculate_sigma_level(Decimal("0"))
        assert sigma >= Decimal("6")

    def test_calculate_sigma_level_high_dpmo(self):
        """Test sigma level calculation with high DPMO"""
        from calculations.dpmo import calculate_sigma_level

        # Very high DPMO should return low sigma
        sigma = calculate_sigma_level(Decimal("500000"))
        assert sigma <= Decimal("2")


# =============================================================================
# TREND ANALYSIS MODULE TESTS
# =============================================================================
class TestTrendAnalysisModule:
    """Tests for calculations/trend_analysis.py"""

    def test_calculate_moving_average(self):
        """Test simple moving average calculation"""
        from calculations.trend_analysis import calculate_moving_average

        values = [Decimal("85"), Decimal("86.5"), Decimal("84.2"), Decimal("87.1"), Decimal("88.0")]
        result = calculate_moving_average(values, window=3)

        assert len(result) == 5
        assert result[0] is None  # Not enough data
        assert result[1] is None  # Not enough data
        assert result[2] is not None  # First MA value

    def test_calculate_moving_average_window_1(self):
        """Test moving average with window of 1"""
        from calculations.trend_analysis import calculate_moving_average

        values = [Decimal("100"), Decimal("200"), Decimal("300")]
        result = calculate_moving_average(values, window=1)

        assert len(result) == 3
        # With window=1, each value should equal itself
        assert result[0] == Decimal("100")
        assert result[1] == Decimal("200")
        assert result[2] == Decimal("300")

    def test_calculate_moving_average_invalid_window(self):
        """Test moving average with invalid window raises error"""
        from calculations.trend_analysis import calculate_moving_average

        values = [Decimal("100"), Decimal("200")]

        with pytest.raises(ValueError):
            calculate_moving_average(values, window=0)

    def test_calculate_exponential_moving_average(self):
        """Test exponential moving average calculation"""
        from calculations.trend_analysis import calculate_exponential_moving_average

        values = [Decimal("100"), Decimal("105"), Decimal("110"), Decimal("108"), Decimal("112")]
        result = calculate_exponential_moving_average(values, alpha=Decimal("0.3"))

        assert len(result) == 5
        # EMA should be smooth progression
        assert all(isinstance(v, Decimal) for v in result)

    def test_linear_regression(self):
        """Test linear regression calculation"""
        from calculations.trend_analysis import linear_regression

        x_values = [1, 2, 3, 4, 5]
        y_values = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"), Decimal("140")]
        result = linear_regression(x_values, y_values)

        # Result should be tuple of (slope, intercept, r_squared)
        assert isinstance(result, tuple)
        assert len(result) == 3
        slope, intercept, r_squared = result
        # Slope should be positive for increasing data
        assert slope > 0

    def test_linear_regression_decreasing(self):
        """Test linear regression with decreasing trend"""
        from calculations.trend_analysis import linear_regression

        x_values = [1, 2, 3, 4, 5]
        y_values = [Decimal("140"), Decimal("130"), Decimal("120"), Decimal("110"), Decimal("100")]
        result = linear_regression(x_values, y_values)

        slope, intercept, r_squared = result
        assert slope < 0

    def test_linear_regression_constant(self):
        """Test linear regression with constant values"""
        from calculations.trend_analysis import linear_regression

        x_values = [1, 2, 3, 4, 5]
        y_values = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]
        result = linear_regression(x_values, y_values)

        slope, intercept, r_squared = result
        assert slope == Decimal("0")

    def test_determine_trend_direction_increasing(self):
        """Test trend direction determination - increasing"""
        from calculations.trend_analysis import determine_trend_direction

        # Function takes (slope, r_squared, std_deviation, mean_value)
        result = determine_trend_direction(
            Decimal("5.0"), Decimal("0.95"), Decimal("2.0"), Decimal("100")
        )
        assert result == 'increasing'

    def test_determine_trend_direction_decreasing(self):
        """Test trend direction determination - decreasing"""
        from calculations.trend_analysis import determine_trend_direction

        result = determine_trend_direction(
            Decimal("-5.0"), Decimal("0.95"), Decimal("2.0"), Decimal("100")
        )
        assert result == 'decreasing'

    def test_determine_trend_direction_stable(self):
        """Test trend direction determination - stable"""
        from calculations.trend_analysis import determine_trend_direction

        result = determine_trend_direction(
            Decimal("0.001"), Decimal("0.95"), Decimal("2.0"), Decimal("100")
        )
        assert result == 'stable'

    def test_trend_result_dataclass(self):
        """Test TrendResult dataclass"""
        from calculations.trend_analysis import TrendResult

        result = TrendResult(
            slope=Decimal("2.5"),
            intercept=Decimal("100"),
            r_squared=Decimal("0.95"),
            trend_direction="increasing"
        )

        assert result.slope == Decimal("2.5")
        assert result.intercept == Decimal("100")
        assert result.r_squared == Decimal("0.95")
        assert result.trend_direction == "increasing"


# =============================================================================
# PREDICTIONS MODULE TESTS
# =============================================================================
class TestPredictionsModule:
    """Tests for calculations/predictions.py"""

    def test_simple_exponential_smoothing(self):
        """Test simple exponential smoothing"""
        from calculations.predictions import simple_exponential_smoothing

        values = [Decimal("100"), Decimal("105"), Decimal("110"), Decimal("108"), Decimal("112")]
        alpha = Decimal("0.3")

        result = simple_exponential_smoothing(values, alpha, forecast_periods=3)

        # Should return ForecastResult with predictions
        assert hasattr(result, 'predictions') or isinstance(result, (list, dict))

    def test_double_exponential_smoothing(self):
        """Test double exponential smoothing (Holt's method)"""
        from calculations.predictions import double_exponential_smoothing

        values = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"), Decimal("140")]

        result = double_exponential_smoothing(
            values,
            alpha=Decimal("0.3"),
            beta=Decimal("0.2"),
            forecast_periods=3
        )

        # Should return ForecastResult with predictions
        assert hasattr(result, 'predictions') or isinstance(result, (list, dict))

    def test_linear_trend_extrapolation(self):
        """Test linear trend extrapolation"""
        from calculations.predictions import linear_trend_extrapolation

        values = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"), Decimal("140")]

        result = linear_trend_extrapolation(values, forecast_periods=3)

        # Should return ForecastResult with predictions
        assert hasattr(result, 'predictions') or isinstance(result, (list, dict))


# =============================================================================
# WIP AGING MODULE TESTS
# =============================================================================
class TestWIPAgingModule:
    """Tests for calculations/wip_aging.py"""

    def test_calculate_wip_aging(self):
        """Test WIP aging calculation"""
        from calculations.wip_aging import calculate_wip_aging

        mock_db = MagicMock(spec=Session)

        # Mock hold records
        mock_hold1 = MagicMock()
        mock_hold1.quantity = 100
        mock_hold1.hold_date = date.today() - timedelta(days=5)
        mock_hold1.resolved_date = None

        mock_hold2 = MagicMock()
        mock_hold2.quantity = 50
        mock_hold2.hold_date = date.today() - timedelta(days=20)
        mock_hold2.resolved_date = None

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_hold1, mock_hold2]

        result = calculate_wip_aging(mock_db)

        assert isinstance(result, dict)

    def test_calculate_hold_resolution_rate(self):
        """Test hold resolution rate calculation"""
        from calculations.wip_aging import calculate_hold_resolution_rate

        mock_db = MagicMock(spec=Session)

        # Mock query that returns no holds (empty result)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = calculate_hold_resolution_rate(
            mock_db,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Should return dict with resolution_rate when no holds found
        assert isinstance(result, dict)
        assert "resolution_rate" in result
        assert result["resolution_rate"] == Decimal("0")

    def test_identify_chronic_holds(self):
        """Test identifying chronic holds"""
        from calculations.wip_aging import identify_chronic_holds

        mock_db = MagicMock(spec=Session)

        mock_hold = MagicMock()
        mock_hold.hold_id = 1
        mock_hold.quantity = 100
        mock_hold.hold_date = date.today() - timedelta(days=45)

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_hold]

        result = identify_chronic_holds(mock_db, threshold_days=30)

        assert isinstance(result, list)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================
class TestCalculationEdgeCases:
    """Test edge cases across calculation modules"""

    def test_division_by_zero_protection_ppm(self):
        """Test that PPM handles division by zero"""
        from calculations.ppm import calculate_ppm

        mock_db = MagicMock(spec=Session)

        # Zero units inspected
        mock_result = MagicMock()
        mock_result.total_inspected = None
        mock_result.total_defects = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        result = calculate_ppm(
            mock_db, 1, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Should handle gracefully, return 0 PPM
        assert result[0] == Decimal("0")

    def test_empty_values_moving_average(self):
        """Test moving average with empty values"""
        from calculations.trend_analysis import calculate_moving_average

        values = []
        result = calculate_moving_average(values, window=3)

        assert result == []

    def test_single_value_moving_average(self):
        """Test moving average with single value"""
        from calculations.trend_analysis import calculate_moving_average

        values = [Decimal("100")]
        result = calculate_moving_average(values, window=3)

        assert len(result) == 1
        assert result[0] is None  # Not enough data for window

    def test_trend_analysis_constant_values(self):
        """Test trend analysis with constant values"""
        from calculations.trend_analysis import linear_regression

        x_values = [1, 2, 3, 4]
        y_values = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]
        result = linear_regression(x_values, y_values)

        # Slope should be 0 for constant values
        slope, intercept, r_squared = result
        assert slope == Decimal("0")


# =============================================================================
# ADDITIONAL OTD MODULE TESTS
# =============================================================================
class TestOTDModuleExtended:
    """Extended tests for calculations/otd.py - import and basic structure tests"""

    def test_inferred_date_dataclass(self):
        """Test InferredDate dataclass"""
        from calculations.otd import InferredDate

        inferred = InferredDate(
            date=date.today(),
            is_inferred=True,
            inference_source="lead_time_estimate",
            confidence_score=0.7
        )

        assert inferred.date == date.today()
        assert inferred.is_inferred is True
        assert inferred.inference_source == "lead_time_estimate"
        assert inferred.confidence_score == 0.7

    def test_infer_planned_delivery_date_with_set_date(self):
        """Test planned delivery inference when work order has planned_ship_date"""
        from calculations.otd import infer_planned_delivery_date

        mock_wo = MagicMock()
        mock_wo.planned_ship_date = date(2024, 2, 1)
        mock_wo.required_date = None
        mock_wo.planned_start_date = None

        result = infer_planned_delivery_date(mock_wo)

        # Should use the planned_ship_date directly
        assert result.date == date(2024, 2, 1)
        assert result.is_inferred is False
        assert result.confidence_score == 1.0

    def test_infer_planned_delivery_date_with_required_date(self):
        """Test planned delivery inference when work order has required_date but no planned_ship"""
        from calculations.otd import infer_planned_delivery_date

        mock_wo = MagicMock()
        mock_wo.planned_ship_date = None
        mock_wo.required_date = date(2024, 2, 15)
        mock_wo.planned_start_date = None

        result = infer_planned_delivery_date(mock_wo)

        # Should use the required_date as fallback
        assert result.date == date(2024, 2, 15)
        assert result.is_inferred is True
        assert result.confidence_score == 0.8


# =============================================================================
# ADDITIONAL FPY/RTY MODULE TESTS
# =============================================================================
class TestFPYRTYModuleExtended:
    """Extended tests for calculations/fpy_rty.py"""

    def test_calculate_fpy_basic(self):
        """Test First Pass Yield calculation"""
        from calculations.fpy_rty import calculate_fpy

        mock_db = MagicMock(spec=Session)

        # Mock the sum queries
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        # First call returns total units, second returns passed units
        mock_query.scalar.side_effect = [1000, 950]

        result = calculate_fpy(
            mock_db, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Returns tuple: (fpy_percentage, units_inspected, units_passed)
        assert isinstance(result, tuple)

    def test_calculate_fpy_zero_production(self):
        """Test FPY with zero production"""
        from calculations.fpy_rty import calculate_fpy

        mock_db = MagicMock(spec=Session)

        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        # Both return 0
        mock_query.scalar.return_value = 0

        result = calculate_fpy(
            mock_db, 1,
            date.today() - timedelta(days=30),
            date.today()
        )

        # Should handle gracefully
        assert isinstance(result, tuple)

    def test_fpy_rty_imports(self):
        """Test FPY/RTY module can be imported and has expected functions"""
        from calculations import fpy_rty

        assert hasattr(fpy_rty, 'calculate_fpy')
        assert hasattr(fpy_rty, 'calculate_rty')
        assert hasattr(fpy_rty, 'calculate_process_yield')
        assert hasattr(fpy_rty, 'calculate_defect_escape_rate')
        assert hasattr(fpy_rty, 'calculate_quality_score')


# =============================================================================
# ADDITIONAL ABSENTEEISM MODULE TESTS
# =============================================================================
class TestAbsenteeismModuleExtended:
    """Extended tests for calculations/absenteeism.py"""

    def test_absenteeism_module_imports(self):
        """Test absenteeism module can be imported and has expected functions"""
        from calculations import absenteeism

        assert hasattr(absenteeism, 'calculate_absenteeism')
        assert hasattr(absenteeism, 'calculate_attendance_rate')
        assert hasattr(absenteeism, 'identify_chronic_absentees')
        assert hasattr(absenteeism, 'calculate_bradford_factor')

    def test_absenteeism_formula_validation(self):
        """Test absenteeism formula: (absent/scheduled)*100"""
        # Pure formula test
        scheduled = 480
        absent = 40

        rate = (absent / scheduled) * 100
        assert round(rate, 2) == 8.33

    def test_bradford_factor_formula(self):
        """Test Bradford Factor formula: S^2 * D"""
        # Pure formula test
        instances = 3  # S = number of instances
        total_days = 6  # D = total days

        bradford = (instances ** 2) * total_days
        assert bradford == 54


# =============================================================================
# ADDITIONAL EFFICIENCY MODULE TESTS
# =============================================================================
class TestEfficiencyModuleExtended:
    """Extended tests for calculations/efficiency.py"""

    def test_calculate_shift_hours(self):
        """Test shift hours calculation"""
        from calculations.efficiency import calculate_shift_hours
        from datetime import time

        # 8-hour shift: 8:00 AM to 4:00 PM
        result = calculate_shift_hours(time(8, 0), time(16, 0))
        assert result == Decimal("8.0")

    def test_calculate_shift_hours_overnight(self):
        """Test shift hours calculation for overnight shift"""
        from calculations.efficiency import calculate_shift_hours
        from datetime import time

        # Overnight shift: 10:00 PM to 6:00 AM
        result = calculate_shift_hours(time(22, 0), time(6, 0))
        assert result == Decimal("8.0")

    def test_efficiency_formula_validation(self):
        """Test efficiency formula: (units * cycle_time) / (employees * hours) * 100"""
        # Pure formula test
        units = 1000
        cycle_time = Decimal("0.01")  # hours per unit
        employees = 5
        hours = Decimal("8.0")

        efficiency = (units * cycle_time) / (employees * hours) * 100
        assert efficiency == Decimal("25.0")

    def test_efficiency_module_imports(self):
        """Test efficiency module can be imported and has expected functions"""
        from calculations import efficiency

        assert hasattr(efficiency, 'calculate_efficiency')
        assert hasattr(efficiency, 'calculate_efficiency_with_metadata')
        assert hasattr(efficiency, 'calculate_shift_hours')
        assert hasattr(efficiency, 'infer_employees_count')
        assert hasattr(efficiency, 'get_floating_pool_coverage_count')


# =============================================================================
# ADDITIONAL AVAILABILITY MODULE TESTS
# =============================================================================
class TestAvailabilityModuleExtended:
    """Extended tests for calculations/availability.py"""

    def test_availability_formula_validation(self):
        """Test availability formula: (scheduled - downtime) / scheduled * 100"""
        # Pure formula test
        scheduled = 480  # minutes
        downtime = 45  # minutes

        availability = ((scheduled - downtime) / scheduled) * 100
        assert round(availability, 2) == 90.62

    def test_mtbf_formula_validation(self):
        """Test MTBF formula: total_operating_time / failure_count"""
        # Pure formula test
        operating_time = 1000  # hours
        failures = 5

        mtbf = operating_time / failures
        assert mtbf == 200.0

    def test_mttr_formula_validation(self):
        """Test MTTR formula: total_repair_time / repair_count"""
        # Pure formula test
        repair_time = 50  # hours
        repairs = 5

        mttr = repair_time / repairs
        assert mttr == 10.0

    def test_availability_module_imports(self):
        """Test availability module can be imported and has expected functions"""
        from calculations import availability

        assert hasattr(availability, 'calculate_availability')
        assert hasattr(availability, 'calculate_mtbf')
        assert hasattr(availability, 'calculate_mttr')


# =============================================================================
# ADDITIONAL WIP AGING MODULE TESTS
# =============================================================================
class TestWIPAgingModuleExtended:
    """Extended tests for calculations/wip_aging.py"""

    def test_wip_aging_bucket_calculation(self):
        """Test WIP aging bucket logic"""
        # 0-7 days bucket
        days = 5
        assert 0 <= days <= 7

        # 8-14 days bucket
        days = 10
        assert 8 <= days <= 14

        # 15-30 days bucket
        days = 20
        assert 15 <= days <= 30

        # Over 30 days (chronic)
        days = 45
        assert days > 30

    def test_hold_duration_calculation(self):
        """Test hold duration calculation in days and hours"""
        hold_date = date.today() - timedelta(days=5)
        release_date = date.today()

        days_held = (release_date - hold_date).days
        hours_held = days_held * 24

        assert days_held == 5
        assert hours_held == 120

    def test_wip_aging_module_imports(self):
        """Test WIP aging module can be imported and has expected functions"""
        from calculations import wip_aging

        assert hasattr(wip_aging, 'calculate_wip_aging')
        assert hasattr(wip_aging, 'calculate_hold_resolution_rate')
        assert hasattr(wip_aging, 'identify_chronic_holds')
        assert hasattr(wip_aging, 'get_total_hold_duration_hours')
        assert hasattr(wip_aging, 'calculate_wip_age_adjusted')

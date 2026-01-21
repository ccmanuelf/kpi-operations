"""
Comprehensive Unit Tests for Calculation Modules
Tests all calculation functions with mocked database
Targets 90% code coverage
"""
import pytest
from decimal import Decimal
from datetime import date, time, datetime, timedelta
from unittest.mock import MagicMock, patch


# =============================================================================
# EFFICIENCY CALCULATION TESTS
# =============================================================================
class TestEfficiencyCalculations:
    """Test efficiency calculation functions"""

    def test_calculate_shift_hours_normal(self):
        """Test normal day shift calculation"""
        from backend.calculations.efficiency import calculate_shift_hours
        
        # 7am to 3:30pm = 8.5 hours
        result = calculate_shift_hours(time(7, 0), time(15, 30))
        assert result == Decimal('8.5')
    
    def test_calculate_shift_hours_overnight(self):
        """Test overnight shift calculation"""
        from backend.calculations.efficiency import calculate_shift_hours
        
        # 11pm to 7am = 8 hours (overnight)
        result = calculate_shift_hours(time(23, 0), time(7, 0))
        assert result == Decimal('8.0')
    
    def test_calculate_shift_hours_same_time(self):
        """Test same start/end time (24 hours)"""
        from backend.calculations.efficiency import calculate_shift_hours
        
        result = calculate_shift_hours(time(8, 0), time(8, 0))
        assert result == Decimal('0.0')
    
    def test_calculate_shift_hours_short_shift(self):
        """Test short 4-hour shift"""
        from backend.calculations.efficiency import calculate_shift_hours
        
        # 9am to 1pm = 4 hours
        result = calculate_shift_hours(time(9, 0), time(13, 0))
        assert result == Decimal('4.0')

    def test_calculate_shift_hours_with_minutes(self):
        """Test shift calculation with minutes"""
        from backend.calculations.efficiency import calculate_shift_hours
        
        # 6:30am to 3:15pm = 8.75 hours
        result = calculate_shift_hours(time(6, 30), time(15, 15))
        assert abs(result - Decimal('8.75')) < Decimal('0.01')

    def test_infer_ideal_cycle_time_from_product(self):
        """Test cycle time inference when product has defined value"""
        from backend.calculations.efficiency import infer_ideal_cycle_time
        
        # Mock DB and product
        mock_db = MagicMock()
        mock_product = MagicMock()
        mock_product.ideal_cycle_time = 0.5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_product
        
        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)
        
        assert cycle_time == Decimal('0.5')
        assert was_inferred == False

    def test_infer_ideal_cycle_time_default(self):
        """Test cycle time inference with no data falls back to default"""
        from backend.calculations.efficiency import infer_ideal_cycle_time, DEFAULT_CYCLE_TIME
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []
        
        cycle_time, was_inferred = infer_ideal_cycle_time(mock_db, product_id=1)
        
        assert cycle_time == DEFAULT_CYCLE_TIME
        assert was_inferred == False


# =============================================================================
# PPM CALCULATION TESTS
# =============================================================================
class TestPPMCalculations:
    """Test PPM calculation functions"""

    def test_calculate_ppm_basic(self):
        """Test basic PPM calculation"""
        from backend.calculations.ppm import calculate_ppm
        
        mock_db = MagicMock()
        # Mock query results: 1000 inspected, 5 defects
        mock_result = MagicMock()
        mock_result.total_inspected = 1000
        mock_result.total_defects = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result
        
        ppm, total_inspected, total_defects = calculate_ppm(
            mock_db, product_id=1, shift_id=1, 
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # PPM = 5/1000 * 1,000,000 = 5000
        assert ppm == Decimal('5000')
        assert total_inspected == 1000
        assert total_defects == 5

    def test_calculate_ppm_zero_inspected(self):
        """Test PPM with no inspections"""
        from backend.calculations.ppm import calculate_ppm
        
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.total_inspected = 0
        mock_result.total_defects = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result
        
        ppm, total_inspected, total_defects = calculate_ppm(
            mock_db, product_id=1, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert ppm == Decimal('0')

    def test_calculate_ppm_perfect_quality(self):
        """Test PPM with zero defects"""
        from backend.calculations.ppm import calculate_ppm
        
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.total_inspected = 10000
        mock_result.total_defects = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result
        
        ppm, total_inspected, total_defects = calculate_ppm(
            mock_db, product_id=1, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert ppm == Decimal('0')
        assert total_defects == 0

    def test_calculate_ppm_by_category_empty(self):
        """Test PPM by category with no data"""
        from backend.calculations.ppm import calculate_ppm_by_category
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = calculate_ppm_by_category(
            mock_db, product_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert result['total_inspected'] == 0
        assert result['categories'] == {}

    def test_identify_top_defects_empty(self):
        """Test top defects with no data"""
        from backend.calculations.ppm import identify_top_defects
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = identify_top_defects(mock_db)
        assert result == []

    def test_calculate_cost_of_quality(self):
        """Test Cost of Quality calculation"""
        from backend.calculations.ppm import calculate_cost_of_quality
        
        mock_db = MagicMock()
        mock_inspection = MagicMock()
        mock_inspection.scrap_units = 10
        mock_inspection.rework_units = 20
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_inspection]
        
        result = calculate_cost_of_quality(
            mock_db, product_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # Scrap: 10 × $10 = $100
        # Rework: 20 × $3 = $60
        # Inspection: 1 × $50 = $50
        assert result['scrap_cost'] == Decimal('100.00')
        assert result['rework_cost'] == Decimal('60.00')
        assert result['inspection_cost'] == Decimal('50.00')
        assert result['total_cost_of_quality'] == Decimal('210.00')


# =============================================================================
# ABSENTEEISM CALCULATION TESTS
# =============================================================================
class TestAbsenteeismCalculations:
    """Test absenteeism calculation functions"""

    def test_calculate_absenteeism_no_records(self):
        """Test absenteeism with no records"""
        from backend.calculations.absenteeism import calculate_absenteeism
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
            mock_db, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert rate == Decimal('0')
        assert scheduled == Decimal('0')
        assert emp_count == 0

    def test_calculate_absenteeism_basic(self):
        """Test basic absenteeism calculation"""
        from backend.calculations.absenteeism import calculate_absenteeism
        
        mock_db = MagicMock()
        
        # Mock record: 8 scheduled, 7 worked
        mock_record = MagicMock()
        mock_record.scheduled_hours = 8.0
        mock_record.actual_hours = 7.0
        mock_record.employee_id = 1
        mock_record.status = 'Present'
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_record]
        
        rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
            mock_db, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # Absenteeism = (8-7)/8 * 100 = 12.5%
        assert rate == Decimal('12.5')
        assert scheduled == Decimal('8.0')
        assert absent == Decimal('1.0')
        assert emp_count == 1

    def test_calculate_attendance_rate_no_records(self):
        """Test attendance rate with no records"""
        from backend.calculations.absenteeism import calculate_attendance_rate
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        
        rate = calculate_attendance_rate(
            mock_db, employee_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert rate == Decimal('0')

    def test_calculate_attendance_rate_perfect(self):
        """Test 100% attendance rate"""
        from backend.calculations.absenteeism import calculate_attendance_rate
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [20, 20]  # 20 total, 20 present
        
        rate = calculate_attendance_rate(
            mock_db, employee_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert rate == Decimal('100')

    def test_identify_chronic_absentees_empty(self):
        """Test chronic absentees with no employees"""
        from backend.calculations.absenteeism import identify_chronic_absentees
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        
        result = identify_chronic_absentees(mock_db)
        assert result == []

    def test_calculate_bradford_factor_no_absences(self):
        """Test Bradford Factor with no absences"""
        from backend.calculations.absenteeism import calculate_bradford_factor
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        score = calculate_bradford_factor(
            mock_db, employee_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert score == 0

    def test_calculate_bradford_factor_single_spell(self):
        """Test Bradford Factor with one spell of 3 days"""
        from backend.calculations.absenteeism import calculate_bradford_factor
        
        mock_db = MagicMock()
        
        # 3 consecutive days of absence
        mock_absences = []
        for i in range(3):
            absence = MagicMock()
            absence.attendance_date = date(2025, 1, i+1)
            mock_absences.append(absence)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_absences
        
        score = calculate_bradford_factor(
            mock_db, employee_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # Bradford = S² × D = 1² × 3 = 3
        assert score == 3

    def test_calculate_bradford_factor_multiple_spells(self):
        """Test Bradford Factor with multiple spells"""
        from backend.calculations.absenteeism import calculate_bradford_factor
        
        mock_db = MagicMock()
        
        # 3 separate single-day absences (3 spells, 3 days)
        mock_absences = []
        for day in [1, 5, 10]:  # Non-consecutive days
            absence = MagicMock()
            absence.attendance_date = date(2025, 1, day)
            mock_absences.append(absence)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_absences
        
        score = calculate_bradford_factor(
            mock_db, employee_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # Bradford = S² × D = 3² × 3 = 27
        assert score == 27


# =============================================================================
# AVAILABILITY CALCULATION TESTS
# =============================================================================
class TestAvailabilityCalculations:
    """Test availability calculation functions"""

    def test_calculate_availability_basic(self):
        """Test basic availability calculation"""
        from backend.calculations.availability import calculate_availability
        
        mock_db = MagicMock()
        
        # Mock shift with 8 hours
        mock_shift = MagicMock()
        mock_shift.duration_hours = 8.0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_shift
        
        # Mock downtime (1 hour)
        mock_db.query.return_value.filter.return_value.scalar.return_value = 1.0
        
        availability, scheduled, downtime, event_count = calculate_availability(
            mock_db, product_id=1, shift_id=1, production_date=date(2025, 1, 15)
        )
        
        # Availability = (8 - 1) / 8 * 100 = 87.5%
        assert availability == Decimal('87.5')
        assert scheduled == Decimal('8.0')
        assert downtime == Decimal('1.0')

    def test_calculate_availability_no_shift(self):
        """Test availability with no shift data (defaults to 8 hours)"""
        from backend.calculations.availability import calculate_availability
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [0.5, 1]  # downtime, event_count
        
        availability, scheduled, downtime, event_count = calculate_availability(
            mock_db, product_id=1, shift_id=1, production_date=date(2025, 1, 15)
        )
        
        assert scheduled == Decimal('8.0')  # Default 8 hours

    def test_calculate_mtbf(self):
        """Test MTBF calculation"""
        from backend.calculations.availability import calculate_mtbf
        
        mock_db = MagicMock()
        
        # Mock failures
        mock_failure1 = MagicMock()
        mock_failure1.duration_hours = 2.0
        mock_failure2 = MagicMock()
        mock_failure2.duration_hours = 3.0
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_failure1, mock_failure2]
        
        result = calculate_mtbf(
            mock_db, machine_id="MACH-001",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10)
        )
        
        assert result is not None

    def test_calculate_mttr(self):
        """Test MTTR calculation"""
        from backend.calculations.availability import calculate_mttr
        
        mock_db = MagicMock()
        
        # Mock repairs
        mock_repair = MagicMock()
        mock_repair.duration_hours = 1.5
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_repair]
        
        result = calculate_mttr(
            mock_db, machine_id="MACH-001",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert result == Decimal('1.5')


# =============================================================================
# PERFORMANCE CALCULATION TESTS
# =============================================================================
class TestPerformanceCalculations:
    """Test performance calculation functions"""

    def test_calculate_performance_zero_runtime(self):
        """Test performance with zero runtime returns 0"""
        from backend.calculations.performance import calculate_performance
        
        mock_db = MagicMock()
        mock_entry = MagicMock()
        mock_entry.units_produced = 100
        mock_entry.run_time_hours = Decimal('0')
        mock_entry.product_id = 1
        mock_entry.entry_id = 1
        
        mock_product = MagicMock()
        mock_product.ideal_cycle_time = Decimal('0.05')
        mock_db.query.return_value.filter.return_value.first.return_value = mock_product
        
        performance, _, _ = calculate_performance(mock_db, mock_entry)
        
        assert performance == Decimal('0')

    def test_calculate_quality_rate(self):
        """Test quality rate calculation"""
        from backend.calculations.performance import calculate_quality_rate
        
        mock_entry = MagicMock()
        mock_entry.units_produced = Decimal('100')
        mock_entry.defect_count = Decimal('5')
        mock_entry.scrap_count = Decimal('3')
        
        rate = calculate_quality_rate(mock_entry)
        
        # Quality = (100 - 5 - 3) / 100 * 100 = 92%
        assert rate == Decimal('92.00')

    def test_calculate_quality_rate_zero_units(self):
        """Test quality rate with zero units"""
        from backend.calculations.performance import calculate_quality_rate
        
        mock_entry = MagicMock()
        mock_entry.units_produced = Decimal('0')
        mock_entry.defect_count = Decimal('0')
        mock_entry.scrap_count = Decimal('0')
        
        rate = calculate_quality_rate(mock_entry)
        assert rate == Decimal('0')


# =============================================================================
# FPY/RTY CALCULATION TESTS
# =============================================================================
class TestFPYRTYCalculations:
    """Test First Pass Yield and Rolled Throughput Yield calculations"""

    def test_calculate_fpy_basic(self):
        """Test basic FPY calculation"""
        from backend.calculations.fpy_rty import calculate_fpy
        
        mock_db = MagicMock()
        
        # Mock inspection: 100 units, 5 defects, 3 rework
        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 100
        mock_inspection.defects_found = 5
        mock_inspection.rework_units = 3
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_inspection]
        
        fpy, first_pass, total = calculate_fpy(
            mock_db, product_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # FPY = (100 - 5 - 3) / 100 * 100 = 92%
        assert fpy == Decimal('92')
        assert first_pass == 92
        assert total == 100

    def test_calculate_fpy_no_inspections(self):
        """Test FPY with no inspections"""
        from backend.calculations.fpy_rty import calculate_fpy
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        fpy, first_pass, total = calculate_fpy(
            mock_db, product_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert fpy == Decimal('0')
        assert first_pass == 0
        assert total == 0


# =============================================================================
# DPMO CALCULATION TESTS
# =============================================================================
class TestDPMOCalculations:
    """Test DPMO calculations"""

    def test_calculate_dpmo_basic(self):
        """Test basic DPMO calculation"""
        from backend.calculations.dpmo import calculate_dpmo
        
        mock_db = MagicMock()
        
        # Mock inspection: 1000 units, 5 defects
        mock_inspection = MagicMock()
        mock_inspection.units_inspected = 1000
        mock_inspection.defects_found = 5
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_inspection]
        
        dpmo, sigma, total_units, total_defects = calculate_dpmo(
            mock_db, product_id=1, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31),
            opportunities_per_unit=10
        )
        
        # DPMO = 5 / (1000 * 10) * 1,000,000 = 500
        assert dpmo == Decimal('500')
        assert total_units == 1000
        assert total_defects == 5

    def test_calculate_dpmo_no_inspections(self):
        """Test DPMO with no inspections"""
        from backend.calculations.dpmo import calculate_dpmo
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        dpmo, sigma, total_units, total_defects = calculate_dpmo(
            mock_db, product_id=1, shift_id=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert dpmo == Decimal('0')

    def test_calculate_sigma_level(self):
        """Test sigma level calculation"""
        from backend.calculations.dpmo import calculate_sigma_level
        
        # 3.4 DPMO = 6 Sigma
        sigma = calculate_sigma_level(Decimal('3.4'))
        assert sigma == Decimal('6.0')
        
        # 233 DPMO = 5 Sigma
        sigma = calculate_sigma_level(Decimal('233'))
        assert sigma == Decimal('5.0')
        
        # 6210 DPMO = 4 Sigma
        sigma = calculate_sigma_level(Decimal('6210'))
        assert sigma == Decimal('4.0')


# =============================================================================
# OTD CALCULATION TESTS
# =============================================================================
class TestOTDCalculations:
    """Test On-Time Delivery calculations"""

    def test_calculate_otd_basic(self):
        """Test basic OTD calculation"""
        from backend.calculations.otd import calculate_otd
        
        mock_db = MagicMock()
        
        # Mock entries: 2 confirmed (on-time), 1 not confirmed
        mock_entry1 = MagicMock()
        mock_entry1.confirmed_by = "User1"
        mock_entry2 = MagicMock()
        mock_entry2.confirmed_by = "User2"
        mock_entry3 = MagicMock()
        mock_entry3.confirmed_by = None
        
        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_entry1, mock_entry2, mock_entry3
        ]
        
        otd, on_time, total = calculate_otd(
            mock_db,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # OTD = 2/3 * 100 ≈ 66.67%
        assert total == 3
        assert on_time == 2

    def test_calculate_otd_no_entries(self):
        """Test OTD with no entries"""
        from backend.calculations.otd import calculate_otd
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        otd, on_time, total = calculate_otd(
            mock_db,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        assert otd == Decimal('0')
        assert total == 0


# =============================================================================
# WIP AGING CALCULATION TESTS
# =============================================================================
class TestWIPAgingCalculations:
    """Test WIP Aging calculations"""

    def test_calculate_wip_aging_empty(self):
        """Test WIP aging with no holds"""
        from backend.calculations.wip_aging import calculate_wip_aging
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = calculate_wip_aging(mock_db)
        
        assert result['total_held_quantity'] == 0
        assert result['total_hold_events'] == 0

    def test_calculate_wip_aging_basic(self):
        """Test basic WIP aging calculation"""
        from backend.calculations.wip_aging import calculate_wip_aging
        
        mock_db = MagicMock()
        
        # Mock hold: 5 days old, 100 units
        mock_hold = MagicMock()
        mock_hold.hold_date = date.today() - timedelta(days=5)
        mock_hold.quantity_held = 100
        mock_hold.quantity_released = 0
        mock_hold.quantity_scrapped = 0
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_hold]
        
        result = calculate_wip_aging(mock_db)
        
        assert result['total_held_quantity'] == 100
        assert result['aging_0_7_days'] == 100  # 5 days is in 0-7 bucket

    def test_calculate_hold_resolution_rate(self):
        """Test hold resolution rate"""
        from backend.calculations.wip_aging import calculate_hold_resolution_rate
        
        mock_db = MagicMock()
        
        # Mock hold resolved in 3 days
        mock_hold = MagicMock()
        mock_hold.hold_date = date(2025, 1, 1)
        mock_hold.release_date = date(2025, 1, 4)  # 3 days
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_hold]
        
        rate = calculate_hold_resolution_rate(
            mock_db,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        
        # Resolved within 7 days, so 100%
        assert rate == Decimal('100')


# =============================================================================
# TREND ANALYSIS TESTS
# =============================================================================
class TestTrendAnalysis:
    """Test trend analysis functions"""

    def test_calculate_moving_average(self):
        """Test moving average calculation"""
        from backend.calculations.trend_analysis import calculate_moving_average
        
        values = [Decimal('85.0'), Decimal('86.5'), Decimal('84.2'), Decimal('87.1'), Decimal('88.0')]
        result = calculate_moving_average(values, window=3)
        
        assert result[0] is None  # Not enough data
        assert result[1] is None  # Not enough data
        assert result[2] is not None  # First valid MA

    def test_linear_regression(self):
        """Test linear regression calculation"""
        from backend.calculations.trend_analysis import linear_regression
        
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [Decimal('85.0'), Decimal('86.5'), Decimal('87.0'), Decimal('88.5'), Decimal('90.0')]
        
        slope, intercept, r_squared = linear_regression(x, y)
        
        assert slope > 0  # Positive trend
        assert r_squared > Decimal('0.9')  # Good fit

    def test_detect_anomalies(self):
        """Test anomaly detection"""
        from backend.calculations.trend_analysis import detect_anomalies
        
        # Use more values to stabilize mean/std dev, with one clear outlier
        # Normal values cluster around 85-88, single anomaly at index 5
        values = [
            Decimal('85.0'), Decimal('86.5'), Decimal('84.2'),
            Decimal('87.0'), Decimal('86.0'), Decimal('200.0'),  # 200.0 is anomaly at index 5
            Decimal('85.5'), Decimal('87.5'), Decimal('86.8'),
            Decimal('85.2')
        ]
        anomalies = detect_anomalies(values, threshold_std=Decimal('2.0'))
        
        # With 10 values, mean ≈ 97.4, std ≈ 36.4, threshold = 72.8
        # |200.0 - 97.4| = 102.6 > 72.8, so index 5 should be flagged
        assert 5 in anomalies

    def test_analyze_trend(self):
        """Test comprehensive trend analysis"""
        from backend.calculations.trend_analysis import analyze_trend
        
        dates = [date(2025, 1, i) for i in range(1, 6)]
        values = [Decimal('85.0'), Decimal('86.5'), Decimal('87.0'), Decimal('88.5'), Decimal('90.0')]
        
        result = analyze_trend(dates, values)
        
        assert result.slope > 0
        assert result.trend_direction == 'increasing'


# =============================================================================
# PREDICTION TESTS
# =============================================================================
class TestPredictions:
    """Test prediction functions"""

    def test_simple_exponential_smoothing(self):
        """Test simple exponential smoothing"""
        from backend.calculations.predictions import simple_exponential_smoothing
        
        values = [Decimal('85.0'), Decimal('86.5'), Decimal('84.2'), Decimal('87.1'), Decimal('88.0')]
        result = simple_exponential_smoothing(values, forecast_periods=3)
        
        assert len(result.predictions) == 3
        assert result.method == "simple_exponential_smoothing"
        assert result.accuracy_score >= Decimal('0')

    def test_double_exponential_smoothing(self):
        """Test double exponential smoothing"""
        from backend.calculations.predictions import double_exponential_smoothing
        
        values = [Decimal('85.0'), Decimal('86.5'), Decimal('87.0'), Decimal('88.5'), Decimal('90.0')]
        result = double_exponential_smoothing(values, forecast_periods=3)
        
        assert len(result.predictions) == 3
        assert result.method == "double_exponential_smoothing"

    def test_auto_forecast(self):
        """Test automatic forecast selection"""
        from backend.calculations.predictions import auto_forecast
        
        values = [Decimal('85.0'), Decimal('86.5'), Decimal('84.2'), Decimal('87.1'), Decimal('88.0')]
        result = auto_forecast(values, forecast_periods=5)
        
        assert len(result.predictions) == 5
        assert result.method in [
            "simple_exponential_smoothing",
            "double_exponential_smoothing",
            "linear_trend_extrapolation"
        ]


# =============================================================================
# INFERENCE ENGINE TESTS
# =============================================================================
class TestInferenceEngine:
    """Test inference engine functions"""

    def test_infer_ideal_cycle_time_from_product(self):
        """Test cycle time inference from product"""
        from backend.calculations.inference import InferenceEngine
        
        mock_db = MagicMock()
        mock_product = MagicMock()
        mock_product.ideal_cycle_time = 0.25
        mock_db.query.return_value.filter.return_value.first.return_value = mock_product
        
        value, confidence, source, is_estimated = InferenceEngine.infer_ideal_cycle_time(mock_db, product_id=1)
        
        assert value == Decimal('0.25')
        assert confidence == 1.0
        assert source == "client_style_standard"
        assert is_estimated == False

    def test_infer_ideal_cycle_time_fallback(self):
        """Test cycle time inference fallback"""
        from backend.calculations.inference import InferenceEngine
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        
        value, confidence, source, is_estimated = InferenceEngine.infer_ideal_cycle_time(mock_db, product_id=1)
        
        assert value == Decimal('0.20')  # System fallback
        assert confidence == 0.3
        assert source == "system_fallback"
        assert is_estimated == True

    def test_flag_low_confidence(self):
        """Test low confidence flagging"""
        from backend.calculations.inference import InferenceEngine
        
        # Low confidence
        result = InferenceEngine.flag_low_confidence(0.5, threshold=0.7)
        assert result['warning'] == "LOW_CONFIDENCE_ESTIMATE"
        assert result['needs_review'] == True
        
        # High confidence
        result = InferenceEngine.flag_low_confidence(0.9, threshold=0.7)
        assert result['warning'] is None
        assert result['needs_review'] == False

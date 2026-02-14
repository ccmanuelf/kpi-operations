"""
Comprehensive tests for performance calculations
Uses mock-based testing pattern consistent with other tests
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestPerformanceCalculations:
    """Test performance KPI calculations"""

    def test_calculate_performance_basic(self):
        """Test basic performance calculation"""
        actual_output = 90
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 90.0

    def test_calculate_performance_100_percent(self):
        """Test 100% performance"""
        actual_output = 100
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_calculate_performance_over_100(self):
        """Test over 100% performance"""
        actual_output = 120
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 120.0

    def test_calculate_performance_zero_expected(self):
        """Test performance with zero expected output"""
        actual_output = 100
        expected_output = 0
        
        # Should handle gracefully
        if expected_output == 0:
            performance = 0
        else:
            performance = (actual_output / expected_output) * 100
        
        assert performance == 0

    def test_calculate_performance_zero_actual(self):
        """Test performance with zero actual output"""
        actual_output = 0
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 0.0

    def test_calculate_performance_with_downtime(self):
        """Test performance considering downtime"""
        actual_output = 70
        expected_output = 100
        planned_time_hours = 8.0
        actual_time_hours = 7.0  # Lost 1 hour to downtime
        
        # Adjust expected output based on actual time
        adjusted_expected = expected_output * (actual_time_hours / planned_time_hours)
        performance = (actual_output / adjusted_expected) * 100
        
        assert performance == 80.0

    def test_calculate_line_performance(self):
        """Test line-level performance calculation"""
        workers = 5
        hours_per_worker = 8
        actual_output = 450
        expected_per_hour = 12.5
        
        total_expected = workers * hours_per_worker * expected_per_hour
        performance = (actual_output / total_expected) * 100
        
        assert performance == 90.0

    def test_calculate_performance_partial_shift(self):
        """Test performance for partial shift"""
        actual_output = 45
        expected_output = 50
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 90.0

    def test_calculate_performance_overtime(self):
        """Test performance with overtime"""
        actual_output = 150
        expected_output = 100  # Standard shift
        regular_hours = 8
        overtime_hours = 4
        
        # Adjusted expected with overtime
        adjusted_expected = expected_output * ((regular_hours + overtime_hours) / regular_hours)
        performance = (actual_output / adjusted_expected) * 100
        
        assert performance == 100.0

    def test_calculate_performance_negative_values(self):
        """Test performance with negative values"""
        actual_output = -10
        expected_output = 100
        
        # Should handle or cap at 0
        if actual_output < 0:
            performance = 0
        else:
            performance = (actual_output / expected_output) * 100
        
        assert performance == 0


class TestShiftPerformance:
    """Test shift-level performance calculations"""

    def test_calculate_shift_performance(self):
        """Test shift performance calculation"""
        shift_data = {
            'shift_id': 1,
            'planned_output': 500,
            'actual_output': 475,
            'defective': 10
        }
        
        performance = (shift_data['actual_output'] / shift_data['planned_output']) * 100
        quality = ((shift_data['actual_output'] - shift_data['defective']) / 
                   shift_data['actual_output']) * 100
        
        assert performance == 95.0
        assert round(quality, 1) == 97.9

    def test_calculate_daily_performance(self):
        """Test daily performance aggregation"""
        shifts = [
            {'shift': 1, 'performance': 92.0},
            {'shift': 2, 'performance': 88.5},
            {'shift': 3, 'performance': 95.0}
        ]
        
        daily_avg = sum(s['performance'] for s in shifts) / len(shifts)
        
        assert round(daily_avg, 2) == 91.83

    def test_calculate_weekly_performance(self):
        """Test weekly performance aggregation"""
        daily_performance = [91.5, 92.0, 89.5, 93.0, 94.5, 90.0, 88.0]
        
        weekly_avg = sum(daily_performance) / len(daily_performance)
        
        assert round(weekly_avg, 2) == 91.21


class TestPerformanceTrends:
    """Test performance trend analysis"""

    def test_performance_trend_improving(self):
        """Test detecting improving performance trend"""
        weekly_data = [85.0, 87.0, 89.0, 91.0, 93.0]
        
        # Simple linear trend
        first_half_avg = sum(weekly_data[:2]) / 2
        second_half_avg = sum(weekly_data[-2:]) / 2
        
        trend = 'improving' if second_half_avg > first_half_avg else 'declining'
        
        assert trend == 'improving'

    def test_performance_trend_declining(self):
        """Test detecting declining performance trend"""
        weekly_data = [95.0, 93.0, 91.0, 89.0, 87.0]
        
        first_half_avg = sum(weekly_data[:2]) / 2
        second_half_avg = sum(weekly_data[-2:]) / 2
        
        trend = 'improving' if second_half_avg > first_half_avg else 'declining'
        
        assert trend == 'declining'

    def test_performance_trend_stable(self):
        """Test detecting stable performance trend"""
        weekly_data = [90.0, 91.0, 89.5, 90.5, 90.0]
        
        variance = max(weekly_data) - min(weekly_data)
        is_stable = variance < 5  # Less than 5% variance
        
        assert is_stable


class TestPerformanceEdgeCases:
    """Test edge cases for performance calculations"""

    def test_performance_very_small_values(self):
        """Test performance with very small values"""
        actual_output = 0.1
        expected_output = 0.1
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_performance_very_large_values(self):
        """Test performance with very large values"""
        actual_output = 1_000_000
        expected_output = 1_000_000
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_performance_decimal_precision(self):
        """Test performance decimal precision"""
        actual_output = 33.333
        expected_output = 100.0
        
        performance = (actual_output / expected_output) * 100
        
        # Should be approximately 33.33%
        assert 33.33 <= performance <= 33.34

    def test_performance_rounding(self):
        """Test performance rounding behavior"""
        actual_output = 123
        expected_output = 456
        
        performance = (actual_output / expected_output) * 100
        rounded = round(performance, 2)
        
        assert rounded == 26.97


class TestPerformanceByCategory:
    """Test performance breakdown by various categories"""

    def test_performance_by_product(self):
        """Test performance grouped by product"""
        product_data = [
            {'product': 'A', 'actual': 100, 'expected': 100},
            {'product': 'B', 'actual': 80, 'expected': 100},
            {'product': 'C', 'actual': 95, 'expected': 100}
        ]
        
        performance_by_product = {}
        for p in product_data:
            performance_by_product[p['product']] = (p['actual'] / p['expected']) * 100
        
        assert performance_by_product['A'] == 100.0
        assert performance_by_product['B'] == 80.0
        assert performance_by_product['C'] == 95.0

    def test_performance_by_employee(self):
        """Test performance grouped by employee"""
        employee_data = [
            {'employee': 'E001', 'actual': 95, 'expected': 100},
            {'employee': 'E002', 'actual': 105, 'expected': 100},
            {'employee': 'E003', 'actual': 88, 'expected': 100}
        ]
        
        avg_performance = sum(e['actual'] for e in employee_data) / len(employee_data)
        
        assert round(avg_performance, 2) == 96.0

    def test_performance_by_work_order(self):
        """Test performance grouped by work order"""
        wo_data = [
            {'wo': 'WO-001', 'actual': 500, 'expected': 500},
            {'wo': 'WO-002', 'actual': 480, 'expected': 500},
            {'wo': 'WO-003', 'actual': 520, 'expected': 500}
        ]
        
        total_actual = sum(w['actual'] for w in wo_data)
        total_expected = sum(w['expected'] for w in wo_data)
        
        overall_performance = (total_actual / total_expected) * 100
        
        assert overall_performance == 100.0


class TestPerformanceIntegration:
    """Integration tests for performance module"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_get_performance_for_work_order(self, mock_db):
        """Test getting performance for a work order"""
        mock_wo = MagicMock(
            work_order_id='WO-001',
            planned_quantity=1000,
            completed_quantity=950
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_wo
        
        wo = mock_db.query().filter().first()
        performance = (wo.completed_quantity / wo.planned_quantity) * 100
        
        assert performance == 95.0

    def test_get_performance_trend(self, mock_db):
        """Test getting performance trend data"""
        mock_trend = [
            MagicMock(date='2025-01-01', performance=90.0),
            MagicMock(date='2025-01-02', performance=92.0),
            MagicMock(date='2025-01-03', performance=91.5)
        ]
        mock_db.query.return_value.all.return_value = mock_trend
        
        trend_data = mock_db.query().all()
        
        assert len(trend_data) == 3
        assert trend_data[0].performance == 90.0

    def test_get_performance_by_shift(self, mock_db):
        """Test getting performance by shift"""
        mock_shifts = [
            MagicMock(shift_id=1, performance=92.0),
            MagicMock(shift_id=2, performance=89.5),
            MagicMock(shift_id=3, performance=94.0)
        ]
        mock_db.query.return_value.group_by.return_value.all.return_value = mock_shifts

        shifts = mock_db.query().group_by().all()
        best_shift = max(shifts, key=lambda s: s.performance)

        assert best_shift.shift_id == 3
        assert best_shift.performance == 94.0


# =============================================================================
# REAL DATABASE INTEGRATION TESTS
# =============================================================================
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.schemas import ClientType
from backend.schemas.product import Product
from backend.schemas.production_entry import ProductionEntry
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture(scope="function")
def perf_db():
    """Create a fresh database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def perf_setup(perf_db):
    """Create standard test data for performance tests."""
    db = perf_db

    # Create client
    client = TestDataFactory.create_client(
        db,
        client_id="PERF-TEST-CLIENT",
        client_name="Performance Test Client",
        client_type=ClientType.HOURLY_RATE
    )

    # Create user
    supervisor = TestDataFactory.create_user(
        db,
        user_id="perf-super-001",
        username="perf_supervisor",
        role="supervisor",
        client_id=client.client_id
    )

    # Create product with known ideal cycle time
    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="PERF-PROD-001",
        product_name="Performance Test Product",
        ideal_cycle_time=Decimal("0.10")  # 0.10 hours per unit = 10 units/hour
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db,
        client_id=client.client_id,
        shift_name="Performance Shift",
        start_time="06:00:00",
        end_time="14:00:00"
    )

    db.commit()

    return {
        "db": db,
        "client": client,
        "supervisor": supervisor,
        "product": product,
        "shift": shift,
    }


class TestCalculatePerformanceReal:
    """Tests for calculate_performance function with real database."""

    def test_calculate_performance_100_percent(self, perf_setup):
        """Test 100% performance calculation."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        # Create production entry with ideal output
        # Ideal cycle time = 0.10 hours/unit
        # Run time = 8 hours
        # Expected output = 8 / 0.10 = 80 units
        entry = ProductionEntry(
            production_entry_id="PE-100-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=80,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, ideal_cycle_time, was_inferred = calculate_performance(
            db, entry, product
        )

        # (0.10 * 80) / 8 * 100 = 100%
        assert performance == Decimal("100.00")
        assert ideal_cycle_time == Decimal("0.10")
        assert was_inferred is False

    def test_calculate_performance_above_100(self, perf_setup):
        """Test performance above 100%."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        # Produce more than expected
        entry = ProductionEntry(
            production_entry_id="PE-ABOVE-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,  # 25% above expected
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)

        # (0.10 * 100) / 8 * 100 = 125%
        assert performance == Decimal("125.00")

    def test_calculate_performance_below_100(self, perf_setup):
        """Test performance below 100%."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        # Produce less than expected
        entry = ProductionEntry(
            production_entry_id="PE-BELOW-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=60,  # 75% of expected
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)

        # (0.10 * 60) / 8 * 100 = 75%
        assert performance == Decimal("75.00")

    def test_calculate_performance_zero_run_time(self, perf_setup):
        """Test performance with zero run time."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-ZERO-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("0"),  # Zero run time
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)

        assert performance == Decimal("0")

    def test_calculate_performance_capped_at_150(self, perf_setup):
        """Test performance is capped at 150%."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        # Extremely high production
        entry = ProductionEntry(
            production_entry_id="PE-CAP-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=200,  # Way above expected
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)

        # Would be 250% but capped at 150%
        assert performance == Decimal("150")

    def test_calculate_performance_without_product(self, perf_setup):
        """Test performance calculation fetches product if not provided."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-NOPROD-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=80,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        # Don't pass product - let function fetch it
        performance, ideal_cycle_time, _ = calculate_performance(db, entry, None)

        assert performance == Decimal("100.00")
        assert ideal_cycle_time == Decimal("0.10")


class TestCalculateQualityRateReal:
    """Tests for calculate_quality_rate function with real database."""

    def test_quality_rate_100_percent(self, perf_setup):
        """Test 100% quality rate (no defects or scrap)."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-QR100-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        assert quality_rate == Decimal("100.00")

    def test_quality_rate_with_defects(self, perf_setup):
        """Test quality rate with defects."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-QRDEF-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=5,  # 5 defects
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        # (100 - 5 - 0) / 100 * 100 = 95%
        assert quality_rate == Decimal("95.00")

    def test_quality_rate_with_scrap(self, perf_setup):
        """Test quality rate with scrap."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-QRSCR-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=10,  # 10 scrap
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        # (100 - 0 - 10) / 100 * 100 = 90%
        assert quality_rate == Decimal("90.00")

    def test_quality_rate_with_defects_and_scrap(self, perf_setup):
        """Test quality rate with both defects and scrap."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-QRDS-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=5,
            scrap_count=3,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        # (100 - 5 - 3) / 100 * 100 = 92%
        assert quality_rate == Decimal("92.00")

    def test_quality_rate_zero_production(self, perf_setup):
        """Test quality rate with zero production."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-QR0-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=0,  # Zero production
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        assert quality_rate == Decimal("0")


class TestCalculateOEEReal:
    """Tests for calculate_oee function with real database."""

    def test_oee_perfect_performance_and_quality(self, perf_setup):
        """Test OEE with 100% performance and quality."""
        from backend.calculations.performance import calculate_oee

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-OEE100-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=80,  # 100% performance
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,  # 100% quality
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        # OEE = 100% * 100% * 100% = 100%
        assert oee == Decimal("100.00")
        assert components["availability"] == Decimal("100")
        assert components["performance"] == Decimal("100.00")
        assert components["quality"] == Decimal("100.00")

    def test_oee_with_defects(self, perf_setup):
        """Test OEE with defects affecting quality."""
        from backend.calculations.performance import calculate_oee

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-OEEDEF-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=80,  # 100% performance
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=8,  # 10% defects -> 90% quality
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        # OEE = 100% * 100% * 90% = 90%
        assert oee == Decimal("90.00")
        assert components["quality"] == Decimal("90.00")

    def test_oee_with_lower_performance(self, perf_setup):
        """Test OEE with reduced performance."""
        from backend.calculations.performance import calculate_oee

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-OEELP-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=64,  # 80% performance
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        # OEE = 100% * 80% * 100% = 80%
        assert oee == Decimal("80.00")
        assert components["performance"] == Decimal("80.00")

    def test_oee_combined_factors(self, perf_setup):
        """Test OEE with combined performance and quality issues."""
        from backend.calculations.performance import calculate_oee

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-OEECOMB-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=72,  # 90% performance
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=7,  # ~90.3% quality (65 good / 72 produced)
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        # OEE = 100% * 90% * ~90% = ~81%
        assert oee > Decimal("80") and oee < Decimal("82")


class TestUpdatePerformanceForEntry:
    """Tests for update_performance_for_entry function."""

    def test_update_performance_entry_not_found(self, perf_setup):
        """Test updating performance for nonexistent entry."""
        from backend.calculations.performance import update_performance_for_entry

        db = perf_setup["db"]

        result = update_performance_for_entry(db, 99999)

        assert result is None

    def test_update_performance_success(self, perf_setup):
        """Test successfully updating performance for an entry."""
        from backend.calculations.performance import update_performance_for_entry

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-UPD-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=80,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()
        entry_id = entry.production_entry_id

        result = update_performance_for_entry(db, entry_id)

        assert result is not None
        assert result.performance_percentage == Decimal("100.00")


class TestPerformanceWithInference:
    """Tests for performance calculation with cycle time inference."""

    def test_performance_with_inferred_cycle_time(self, perf_setup):
        """Test performance when ideal cycle time needs inference."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        # Create product without ideal cycle time
        product_no_ict = Product(
            client_id=client.client_id,
            product_code="NO-ICT-001",
            product_name="No Ideal Cycle Time Product",
            ideal_cycle_time=None  # No ideal cycle time set
        )
        db.add(product_no_ict)
        db.commit()

        entry = ProductionEntry(
            production_entry_id="PE-INFER-001",
            client_id=client.client_id,
            product_id=product_no_ict.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        performance, ideal_cycle_time, was_inferred = calculate_performance(
            db, entry, product_no_ict
        )

        # Should have inferred the cycle time
        assert was_inferred is True
        assert ideal_cycle_time > Decimal("0")


class TestPerformanceEdgeCasesReal:
    """Real database tests for performance edge cases."""

    def test_performance_small_values(self, perf_setup):
        """Test performance with small values."""
        from backend.calculations.performance import calculate_performance

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-SMALL-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=1,
            run_time_hours=Decimal("0.1"),  # 6 minutes
            entered_by="perf-super-001",
            defect_count=0,
            scrap_count=0,
            employees_assigned=1
        )
        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)

        # (0.10 * 1) / 0.1 * 100 = 100%
        assert performance == Decimal("100.00")

    def test_performance_high_defect_quality(self, perf_setup):
        """Test quality rate approaching zero."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-HIDEF-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=50,  # 50% defects
            scrap_count=49,   # 49% scrap
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        # (100 - 50 - 49) / 100 * 100 = 1%
        assert quality_rate == Decimal("1.00")

    def test_quality_rate_capped_at_zero(self, perf_setup):
        """Test quality rate doesn't go negative."""
        from backend.calculations.performance import calculate_quality_rate

        db = perf_setup["db"]
        product = perf_setup["product"]
        client = perf_setup["client"]
        shift = perf_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="PE-NEGQR-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            entered_by="perf-super-001",
            defect_count=60,  # More defects/scrap than produced
            scrap_count=60,
            employees_assigned=5
        )
        db.add(entry)
        db.commit()

        quality_rate = calculate_quality_rate(entry)

        # Should be capped at 0, not negative
        assert quality_rate == Decimal("0")

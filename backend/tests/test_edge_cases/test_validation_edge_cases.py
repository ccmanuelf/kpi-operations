"""
Edge Case Tests: Validation, Constraints, and Auth Errors
Task #42: Comprehensive testing of boundary conditions and error scenarios
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def edge_db():
    """Create a fresh database for edge case tests."""
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
def edge_setup(edge_db):
    """Create standard test data for edge case tests."""
    db = edge_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="EDGE-CLIENT-001", client_name="Edge Test Client", client_type=ClientType.HOURLY_RATE
    )

    # Create admin user
    admin = TestDataFactory.create_user(
        db, user_id="edge-admin-001", username="edge_admin", role="admin", client_id=None
    )

    # Create supervisor
    supervisor = TestDataFactory.create_user(
        db, user_id="edge-super-001", username="edge_supervisor", role="supervisor", client_id=client.client_id
    )

    # Create operator (limited access)
    operator = TestDataFactory.create_user(
        db, user_id="edge-oper-001", username="edge_operator", role="operator", client_id=client.client_id
    )

    # Create product
    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="EDGE-PROD-001",
        product_name="Edge Test Product",
        ideal_cycle_time=Decimal("0.10"),
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db, client_id=client.client_id, shift_name="Edge Test Shift", start_time="06:00:00", end_time="14:00:00"
    )

    db.commit()

    return {
        "db": db,
        "client": client,
        "admin": admin,
        "supervisor": supervisor,
        "operator": operator,
        "product": product,
        "shift": shift,
    }


# =============================================================================
# Numeric Boundary Tests
# =============================================================================


class TestNumericBoundaries:
    """Test numeric field boundary conditions."""

    def test_units_produced_zero(self, edge_setup):
        """Test zero units produced edge case."""
        from backend.calculations.performance import calculate_quality_rate
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # Create entry with zero units
        entry = ProductionEntry(
            production_entry_id="EDGE-ZERO-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=0,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="edge-super-001",
        )

        quality_rate = calculate_quality_rate(entry)
        assert quality_rate == Decimal("0")

    def test_run_time_zero_performance(self, edge_setup):
        """Test zero run time in performance calculation."""
        from backend.calculations.performance import calculate_performance
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="EDGE-RUNZERO-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("0"),  # Zero run time
            employees_assigned=5,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        performance, cycle_time, was_inferred = calculate_performance(db, entry, product)
        assert performance == Decimal("0")

    def test_performance_capped_at_150(self, edge_setup):
        """Test performance is capped at 150%."""
        from backend.calculations.performance import calculate_performance
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # Create entry that would calculate > 150% performance
        entry = ProductionEntry(
            production_entry_id="EDGE-CAP-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=10000,  # Very high output
            run_time_hours=Decimal("1.0"),  # Very short time
            employees_assigned=1,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)
        assert performance <= Decimal("150")

    def test_quality_rate_negative_good_units(self, edge_setup):
        """Test quality rate when defects+scrap > units_produced."""
        from backend.calculations.performance import calculate_quality_rate
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # More defects than units (edge case)
        entry = ProductionEntry(
            production_entry_id="EDGE-NEG-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=10,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=8,
            scrap_count=5,  # Total 13 > 10 units
            entered_by="edge-super-001",
        )

        quality_rate = calculate_quality_rate(entry)
        # Should return 0, not negative
        assert quality_rate >= Decimal("0")

    def test_decimal_precision_in_calculations(self, edge_setup):
        """Test decimal precision is maintained in calculations."""
        from backend.calculations.performance import calculate_performance
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.product import Product

        db = edge_setup["db"]
        client = edge_setup["client"]
        shift = edge_setup["shift"]

        # Create product with precise cycle time
        product = Product(
            product_id=9999,
            client_id=client.client_id,
            product_code="PREC-PROD",
            product_name="Precision Product",
            ideal_cycle_time=Decimal("0.0001"),  # Very small
        )
        db.add(product)
        db.commit()

        entry = ProductionEntry(
            production_entry_id="EDGE-PREC-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=1,
            run_time_hours=Decimal("0.0001"),
            employees_assigned=1,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        performance, _, _ = calculate_performance(db, entry, product)
        # Should be a valid Decimal, not NaN or Infinity
        assert isinstance(performance, Decimal)
        assert performance.is_finite()


class TestDateBoundaries:
    """Test date-related boundary conditions."""

    def test_date_range_same_day(self, edge_setup):
        """Test calculations with same start and end date."""
        from backend.calculations.otd import calculate_otd

        db = edge_setup["db"]
        today = date.today()

        # Same day range
        otd_pct, on_time, total = calculate_otd(db, today, today)

        assert isinstance(otd_pct, Decimal)
        assert total >= 0

    def test_date_range_very_wide(self, edge_setup):
        """Test calculations with very wide date range."""
        from backend.calculations.otd import calculate_otd

        db = edge_setup["db"]
        start = date(2020, 1, 1)
        end = date(2030, 12, 31)

        otd_pct, on_time, total = calculate_otd(db, start, end)

        assert isinstance(otd_pct, Decimal)

    def test_production_date_in_future(self, edge_setup):
        """Test production entry with future date."""
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        future_date = date.today() + timedelta(days=30)

        entry = ProductionEntry(
            production_entry_id="EDGE-FUTURE-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=future_date,
            shift_date=future_date,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        # Should be saved successfully
        assert entry.production_entry_id == "EDGE-FUTURE-001"


# =============================================================================
# OEE Edge Cases
# =============================================================================


class TestOEEEdgeCases:
    """Test OEE calculation edge cases."""

    def test_oee_all_zero(self, edge_setup):
        """Test OEE with all zero values."""
        from backend.calculations.performance import calculate_oee
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="EDGE-OEE-ZERO",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=0,
            run_time_hours=Decimal("0"),
            employees_assigned=5,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        assert oee == Decimal("0")
        assert "quality" in components
        assert "performance" in components

    def test_oee_perfect_quality_no_defects(self, edge_setup):
        """Test OEE with perfect quality (no defects)."""
        from backend.calculations.performance import calculate_oee
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        entry = ProductionEntry(
            production_entry_id="EDGE-OEE-PERF",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        oee, components = calculate_oee(db, entry, product)

        assert components["quality"] == Decimal("100.00")


# =============================================================================
# Trend Analysis Edge Cases
# =============================================================================


class TestTrendAnalysisEdgeCases:
    """Test trend analysis edge cases."""

    def test_moving_average_single_value(self):
        """Test moving average with single value."""
        from backend.calculations.trend_analysis import calculate_moving_average

        values = [Decimal("100")]
        result = calculate_moving_average(values, window=3)

        assert len(result) == 1
        # With window=3 and only 1 value, result should be None
        assert result[0] is None

    def test_moving_average_window_larger_than_data(self):
        """Test moving average with window larger than data."""
        from backend.calculations.trend_analysis import calculate_moving_average

        values = [Decimal("100"), Decimal("110")]
        result = calculate_moving_average(values, window=5)

        assert len(result) == 2
        assert all(v is None for v in result)

    def test_ema_single_value(self):
        """Test EMA with single value."""
        from backend.calculations.trend_analysis import calculate_exponential_moving_average

        values = [Decimal("100")]
        result = calculate_exponential_moving_average(values, alpha=Decimal("0.5"))

        assert len(result) == 1
        assert result[0] == Decimal("100")

    def test_linear_regression_two_points(self):
        """Test linear regression with minimum data (2 points)."""
        from backend.calculations.trend_analysis import linear_regression

        x = [1.0, 2.0]
        y = [Decimal("100"), Decimal("110")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert float(slope) == pytest.approx(10.0, rel=0.001)
        assert float(r_squared) == pytest.approx(1.0, rel=0.001)

    def test_linear_regression_all_same_y(self):
        """Test linear regression with all same Y values."""
        from backend.calculations.trend_analysis import linear_regression

        x = [1.0, 2.0, 3.0, 4.0]
        y = [Decimal("100")] * 4

        slope, intercept, r_squared = linear_regression(x, y)

        assert float(slope) == pytest.approx(0.0, abs=0.001)

    def test_detect_anomalies_all_same(self):
        """Test anomaly detection with all same values."""
        from backend.calculations.trend_analysis import detect_anomalies

        values = [Decimal("100")] * 10
        anomalies = detect_anomalies(values)

        assert anomalies == []

    def test_detect_anomalies_too_few_values(self):
        """Test anomaly detection with insufficient data."""
        from backend.calculations.trend_analysis import detect_anomalies

        values = [Decimal("100"), Decimal("200")]
        anomalies = detect_anomalies(values)

        assert anomalies == []


# =============================================================================
# Efficiency Calculation Edge Cases
# =============================================================================


class TestEfficiencyEdgeCases:
    """Test efficiency calculation edge cases."""

    def test_efficiency_zero_employees(self, edge_setup):
        """Test efficiency with inference chain for employees."""
        from backend.calculations.efficiency import calculate_efficiency
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # Entry with 0 employees (should use inference)
        entry = ProductionEntry(
            production_entry_id="EDGE-EFF-ZERO",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=0,  # Zero employees
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        efficiency, _, was_inferred = calculate_efficiency(db, entry, product)

        # Should use default employees via inference
        assert efficiency >= Decimal("0")
        assert was_inferred is True

    def test_shift_hours_overnight(self, edge_setup):
        """Test shift hours calculation for overnight shift."""
        from backend.calculations.efficiency import calculate_shift_hours
        from datetime import time

        # 11pm to 7am overnight shift
        start = time(23, 0)
        end = time(7, 0)

        hours = calculate_shift_hours(start, end)

        assert hours == Decimal("8.0")

    def test_shift_hours_same_time(self, edge_setup):
        """Test shift hours when start equals end."""
        from backend.calculations.efficiency import calculate_shift_hours
        from datetime import time

        start = time(8, 0)
        end = time(8, 0)

        hours = calculate_shift_hours(start, end)

        # Same time = 0 or 24 hours (edge case)
        assert hours in [Decimal("0"), Decimal("24")]


# =============================================================================
# Inference Chain Edge Cases
# =============================================================================


class TestInferenceChainEdgeCases:
    """Test inference chain edge cases."""

    def test_infer_employees_no_historical_data(self, edge_setup):
        """Test employee inference with no historical data."""
        from backend.calculations.efficiency import infer_employees_count
        from backend.schemas.production_entry import ProductionEntry

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # Entry with no employees assigned and no historical data
        entry = ProductionEntry(
            production_entry_id="EDGE-INFER-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=0,
            entered_by="edge-super-001",
        )

        db.add(entry)
        db.commit()

        result = infer_employees_count(db, entry)

        assert result.count >= 1  # Should use default
        assert result.is_inferred is True
        assert result.inference_source == "default"

    def test_infer_cycle_time_no_product(self, edge_setup):
        """Test cycle time inference when product has no ideal_cycle_time."""
        from backend.calculations.efficiency import infer_ideal_cycle_time
        from backend.schemas.product import Product

        db = edge_setup["db"]

        # Create product without ideal cycle time
        product = Product(
            product_id=8888,
            client_id=edge_setup["client"].client_id,
            product_code="NO-ICT-PROD",
            product_name="No Ideal Cycle Time",
            ideal_cycle_time=None,
        )
        db.add(product)
        db.commit()

        cycle_time, was_inferred = infer_ideal_cycle_time(db, product.product_id)

        assert cycle_time > Decimal("0")
        assert was_inferred is True


# =============================================================================
# Client Config Edge Cases
# =============================================================================


class TestClientConfigEdgeCases:
    """Test client configuration edge cases."""

    def test_get_config_nonexistent_client(self, edge_setup):
        """Test getting config for non-existent client."""
        from backend.crud.client_config import get_client_config_or_defaults

        db = edge_setup["db"]

        config = get_client_config_or_defaults(db, "NONEXISTENT-CLIENT-999")

        # Should return defaults, not None or error
        assert config is not None
        assert isinstance(config, dict)

    def test_get_config_null_client_id(self, edge_setup):
        """Test getting config with null client ID."""
        from backend.crud.client_config import get_client_config_or_defaults

        db = edge_setup["db"]

        config = get_client_config_or_defaults(db, None)

        # Should return defaults
        assert config is not None


# =============================================================================
# Unique Constraint Edge Cases
# =============================================================================


class TestUniqueConstraints:
    """Test unique constraint violations."""

    def test_duplicate_production_entry_id(self, edge_setup):
        """Test creating duplicate production entry ID."""
        from backend.schemas.production_entry import ProductionEntry
        from sqlalchemy.exc import IntegrityError
        import warnings

        db = edge_setup["db"]
        client = edge_setup["client"]
        product = edge_setup["product"]
        shift = edge_setup["shift"]

        # First entry
        entry1 = ProductionEntry(
            production_entry_id="DUPLICATE-001",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="edge-super-001",
        )
        db.add(entry1)
        db.commit()

        # Expunge to clear identity map so we can test DB-level constraint
        db.expunge(entry1)

        # Duplicate entry - test the database constraint
        entry2 = ProductionEntry(
            production_entry_id="DUPLICATE-001",  # Same ID
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="edge-super-001",
        )
        db.add(entry2)

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()

    def test_duplicate_work_order_id(self, edge_setup):
        """Test creating duplicate work order ID."""
        from backend.schemas.work_order import WorkOrder, WorkOrderStatus
        from sqlalchemy.exc import IntegrityError

        db = edge_setup["db"]
        client = edge_setup["client"]

        # First work order
        wo1 = WorkOrder(
            work_order_id="DUP-WO-001",
            client_id=client.client_id,
            style_model="STYLE-A",
            planned_quantity=100,
            status=WorkOrderStatus.ACTIVE,
        )
        db.add(wo1)
        db.commit()

        # Expunge to clear identity map so we can test DB-level constraint
        db.expunge(wo1)

        # Duplicate work order
        wo2 = WorkOrder(
            work_order_id="DUP-WO-001",  # Same ID
            client_id=client.client_id,
            style_model="STYLE-B",
            planned_quantity=200,
            status=WorkOrderStatus.ACTIVE,
        )
        db.add(wo2)

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()

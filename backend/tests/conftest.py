"""
Pytest Configuration and Fixtures
Shared test fixtures for all test modules
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import date, datetime, timedelta
from decimal import Decimal
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import Base
from backend.schemas.user import User, UserRole
from backend.schemas.production import ProductionEntry
from backend.schemas.quality import QualityInspection
from backend.schemas.downtime import Downtime
from backend.schemas.attendance import Attendance
from backend.schemas.hold import Hold


# Test Database Setup
@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create database session for tests"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# User Fixtures
@pytest.fixture
def admin_user():
    """Create admin user for testing"""
    return User(
        user_id=1,
        username="admin",
        email="admin@test.com",
        role=UserRole.ADMIN,
        client_id_assigned=None,  # Admin can access all clients
        is_active=True
    )


@pytest.fixture
def operator_user_client_a():
    """Create operator user for CLIENT-A"""
    return User(
        user_id=2,
        username="operator_a",
        email="operator_a@test.com",
        role=UserRole.OPERATOR,
        client_id_assigned="CLIENT-A",
        is_active=True
    )


@pytest.fixture
def operator_user_client_b():
    """Create operator user for CLIENT-B"""
    return User(
        user_id=3,
        username="operator_b",
        email="operator_b@test.com",
        role=UserRole.OPERATOR,
        client_id_assigned="CLIENT-B",
        is_active=True
    )


@pytest.fixture
def leader_user_multi_client():
    """Create leader user with access to multiple clients"""
    return User(
        user_id=4,
        username="leader_multi",
        email="leader@test.com",
        role=UserRole.LEADER,
        client_id_assigned="CLIENT-A,CLIENT-B",
        is_active=True
    )


# Production Test Data
@pytest.fixture
def sample_production_entry():
    """Sample production entry with known values for KPI calculation"""
    return {
        "entry_id": 1,
        "client_id": "CLIENT-A",
        "product_id": 101,
        "shift_id": 1,
        "work_order_number": "WO-2024-001",
        "production_date": date(2024, 1, 15),
        "units_produced": 1000,
        "employees_assigned": 5,
        "run_time_hours": 8.0,
        "ideal_cycle_time": 0.01,  # 0.01 hrs per unit (36 seconds)
        "shift_start": "07:00:00",
        "shift_end": "15:00:00",  # 8-hour shift
    }


@pytest.fixture
def sample_quality_data():
    """Sample quality inspection data"""
    return {
        "inspection_id": 1,
        "client_id": "CLIENT-A",
        "product_id": 101,
        "shift_id": 1,
        "inspection_date": date(2024, 1, 15),
        "units_inspected": 1000,
        "defects_found": 5,
        "defect_category": "VISUAL",
        "defect_type": "THREAD_LOOSE",
        "scrap_units": 2,
        "rework_units": 3,
    }


@pytest.fixture
def sample_downtime_entry():
    """Sample downtime entry"""
    return {
        "downtime_id": 1,
        "client_id": "CLIENT-A",
        "production_line": "LINE-A",
        "downtime_date": date(2024, 1, 15),
        "downtime_start": datetime(2024, 1, 15, 10, 0),
        "downtime_end": datetime(2024, 1, 15, 10, 30),
        "downtime_minutes": 30,
        "downtime_category": "EQUIPMENT",
        "downtime_reason": "MACHINE_BREAKDOWN",
    }


@pytest.fixture
def sample_attendance_entry():
    """Sample attendance entry"""
    return {
        "attendance_id": 1,
        "client_id": "CLIENT-A",
        "employee_id": "EMP-001",
        "attendance_date": date(2024, 1, 15),
        "shift_id": 1,
        "scheduled_hours": 8.0,
        "actual_hours": 8.0,
        "absence_hours": 0.0,
        "absence_reason": None,
    }


# Expected KPI Results (based on CSV specifications)
@pytest.fixture
def expected_efficiency():
    """
    Expected efficiency calculation:
    Formula: (Units × Cycle Time) / (Employees × Scheduled Hours) × 100
    = (1000 × 0.01) / (5 × 8) × 100
    = 10 / 40 × 100
    = 25.0%
    """
    return 25.0


@pytest.fixture
def expected_performance():
    """
    Expected performance calculation:
    Formula: (Ideal Cycle Time × Units) / Run Time × 100
    = (0.01 × 1000) / 8.0 × 100
    = 10 / 8 × 100
    = 125.0%
    """
    return 125.0


@pytest.fixture
def expected_ppm():
    """
    Expected PPM calculation:
    Formula: (Defects / Units Inspected) × 1,000,000
    = (5 / 1000) × 1,000,000
    = 5000 PPM
    """
    return 5000.0


@pytest.fixture
def expected_dpmo():
    """
    Expected DPMO calculation (10 opportunities per unit):
    Formula: (Defects / (Units × Opportunities)) × 1,000,000
    = (5 / (1000 × 10)) × 1,000,000
    = (5 / 10000) × 1,000,000
    = 500 DPMO
    """
    return 500.0


@pytest.fixture
def expected_availability():
    """
    Expected availability calculation:
    Formula: 1 - (Downtime Hours / Planned Production Hours)
    = 1 - (0.5 / 8.0)
    = 1 - 0.0625
    = 0.9375 = 93.75%
    """
    return 93.75


# Test Data Factories
class TestDataFactory:
    """Factory for generating test data"""

    @staticmethod
    def create_production_entries(
        db: Session,
        count: int,
        client_id: str = "CLIENT-A",
        base_date: date = None
    ):
        """Create multiple production entries"""
        if base_date is None:
            base_date = date(2024, 1, 1)

        entries = []
        for i in range(count):
            entry = ProductionEntry(
                client_id=client_id,
                product_id=101,
                shift_id=1,
                work_order_number=f"WO-2024-{i:03d}",
                production_date=base_date + timedelta(days=i),
                units_produced=1000 + (i * 10),
                employees_assigned=5,
                run_time_hours=8.0,
            )
            db.add(entry)
            entries.append(entry)

        db.commit()
        return entries

    @staticmethod
    def create_quality_inspections(
        db: Session,
        count: int,
        client_id: str = "CLIENT-A",
        defect_rate: float = 0.005  # 0.5% default
    ):
        """Create multiple quality inspections"""
        inspections = []
        for i in range(count):
            units = 1000
            defects = int(units * defect_rate)

            inspection = QualityInspection(
                client_id=client_id,
                product_id=101,
                shift_id=1,
                inspection_date=date(2024, 1, 1) + timedelta(days=i),
                units_inspected=units,
                defects_found=defects,
                defect_category="VISUAL",
                scrap_units=defects // 2,
                rework_units=defects - (defects // 2),
            )
            db.add(inspection)
            inspections.append(inspection)

        db.commit()
        return inspections


@pytest.fixture
def test_data_factory():
    """Provide test data factory"""
    return TestDataFactory


# Assertion Helpers
def assert_decimal_equal(actual: Decimal, expected: float, tolerance: float = 0.01):
    """Assert decimal values are equal within tolerance"""
    assert abs(float(actual) - expected) <= tolerance, \
        f"Expected {expected} ± {tolerance}, got {float(actual)}"


def assert_percentage_equal(actual: float, expected: float, tolerance: float = 0.1):
    """Assert percentage values are equal within tolerance"""
    assert abs(actual - expected) <= tolerance, \
        f"Expected {expected}% ± {tolerance}%, got {actual}%"

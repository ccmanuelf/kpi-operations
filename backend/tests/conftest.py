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

# Add project root to path (parent of backend)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.database import Base, get_db

# Import ALL schemas to ensure tables are created in the correct order
# This is critical for foreign key relationships to work
from backend.schemas import (
    # Core foundation (must be first - no FK dependencies)
    Client, ClientType,
    User, UserRole,
    Employee,
    FloatingPool,
    # Work order management
    WorkOrder, WorkOrderStatus,
    Job,
    PartOpportunities,
    # Phase 1: Production tracking
    Product,
    Shift,
    ProductionEntry,
    # Phase 2: WIP & Downtime
    HoldEntry, HoldStatus,
    DowntimeEntry,
    # Phase 3: Attendance
    AttendanceEntry, AbsenceType,
    CoverageEntry,
    # Phase 4: Quality
    QualityEntry,
    DefectDetail, DefectType,
)

# Import log for batch imports
from backend.schemas.import_log import ImportLog

# Backward compatibility aliases - use the correct _entry schemas
QualityInspection = QualityEntry
Downtime = DowntimeEntry
DowntimeEvent = DowntimeEntry  # Alias for dead schema name
Attendance = AttendanceEntry
Hold = HoldEntry
WIPHold = HoldEntry  # Alias for dead schema name
WIPHoldStatus = HoldStatus  # Alias for dead status enum


# Disable rate limiting for tests
@pytest.fixture(autouse=True)
def disable_rate_limit():
    """Disable rate limiter for all tests to prevent rate limit errors"""
    try:
        from backend.middleware.rate_limit import limiter
        # Set very high limits for tests
        original_enabled = limiter.enabled
        limiter.enabled = False
        yield
        limiter.enabled = original_enabled
    except Exception:
        yield  # Ignore if rate limiter is not available


# Test Database Engine (shared across tests)
TEST_DATABASE_URL = "sqlite:///:memory:"

_test_engine = None
_TestingSessionLocal = None


def get_test_engine():
    """Get or create test engine singleton"""
    global _test_engine, _TestingSessionLocal
    if _test_engine is None:
        _test_engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # CRITICAL: Drop all tables first to avoid index conflicts
        # This prevents 'index ix_CLIENT_client_id already exists' errors
        Base.metadata.drop_all(bind=_test_engine)
        Base.metadata.create_all(bind=_test_engine)
        _TestingSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_test_engine
        )
    return _test_engine


def get_test_db():
    """Dependency override for get_db"""
    engine = get_test_engine()
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


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
            prod_date = datetime.combine(base_date + timedelta(days=i), datetime.min.time())
            entry = ProductionEntry(
                production_entry_id=f"PE-{client_id}-{i:03d}",
                client_id=client_id,
                product_id=101,
                shift_id=1,
                production_date=prod_date,
                shift_date=prod_date,
                units_produced=1000 + (i * 10),
                employees_assigned=5,
                run_time_hours=8.0,
                entered_by=1,  # Test user ID
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
            shift_dt = datetime.combine(date(2024, 1, 1) + timedelta(days=i), datetime.min.time())

            inspection = QualityInspection(
                quality_entry_id=f"QE-{client_id}-{i:03d}",
                client_id=client_id,
                work_order_id=f"WO-{client_id}-001",  # Placeholder work order
                shift_date=shift_dt,
                inspection_date=shift_dt,
                units_inspected=units,
                units_passed=units - defects,
                units_defective=defects,
                total_defects_count=defects,
                units_scrapped=defects // 2,
                units_reworked=defects - (defects // 2),
            )
            db.add(inspection)
            inspections.append(inspection)

        db.commit()
        return inspections


@pytest.fixture
def test_data_factory():
    """Provide test data factory - uses enhanced fixtures"""
    from backend.tests.fixtures.factories import TestDataFactory as EnhancedFactory
    return EnhancedFactory


# Assertion Helpers
def assert_decimal_equal(actual: Decimal, expected: float, tolerance: float = 0.01):
    """Assert decimal values are equal within tolerance"""
    assert abs(float(actual) - expected) <= tolerance, \
        f"Expected {expected} ± {tolerance}, got {float(actual)}"


def assert_percentage_equal(actual: float, expected: float, tolerance: float = 0.1):
    """Assert percentage values are equal within tolerance"""
    assert abs(actual - expected) <= tolerance, \
        f"Expected {expected}% ± {tolerance}%, got {actual}%"


# FastAPI Test Client Fixtures
@pytest.fixture(scope="module")
def test_client():
    """Create a test client with overridden database dependency"""
    from fastapi.testclient import TestClient

    # IMPORTANT: Create test engine and tables BEFORE importing app
    # This ensures the Base.metadata has all tables registered
    engine = get_test_engine()

    # Now import app - this will use our overridden get_db
    from backend.main import app

    # Override the database dependency with our test database
    app.dependency_overrides[get_db] = get_test_db

    # Create test client
    client = TestClient(app)

    yield client

    # Clear dependency overrides after tests
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Test user registration data"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test123!",
        "full_name": "Test User",
        "role": "supervisor"  # Valid roles: admin, supervisor, operator, viewer
    }


@pytest.fixture
def auth_headers(test_client, test_user_data):
    """
    Get authentication headers for testing.
    Creates a test user if needed and returns auth headers.
    """
    # Try to login first
    response = test_client.post("/api/auth/login", json={
        "username": test_user_data["username"],
        "password": test_user_data["password"]
    })

    if response.status_code == 200:
        token = response.json().get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}

    # User doesn't exist, register first
    register_response = test_client.post("/api/auth/register", json=test_user_data)

    if register_response.status_code in [200, 201]:
        # Now login
        login_response = test_client.post("/api/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })

        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}

    # Return empty dict if auth fails - tests can handle gracefully
    pytest.skip("Authentication setup failed - cannot create test user")
    return {}


@pytest.fixture
def admin_auth_headers(test_client):
    """Get admin authentication headers for testing."""
    admin_data = {
        "username": "admin_testuser",
        "email": "admin_test@example.com",
        "password": "AdminPass123!",
        "full_name": "Admin Test User",
        "role": "admin"
    }

    # Try to login first
    response = test_client.post("/api/auth/login", json={
        "username": admin_data["username"],
        "password": admin_data["password"]
    })

    if response.status_code == 200:
        token = response.json().get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}

    # User doesn't exist, register first
    register_response = test_client.post("/api/auth/register", json=admin_data)

    if register_response.status_code in [200, 201]:
        login_response = test_client.post("/api/auth/login", json={
            "username": admin_data["username"],
            "password": admin_data["password"]
        })

        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}

    pytest.skip("Admin authentication setup failed")
    return {}


@pytest.fixture
def authenticated_client(test_client, auth_headers):
    """
    Create an authenticated test client that automatically includes auth headers.
    This provides a cleaner API for tests that need authentication.
    """
    class AuthenticatedTestClient:
        """Wrapper around TestClient that adds auth headers to all requests"""
        def __init__(self, client, headers):
            self._client = client
            self._headers = headers
        
        def get(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.get(url, headers=headers, **kwargs)
        
        def post(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.post(url, headers=headers, **kwargs)
        
        def put(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.put(url, headers=headers, **kwargs)
        
        def patch(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.patch(url, headers=headers, **kwargs)
        
        def delete(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.delete(url, headers=headers, **kwargs)
        
        def head(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.head(url, headers=headers, **kwargs)
        
        def options(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers.update(self._headers)
            return self._client.options(url, headers=headers, **kwargs)
    
    return AuthenticatedTestClient(test_client, auth_headers)


# ============================================================================
# Enhanced Fixtures with Real Database Transactions
# ============================================================================

# Import fixtures package (factories, auth fixtures, seed data)
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.fixtures.auth_fixtures import (
    create_test_user,
    create_test_token,
    AuthenticatedClient as AuthClientWrapper,
    get_admin_client,
    get_supervisor_client,
    get_operator_client,
    get_viewer_client,
    get_leader_client,
    get_multi_tenant_client,
)
from backend.tests.fixtures.seed_data import (
    seed_minimal_data,
    seed_comprehensive_data,
    seed_multi_tenant_data,
    cleanup_test_data,
)


@pytest.fixture(scope="function")
def transactional_db():
    """
    Create a database session with automatic rollback after each test.
    This ensures test isolation without needing to delete data.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    session = TestingSessionLocal()

    # Reset factory counters for clean IDs
    TestDataFactory.reset_counters()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def seeded_db(transactional_db):
    """
    Provide a database session pre-seeded with minimal test data.
    Useful for tests that need basic data setup.
    """
    data = seed_minimal_data(transactional_db)
    yield transactional_db, data


@pytest.fixture(scope="function")
def comprehensive_db(transactional_db):
    """
    Provide a database session pre-seeded with comprehensive test data.
    Useful for integration tests that need realistic data relationships.
    """
    data = seed_comprehensive_data(transactional_db, days_of_data=30)
    yield transactional_db, data


@pytest.fixture(scope="function")
def multi_tenant_db(transactional_db):
    """
    Provide a database session pre-seeded with multi-tenant test data.
    Useful for testing client isolation and tenant-specific access.
    """
    data = seed_multi_tenant_data(transactional_db)
    yield transactional_db, data


@pytest.fixture(scope="function")
def factory(transactional_db):
    """
    Provide the TestDataFactory with an associated database session.
    Allows tests to create specific data as needed.
    """
    return TestDataFactory


# ============================================================================
# Role-Based Authenticated Client Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def admin_authenticated_client(test_client, transactional_db):
    """
    Provide an authenticated client with admin role.
    Admin users can access all clients.
    """
    # Override get_db to use transactional_db
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Create client and admin user
    client = TestDataFactory.create_client(
        transactional_db,
        client_id="ADMIN-TEST-CLIENT",
        client_name="Admin Test Client"
    )
    transactional_db.commit()

    auth_client = get_admin_client(
        test_client,
        transactional_db,
        username="admin_test_user"
    )

    yield auth_client, transactional_db, client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def supervisor_authenticated_client(test_client, transactional_db):
    """
    Provide an authenticated client with supervisor role.
    Supervisors have elevated access within their assigned client.
    """
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Create client
    client = TestDataFactory.create_client(
        transactional_db,
        client_id="SUPERVISOR-TEST-CLIENT",
        client_name="Supervisor Test Client"
    )
    transactional_db.commit()

    auth_client = get_supervisor_client(
        test_client,
        transactional_db,
        client_id=client.client_id,
        username="supervisor_test_user"
    )

    yield auth_client, transactional_db, client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def operator_authenticated_client(test_client, transactional_db):
    """
    Provide an authenticated client with operator role.
    Operators have basic access to their assigned client only.
    """
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Create client
    client = TestDataFactory.create_client(
        transactional_db,
        client_id="OPERATOR-TEST-CLIENT",
        client_name="Operator Test Client"
    )
    transactional_db.commit()

    auth_client = get_operator_client(
        test_client,
        transactional_db,
        client_id=client.client_id,
        username="operator_test_user"
    )

    yield auth_client, transactional_db, client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def multi_tenant_authenticated_clients(test_client, transactional_db):
    """
    Provide authenticated clients for multi-tenant testing.
    Returns dict with clients for different tenants.
    """
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Seed multi-tenant data
    data = seed_multi_tenant_data(transactional_db)

    # Create authenticated clients for each user
    auth_clients = {}

    for user_key, user in data["users"].items():
        token = create_test_token(user)
        auth_clients[user_key] = AuthClientWrapper(test_client, token)

    yield auth_clients, transactional_db, data

    app.dependency_overrides.clear()


# ============================================================================
# Production Route Testing Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def production_test_setup(test_client, transactional_db):
    """
    Complete setup for production route testing.
    Creates all necessary entities: client, user, product, shift.
    """
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Create client
    client = TestDataFactory.create_client(
        transactional_db,
        client_id="PROD-TEST-CLIENT",
        client_name="Production Test Client"
    )

    # Create supervisor user
    user = TestDataFactory.create_user(
        transactional_db,
        username="prod_supervisor",
        role="supervisor",
        client_id=client.client_id,
        password="TestPass123!"
    )

    # Create product
    product = TestDataFactory.create_product(
        transactional_db,
        client_id=client.client_id,
        product_code="PROD-TEST-001",
        product_name="Test Production Product",
        ideal_cycle_time=Decimal("0.15")
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        transactional_db,
        client_id=client.client_id,
        shift_name="Test Day Shift",
        start_time="06:00:00",
        end_time="14:00:00"
    )

    transactional_db.commit()

    # Create authenticated client
    auth_client = get_supervisor_client(
        test_client,
        transactional_db,
        client_id=client.client_id,
        username="prod_route_supervisor"
    )

    yield {
        "auth_client": auth_client,
        "db": transactional_db,
        "client": client,
        "user": user,
        "product": product,
        "shift": shift,
    }

    app.dependency_overrides.clear()


# ============================================================================
# Quality Route Testing Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def quality_test_setup(test_client, transactional_db):
    """
    Complete setup for quality route testing.
    Creates client, user, work order, and related entities.
    """
    from backend.main import app
    app.dependency_overrides[get_db] = lambda: transactional_db

    # Create client
    client = TestDataFactory.create_client(
        transactional_db,
        client_id="QUAL-TEST-CLIENT",
        client_name="Quality Test Client"
    )

    # Create supervisor user
    user = TestDataFactory.create_user(
        transactional_db,
        username="qual_supervisor",
        role="supervisor",
        client_id=client.client_id,
        password="TestPass123!"
    )

    # Create product
    product = TestDataFactory.create_product(
        transactional_db,
        client_id=client.client_id
    )

    transactional_db.flush()

    # Create work order
    work_order = TestDataFactory.create_work_order(
        transactional_db,
        client_id=client.client_id,
        product_id=product.product_id
    )

    transactional_db.commit()

    # Create authenticated client
    auth_client = get_supervisor_client(
        test_client,
        transactional_db,
        client_id=client.client_id,
        username="qual_route_supervisor"
    )

    yield {
        "auth_client": auth_client,
        "db": transactional_db,
        "client": client,
        "user": user,
        "product": product,
        "work_order": work_order,
    }

    app.dependency_overrides.clear()

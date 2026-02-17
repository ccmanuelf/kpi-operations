"""
Pytest Configuration and Shared Fixtures
Provides reusable test fixtures for all test modules
"""

import pytest
from datetime import date
from decimal import Decimal
import sys
import os

# Add app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# Import test data fixtures
from tests.fixtures.test_data import TestDataFixtures


# Database fixtures
@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for testing"""
    # from app.database import create_engine
    # engine = create_engine("sqlite:///:memory:")  # In-memory database
    # yield engine
    # engine.dispose()
    pass


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create fresh database session for each test"""
    # from app.database import SessionLocal
    # session = SessionLocal()
    #
    # # Create tables
    # Base.metadata.create_all(bind=db_engine)
    #
    # yield session
    #
    # # Rollback and close
    # session.rollback()
    # session.close()
    #
    # # Drop tables
    # Base.metadata.drop_all(bind=db_engine)
    pass


# API client fixtures
@pytest.fixture
def api_client():
    """FastAPI test client"""
    # from fastapi.testclient import TestClient
    # from app.main import app
    #
    # client = TestClient(app)
    # return client
    pass


@pytest.fixture
def authenticated_client(api_client):
    """Authenticated API client with JWT token"""
    # # Login and get token
    # response = api_client.post("/api/auth/login", json={
    #     "username": "operator1",
    #     "password": "TestPass123!"
    # })
    #
    # token = response.json()["access_token"]
    # api_client.headers.update({"Authorization": f"Bearer {token}"})
    #
    # return api_client
    pass


# Test data fixtures
@pytest.fixture
def perfect_production_data():
    """Production entry with all fields"""
    return TestDataFixtures.perfect_production_entry()


@pytest.fixture
def missing_cycle_time_data():
    """Production entry missing ideal_cycle_time"""
    return TestDataFixtures.missing_ideal_cycle_time_entry()


@pytest.fixture
def missing_employees_data():
    """Production entry missing employees_assigned"""
    return TestDataFixtures.missing_employees_assigned_entry()


@pytest.fixture
def sample_clients():
    """Sample client data"""
    return TestDataFixtures.sample_clients()


@pytest.fixture
def sample_work_orders():
    """Sample work orders"""
    return TestDataFixtures.sample_work_orders()


@pytest.fixture
def sample_users():
    """Sample users for auth testing"""
    return TestDataFixtures.sample_users()


@pytest.fixture
def csv_valid_247():
    """Valid CSV with 247 rows"""
    return TestDataFixtures.csv_valid_247_rows()


@pytest.fixture
def csv_with_errors():
    """CSV with 235 valid, 12 errors"""
    return TestDataFixtures.csv_with_errors_235_valid_12_invalid()


# Authentication fixtures
@pytest.fixture
def operator_token(api_client):
    """JWT token for OPERATOR_DATAENTRY role"""
    # response = api_client.post("/api/auth/login", json={
    #     "username": "operator1",
    #     "password": "TestPass123!"
    # })
    # return response.json()["access_token"]
    pass


@pytest.fixture
def leader_token(api_client):
    """JWT token for LEADER_DATACONFIG role"""
    # response = api_client.post("/api/auth/login", json={
    #     "username": "leader1",
    #     "password": "TestPass123!"
    # })
    # return response.json()["access_token"]
    pass


@pytest.fixture
def poweruser_token(api_client):
    """JWT token for POWERUSER role"""
    # response = api_client.post("/api/auth/login", json={
    #     "username": "poweruser1",
    #     "password": "TestPass123!"
    # })
    # return response.json()["access_token"]
    pass


@pytest.fixture
def admin_token(api_client):
    """JWT token for ADMIN role"""
    # response = api_client.post("/api/auth/login", json={
    #     "username": "admin1",
    #     "password": "TestPass123!"
    # })
    # return response.json()["access_token"]
    pass


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Add cleanup logic here if needed


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (database required)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full stack)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "kpi: KPI calculation tests")
    config.addinivalue_line("markers", "csv: CSV upload tests")
    config.addinivalue_line("markers", "client_isolation: Multi-tenant isolation tests")


# Custom pytest hooks
def pytest_collection_modifyitems(config, items):
    """Modify test items during collection"""
    for item in items:
        # Auto-mark tests based on file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "backend" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Auto-mark based on test name
        if "csv" in item.name.lower():
            item.add_marker(pytest.mark.csv)
        if "kpi" in item.name.lower() or "efficiency" in item.name.lower() or "performance" in item.name.lower():
            item.add_marker(pytest.mark.kpi)
        if "auth" in item.name.lower() or "login" in item.name.lower():
            item.add_marker(pytest.mark.security)
        if "client_isolation" in item.name.lower() or "multi_client" in item.name.lower():
            item.add_marker(pytest.mark.client_isolation)

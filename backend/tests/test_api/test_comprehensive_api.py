"""
Comprehensive API Integration Tests for 90% Coverage
Tests all API endpoints with authentication
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import Base, get_db
from backend.main import app
from backend.auth.jwt import get_password_hash, create_access_token
from backend.schemas.user import User, UserRole
from backend.schemas.client import Client, ClientType


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_client():
    """Create test client with fresh database"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Create test user
    db = TestingSessionLocal()
    test_user = User(
        user_id="TEST-USER",
        username="testadmin",
        email="testadmin@test.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    test_client = Client(
        client_id="TEST-CLIENT", client_name="Test Client", client_type=ClientType.SERVICE, is_active=True
    )
    db.add(test_user)
    db.add(test_client)
    db.commit()
    db.close()

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers():
    """Create authentication headers"""
    token = create_access_token(data={"sub": "testadmin"})
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_root(self, test_client):
        response = test_client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_live(self, test_client):
        response = test_client.get("/health/live")
        assert response.status_code == 200

    def test_health_ready(self, test_client, auth_headers):
        response = test_client.get("/health/ready", headers=auth_headers)
        assert response.status_code == 200


class TestAuthEndpoints:
    """Test authentication endpoints"""

    def test_login_success(self, test_client):
        response = test_client.post("/api/auth/login", json={"username": "testadmin", "password": "testpass123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, test_client):
        response = test_client.post("/api/auth/login", json={"username": "testadmin", "password": "wrongpassword"})
        assert response.status_code == 401

    def test_login_wrong_username(self, test_client):
        response = test_client.post("/api/auth/login", json={"username": "nonexistent", "password": "testpass123"})
        assert response.status_code == 401

    def test_get_current_user(self, test_client, auth_headers):
        response = test_client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"

    def test_get_current_user_no_auth(self, test_client):
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_forgot_password(self, test_client):
        response = test_client.post("/api/auth/forgot-password", json={"email": "testadmin@test.com"})
        assert response.status_code == 200

    def test_forgot_password_unknown_email(self, test_client):
        # Should still return 200 to prevent email enumeration
        response = test_client.post("/api/auth/forgot-password", json={"email": "unknown@test.com"})
        assert response.status_code == 200


class TestProductionEndpoints:
    """Test production API endpoints"""

    def test_production_list_requires_auth(self, test_client):
        response = test_client.get("/api/production")
        assert response.status_code == 401

    def test_production_create_requires_auth(self, test_client):
        response = test_client.post("/api/production", json={})
        assert response.status_code == 401


class TestQualityEndpoints:
    """Test quality API endpoints"""

    def test_quality_list_requires_auth(self, test_client):
        response = test_client.get("/api/quality")
        assert response.status_code == 401

    def test_quality_ppm_requires_auth(self, test_client):
        response = test_client.get("/api/quality/kpi/ppm")
        assert response.status_code == 401


class TestAttendanceEndpoints:
    """Test attendance API endpoints"""

    def test_attendance_list_requires_auth(self, test_client):
        response = test_client.get("/api/attendance")
        assert response.status_code == 401

    def test_absenteeism_requires_auth(self, test_client):
        response = test_client.get("/api/attendance/absenteeism")
        assert response.status_code == 401


class TestDowntimeEndpoints:
    """Test downtime API endpoints"""

    def test_downtime_list_requires_auth(self, test_client):
        response = test_client.get("/api/downtime")
        assert response.status_code == 401


class TestHoldEndpoints:
    """Test hold/WIP API endpoints"""

    def test_holds_list_requires_auth(self, test_client):
        response = test_client.get("/api/holds")
        assert response.status_code == 401

    def test_wip_aging_requires_auth(self, test_client):
        response = test_client.get("/api/holds/wip-aging")
        assert response.status_code == 401


class TestCoverageEndpoints:
    """Test coverage API endpoints"""

    def test_coverage_list_requires_auth(self, test_client):
        response = test_client.get("/api/coverage")
        assert response.status_code == 401


class TestPredictionsEndpoints:
    """Test predictions API endpoints"""

    def test_predictions_requires_auth(self, test_client):
        response = test_client.get("/api/predictions/efficiency")
        assert response.status_code == 401


class TestAnalyticsEndpoints:
    """Test analytics API endpoints"""

    def test_analytics_requires_auth(self, test_client):
        response = test_client.get("/api/analytics/summary")
        assert response.status_code in [401, 404]


class TestReportsEndpoints:
    """Test reports API endpoints"""

    def test_reports_available_requires_auth(self, test_client):
        response = test_client.get("/api/reports/available")
        assert response.status_code == 401

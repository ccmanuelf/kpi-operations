"""
API Integration Tests
Tests full API workflows for all endpoints

Note: These tests verify endpoint existence and require authentication.
For comprehensive API testing with authentication, see test_reports.py pattern.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestPublicEndpoints:
    """Test endpoints that don't require authentication"""

    def test_root_health_check(self):
        """Test root endpoint returns health status"""
        response = client.get("/")
        assert response.status_code == 200
        assert "status" in response.json()
        assert response.json()["status"] == "healthy"

    def test_health_endpoint(self):
        """Test /health endpoint"""
        response = client.get("/health/")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_health_live_endpoint(self):
        """Test /health/live endpoint"""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestProductionAPI:
    """Test Production Entry API endpoints (authentication required)"""

    def test_create_production_entry_requires_auth(self):
        """Test that creating production entry requires authentication"""
        data = {
            "client_id": "CLIENT-A",
            "product_id": 101,
            "shift_id": 1,
            "work_order_number": "WO-TEST-001",
            "production_date": "2024-01-15",
            "units_produced": 1000,
            "employees_assigned": 5,
            "run_time_hours": 8.0
        }
        # Without authentication, should return 401
        response = client.post("/api/production", json=data)
        assert response.status_code == 401

    def test_get_production_entry_requires_auth(self):
        """Test that retrieving production entry requires authentication"""
        response = client.get("/api/production/1")
        assert response.status_code == 401

    def test_update_production_entry_requires_auth(self):
        """Test that updating production entry requires authentication"""
        data = {"units_produced": 1100}
        response = client.put("/api/production/1", json=data)
        assert response.status_code == 401

    def test_delete_production_entry_requires_auth(self):
        """Test that deleting production entry requires authentication"""
        response = client.delete("/api/production/1")
        assert response.status_code == 401


class TestKPIAPI:
    """Test KPI calculation API endpoints (authentication required)"""

    def test_kpi_calculate_requires_auth(self):
        """Test efficiency calculation endpoint requires authentication"""
        response = client.get("/api/kpi/calculate/1")
        assert response.status_code == 401

    def test_kpi_dashboard_requires_auth(self):
        """Test dashboard endpoint requires authentication"""
        response = client.get("/api/kpi/dashboard")
        assert response.status_code == 401

    def test_kpi_otd_requires_auth(self):
        """Test OTD endpoint requires authentication"""
        response = client.get("/api/kpi/otd?start_date=2024-01-01&end_date=2024-12-31")
        assert response.status_code == 401


class TestDowntimeAPI:
    """Test Downtime API endpoints (authentication required)"""

    def test_downtime_list_requires_auth(self):
        """Test listing downtime events requires authentication"""
        response = client.get("/api/downtime")
        assert response.status_code == 401

    def test_downtime_create_requires_auth(self):
        """Test creating downtime event requires authentication"""
        data = {
            "product_id": 101,
            "shift_id": 1,
            "downtime_category": "maintenance",
            "downtime_minutes": 30,
            "downtime_date": "2024-01-15"
        }
        response = client.post("/api/downtime", json=data)
        assert response.status_code == 401


class TestHoldsAPI:
    """Test WIP Holds API endpoints (authentication required)"""

    def test_holds_list_requires_auth(self):
        """Test listing WIP holds requires authentication"""
        response = client.get("/api/holds")
        assert response.status_code == 401

    def test_holds_create_requires_auth(self):
        """Test creating WIP hold requires authentication"""
        data = {
            "product_id": 101,
            "quantity": 50,
            "hold_reason": "Quality inspection"
        }
        response = client.post("/api/holds", json=data)
        assert response.status_code == 401


class TestAttendanceAPI:
    """Test Attendance API endpoints (authentication required)"""

    def test_attendance_list_requires_auth(self):
        """Test listing attendance records requires authentication"""
        response = client.get("/api/attendance")
        assert response.status_code == 401


class TestQualityAPI:
    """Test Quality API endpoints (authentication required)"""

    def test_quality_list_requires_auth(self):
        """Test listing quality inspections requires authentication"""
        response = client.get("/api/quality")
        assert response.status_code == 401

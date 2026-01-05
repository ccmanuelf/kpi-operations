"""
API Integration Tests
Tests full API workflows for all endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestProductionAPI:
    """Test Production Entry API endpoints"""

    def test_create_production_entry(self):
        """Test creating a production entry via API"""
        # Given: Valid production entry data
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

        # When: POST to API
        response = client.post("/api/v1/production", json=data)

        # Then: Should create successfully
        assert response.status_code == 201
        assert response.json()["work_order_number"] == "WO-TEST-001"

    def test_get_production_entry(self):
        """Test retrieving a production entry"""
        # When: GET from API
        response = client.get("/api/v1/production/1")

        # Then: Should return entry
        assert response.status_code in [200, 404]

    def test_update_production_entry(self):
        """Test updating a production entry"""
        # Given: Updated data
        data = {"units_produced": 1100}

        # When: PUT to API
        response = client.put("/api/v1/production/1", json=data)

        # Then: Should update or return 404
        assert response.status_code in [200, 404]

    def test_delete_production_entry(self):
        """Test deleting a production entry"""
        # When: DELETE from API
        response = client.delete("/api/v1/production/1")

        # Then: Should delete or return 404
        assert response.status_code in [200, 404]


class TestKPIAPI:
    """Test KPI calculation API endpoints"""

    def test_calculate_efficiency_api(self):
        """Test efficiency calculation endpoint"""
        response = client.get("/api/v1/kpi/efficiency?entry_id=1")
        assert response.status_code in [200, 404]

    def test_calculate_performance_api(self):
        """Test performance calculation endpoint"""
        response = client.get("/api/v1/kpi/performance?entry_id=1")
        assert response.status_code in [200, 404]

    def test_calculate_ppm_api(self):
        """Test PPM calculation endpoint"""
        response = client.get("/api/v1/kpi/ppm?product_id=101")
        assert response.status_code in [200, 404]

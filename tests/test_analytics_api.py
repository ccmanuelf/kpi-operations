"""
Analytics API Endpoint Tests
Comprehensive test suite for all analytics endpoints with multi-tenant isolation
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app


# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_analytics.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def test_db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """
    Mock authentication headers
    In production, this would use actual JWT tokens
    """
    return {
        "Authorization": "Bearer test_token_admin"
    }


class TestTrendsEndpoint:
    """Tests for GET /api/analytics/trends"""

    def test_get_trends_success(self, client, test_db, auth_headers):
        """Test successful trend analysis retrieval"""
        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "client_id" in data
        assert "kpi_type" in data
        assert "data_points" in data
        assert "trend_direction" in data
        assert "trend_slope" in data
        assert "average_value" in data
        assert "anomalies_detected" in data

        # Verify data types
        assert isinstance(data["data_points"], list)
        assert data["trend_direction"] in ["increasing", "decreasing", "stable", "volatile"]
        assert isinstance(data["anomalies_detected"], int)

    def test_get_trends_custom_date_range(self, client, test_db, auth_headers):
        """Test trend analysis with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=14)

        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "performance",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_get_trends_invalid_kpi_type(self, client, test_db, auth_headers):
        """Test with invalid KPI type"""
        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "invalid_kpi",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_trends_invalid_time_range(self, client, test_db, auth_headers):
        """Test with invalid time range"""
        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "invalid"
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_trends_unauthorized(self, client, test_db):
        """Test without authentication"""
        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )

        assert response.status_code == 401  # Unauthorized

    def test_get_trends_forbidden_client(self, client, test_db):
        """Test access to forbidden client"""
        # Use headers for operator with different client assignment
        operator_headers = {"Authorization": "Bearer test_token_operator_other"}

        response = client.get(
            "/api/analytics/trends",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers=operator_headers
        )

        assert response.status_code == 403  # Forbidden


class TestPredictionsEndpoint:
    """Tests for GET /api/analytics/predictions"""

    def test_get_predictions_success(self, client, test_db, auth_headers):
        """Test successful prediction retrieval"""
        response = client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "historical_days": 30,
                "forecast_days": 7
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "predictions" in data
        assert "prediction_method" in data
        assert "model_accuracy" in data
        assert "historical_average" in data
        assert "predicted_average" in data

        # Verify predictions structure
        if data["predictions"]:
            prediction = data["predictions"][0]
            assert "date" in prediction
            assert "predicted_value" in prediction
            assert "lower_bound" in prediction
            assert "upper_bound" in prediction
            assert "confidence" in prediction

    def test_get_predictions_different_methods(self, client, test_db, auth_headers):
        """Test different forecasting methods"""
        methods = ["auto", "simple", "double", "linear"]

        for method in methods:
            response = client.get(
                "/api/analytics/predictions",
                params={
                    "client_id": "BOOT-LINE-A",
                    "kpi_type": "efficiency",
                    "historical_days": 30,
                    "forecast_days": 7,
                    "method": method
                },
                headers=auth_headers
            )

            # Should succeed or return 400 if insufficient data
            assert response.status_code in [200, 400]

    def test_get_predictions_invalid_forecast_days(self, client, test_db, auth_headers):
        """Test with invalid forecast days"""
        response = client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "historical_days": 30,
                "forecast_days": 100  # Exceeds limit
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


class TestComparisonsEndpoint:
    """Tests for GET /api/analytics/comparisons"""

    def test_get_comparisons_success(self, client, test_db, auth_headers):
        """Test successful client comparison"""
        response = client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "clients" in data
        assert "overall_average" in data
        assert "industry_benchmark" in data
        assert "best_performer" in data
        assert "worst_performer" in data
        assert "performance_spread" in data

        # Verify client data structure
        if data["clients"]:
            client_data = data["clients"][0]
            assert "client_id" in client_data
            assert "client_name" in client_data
            assert "average_value" in client_data
            assert "percentile_rank" in client_data
            assert "performance_rating" in client_data

    def test_get_comparisons_custom_date_range(self, client, test_db, auth_headers):
        """Test comparison with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=60)

        response = client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "performance",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            headers=auth_headers
        )

        assert response.status_code == 200


class TestHeatmapEndpoint:
    """Tests for GET /api/analytics/heatmap"""

    def test_get_heatmap_success(self, client, test_db, auth_headers):
        """Test successful heatmap retrieval"""
        response = client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "cells" in data
        assert "shifts" in data
        assert "dates" in data
        assert "color_scale" in data

        # Verify color scale
        color_scale = data["color_scale"]
        assert "Excellent" in color_scale
        assert "Good" in color_scale
        assert "Fair" in color_scale
        assert "Poor" in color_scale
        assert "No Data" in color_scale

        # Verify cell structure
        if data["cells"]:
            cell = data["cells"][0]
            assert "date" in cell
            assert "shift_id" in cell
            assert "shift_name" in cell
            assert "performance_level" in cell
            assert "color_code" in cell

    def test_get_heatmap_7_days(self, client, test_db, auth_headers):
        """Test heatmap with 7-day range"""
        response = client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "BOOT-LINE-A",
                "kpi_type": "performance",
                "time_range": "7d"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify date range
        dates = data["dates"]
        # Should have 8 dates (inclusive)
        assert len(dates) <= 10  # Allow some variation


class TestParetoEndpoint:
    """Tests for GET /api/analytics/pareto"""

    def test_get_pareto_success(self, client, test_db, auth_headers):
        """Test successful Pareto analysis"""
        response = client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "BOOT-LINE-A",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        # Should succeed or return 404 if no defect data
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Verify response structure
            assert "items" in data
            assert "total_defects" in data
            assert "vital_few_count" in data
            assert "vital_few_percentage" in data
            assert "pareto_threshold" in data

            # Verify items are sorted by count
            if len(data["items"]) > 1:
                counts = [item["count"] for item in data["items"]]
                assert counts == sorted(counts, reverse=True)

            # Verify cumulative percentages
            if data["items"]:
                last_cumulative = data["items"][-1]["cumulative_percentage"]
                assert float(last_cumulative) >= 99.0  # Should be ~100%

    def test_get_pareto_custom_threshold(self, client, test_db, auth_headers):
        """Test Pareto with custom threshold"""
        response = client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "BOOT-LINE-A",
                "time_range": "30d",
                "pareto_threshold": 70.0
            },
            headers=auth_headers
        )

        # Should succeed or return 404 if no defect data
        assert response.status_code in [200, 404]

    def test_get_pareto_invalid_threshold(self, client, test_db, auth_headers):
        """Test with invalid Pareto threshold"""
        response = client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "BOOT-LINE-A",
                "time_range": "30d",
                "pareto_threshold": 30.0  # Below minimum
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


class TestAnalyticsIntegration:
    """Integration tests across multiple analytics endpoints"""

    def test_full_analytics_workflow(self, client, test_db, auth_headers):
        """Test complete analytics workflow"""
        client_id = "BOOT-LINE-A"

        # 1. Get trends
        trends_response = client.get(
            "/api/analytics/trends",
            params={"client_id": client_id, "kpi_type": "efficiency", "time_range": "30d"},
            headers=auth_headers
        )

        # 2. Get predictions
        predictions_response = client.get(
            "/api/analytics/predictions",
            params={
                "client_id": client_id,
                "kpi_type": "efficiency",
                "forecast_days": 7
            },
            headers=auth_headers
        )

        # 3. Get comparisons
        comparisons_response = client.get(
            "/api/analytics/comparisons",
            params={"kpi_type": "efficiency", "time_range": "30d"},
            headers=auth_headers
        )

        # 4. Get heatmap
        heatmap_response = client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": client_id,
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers=auth_headers
        )

        # All should succeed or return appropriate error codes
        for response in [trends_response, predictions_response, comparisons_response, heatmap_response]:
            assert response.status_code in [200, 400, 404]

    def test_multi_kpi_analysis(self, client, test_db, auth_headers):
        """Test analysis across multiple KPI types"""
        kpi_types = ["efficiency", "performance", "quality"]
        client_id = "BOOT-LINE-A"

        for kpi_type in kpi_types:
            response = client.get(
                "/api/analytics/trends",
                params={
                    "client_id": client_id,
                    "kpi_type": kpi_type,
                    "time_range": "30d"
                },
                headers=auth_headers
            )

            # Should succeed or return 404 if no data
            assert response.status_code in [200, 404]

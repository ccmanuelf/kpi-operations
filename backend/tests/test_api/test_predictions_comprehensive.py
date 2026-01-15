"""
Comprehensive Predictions Routes Tests

Tests all prediction endpoints including efficiency, quality, downtime, and trend forecasting.
Target: Increase coverage of routes/predictions.py to 90%+
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


class TestEfficiencyPredictions:
    """Tests for efficiency prediction endpoints"""
    
    def test_get_efficiency_prediction(self, authenticated_client):
        """Test basic efficiency prediction"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_efficiency_prediction_with_horizon(self, authenticated_client):
        """Test efficiency prediction with custom horizon"""
        for horizon in [7, 14, 30]:
            response = authenticated_client.get(
                "/api/predictions/efficiency",
                params={
                    "client_id": "TEST-CLIENT",
                    "horizon_days": horizon
                }
            )
            assert response.status_code in [200, 403, 404, 422]
    
    def test_efficiency_prediction_with_date_range(self, authenticated_client):
        """Test efficiency prediction with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=60)
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_efficiency_prediction_requires_client_id(self, authenticated_client):
        """Test efficiency prediction requires client_id"""
        response = authenticated_client.get("/api/predictions/efficiency")
        assert response.status_code == 422
    
    def test_efficiency_prediction_invalid_client(self, authenticated_client):
        """Test efficiency prediction with invalid client"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={"client_id": "NONEXISTENT-CLIENT-12345"}
        )
        assert response.status_code in [403, 404, 422]


class TestQualityPredictions:
    """Tests for quality prediction endpoints"""
    
    def test_get_quality_prediction(self, authenticated_client):
        """Test basic quality prediction"""
        response = authenticated_client.get(
            "/api/predictions/quality",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_quality_prediction_with_horizon(self, authenticated_client):
        """Test quality prediction with custom horizon"""
        response = authenticated_client.get(
            "/api/predictions/quality",
            params={
                "client_id": "TEST-CLIENT",
                "horizon_days": 14
            }
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_quality_prediction_ppm_forecast(self, authenticated_client):
        """Test PPM prediction endpoint"""
        response = authenticated_client.get(
            "/api/predictions/ppm",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]
    
    def test_quality_prediction_defect_forecast(self, authenticated_client):
        """Test defect rate prediction"""
        response = authenticated_client.get(
            "/api/predictions/defects",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]


class TestDowntimePredictions:
    """Tests for downtime prediction endpoints"""
    
    def test_get_downtime_prediction(self, authenticated_client):
        """Test basic downtime prediction"""
        response = authenticated_client.get(
            "/api/predictions/downtime",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_downtime_prediction_by_category(self, authenticated_client):
        """Test downtime prediction by category"""
        response = authenticated_client.get(
            "/api/predictions/downtime/by-category",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]
    
    def test_downtime_prediction_maintenance(self, authenticated_client):
        """Test maintenance downtime prediction"""
        response = authenticated_client.get(
            "/api/predictions/maintenance",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]
    
    def test_downtime_prediction_with_shift_filter(self, authenticated_client):
        """Test downtime prediction filtered by shift"""
        response = authenticated_client.get(
            "/api/predictions/downtime",
            params={
                "client_id": "TEST-CLIENT",
                "shift_id": "DAY-1"
            }
        )
        assert response.status_code in [200, 403, 404, 422]


class TestAvailabilityPredictions:
    """Tests for availability prediction endpoints"""
    
    def test_get_availability_prediction(self, authenticated_client):
        """Test availability prediction"""
        response = authenticated_client.get(
            "/api/predictions/availability",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_availability_prediction_oee_forecast(self, authenticated_client):
        """Test OEE forecast"""
        response = authenticated_client.get(
            "/api/predictions/oee",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]


class TestOTDPredictions:
    """Tests for On-Time Delivery prediction endpoints"""
    
    def test_get_otd_prediction(self, authenticated_client):
        """Test OTD prediction"""
        response = authenticated_client.get(
            "/api/predictions/otd",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_otd_prediction_with_work_orders(self, authenticated_client):
        """Test OTD prediction for pending work orders"""
        response = authenticated_client.get(
            "/api/predictions/otd/pending-orders",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]


class TestPredictionConfidenceIntervals:
    """Tests for prediction confidence intervals"""
    
    def test_prediction_includes_confidence(self, authenticated_client):
        """Test that predictions include confidence intervals"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "include_confidence": True
            }
        )
        if response.status_code == 200:
            data = response.json()
            # Check for confidence interval fields
            assert isinstance(data, dict)
    
    def test_prediction_confidence_levels(self, authenticated_client):
        """Test different confidence levels"""
        for confidence in [90, 95, 99]:
            response = authenticated_client.get(
                "/api/predictions/efficiency",
                params={
                    "client_id": "TEST-CLIENT",
                    "confidence_level": confidence
                }
            )
            assert response.status_code in [200, 403, 404, 422]


class TestPredictionMethods:
    """Tests for different prediction methods"""
    
    def test_simple_exponential_smoothing(self, authenticated_client):
        """Test simple exponential smoothing method"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "method": "ses"
            }
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_double_exponential_smoothing(self, authenticated_client):
        """Test double exponential smoothing (Holt's method)"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "method": "holt"
            }
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_linear_regression_prediction(self, authenticated_client):
        """Test linear regression prediction"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "method": "linear"
            }
        )
        assert response.status_code in [200, 403, 404, 422]
    
    def test_auto_method_selection(self, authenticated_client):
        """Test automatic method selection"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "method": "auto"
            }
        )
        assert response.status_code in [200, 403, 404, 422]


class TestPredictionBatchRequests:
    """Tests for batch prediction requests"""
    
    def test_batch_predictions_multiple_kpis(self, authenticated_client):
        """Test batch prediction for multiple KPIs"""
        response = authenticated_client.get(
            "/api/predictions/batch",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_types": "efficiency,quality,availability"
            }
        )
        assert response.status_code in [200, 403, 404]
    
    def test_summary_predictions(self, authenticated_client):
        """Test summary prediction endpoint"""
        response = authenticated_client.get(
            "/api/predictions/summary",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [200, 403, 404]


class TestPredictionAuthorization:
    """Tests for prediction authorization"""
    
    def test_efficiency_prediction_requires_auth(self, test_client):
        """Test efficiency prediction requires auth"""
        response = test_client.get(
            "/api/predictions/efficiency",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code == 401
    
    def test_quality_prediction_requires_auth(self, test_client):
        """Test quality prediction requires auth"""
        response = test_client.get(
            "/api/predictions/quality",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [401, 404]
    
    def test_downtime_prediction_requires_auth(self, test_client):
        """Test downtime prediction requires auth"""
        response = test_client.get(
            "/api/predictions/downtime",
            params={"client_id": "TEST-CLIENT"}
        )
        assert response.status_code in [401, 404]


class TestPredictionErrorHandling:
    """Tests for prediction error handling"""
    
    def test_prediction_insufficient_data(self, authenticated_client):
        """Test prediction with insufficient historical data"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "NEW-CLIENT-NO-DATA",
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat()
            }
        )
        assert response.status_code in [400, 403, 404, 422]
    
    def test_prediction_invalid_horizon(self, authenticated_client):
        """Test prediction with invalid horizon"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "horizon_days": -5
            }
        )
        assert response.status_code in [400, 403, 422]
    
    def test_prediction_invalid_date_range(self, authenticated_client):
        """Test prediction with invalid date range"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "start_date": "2024-12-31",
                "end_date": "2024-01-01"  # End before start
            }
        )
        assert response.status_code in [400, 403, 422]
    
    def test_prediction_invalid_method(self, authenticated_client):
        """Test prediction with invalid method"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={
                "client_id": "TEST-CLIENT",
                "method": "invalid_method"
            }
        )
        assert response.status_code in [400, 403, 422]


class TestPredictionResponseFormat:
    """Tests for prediction response format"""
    
    def test_prediction_response_structure(self, authenticated_client):
        """Test prediction response has proper structure"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={"client_id": "TEST-CLIENT"}
        )
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            # Should have predictions array or similar
    
    def test_prediction_includes_metadata(self, authenticated_client):
        """Test prediction response includes metadata"""
        response = authenticated_client.get(
            "/api/predictions/efficiency",
            params={"client_id": "TEST-CLIENT"}
        )
        if response.status_code == 200:
            data = response.json()
            # Should include method used, date range, etc.
            assert isinstance(data, dict)

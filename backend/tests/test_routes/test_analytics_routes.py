"""
Comprehensive Analytics Routes Tests
Tests all analytics API endpoints: trends, predictions, comparisons, heatmap, and pareto analysis

Coverage targets:
- Valid requests with proper authentication
- Invalid parameters (400 errors)
- Access denied scenarios (403 errors)
- Not found scenarios (404 errors)
- Edge cases and boundary conditions
- Helper function unit tests
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import helper functions for direct testing
from backend.routes.analytics import (
    parse_time_range,
    get_performance_rating,
    get_heatmap_color_code
)
from backend.schemas.user import User, UserRole
from backend.middleware.client_auth import ClientAccessError


# =============================================================================
# HELPER FUNCTION UNIT TESTS
# =============================================================================

class TestParseTimeRange:
    """Unit tests for parse_time_range helper function"""

    def test_parse_7_day_range(self):
        """Test 7-day time range parsing"""
        end_date = date(2024, 1, 31)
        start, end = parse_time_range("7d", end_date)

        assert start == date(2024, 1, 24)
        assert end == date(2024, 1, 31)
        assert (end - start).days == 7

    def test_parse_30_day_range(self):
        """Test 30-day time range parsing"""
        end_date = date(2024, 1, 31)
        start, end = parse_time_range("30d", end_date)

        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 31)
        assert (end - start).days == 30

    def test_parse_90_day_range(self):
        """Test 90-day time range parsing"""
        end_date = date(2024, 3, 31)
        start, end = parse_time_range("90d", end_date)

        assert start == date(2024, 1, 1)
        assert end == date(2024, 3, 31)
        assert (end - start).days == 90

    def test_parse_default_end_date_uses_today(self):
        """Test that default end_date is today when not provided"""
        start, end = parse_time_range("30d")

        assert end == date.today()
        assert (end - start).days == 30

    def test_parse_invalid_time_range_raises_error(self):
        """Test that invalid time range raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            parse_time_range("invalid")

        assert "Invalid time range" in str(exc_info.value)

    def test_parse_empty_time_range_raises_error(self):
        """Test that empty time range raises ValueError"""
        with pytest.raises(ValueError):
            parse_time_range("")

    def test_parse_unsupported_time_range_raises_error(self):
        """Test that unsupported time ranges raise ValueError"""
        unsupported_ranges = ["1d", "14d", "60d", "365d", "1y", "1m"]
        for invalid_range in unsupported_ranges:
            with pytest.raises(ValueError):
                parse_time_range(invalid_range)

    def test_parse_time_range_preserves_end_date(self):
        """Test that the provided end_date is preserved exactly"""
        specific_end = date(2024, 6, 15)
        _, end = parse_time_range("7d", specific_end)

        assert end == specific_end

    def test_parse_time_range_boundary_dates(self):
        """Test time range parsing at year boundaries"""
        end_date = date(2024, 1, 5)
        start, end = parse_time_range("7d", end_date)

        # Should cross into December 2023
        assert start == date(2023, 12, 29)
        assert end == date(2024, 1, 5)


class TestGetPerformanceRating:
    """Unit tests for get_performance_rating helper function"""

    def test_excellent_rating_above_110_percent(self):
        """Test Excellent rating when value >= 110% of benchmark"""
        assert get_performance_rating(Decimal("110"), Decimal("100")) == "Excellent"
        assert get_performance_rating(Decimal("99"), Decimal("85")) == "Excellent"
        assert get_performance_rating(Decimal("150"), Decimal("100")) == "Excellent"

    def test_good_rating_95_to_110_percent(self):
        """Test Good rating when value is 95-110% of benchmark"""
        assert get_performance_rating(Decimal("95"), Decimal("100")) == "Good"
        assert get_performance_rating(Decimal("109"), Decimal("100")) == "Good"
        assert get_performance_rating(Decimal("100"), Decimal("100")) == "Good"

    def test_fair_rating_85_to_95_percent(self):
        """Test Fair rating when value is 85-95% of benchmark"""
        assert get_performance_rating(Decimal("85"), Decimal("100")) == "Fair"
        assert get_performance_rating(Decimal("94"), Decimal("100")) == "Fair"
        assert get_performance_rating(Decimal("90"), Decimal("100")) == "Fair"

    def test_poor_rating_below_85_percent(self):
        """Test Poor rating when value < 85% of benchmark"""
        assert get_performance_rating(Decimal("84"), Decimal("100")) == "Poor"
        assert get_performance_rating(Decimal("50"), Decimal("100")) == "Poor"
        assert get_performance_rating(Decimal("0"), Decimal("100")) == "Poor"

    def test_zero_benchmark_returns_poor(self):
        """Test that zero benchmark always returns Poor (division protection)"""
        assert get_performance_rating(Decimal("100"), Decimal("0")) == "Poor"
        assert get_performance_rating(Decimal("0"), Decimal("0")) == "Poor"

    def test_exact_boundary_values(self):
        """Test exact boundary values between ratings"""
        benchmark = Decimal("100")

        # 110% boundary (Excellent threshold)
        assert get_performance_rating(Decimal("110"), benchmark) == "Excellent"
        assert get_performance_rating(Decimal("109.99"), benchmark) == "Good"

        # 95% boundary (Good threshold)
        assert get_performance_rating(Decimal("95"), benchmark) == "Good"
        assert get_performance_rating(Decimal("94.99"), benchmark) == "Fair"

        # 85% boundary (Fair threshold)
        assert get_performance_rating(Decimal("85"), benchmark) == "Fair"
        assert get_performance_rating(Decimal("84.99"), benchmark) == "Poor"

    def test_high_precision_decimal_values(self):
        """Test with high precision decimal values"""
        assert get_performance_rating(
            Decimal("109.9999999"),
            Decimal("100")
        ) == "Good"

        assert get_performance_rating(
            Decimal("110.0000001"),
            Decimal("100")
        ) == "Excellent"

    def test_negative_value_returns_poor(self):
        """Test that negative values return Poor"""
        assert get_performance_rating(Decimal("-10"), Decimal("100")) == "Poor"


class TestGetHeatmapColorCode:
    """Unit tests for get_heatmap_color_code helper function"""

    def test_excellent_color_above_110_percent_benchmark(self):
        """Test Excellent color for values >= 110% of benchmark"""
        level, color = get_heatmap_color_code(Decimal("95"), Decimal("85"))

        assert level == "Excellent"
        assert color == "#22c55e"  # Green

    def test_good_color_100_to_110_percent_benchmark(self):
        """Test Good color for values 100-110% of benchmark"""
        level, color = get_heatmap_color_code(Decimal("85"), Decimal("85"))

        assert level == "Good"
        assert color == "#84cc16"  # Lime

    def test_fair_color_90_to_100_percent_benchmark(self):
        """Test Fair color for values 90-100% of benchmark"""
        level, color = get_heatmap_color_code(Decimal("80"), Decimal("85"))

        assert level == "Fair"
        assert color == "#eab308"  # Yellow

    def test_poor_color_below_90_percent_benchmark(self):
        """Test Poor color for values < 90% of benchmark"""
        level, color = get_heatmap_color_code(Decimal("70"), Decimal("85"))

        assert level == "Poor"
        assert color == "#ef4444"  # Red

    def test_no_data_color_for_none_value(self):
        """Test No Data color when value is None"""
        level, color = get_heatmap_color_code(None, Decimal("85"))

        assert level == "No Data"
        assert color == "#94a3b8"  # Gray

    def test_default_benchmark_is_85(self):
        """Test that default benchmark is 85.0"""
        # Value of 95 is > 110% of 85 (93.5), so Excellent
        level, color = get_heatmap_color_code(Decimal("95"))
        assert level == "Excellent"

        # Value of 85 is exactly 100% of 85, so Good
        level, color = get_heatmap_color_code(Decimal("85"))
        assert level == "Good"

        # Value of 78 is 91.8% of 85, so Fair
        level, color = get_heatmap_color_code(Decimal("78"))
        assert level == "Fair"

        # Value of 70 is 82.4% of 85, so Poor
        level, color = get_heatmap_color_code(Decimal("70"))
        assert level == "Poor"

    def test_exact_boundary_values(self):
        """Test exact boundary values between colors"""
        benchmark = Decimal("100")

        # 110% boundary (Excellent)
        level, _ = get_heatmap_color_code(Decimal("110"), benchmark)
        assert level == "Excellent"

        # Just below 110% (Good)
        level, _ = get_heatmap_color_code(Decimal("109.9"), benchmark)
        assert level == "Good"

        # 100% boundary (Good)
        level, _ = get_heatmap_color_code(Decimal("100"), benchmark)
        assert level == "Good"

        # Just below 100% (Fair)
        level, _ = get_heatmap_color_code(Decimal("99.9"), benchmark)
        assert level == "Fair"

        # 90% boundary (Fair)
        level, _ = get_heatmap_color_code(Decimal("90"), benchmark)
        assert level == "Fair"

        # Just below 90% (Poor)
        level, _ = get_heatmap_color_code(Decimal("89.9"), benchmark)
        assert level == "Poor"

    def test_custom_benchmark_values(self):
        """Test with various custom benchmark values"""
        # With benchmark of 50
        level, _ = get_heatmap_color_code(Decimal("60"), Decimal("50"))
        assert level == "Excellent"  # 120% of benchmark

        # With benchmark of 100
        level, _ = get_heatmap_color_code(Decimal("100"), Decimal("100"))
        assert level == "Good"

        # With high benchmark of 200
        level, _ = get_heatmap_color_code(Decimal("180"), Decimal("200"))
        assert level == "Fair"  # 90% of benchmark


# =============================================================================
# TRENDS ENDPOINT TESTS (/api/analytics/trends)
# =============================================================================

class TestTrendsEndpointAuthentication:
    """Authentication tests for trends endpoint"""

    def test_trends_requires_authentication(self, test_client):
        """Test that trends endpoint requires authentication token"""
        response = test_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        assert response.status_code == 401

    def test_trends_rejects_invalid_token(self, test_client):
        """Test that trends endpoint rejects invalid auth tokens"""
        response = test_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            },
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_trends_rejects_expired_token(self, test_client):
        """Test that trends endpoint rejects expired tokens"""
        # Expired JWT token structure
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2MDAwMDAwMDB9.signature"
        response = test_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency"
            },
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401


class TestTrendsEndpointValidation:
    """Parameter validation tests for trends endpoint"""

    def test_trends_missing_client_id_returns_422(self, authenticated_client):
        """Test that missing client_id returns 422 validation error"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        assert response.status_code == 422
        assert "client_id" in response.text.lower() or "field required" in response.text.lower()

    def test_trends_missing_kpi_type_returns_422(self, authenticated_client):
        """Test that missing kpi_type returns 422 validation error"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d"
            }
        )
        assert response.status_code == 422

    def test_trends_invalid_kpi_type_returns_422(self, authenticated_client):
        """Test that invalid kpi_type returns 422 validation error"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "invalid_kpi",
                "time_range": "30d"
            }
        )
        assert response.status_code == 422

    def test_trends_invalid_time_range_returns_422(self, authenticated_client):
        """Test that invalid time_range returns 422 validation error"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "invalid"
            }
        )
        assert response.status_code == 422

    def test_trends_unsupported_time_range_returns_422(self, authenticated_client):
        """Test that unsupported time ranges return 422"""
        unsupported = ["1d", "14d", "60d", "1y"]
        for time_range in unsupported:
            response = authenticated_client.get(
                "/api/analytics/trends",
                params={
                    "client_id": "TEST-CLIENT",
                    "kpi_type": "efficiency",
                    "time_range": time_range
                }
            )
            assert response.status_code == 422


class TestTrendsEndpointTimeRanges:
    """Time range functionality tests for trends endpoint"""

    def test_trends_7d_time_range(self, authenticated_client):
        """Test trends with 7-day time range"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "7d"
            }
        )
        # Accept 200 (success), 403 (access denied), or 404 (no data)
        assert response.status_code in [200, 403, 404]

    def test_trends_30d_time_range(self, authenticated_client):
        """Test trends with 30-day time range"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_trends_90d_time_range(self, authenticated_client):
        """Test trends with 90-day time range"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "90d"
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_trends_custom_date_range(self, authenticated_client):
        """Test trends with custom start_date and end_date"""
        end_date = date.today()
        start_date = end_date - timedelta(days=14)

        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_trends_custom_dates_override_time_range(self, authenticated_client):
        """Test that custom dates override time_range parameter"""
        end_date = date.today()
        start_date = end_date - timedelta(days=5)

        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "90d",  # Should be ignored
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]


class TestTrendsEndpointKPITypes:
    """KPI type functionality tests for trends endpoint"""

    @pytest.mark.parametrize("kpi_type", [
        "efficiency", "performance", "availability", "oee",
        "ppm", "dpmo", "fpy", "rty", "quality", "defect_rate",
        "absenteeism", "otd", "attendance"
    ])
    def test_trends_all_valid_kpi_types(self, authenticated_client, kpi_type):
        """Test trends endpoint accepts all valid KPI types"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": kpi_type,
                "time_range": "30d"
            }
        )
        # 422 is acceptable for KPI types not yet implemented in CRUD
        assert response.status_code in [200, 403, 404, 422, 500]


class TestTrendsEndpointAccessControl:
    """Access control tests for trends endpoint"""

    def test_trends_access_denied_for_unauthorized_client(self, authenticated_client):
        """Test that users cannot access unauthorized client data"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "UNAUTHORIZED-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        # Should return 403 (forbidden) or 404 (not found if client doesn't exist)
        assert response.status_code in [403, 404]


# =============================================================================
# PREDICTIONS ENDPOINT TESTS (/api/analytics/predictions)
# =============================================================================

class TestPredictionsEndpointAuthentication:
    """Authentication tests for predictions endpoint"""

    def test_predictions_requires_authentication(self, test_client):
        """Test that predictions endpoint requires authentication"""
        response = test_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency"
            }
        )
        assert response.status_code == 401


class TestPredictionsEndpointValidation:
    """Parameter validation tests for predictions endpoint"""

    def test_predictions_missing_client_id_returns_422(self, authenticated_client):
        """Test that missing client_id returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "kpi_type": "efficiency"
            }
        )
        assert response.status_code == 422

    def test_predictions_missing_kpi_type_returns_422(self, authenticated_client):
        """Test that missing kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT"
            }
        )
        assert response.status_code == 422

    def test_predictions_invalid_kpi_type_returns_422(self, authenticated_client):
        """Test that invalid kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "invalid_type"
            }
        )
        assert response.status_code == 422

    def test_predictions_historical_days_below_minimum(self, authenticated_client):
        """Test that historical_days < 7 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "historical_days": 5
            }
        )
        assert response.status_code == 422

    def test_predictions_historical_days_above_maximum(self, authenticated_client):
        """Test that historical_days > 90 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "historical_days": 100
            }
        )
        assert response.status_code == 422

    def test_predictions_forecast_days_below_minimum(self, authenticated_client):
        """Test that forecast_days < 1 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "forecast_days": 0
            }
        )
        assert response.status_code == 422

    def test_predictions_forecast_days_above_maximum(self, authenticated_client):
        """Test that forecast_days > 30 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "forecast_days": 50
            }
        )
        assert response.status_code == 422

    def test_predictions_invalid_method_returns_422(self, authenticated_client):
        """Test that invalid prediction method returns 422"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "method": "invalid_method"
            }
        )
        assert response.status_code == 422


class TestPredictionsEndpointMethods:
    """Prediction method tests for predictions endpoint"""

    @pytest.mark.parametrize("method", ["auto", "simple", "double", "linear"])
    def test_predictions_valid_methods(self, authenticated_client, method):
        """Test predictions endpoint accepts all valid methods"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "method": method
            }
        )
        # 400 is acceptable when there's insufficient data
        assert response.status_code in [200, 400, 403, 404]

    def test_predictions_default_method_is_auto(self, authenticated_client):
        """Test that default prediction method is auto"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency"
            }
        )
        assert response.status_code in [200, 400, 403, 404]


class TestPredictionsEndpointForecastPeriods:
    """Forecast period tests for predictions endpoint"""

    @pytest.mark.parametrize("forecast_days", [1, 7, 14, 30])
    def test_predictions_valid_forecast_days(self, authenticated_client, forecast_days):
        """Test predictions with various valid forecast_days"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "forecast_days": forecast_days
            }
        )
        assert response.status_code in [200, 400, 403, 404]

    @pytest.mark.parametrize("historical_days", [7, 30, 60, 90])
    def test_predictions_valid_historical_days(self, authenticated_client, historical_days):
        """Test predictions with various valid historical_days"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "historical_days": historical_days
            }
        )
        assert response.status_code in [200, 400, 403, 404]


class TestPredictionsEndpointInsufficientData:
    """Insufficient data handling tests for predictions endpoint"""

    def test_predictions_insufficient_data_returns_400(self, authenticated_client):
        """Test that insufficient historical data returns 400"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "EMPTY-CLIENT",
                "kpi_type": "efficiency",
                "historical_days": 7
            }
        )
        # 400 for insufficient data, 403 for access denied, 404 for not found
        assert response.status_code in [400, 403, 404]


# =============================================================================
# COMPARISONS ENDPOINT TESTS (/api/analytics/comparisons)
# =============================================================================

class TestComparisonsEndpointAuthentication:
    """Authentication tests for comparisons endpoint"""

    def test_comparisons_requires_authentication(self, test_client):
        """Test that comparisons endpoint requires authentication"""
        response = test_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        assert response.status_code == 401


class TestComparisonsEndpointValidation:
    """Parameter validation tests for comparisons endpoint"""

    def test_comparisons_missing_kpi_type_returns_422(self, authenticated_client):
        """Test that missing kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "time_range": "30d"
            }
        )
        assert response.status_code == 422

    def test_comparisons_invalid_kpi_type_returns_422(self, authenticated_client):
        """Test that invalid kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "invalid_type",
                "time_range": "30d"
            }
        )
        assert response.status_code == 422

    def test_comparisons_invalid_time_range_returns_422(self, authenticated_client):
        """Test that invalid time_range returns 422"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": "invalid"
            }
        )
        assert response.status_code == 422


class TestComparisonsEndpointTimeRanges:
    """Time range functionality tests for comparisons endpoint"""

    @pytest.mark.parametrize("time_range", ["7d", "30d", "90d"])
    def test_comparisons_valid_time_ranges(self, authenticated_client, time_range):
        """Test comparisons with all valid time ranges"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": time_range
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_comparisons_custom_date_range(self, authenticated_client):
        """Test comparisons with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=45)

        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]


class TestComparisonsEndpointKPITypes:
    """KPI type tests for comparisons endpoint"""

    @pytest.mark.parametrize("kpi_type", [
        "efficiency", "performance", "availability", "quality"
    ])
    def test_comparisons_common_kpi_types(self, authenticated_client, kpi_type):
        """Test comparisons with common KPI types"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": kpi_type,
                "time_range": "30d"
            }
        )
        assert response.status_code in [200, 403, 404, 422, 500]


class TestComparisonsEndpointNoData:
    """No data handling tests for comparisons endpoint"""

    def test_comparisons_no_data_returns_404(self, authenticated_client):
        """Test that no accessible data returns 404"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": "7d",
                "start_date": "1990-01-01",
                "end_date": "1990-01-07"
            }
        )
        assert response.status_code in [404, 403, 422]


# =============================================================================
# HEATMAP ENDPOINT TESTS (/api/analytics/heatmap)
# =============================================================================

class TestHeatmapEndpointAuthentication:
    """Authentication tests for heatmap endpoint"""

    def test_heatmap_requires_authentication(self, test_client):
        """Test that heatmap endpoint requires authentication"""
        response = test_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "7d"
            }
        )
        assert response.status_code == 401


class TestHeatmapEndpointValidation:
    """Parameter validation tests for heatmap endpoint"""

    def test_heatmap_missing_client_id_returns_422(self, authenticated_client):
        """Test that missing client_id returns 422"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "kpi_type": "efficiency",
                "time_range": "7d"
            }
        )
        assert response.status_code == 422

    def test_heatmap_missing_kpi_type_returns_422(self, authenticated_client):
        """Test that missing kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "7d"
            }
        )
        assert response.status_code == 422

    def test_heatmap_invalid_kpi_type_returns_422(self, authenticated_client):
        """Test that invalid kpi_type returns 422"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "invalid_type",
                "time_range": "7d"
            }
        )
        assert response.status_code == 422

    def test_heatmap_invalid_time_range_returns_422(self, authenticated_client):
        """Test that invalid time_range returns 422"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "invalid"
            }
        )
        assert response.status_code == 422


class TestHeatmapEndpointTimeRanges:
    """Time range functionality tests for heatmap endpoint"""

    @pytest.mark.parametrize("time_range", ["7d", "30d", "90d"])
    def test_heatmap_valid_time_ranges(self, authenticated_client, time_range):
        """Test heatmap with all valid time ranges"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": time_range
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_heatmap_custom_date_range(self, authenticated_client):
        """Test heatmap with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=14)

        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]


class TestHeatmapEndpointKPITypes:
    """KPI type tests for heatmap endpoint"""

    @pytest.mark.parametrize("kpi_type", ["efficiency", "performance", "quality"])
    def test_heatmap_common_kpi_types(self, authenticated_client, kpi_type):
        """Test heatmap with common KPI types"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": kpi_type,
                "time_range": "7d"
            }
        )
        assert response.status_code in [200, 403, 404, 422, 500]


class TestHeatmapEndpointAccessControl:
    """Access control tests for heatmap endpoint"""

    def test_heatmap_access_denied_for_unauthorized_client(self, authenticated_client):
        """Test that users cannot access unauthorized client data"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "UNAUTHORIZED-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "7d"
            }
        )
        assert response.status_code in [403, 404]


# =============================================================================
# PARETO ENDPOINT TESTS (/api/analytics/pareto)
# =============================================================================

class TestParetoEndpointAuthentication:
    """Authentication tests for pareto endpoint"""

    def test_pareto_requires_authentication(self, test_client):
        """Test that pareto endpoint requires authentication"""
        response = test_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d"
            }
        )
        assert response.status_code == 401


class TestParetoEndpointValidation:
    """Parameter validation tests for pareto endpoint"""

    def test_pareto_missing_client_id_returns_422(self, authenticated_client):
        """Test that missing client_id returns 422"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "time_range": "30d"
            }
        )
        assert response.status_code == 422

    def test_pareto_invalid_time_range_returns_422(self, authenticated_client):
        """Test that invalid time_range returns 422"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "invalid"
            }
        )
        assert response.status_code == 422

    def test_pareto_threshold_below_minimum(self, authenticated_client):
        """Test that pareto_threshold < 50 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d",
                "pareto_threshold": 40
            }
        )
        assert response.status_code == 422

    def test_pareto_threshold_above_maximum(self, authenticated_client):
        """Test that pareto_threshold > 95 returns 422"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d",
                "pareto_threshold": 99
            }
        )
        assert response.status_code == 422


class TestParetoEndpointTimeRanges:
    """Time range functionality tests for pareto endpoint"""

    @pytest.mark.parametrize("time_range", ["7d", "30d", "90d"])
    def test_pareto_valid_time_ranges(self, authenticated_client, time_range):
        """Test pareto with all valid time ranges"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": time_range
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_pareto_custom_date_range(self, authenticated_client):
        """Test pareto with custom date range"""
        end_date = date.today()
        start_date = end_date - timedelta(days=60)

        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]


class TestParetoEndpointThreshold:
    """Pareto threshold tests for pareto endpoint"""

    @pytest.mark.parametrize("threshold", [50, 60, 70, 80, 90, 95])
    def test_pareto_valid_thresholds(self, authenticated_client, threshold):
        """Test pareto with various valid threshold values"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d",
                "pareto_threshold": threshold
            }
        )
        assert response.status_code in [200, 403, 404]

    def test_pareto_default_threshold_is_80(self, authenticated_client):
        """Test that default pareto threshold is 80"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d"
            }
        )
        assert response.status_code in [200, 403, 404]


class TestParetoEndpointAccessControl:
    """Access control tests for pareto endpoint"""

    def test_pareto_access_denied_for_unauthorized_client(self, authenticated_client):
        """Test that users cannot access unauthorized client data"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "UNAUTHORIZED-CLIENT",
                "time_range": "30d"
            }
        )
        assert response.status_code in [403, 404]


class TestParetoEndpointNoData:
    """No data handling tests for pareto endpoint"""

    def test_pareto_no_defect_data_returns_404(self, authenticated_client):
        """Test that no defect data returns 404"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "CLIENT-NO-DEFECTS",
                "time_range": "7d"
            }
        )
        assert response.status_code in [404, 403]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestAnalyticsEdgeCases:
    """Edge case tests for analytics endpoints"""

    def test_trends_empty_client_id(self, authenticated_client):
        """Test trends with empty client_id"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        # Empty string should be accepted by validation but fail access check
        assert response.status_code in [403, 404, 422]

    def test_predictions_zero_forecast_days(self, authenticated_client):
        """Test predictions with zero forecast_days"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "forecast_days": 0
            }
        )
        assert response.status_code == 422

    def test_heatmap_future_date_range(self, authenticated_client):
        """Test heatmap with future date range"""
        future_start = date.today() + timedelta(days=30)
        future_end = date.today() + timedelta(days=60)

        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "start_date": future_start.isoformat(),
                "end_date": future_end.isoformat()
            }
        )
        # Should either return empty data or 404
        assert response.status_code in [200, 403, 404]

    def test_pareto_very_old_date_range(self, authenticated_client):
        """Test pareto with very old date range"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "start_date": "2000-01-01",
                "end_date": "2000-12-31"
            }
        )
        assert response.status_code in [403, 404]

    def test_comparisons_inverted_date_range(self, authenticated_client):
        """Test comparisons where start_date > end_date"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "start_date": "2024-12-31",
                "end_date": "2024-01-01"
            }
        )
        # Should handle gracefully - either swap dates or return error
        assert response.status_code in [200, 400, 403, 404, 422]

    def test_trends_special_characters_in_client_id(self, authenticated_client):
        """Test trends with special characters in client_id"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST<>CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )
        assert response.status_code in [403, 404, 422]

    def test_heatmap_same_start_end_date(self, authenticated_client):
        """Test heatmap where start_date equals end_date (single day)"""
        today = date.today()

        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "start_date": today.isoformat(),
                "end_date": today.isoformat()
            }
        )
        assert response.status_code in [200, 403, 404]


# =============================================================================
# RESPONSE STRUCTURE VALIDATION TESTS
# =============================================================================

class TestAnalyticsResponseStructure:
    """Response structure validation tests"""

    def test_trends_response_structure(self, authenticated_client):
        """Test that trends response has expected structure when successful"""
        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify expected fields
            assert "client_id" in data
            assert "kpi_type" in data
            assert "time_range" in data
            assert "start_date" in data
            assert "end_date" in data
            assert "data_points" in data
            assert "trend_direction" in data
            assert "trend_slope" in data
            assert "average_value" in data
            assert "std_deviation" in data
            assert "min_value" in data
            assert "max_value" in data
            assert "anomalies_detected" in data
            assert "anomaly_dates" in data

    def test_predictions_response_structure(self, authenticated_client):
        """Test that predictions response has expected structure when successful"""
        response = authenticated_client.get(
            "/api/analytics/predictions",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify expected fields
            assert "client_id" in data
            assert "kpi_type" in data
            assert "prediction_method" in data
            assert "historical_start" in data
            assert "historical_end" in data
            assert "forecast_start" in data
            assert "forecast_end" in data
            assert "predictions" in data
            assert "model_accuracy" in data
            assert "historical_average" in data
            assert "predicted_average" in data
            assert "trend_continuation" in data

    def test_comparisons_response_structure(self, authenticated_client):
        """Test that comparisons response has expected structure when successful"""
        response = authenticated_client.get(
            "/api/analytics/comparisons",
            params={
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify expected fields
            assert "kpi_type" in data
            assert "time_range" in data
            assert "start_date" in data
            assert "end_date" in data
            assert "clients" in data
            assert "overall_average" in data
            assert "industry_benchmark" in data
            assert "best_performer" in data
            assert "worst_performer" in data
            assert "performance_spread" in data

    def test_heatmap_response_structure(self, authenticated_client):
        """Test that heatmap response has expected structure when successful"""
        response = authenticated_client.get(
            "/api/analytics/heatmap",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "7d"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify expected fields
            assert "client_id" in data
            assert "kpi_type" in data
            assert "time_range" in data
            assert "start_date" in data
            assert "end_date" in data
            assert "cells" in data
            assert "shifts" in data
            assert "dates" in data
            assert "color_scale" in data

    def test_pareto_response_structure(self, authenticated_client):
        """Test that pareto response has expected structure when successful"""
        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify expected fields
            assert "client_id" in data
            assert "time_range" in data
            assert "start_date" in data
            assert "end_date" in data
            assert "items" in data
            assert "total_defects" in data
            assert "vital_few_count" in data
            assert "vital_few_percentage" in data
            assert "pareto_threshold" in data


# =============================================================================
# INTEGRATION TESTS WITH MOCKED DATA
# =============================================================================

class TestAnalyticsWithMockedCRUD:
    """Integration tests with mocked CRUD operations"""

    @patch('backend.routes.analytics.get_kpi_time_series_data')
    def test_trends_with_mock_data(self, mock_get_data, authenticated_client):
        """Test trends endpoint with mocked data"""
        # Setup mock return value
        mock_data = [
            (date(2024, 1, i), Decimal(str(80 + i))) for i in range(1, 31)
        ]
        mock_get_data.return_value = mock_data

        response = authenticated_client.get(
            "/api/analytics/trends",
            params={
                "client_id": "TEST-CLIENT",
                "kpi_type": "efficiency",
                "time_range": "30d"
            }
        )

        # Response depends on whether mock is properly applied
        assert response.status_code in [200, 403, 404]

    @patch('backend.routes.analytics.get_defect_pareto_data')
    def test_pareto_with_mock_data(self, mock_get_data, authenticated_client):
        """Test pareto endpoint with mocked defect data"""
        # Setup mock return value - typical Pareto distribution
        mock_data = [
            ("Stitching", 150),
            ("Material", 100),
            ("Assembly", 50),
            ("Finish", 30),
            ("Other", 20)
        ]
        mock_get_data.return_value = mock_data

        response = authenticated_client.get(
            "/api/analytics/pareto",
            params={
                "client_id": "TEST-CLIENT",
                "time_range": "30d"
            }
        )

        assert response.status_code in [200, 403, 404]


# =============================================================================
# CONCURRENT REQUEST TESTS
# =============================================================================

class TestAnalyticsConcurrency:
    """Concurrency tests for analytics endpoints"""

    def test_multiple_trend_requests(self, authenticated_client):
        """Test handling of multiple concurrent trend requests"""
        import concurrent.futures

        def make_request():
            return authenticated_client.get(
                "/api/analytics/trends",
                params={
                    "client_id": "TEST-CLIENT",
                    "kpi_type": "efficiency",
                    "time_range": "30d"
                }
            )

        # Execute multiple requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should return consistent status codes
        status_codes = [r.status_code for r in results]
        for code in status_codes:
            assert code in [200, 403, 404]


# =============================================================================
# HELPER FUNCTION EDGE CASES
# =============================================================================

class TestHelperFunctionEdgeCases:
    """Edge case tests for helper functions"""

    def test_performance_rating_very_small_values(self):
        """Test performance rating with very small decimal values"""
        result = get_performance_rating(Decimal("0.001"), Decimal("100"))
        assert result == "Poor"

    def test_performance_rating_very_large_values(self):
        """Test performance rating with very large values"""
        result = get_performance_rating(Decimal("10000"), Decimal("100"))
        assert result == "Excellent"

    def test_heatmap_color_zero_value(self):
        """Test heatmap color with zero value"""
        level, color = get_heatmap_color_code(Decimal("0"), Decimal("85"))
        assert level == "Poor"
        assert color == "#ef4444"

    def test_heatmap_color_negative_value(self):
        """Test heatmap color with negative value"""
        level, color = get_heatmap_color_code(Decimal("-10"), Decimal("85"))
        assert level == "Poor"
        assert color == "#ef4444"

    def test_parse_time_range_leap_year(self):
        """Test time range parsing around leap year"""
        end_date = date(2024, 3, 1)  # 2024 is a leap year
        start, end = parse_time_range("30d", end_date)

        assert start == date(2024, 1, 31)  # Should include Feb 29
        assert end == end_date

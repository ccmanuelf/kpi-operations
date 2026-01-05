"""
Trend Analysis and Predictions Calculation Tests
Unit tests for trend analysis and forecasting algorithms
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from backend.calculations.trend_analysis import (
    calculate_moving_average,
    calculate_exponential_moving_average,
    linear_regression,
    determine_trend_direction,
    detect_anomalies,
    calculate_seasonal_decomposition,
    analyze_trend
)
from backend.calculations.predictions import (
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
    auto_forecast,
    calculate_forecast_accuracy
)


class TestMovingAverage:
    """Tests for moving average calculations"""

    def test_simple_moving_average(self):
        """Test simple moving average calculation"""
        values = [Decimal("85.0"), Decimal("86.5"), Decimal("84.2"), Decimal("87.1"), Decimal("88.0")]
        result = calculate_moving_average(values, 3)

        assert len(result) == len(values)
        assert result[0] is None  # Not enough data
        assert result[1] is None  # Not enough data
        assert result[2] is not None
        # (85.0 + 86.5 + 84.2) / 3 = 85.23
        assert abs(result[2] - Decimal("85.23")) < Decimal("0.1")

    def test_moving_average_window_size_1(self):
        """Test moving average with window size 1 (returns original values)"""
        values = [Decimal("85.0"), Decimal("86.5"), Decimal("84.2")]
        result = calculate_moving_average(values, 1)

        for i in range(len(values)):
            assert result[i] == values[i]

    def test_moving_average_invalid_window(self):
        """Test with invalid window size"""
        values = [Decimal("85.0"), Decimal("86.5")]

        with pytest.raises(ValueError):
            calculate_moving_average(values, 0)

    def test_exponential_moving_average(self):
        """Test exponential moving average"""
        values = [Decimal("85.0"), Decimal("86.5"), Decimal("84.2"), Decimal("87.1"), Decimal("88.0")]
        result = calculate_exponential_moving_average(values, Decimal("0.3"))

        assert len(result) == len(values)
        assert result[0] == values[0]  # First value unchanged
        assert all(r is not None for r in result)

    def test_exponential_moving_average_invalid_alpha(self):
        """Test with invalid alpha parameter"""
        values = [Decimal("85.0"), Decimal("86.5")]

        with pytest.raises(ValueError):
            calculate_exponential_moving_average(values, Decimal("0"))

        with pytest.raises(ValueError):
            calculate_exponential_moving_average(values, Decimal("1.5"))


class TestLinearRegression:
    """Tests for linear regression"""

    def test_linear_regression_increasing_trend(self):
        """Test regression with clear increasing trend"""
        x = [1, 2, 3, 4, 5]
        y = [Decimal("85.0"), Decimal("87.0"), Decimal("89.0"), Decimal("91.0"), Decimal("93.0")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert slope > 0  # Positive trend
        assert r_squared > Decimal("0.9")  # Good fit

    def test_linear_regression_decreasing_trend(self):
        """Test regression with decreasing trend"""
        x = [1, 2, 3, 4, 5]
        y = [Decimal("93.0"), Decimal("91.0"), Decimal("89.0"), Decimal("87.0"), Decimal("85.0")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert slope < 0  # Negative trend
        assert r_squared > Decimal("0.9")  # Good fit

    def test_linear_regression_stable(self):
        """Test regression with stable data"""
        x = [1, 2, 3, 4, 5]
        y = [Decimal("85.0"), Decimal("85.0"), Decimal("85.0"), Decimal("85.0"), Decimal("85.0")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert abs(slope) < Decimal("0.01")  # Near-zero slope
        assert abs(intercept - Decimal("85.0")) < Decimal("0.1")

    def test_linear_regression_insufficient_data(self):
        """Test with insufficient data points"""
        x = [1]
        y = [Decimal("85.0")]

        with pytest.raises(ValueError):
            linear_regression(x, y)

    def test_linear_regression_mismatched_lengths(self):
        """Test with mismatched X and Y lengths"""
        x = [1, 2, 3]
        y = [Decimal("85.0"), Decimal("86.0")]

        with pytest.raises(ValueError):
            linear_regression(x, y)


class TestTrendDirection:
    """Tests for trend direction classification"""

    def test_trend_increasing(self):
        """Test increasing trend classification"""
        slope = Decimal("0.5")
        r_squared = Decimal("0.8")
        std_dev = Decimal("2.0")
        mean_value = Decimal("85.0")

        direction = determine_trend_direction(slope, r_squared, std_dev, mean_value)
        assert direction == "increasing"

    def test_trend_decreasing(self):
        """Test decreasing trend classification"""
        slope = Decimal("-0.5")
        r_squared = Decimal("0.8")
        std_dev = Decimal("2.0")
        mean_value = Decimal("85.0")

        direction = determine_trend_direction(slope, r_squared, std_dev, mean_value)
        assert direction == "decreasing"

    def test_trend_stable(self):
        """Test stable trend classification"""
        slope = Decimal("0.05")
        r_squared = Decimal("0.8")
        std_dev = Decimal("1.0")
        mean_value = Decimal("85.0")

        direction = determine_trend_direction(slope, r_squared, std_dev, mean_value)
        assert direction == "stable"

    def test_trend_volatile(self):
        """Test volatile trend classification"""
        slope = Decimal("0.5")
        r_squared = Decimal("0.2")  # Low R-squared
        std_dev = Decimal("5.0")
        mean_value = Decimal("85.0")

        direction = determine_trend_direction(slope, r_squared, std_dev, mean_value)
        assert direction == "volatile"


class TestAnomalyDetection:
    """Tests for anomaly detection"""

    def test_detect_anomalies_with_outlier(self):
        """Test anomaly detection with clear outlier"""
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("84.5"), Decimal("100.0"), Decimal("85.5")]

        anomalies = detect_anomalies(values, Decimal("2.0"))

        assert len(anomalies) > 0
        assert 3 in anomalies  # Index of 100.0

    def test_detect_anomalies_no_outliers(self):
        """Test with no anomalies"""
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("84.5"), Decimal("85.5"), Decimal("86.5")]

        anomalies = detect_anomalies(values, Decimal("2.0"))

        assert len(anomalies) == 0

    def test_detect_anomalies_insufficient_data(self):
        """Test with insufficient data"""
        values = [Decimal("85.0"), Decimal("86.0")]

        anomalies = detect_anomalies(values, Decimal("2.0"))

        assert len(anomalies) == 0


class TestSeasonalDecomposition:
    """Tests for seasonal decomposition"""

    def test_seasonal_decomposition(self):
        """Test seasonal decomposition with weekly pattern"""
        # Create data with weekly pattern
        values = []
        for week in range(4):
            values.extend([
                Decimal("80.0"), Decimal("85.0"), Decimal("90.0"),
                Decimal("88.0"), Decimal("85.0"), Decimal("82.0"), Decimal("78.0")
            ])

        result = calculate_seasonal_decomposition(values, period=7)

        assert "trend" in result
        assert "seasonal" in result
        assert "residual" in result

        assert len(result["trend"]) == len(values)
        assert len(result["seasonal"]) == len(values)
        assert len(result["residual"]) == len(values)

    def test_seasonal_decomposition_insufficient_data(self):
        """Test with insufficient data for decomposition"""
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("87.0")]

        result = calculate_seasonal_decomposition(values, period=7)

        # Should return simplified results
        assert len(result["trend"]) == len(values)


class TestAnalyzeTrend:
    """Tests for comprehensive trend analysis"""

    def test_analyze_trend_increasing(self):
        """Test trend analysis with increasing data"""
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]
        values = [Decimal(str(85.0 + i)) for i in range(10)]

        result = analyze_trend(dates, values)

        assert result.slope > 0
        assert result.trend_direction in ["increasing", "stable"]
        assert result.r_squared > Decimal("0.8")

    def test_analyze_trend_insufficient_data(self):
        """Test with insufficient data"""
        dates = [date(2024, 1, 1)]
        values = [Decimal("85.0")]

        with pytest.raises(ValueError):
            analyze_trend(dates, values)


class TestSimpleExponentialSmoothing:
    """Tests for simple exponential smoothing"""

    def test_simple_exponential_smoothing(self):
        """Test basic exponential smoothing forecast"""
        values = [Decimal("85.0"), Decimal("86.5"), Decimal("84.2"), Decimal("87.1"), Decimal("88.0")]

        result = simple_exponential_smoothing(values, forecast_periods=7)

        assert len(result.predictions) == 7
        assert len(result.lower_bounds) == 7
        assert len(result.upper_bounds) == 7
        assert len(result.confidence_scores) == 7

        # Confidence should decrease over time
        assert result.confidence_scores[0] > result.confidence_scores[-1]

        # Bounds should make sense
        for i in range(len(result.predictions)):
            assert result.lower_bounds[i] < result.predictions[i]
            assert result.upper_bounds[i] > result.predictions[i]

    def test_simple_exponential_smoothing_insufficient_data(self):
        """Test with insufficient historical data"""
        values = [Decimal("85.0")]

        with pytest.raises(ValueError):
            simple_exponential_smoothing(values, forecast_periods=7)


class TestDoubleExponentialSmoothing:
    """Tests for double exponential smoothing (Holt's method)"""

    def test_double_exponential_smoothing(self):
        """Test double exponential smoothing with trending data"""
        values = [Decimal(str(85.0 + i * 0.5)) for i in range(20)]

        result = double_exponential_smoothing(values, forecast_periods=7)

        assert len(result.predictions) == 7
        assert result.method == "double_exponential_smoothing"

        # Should capture upward trend
        assert result.predictions[-1] > values[-1]

    def test_double_exponential_smoothing_fallback(self):
        """Test fallback to simple smoothing with insufficient data"""
        values = [Decimal("85.0"), Decimal("86.0")]

        result = double_exponential_smoothing(values, forecast_periods=7)

        # Should fall back to simple exponential smoothing
        assert result.method == "simple_exponential_smoothing"


class TestLinearTrendExtrapolation:
    """Tests for linear trend extrapolation"""

    def test_linear_trend_extrapolation(self):
        """Test linear extrapolation with clear trend"""
        values = [Decimal(str(85.0 + i)) for i in range(10)]

        result = linear_trend_extrapolation(values, forecast_periods=7)

        assert len(result.predictions) == 7
        assert result.method == "linear_trend_extrapolation"

        # Should continue upward trend
        assert result.predictions[0] > values[-1]

    def test_linear_trend_extrapolation_insufficient_data(self):
        """Test with insufficient data"""
        values = [Decimal("85.0")]

        with pytest.raises(ValueError):
            linear_trend_extrapolation(values, forecast_periods=7)


class TestAutoForecast:
    """Tests for automatic forecast method selection"""

    def test_auto_forecast_stable_data(self):
        """Test auto forecast with stable data"""
        values = [Decimal("85.0") + Decimal(str(i % 3)) for i in range(20)]

        result = auto_forecast(values, forecast_periods=7)

        assert len(result.predictions) == 7
        # Should use simple smoothing for stable data
        assert result.method in ["simple_exponential_smoothing", "linear_trend_extrapolation"]

    def test_auto_forecast_trending_data(self):
        """Test auto forecast with trending data"""
        values = [Decimal(str(85.0 + i * 0.5)) for i in range(20)]

        result = auto_forecast(values, forecast_periods=7)

        assert len(result.predictions) == 7
        # Should use method appropriate for trending data


class TestForecastAccuracy:
    """Tests for forecast accuracy metrics"""

    def test_calculate_forecast_accuracy(self):
        """Test accuracy metric calculation"""
        actual = [Decimal("85.0"), Decimal("86.0"), Decimal("87.0")]
        predicted = [Decimal("85.5"), Decimal("85.8"), Decimal("87.2")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        assert "mae" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics

        assert metrics["mae"] > 0
        assert metrics["rmse"] > 0
        assert metrics["mape"] >= 0

    def test_calculate_forecast_accuracy_perfect_fit(self):
        """Test with perfect predictions"""
        actual = [Decimal("85.0"), Decimal("86.0"), Decimal("87.0")]
        predicted = [Decimal("85.0"), Decimal("86.0"), Decimal("87.0")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        assert metrics["mae"] == Decimal("0")
        assert metrics["rmse"] == Decimal("0")
        assert metrics["mape"] == Decimal("0")

    def test_calculate_forecast_accuracy_mismatched_lengths(self):
        """Test with mismatched array lengths"""
        actual = [Decimal("85.0"), Decimal("86.0")]
        predicted = [Decimal("85.5")]

        with pytest.raises(ValueError):
            calculate_forecast_accuracy(actual, predicted)

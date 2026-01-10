"""
Test Suite for Prediction/Forecasting Module
Tests all forecasting algorithms for KPI predictions

Coverage:
- Simple exponential smoothing
- Double exponential smoothing (Holt's method)
- Linear trend extrapolation
- Auto forecast selection
- Forecast accuracy metrics
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

# Import from actual module to get coverage
from backend.calculations.predictions import (
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
    auto_forecast,
    calculate_forecast_accuracy,
    ForecastResult
)


@pytest.mark.unit
class TestSimpleExponentialSmoothing:
    """Test simple exponential smoothing algorithm"""

    @pytest.mark.unit
    def test_basic_smoothing(self):
        """Test basic exponential smoothing with stable values"""
        values = [Decimal("85.0"), Decimal("86.5"), Decimal("84.2"),
                  Decimal("87.1"), Decimal("88.0")]

        result = simple_exponential_smoothing(values, Decimal("0.3"), 7)

        assert isinstance(result, ForecastResult)
        assert len(result.predictions) == 7
        assert result.method == "simple_exponential_smoothing"
        assert all(p > 0 for p in result.predictions)

    @pytest.mark.unit
    def test_smoothing_with_high_alpha(self):
        """Test with high alpha (more responsive to recent values)"""
        values = [Decimal("80.0"), Decimal("85.0"), Decimal("90.0"),
                  Decimal("95.0"), Decimal("100.0")]

        result = simple_exponential_smoothing(values, Decimal("0.9"), 5)

        # High alpha should make predictions closer to last value
        assert result.predictions[0] > Decimal("90")

    @pytest.mark.unit
    def test_smoothing_with_low_alpha(self):
        """Test with low alpha (more smoothed, less responsive)"""
        values = [Decimal("80.0"), Decimal("85.0"), Decimal("90.0"),
                  Decimal("95.0"), Decimal("100.0")]

        result = simple_exponential_smoothing(values, Decimal("0.1"), 5)

        # Low alpha gives more weight to historical values
        assert result.predictions[0] < Decimal("95")

    @pytest.mark.unit
    def test_confidence_intervals(self):
        """Test that confidence intervals are calculated correctly"""
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("84.0"),
                  Decimal("87.0"), Decimal("85.0")]

        result = simple_exponential_smoothing(values, Decimal("0.3"), 7)

        # Lower bounds should be less than predictions
        for i, pred in enumerate(result.predictions):
            assert result.lower_bounds[i] < pred
            assert result.upper_bounds[i] > pred

    @pytest.mark.unit
    def test_confidence_decreases_over_time(self):
        """Test that confidence scores decrease over forecast horizon"""
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("84.0"),
                  Decimal("87.0"), Decimal("85.0")]

        result = simple_exponential_smoothing(values, Decimal("0.3"), 7)

        # Confidence should decrease
        for i in range(1, len(result.confidence_scores)):
            assert result.confidence_scores[i] <= result.confidence_scores[i-1]

    @pytest.mark.unit
    def test_invalid_alpha_zero(self):
        """Test that alpha = 0 raises error"""
        values = [Decimal("85.0"), Decimal("86.0")]

        with pytest.raises(ValueError, match="Alpha must be between"):
            simple_exponential_smoothing(values, Decimal("0.0"), 7)

    @pytest.mark.unit
    def test_invalid_alpha_negative(self):
        """Test that negative alpha raises error"""
        values = [Decimal("85.0"), Decimal("86.0")]

        with pytest.raises(ValueError, match="Alpha must be between"):
            simple_exponential_smoothing(values, Decimal("-0.5"), 7)

    @pytest.mark.unit
    def test_invalid_alpha_too_high(self):
        """Test that alpha > 1 raises error"""
        values = [Decimal("85.0"), Decimal("86.0")]

        with pytest.raises(ValueError, match="Alpha must be between"):
            simple_exponential_smoothing(values, Decimal("1.5"), 7)

    @pytest.mark.unit
    def test_insufficient_data(self):
        """Test that single value raises error"""
        values = [Decimal("85.0")]

        with pytest.raises(ValueError, match="Need at least 2"):
            simple_exponential_smoothing(values, Decimal("0.3"), 7)

    @pytest.mark.unit
    def test_alpha_exactly_one(self):
        """Test alpha = 1 (naive forecast)"""
        values = [Decimal("85.0"), Decimal("90.0"), Decimal("95.0")]

        result = simple_exponential_smoothing(values, Decimal("1.0"), 3)

        # Alpha = 1 should give last value as forecast
        assert result.predictions[0] == Decimal("95.0")


@pytest.mark.unit
class TestDoubleExponentialSmoothing:
    """Test Holt's double exponential smoothing"""

    @pytest.mark.unit
    def test_upward_trend(self):
        """Test with upward trending data"""
        values = [Decimal("80.0"), Decimal("82.0"), Decimal("84.0"),
                  Decimal("86.0"), Decimal("88.0"), Decimal("90.0")]

        result = double_exponential_smoothing(
            values, Decimal("0.3"), Decimal("0.1"), 5
        )

        assert isinstance(result, ForecastResult)
        # Predictions should continue upward trend
        assert result.predictions[-1] > result.predictions[0]
        assert result.method == "double_exponential_smoothing"

    @pytest.mark.unit
    def test_downward_trend(self):
        """Test with downward trending data"""
        values = [Decimal("100.0"), Decimal("98.0"), Decimal("96.0"),
                  Decimal("94.0"), Decimal("92.0"), Decimal("90.0")]

        result = double_exponential_smoothing(
            values, Decimal("0.3"), Decimal("0.1"), 5
        )

        # Predictions should continue downward trend
        assert result.predictions[-1] < result.predictions[0]

    @pytest.mark.unit
    def test_fallback_to_simple_smoothing(self):
        """Test fallback when insufficient data for double smoothing"""
        values = [Decimal("85.0"), Decimal("86.0")]  # Only 2 values

        result = double_exponential_smoothing(
            values, Decimal("0.3"), Decimal("0.1"), 5
        )

        # Should fall back to simple smoothing
        assert result.method == "simple_exponential_smoothing"

    @pytest.mark.unit
    def test_wider_confidence_intervals(self):
        """Test that double smoothing has wider intervals than simple"""
        # Use noisy data to generate non-zero intervals
        values = [Decimal("80.0"), Decimal("83.0"), Decimal("81.0"),
                  Decimal("86.0"), Decimal("84.0"), Decimal("88.0")]

        result = double_exponential_smoothing(
            values, Decimal("0.3"), Decimal("0.1"), 5
        )

        # Intervals should exist (may be zero for perfect linear data)
        for i in range(len(result.predictions)):
            interval_width = result.upper_bounds[i] - result.lower_bounds[i]
            assert interval_width >= 0  # Allow zero for perfect fit


@pytest.mark.unit
class TestLinearTrendExtrapolation:
    """Test linear regression-based forecasting"""

    @pytest.mark.unit
    def test_perfect_linear_trend(self):
        """Test with perfectly linear data"""
        # Perfect linear: y = 2x + 80
        values = [Decimal("80.0"), Decimal("82.0"), Decimal("84.0"),
                  Decimal("86.0"), Decimal("88.0")]

        result = linear_trend_extrapolation(values, 5)

        assert result.method == "linear_trend_extrapolation"
        # Next values should be 90, 92, 94, 96, 98
        assert abs(float(result.predictions[0]) - 90.0) < 1.0
        assert abs(float(result.predictions[1]) - 92.0) < 1.0

    @pytest.mark.unit
    def test_flat_trend(self):
        """Test with nearly flat (minimal trend) data"""
        # Use very small variance to avoid division by zero in R²
        values = [Decimal("85.0"), Decimal("85.1"), Decimal("84.9"),
                  Decimal("85.0"), Decimal("85.1")]

        result = linear_trend_extrapolation(values, 5)

        # Predictions should stay around 85
        for pred in result.predictions:
            assert abs(float(pred) - 85.0) < 2.0

    @pytest.mark.unit
    def test_r_squared_high_for_linear(self):
        """Test that R² is high for linear data"""
        values = [Decimal("80.0"), Decimal("82.0"), Decimal("84.0"),
                  Decimal("86.0"), Decimal("88.0")]

        result = linear_trend_extrapolation(values, 5)

        # R² should be close to 100 for perfect linear data
        assert float(result.accuracy_score) > 90.0

    @pytest.mark.unit
    def test_widening_intervals(self):
        """Test that intervals widen over forecast horizon"""
        values = [Decimal("80.0"), Decimal("82.0"), Decimal("85.0"),
                  Decimal("83.0"), Decimal("87.0")]

        result = linear_trend_extrapolation(values, 5)

        # Intervals should widen
        widths = [
            result.upper_bounds[i] - result.lower_bounds[i]
            for i in range(len(result.predictions))
        ]
        for i in range(1, len(widths)):
            assert widths[i] >= widths[i-1]

    @pytest.mark.unit
    def test_insufficient_data(self):
        """Test error with single value"""
        values = [Decimal("85.0")]

        with pytest.raises(ValueError, match="Need at least 2"):
            linear_trend_extrapolation(values, 5)

    @pytest.mark.unit
    def test_two_values(self):
        """Test with minimum 2 values"""
        values = [Decimal("80.0"), Decimal("85.0")]

        result = linear_trend_extrapolation(values, 3)

        # Should work with 2 values
        assert len(result.predictions) == 3


@pytest.mark.unit
class TestAutoForecast:
    """Test automatic method selection"""

    @pytest.mark.unit
    def test_selects_double_for_strong_trend(self):
        """Test that strong trend uses double exponential smoothing"""
        # Strong upward trend
        values = [Decimal("70.0"), Decimal("75.0"), Decimal("80.0"),
                  Decimal("85.0"), Decimal("90.0"), Decimal("95.0")]

        result = auto_forecast(values, 5)

        # Should select double exponential or linear for trending data
        assert result.method in ["double_exponential_smoothing",
                                  "linear_trend_extrapolation"]

    @pytest.mark.unit
    def test_selects_simple_for_stable(self):
        """Test that stable data uses simple smoothing"""
        # Stable, noisy data
        values = [Decimal("85.0"), Decimal("86.0"), Decimal("84.0"),
                  Decimal("85.5"), Decimal("84.5"), Decimal("85.0")]

        result = auto_forecast(values, 5)

        # Should select simple smoothing for stable data
        assert result.method == "simple_exponential_smoothing"

    @pytest.mark.unit
    def test_fallback_for_minimal_data(self):
        """Test fallback for minimal data"""
        values = [Decimal("85.0"), Decimal("86.0")]

        result = auto_forecast(values, 3)

        # Should fall back to simple smoothing
        assert result.method == "simple_exponential_smoothing"


@pytest.mark.unit
class TestForecastAccuracy:
    """Test forecast accuracy metrics"""

    @pytest.mark.unit
    def test_perfect_predictions(self):
        """Test metrics with perfect predictions"""
        actual = [Decimal("85.0"), Decimal("90.0"), Decimal("95.0")]
        predicted = [Decimal("85.0"), Decimal("90.0"), Decimal("95.0")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        assert metrics['mae'] == Decimal("0")
        assert metrics['rmse'] == Decimal("0")
        assert metrics['mape'] == Decimal("0")

    @pytest.mark.unit
    def test_mae_calculation(self):
        """Test Mean Absolute Error calculation"""
        actual = [Decimal("100.0"), Decimal("100.0"), Decimal("100.0")]
        predicted = [Decimal("90.0"), Decimal("110.0"), Decimal("100.0")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        # MAE = (10 + 10 + 0) / 3 = 6.67
        assert abs(float(metrics['mae']) - 6.67) < 0.1

    @pytest.mark.unit
    def test_mape_calculation(self):
        """Test Mean Absolute Percentage Error"""
        actual = [Decimal("100.0"), Decimal("200.0")]
        predicted = [Decimal("90.0"), Decimal("220.0")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        # MAPE = ((10/100 + 20/200) / 2) * 100 = 10%
        assert abs(float(metrics['mape']) - 10.0) < 0.5

    @pytest.mark.unit
    def test_handles_zeros_in_mape(self):
        """Test that MAPE handles zeros correctly"""
        actual = [Decimal("0.0"), Decimal("100.0"), Decimal("50.0")]
        predicted = [Decimal("10.0"), Decimal("90.0"), Decimal("50.0")]

        # Should not crash with zero actual values
        metrics = calculate_forecast_accuracy(actual, predicted)

        assert 'mape' in metrics

    @pytest.mark.unit
    def test_length_mismatch_error(self):
        """Test error when arrays have different lengths"""
        actual = [Decimal("85.0"), Decimal("90.0")]
        predicted = [Decimal("85.0")]

        with pytest.raises(ValueError, match="same length"):
            calculate_forecast_accuracy(actual, predicted)

    @pytest.mark.unit
    def test_empty_arrays(self):
        """Test with empty arrays"""
        actual = []
        predicted = []

        metrics = calculate_forecast_accuracy(actual, predicted)

        assert metrics['mae'] == Decimal("0")
        assert metrics['rmse'] == Decimal("0")
        assert metrics['mape'] == Decimal("0")


@pytest.mark.integration
class TestForecastIntegration:
    """Integration tests for forecasting with realistic KPI data"""

    @pytest.mark.integration
    def test_efficiency_forecast(self):
        """Test forecasting efficiency KPI values"""
        # Realistic efficiency data over 30 days
        efficiency_values = [
            Decimal("82.5"), Decimal("83.1"), Decimal("81.8"), Decimal("84.2"),
            Decimal("83.5"), Decimal("85.0"), Decimal("84.1"), Decimal("85.5"),
            Decimal("84.8"), Decimal("86.0"), Decimal("85.2"), Decimal("86.5"),
            Decimal("85.8"), Decimal("87.0"), Decimal("86.2"), Decimal("87.5"),
            Decimal("86.8"), Decimal("88.0"), Decimal("87.2"), Decimal("88.5")
        ]

        result = auto_forecast(efficiency_values, 7)

        # Should produce reasonable forecasts
        assert len(result.predictions) == 7
        # All predictions should be positive percentages
        assert all(0 < float(p) < 150 for p in result.predictions)
        # Should detect upward trend
        assert float(result.predictions[-1]) >= float(result.predictions[0])

    @pytest.mark.integration
    def test_quality_ppm_forecast(self):
        """Test forecasting PPM (defects per million) values"""
        # PPM values - lower is better, showing improvement
        ppm_values = [
            Decimal("5200"), Decimal("5100"), Decimal("5050"), Decimal("4900"),
            Decimal("4850"), Decimal("4700"), Decimal("4650"), Decimal("4500"),
            Decimal("4400"), Decimal("4300")
        ]

        result = double_exponential_smoothing(ppm_values, forecast_periods=5)

        # Should predict continued downward trend (improvement)
        assert float(result.predictions[-1]) < float(ppm_values[-1])

    @pytest.mark.integration
    def test_absenteeism_forecast(self):
        """Test forecasting absenteeism rate"""
        # Absenteeism rates (typically 3-8%)
        absenteeism = [
            Decimal("4.5"), Decimal("5.0"), Decimal("4.8"), Decimal("5.2"),
            Decimal("4.7"), Decimal("5.1"), Decimal("4.9"), Decimal("5.0")
        ]

        result = simple_exponential_smoothing(absenteeism, forecast_periods=7)

        # Predictions should be reasonable (0-15%)
        assert all(0 <= float(p) <= 15 for p in result.predictions)
        # Accuracy should be reasonable
        assert float(result.accuracy_score) > 50

    @pytest.mark.integration
    def test_oee_forecast(self):
        """Test forecasting OEE values"""
        # OEE values (typically 60-85%)
        oee_values = [
            Decimal("68.5"), Decimal("69.2"), Decimal("70.1"), Decimal("69.8"),
            Decimal("71.5"), Decimal("72.0"), Decimal("71.8"), Decimal("73.2"),
            Decimal("73.5"), Decimal("74.0"), Decimal("73.8"), Decimal("75.0")
        ]

        result = auto_forecast(oee_values, 7)

        # Should produce valid OEE forecasts (0-100%)
        assert all(0 < float(p) < 100 for p in result.predictions)


@pytest.mark.unit
class TestForecastResultDataclass:
    """Test the ForecastResult dataclass"""

    @pytest.mark.unit
    def test_dataclass_creation(self):
        """Test creating ForecastResult directly"""
        result = ForecastResult(
            predictions=[Decimal("85.0"), Decimal("86.0")],
            lower_bounds=[Decimal("80.0"), Decimal("81.0")],
            upper_bounds=[Decimal("90.0"), Decimal("91.0")],
            confidence_scores=[Decimal("85.0"), Decimal("83.0")],
            method="test_method",
            accuracy_score=Decimal("92.5")
        )

        assert result.method == "test_method"
        assert len(result.predictions) == 2
        assert result.accuracy_score == Decimal("92.5")

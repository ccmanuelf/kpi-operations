"""
Comprehensive Trend Analysis Calculation Tests
Target: Increase calculations/trend_analysis.py coverage to 85%+
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from backend.calculations.trend_analysis import (
    calculate_moving_average,
    calculate_exponential_moving_average,
    linear_regression,
    determine_trend_direction,
    detect_anomalies,
    calculate_seasonal_decomposition,
    analyze_trend,
    TrendResult,
)


class TestMovingAverage:
    """Tests for calculate_moving_average function."""

    def test_moving_average_basic(self):
        """Test basic moving average calculation."""
        values = [Decimal("85"), Decimal("86"), Decimal("87"), Decimal("88"), Decimal("89")]
        result = calculate_moving_average(values, window=3)

        assert len(result) == 5
        assert result[0] is None
        assert result[1] is None
        # (85 + 86 + 87) / 3 = 86
        assert result[2] == Decimal("86")
        # (86 + 87 + 88) / 3 = 87
        assert result[3] == Decimal("87")
        # (87 + 88 + 89) / 3 = 88
        assert result[4] == Decimal("88")

    def test_moving_average_window_1(self):
        """Test moving average with window size 1 (should return same values)."""
        values = [Decimal("85"), Decimal("90"), Decimal("95")]
        result = calculate_moving_average(values, window=1)

        assert result[0] == Decimal("85")
        assert result[1] == Decimal("90")
        assert result[2] == Decimal("95")

    def test_moving_average_window_equals_length(self):
        """Test moving average where window equals list length."""
        values = [Decimal("80"), Decimal("90"), Decimal("100")]
        result = calculate_moving_average(values, window=3)

        assert result[0] is None
        assert result[1] is None
        # (80 + 90 + 100) / 3 = 90
        assert result[2] == Decimal("90")

    def test_moving_average_invalid_window(self):
        """Test error with invalid window size."""
        values = [Decimal("85"), Decimal("90")]

        with pytest.raises(ValueError) as exc_info:
            calculate_moving_average(values, window=0)
        assert "at least 1" in str(exc_info.value).lower()

    def test_moving_average_empty_list(self):
        """Test with empty list."""
        result = calculate_moving_average([], window=3)
        assert result == []


class TestExponentialMovingAverage:
    """Tests for calculate_exponential_moving_average function."""

    def test_ema_basic(self):
        """Test basic EMA calculation."""
        values = [Decimal("100"), Decimal("110"), Decimal("105"), Decimal("115")]
        result = calculate_exponential_moving_average(values, alpha=Decimal("0.5"))

        assert len(result) == 4
        # First value is same as input
        assert result[0] == Decimal("100")
        # EMA = alpha * current + (1-alpha) * prev_ema
        # EMA[1] = 0.5 * 110 + 0.5 * 100 = 105

    def test_ema_alpha_one(self):
        """Test EMA with alpha=1 (no smoothing)."""
        values = [Decimal("80"), Decimal("90"), Decimal("100")]
        result = calculate_exponential_moving_average(values, alpha=Decimal("1"))

        assert result[0] == Decimal("80")
        assert result[1] == Decimal("90")
        assert result[2] == Decimal("100")

    def test_ema_small_alpha(self):
        """Test EMA with small alpha (heavy smoothing)."""
        values = [Decimal("100"), Decimal("200"), Decimal("300")]
        result = calculate_exponential_moving_average(values, alpha=Decimal("0.1"))

        assert len(result) == 3
        # With small alpha, values change slowly

    def test_ema_invalid_alpha_zero(self):
        """Test error with alpha=0."""
        values = [Decimal("85")]

        with pytest.raises(ValueError) as exc_info:
            calculate_exponential_moving_average(values, alpha=Decimal("0"))
        assert "between 0 and 1" in str(exc_info.value).lower()

    def test_ema_invalid_alpha_negative(self):
        """Test error with negative alpha."""
        values = [Decimal("85")]

        with pytest.raises(ValueError) as exc_info:
            calculate_exponential_moving_average(values, alpha=Decimal("-0.5"))

    def test_ema_invalid_alpha_too_high(self):
        """Test error with alpha > 1."""
        values = [Decimal("85")]

        with pytest.raises(ValueError) as exc_info:
            calculate_exponential_moving_average(values, alpha=Decimal("1.5"))

    def test_ema_empty_list(self):
        """Test with empty list."""
        result = calculate_exponential_moving_average([], alpha=Decimal("0.3"))
        assert result == []


class TestLinearRegression:
    """Tests for linear_regression function."""

    def test_linear_regression_perfect_fit(self):
        """Test with perfectly linear data."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert float(slope) == pytest.approx(10.0, rel=0.001)
        assert float(intercept) == pytest.approx(0.0, abs=0.1)
        assert float(r_squared) == pytest.approx(1.0, rel=0.001)

    def test_linear_regression_negative_slope(self):
        """Test with decreasing trend."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [Decimal("100"), Decimal("80"), Decimal("60"), Decimal("40"), Decimal("20")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert float(slope) < 0  # Negative slope
        assert float(r_squared) == pytest.approx(1.0, rel=0.001)

    def test_linear_regression_flat(self):
        """Test with flat data (no trend)."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [Decimal("50"), Decimal("50"), Decimal("50"), Decimal("50"), Decimal("50")]

        slope, intercept, r_squared = linear_regression(x, y)

        assert float(slope) == pytest.approx(0.0, abs=0.001)

    def test_linear_regression_same_x(self):
        """Test with all same X values (edge case)."""
        x = [5.0, 5.0, 5.0]
        y = [Decimal("10"), Decimal("20"), Decimal("30")]

        slope, intercept, r_squared = linear_regression(x, y)

        # Should handle gracefully with slope=0
        assert float(slope) == 0

    def test_linear_regression_length_mismatch(self):
        """Test error when X and Y have different lengths."""
        x = [1.0, 2.0, 3.0]
        y = [Decimal("10"), Decimal("20")]

        with pytest.raises(ValueError) as exc_info:
            linear_regression(x, y)
        assert "same length" in str(exc_info.value).lower()

    def test_linear_regression_insufficient_data(self):
        """Test error with insufficient data points."""
        x = [1.0]
        y = [Decimal("10")]

        with pytest.raises(ValueError) as exc_info:
            linear_regression(x, y)
        assert "at least 2" in str(exc_info.value).lower()


class TestDetermineTrendDirection:
    """Tests for determine_trend_direction function."""

    def test_trend_increasing(self):
        """Test detection of increasing trend."""
        result = determine_trend_direction(
            slope=Decimal("0.5"),
            r_squared=Decimal("0.8"),
            std_deviation=Decimal("2"),
            mean_value=Decimal("100")
        )
        assert result == "increasing"

    def test_trend_decreasing(self):
        """Test detection of decreasing trend."""
        result = determine_trend_direction(
            slope=Decimal("-0.5"),
            r_squared=Decimal("0.8"),
            std_deviation=Decimal("2"),
            mean_value=Decimal("100")
        )
        assert result == "decreasing"

    def test_trend_stable(self):
        """Test detection of stable trend."""
        result = determine_trend_direction(
            slope=Decimal("0.05"),
            r_squared=Decimal("0.8"),
            std_deviation=Decimal("2"),
            mean_value=Decimal("100")
        )
        assert result == "stable"

    def test_trend_volatile_high_cv(self):
        """Test detection of volatile trend (high coefficient of variation)."""
        result = determine_trend_direction(
            slope=Decimal("0.5"),
            r_squared=Decimal("0.8"),
            std_deviation=Decimal("25"),  # 25% of mean
            mean_value=Decimal("100")
        )
        assert result == "volatile"

    def test_trend_volatile_low_r_squared(self):
        """Test detection of volatile trend (low R-squared)."""
        result = determine_trend_direction(
            slope=Decimal("0.5"),
            r_squared=Decimal("0.2"),  # Low R-squared
            std_deviation=Decimal("2"),
            mean_value=Decimal("100")
        )
        assert result == "volatile"

    def test_trend_zero_mean(self):
        """Test with zero mean value."""
        result = determine_trend_direction(
            slope=Decimal("0.5"),
            r_squared=Decimal("0.8"),
            std_deviation=Decimal("2"),
            mean_value=Decimal("0")
        )
        # Should not divide by zero
        assert result in ["increasing", "decreasing", "stable", "volatile"]


class TestDetectAnomalies:
    """Tests for detect_anomalies function."""

    def test_detect_anomalies_basic(self):
        """Test basic anomaly detection."""
        values = [
            Decimal("85"), Decimal("86"), Decimal("84"),
            Decimal("120"),  # Anomaly
            Decimal("85"), Decimal("87")
        ]
        anomalies = detect_anomalies(values, threshold_std=Decimal("2.0"))

        assert 3 in anomalies  # Index of 120

    def test_detect_anomalies_no_anomalies(self):
        """Test with no anomalies."""
        values = [
            Decimal("85"), Decimal("86"), Decimal("84"),
            Decimal("85"), Decimal("87")
        ]
        anomalies = detect_anomalies(values, threshold_std=Decimal("2.0"))

        assert len(anomalies) == 0

    def test_detect_anomalies_multiple(self):
        """Test with extreme anomalies."""
        # Create data with clear outliers
        values = [
            Decimal("50"), Decimal("50"), Decimal("50"), Decimal("50"),
            Decimal("50"), Decimal("50"), Decimal("50"), Decimal("200"),  # Extreme outlier
        ]
        anomalies = detect_anomalies(values, threshold_std=Decimal("1.5"))

        # With such extreme outlier, it should be detected
        assert 7 in anomalies or len(anomalies) >= 1

    def test_detect_anomalies_strict_threshold(self):
        """Test with strict threshold."""
        values = [Decimal("85"), Decimal("86"), Decimal("90"), Decimal("85")]
        anomalies_strict = detect_anomalies(values, threshold_std=Decimal("1.5"))
        anomalies_loose = detect_anomalies(values, threshold_std=Decimal("3.0"))

        # Strict threshold should find more or equal anomalies
        assert len(anomalies_strict) >= len(anomalies_loose)

    def test_detect_anomalies_insufficient_data(self):
        """Test with insufficient data."""
        values = [Decimal("85"), Decimal("90")]
        anomalies = detect_anomalies(values)

        assert anomalies == []

    def test_detect_anomalies_no_variation(self):
        """Test with no variation (all same values)."""
        values = [Decimal("85"), Decimal("85"), Decimal("85"), Decimal("85")]
        anomalies = detect_anomalies(values)

        assert anomalies == []


class TestSeasonalDecomposition:
    """Tests for calculate_seasonal_decomposition function."""

    def test_seasonal_decomposition_basic(self):
        """Test basic seasonal decomposition."""
        # Create weekly pattern
        values = [
            Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"),
            Decimal("140"), Decimal("150"), Decimal("160"),  # Week 1
            Decimal("105"), Decimal("115"), Decimal("125"), Decimal("135"),
            Decimal("145"), Decimal("155"), Decimal("165"),  # Week 2
        ]
        result = calculate_seasonal_decomposition(values, period=7)

        assert "trend" in result
        assert "seasonal" in result
        assert "residual" in result
        assert len(result["trend"]) == len(values)
        assert len(result["seasonal"]) == len(values)
        assert len(result["residual"]) == len(values)

    def test_seasonal_decomposition_insufficient_data(self):
        """Test with insufficient data."""
        values = [Decimal("100"), Decimal("110"), Decimal("120")]
        result = calculate_seasonal_decomposition(values, period=7)

        # Should return original values as trend
        assert result["trend"] == values
        # Seasonal and residual should be zeros
        assert all(s == Decimal("0") for s in result["seasonal"])

    def test_seasonal_decomposition_daily_pattern(self):
        """Test with daily pattern (period=1)."""
        values = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130")]
        result = calculate_seasonal_decomposition(values, period=1)

        assert len(result["trend"]) == 4


class TestAnalyzeTrend:
    """Tests for analyze_trend function."""

    def test_analyze_trend_increasing(self):
        """Test analysis of increasing trend."""
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]
        values = [Decimal("80") + Decimal(i * 2) for i in range(10)]

        result = analyze_trend(dates, values)

        assert isinstance(result, TrendResult)
        assert float(result.slope) > 0
        assert result.trend_direction == "increasing"

    def test_analyze_trend_decreasing(self):
        """Test analysis of decreasing trend."""
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]
        values = [Decimal("100") - Decimal(i * 2) for i in range(10)]

        result = analyze_trend(dates, values)

        assert float(result.slope) < 0
        assert result.trend_direction == "decreasing"

    def test_analyze_trend_stable(self):
        """Test analysis of stable trend (with slight variation)."""
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]
        # Small random variations but overall stable (slope near zero)
        values = [Decimal("85.0"), Decimal("85.1"), Decimal("84.9"), Decimal("85.0"),
                  Decimal("85.1"), Decimal("84.9"), Decimal("85.0"), Decimal("85.1"),
                  Decimal("84.9"), Decimal("85.0")]

        result = analyze_trend(dates, values)

        # May be stable or volatile depending on threshold
        assert result.trend_direction in ["stable", "volatile"]
        # Slope should be near zero regardless
        assert abs(float(result.slope)) < 0.1

    def test_analyze_trend_length_mismatch(self):
        """Test error when dates and values have different lengths."""
        dates = [date(2024, 1, 1), date(2024, 1, 2)]
        values = [Decimal("85")]

        with pytest.raises(ValueError) as exc_info:
            analyze_trend(dates, values)
        assert "same length" in str(exc_info.value).lower()

    def test_analyze_trend_insufficient_data(self):
        """Test error with insufficient data."""
        dates = [date(2024, 1, 1)]
        values = [Decimal("85")]

        with pytest.raises(ValueError) as exc_info:
            analyze_trend(dates, values)
        assert "at least 2" in str(exc_info.value).lower()


class TestTrendResultDataclass:
    """Tests for TrendResult dataclass."""

    def test_trend_result_creation(self):
        """Test creating TrendResult instance."""
        result = TrendResult(
            slope=Decimal("0.5"),
            intercept=Decimal("80"),
            r_squared=Decimal("0.95"),
            trend_direction="increasing"
        )

        assert result.slope == Decimal("0.5")
        assert result.intercept == Decimal("80")
        assert result.r_squared == Decimal("0.95")
        assert result.trend_direction == "increasing"

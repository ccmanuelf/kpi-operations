"""
Trend Analysis Calculations Module
Provides moving averages, linear regression, seasonal decomposition, and anomaly detection
"""

from typing import List, Tuple, Optional, Dict, Any
from decimal import Decimal
from datetime import date, timedelta
import statistics
from dataclasses import dataclass


@dataclass
class TrendResult:
    """Container for trend analysis results"""

    slope: Decimal  # Linear regression slope (change per day)
    intercept: Decimal  # Y-intercept
    r_squared: Decimal  # R-squared (goodness of fit)
    trend_direction: str  # 'increasing', 'decreasing', 'stable', 'volatile'


def calculate_moving_average(values: List[Decimal], window: int) -> List[Optional[Decimal]]:
    """
    Calculate simple moving average

    Args:
        values: List of KPI values
        window: Moving average window size (e.g., 7 for 7-day)

    Returns:
        List of moving averages (same length as input, with None for insufficient data)

    Example:
        >>> values = [85.0, 86.5, 84.2, 87.1, 88.0]
        >>> calculate_moving_average(values, 3)
        [None, None, 85.23, 85.93, 86.43]
    """
    if window < 1:
        raise ValueError("Window size must be at least 1")

    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)  # Not enough data yet
        else:
            window_values = values[i - window + 1 : i + 1]
            avg = sum(window_values) / len(window_values)
            result.append(Decimal(str(round(avg, 4))))

    return result


def calculate_exponential_moving_average(values: List[Decimal], alpha: Decimal = Decimal("0.2")) -> List[Decimal]:
    """
    Calculate exponential moving average (EMA)

    Args:
        values: List of KPI values
        alpha: Smoothing factor (0 < alpha <= 1), default 0.2

    Returns:
        List of EMA values

    Example:
        >>> values = [85.0, 86.5, 84.2, 87.1, 88.0]
        >>> calculate_exponential_moving_average(values, Decimal("0.3"))
    """
    if not (Decimal("0") < alpha <= Decimal("1")):
        raise ValueError("Alpha must be between 0 and 1")

    if not values:
        return []

    ema = [values[0]]  # Start with first value

    for i in range(1, len(values)):
        new_ema = alpha * values[i] + (Decimal("1") - alpha) * ema[-1]
        ema.append(Decimal(str(round(new_ema, 4))))

    return ema


def linear_regression(x_values: List[float], y_values: List[Decimal]) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Calculate linear regression (least squares method)

    Args:
        x_values: X-axis values (typically day numbers)
        y_values: Y-axis values (KPI values)

    Returns:
        Tuple of (slope, intercept, r_squared)

    Example:
        >>> x = [1, 2, 3, 4, 5]
        >>> y = [85.0, 86.5, 84.2, 87.1, 88.0]
        >>> slope, intercept, r2 = linear_regression(x, y)
    """
    if len(x_values) != len(y_values):
        raise ValueError("X and Y must have same length")

    if len(x_values) < 2:
        raise ValueError("Need at least 2 data points for regression")

    n = len(x_values)

    # Convert to float for calculations
    y_float = [float(y) for y in y_values]

    # Calculate means
    x_mean = sum(x_values) / n
    y_mean = sum(y_float) / n

    # Calculate slope and intercept
    numerator = sum((x_values[i] - x_mean) * (y_float[i] - y_mean) for i in range(n))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        # All X values are the same
        return Decimal("0"), Decimal(str(y_mean)), Decimal("0")

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Calculate R-squared
    ss_tot = sum((y - y_mean) ** 2 for y in y_float)
    ss_res = sum((y_float[i] - (slope * x_values[i] + intercept)) ** 2 for i in range(n))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return (Decimal(str(round(slope, 6))), Decimal(str(round(intercept, 4))), Decimal(str(round(r_squared, 4))))


def determine_trend_direction(slope: Decimal, r_squared: Decimal, std_deviation: Decimal, mean_value: Decimal) -> str:
    """
    Determine trend direction based on regression analysis

    Args:
        slope: Linear regression slope
        r_squared: R-squared value
        std_deviation: Standard deviation of data
        mean_value: Mean value of data

    Returns:
        Trend direction: 'increasing', 'decreasing', 'stable', 'volatile'

    Logic:
        - Volatile: High std deviation (>20% of mean) OR low R-squared (<0.3)
        - Stable: Slope near zero (<0.1 units/day) AND good fit
        - Increasing: Positive slope AND good fit
        - Decreasing: Negative slope AND good fit
    """
    # Calculate coefficient of variation
    cv = (std_deviation / mean_value * 100) if mean_value != 0 else Decimal("0")

    # High volatility check
    if cv > Decimal("20") or r_squared < Decimal("0.3"):
        return "volatile"

    # Check slope magnitude (threshold: 0.1 units/day)
    slope_threshold = Decimal("0.1")

    if abs(slope) < slope_threshold:
        return "stable"
    elif slope > 0:
        return "increasing"
    else:
        return "decreasing"


def detect_anomalies(values: List[Decimal], threshold_std: Decimal = Decimal("2.0")) -> List[int]:
    """
    Detect anomalies using standard deviation method

    Args:
        values: List of KPI values
        threshold_std: Number of standard deviations for anomaly threshold (default 2.0)

    Returns:
        List of indices where anomalies were detected

    Example:
        >>> values = [85.0, 86.5, 84.2, 95.0, 88.0]  # 95.0 is anomaly
        >>> detect_anomalies(values, Decimal("2.0"))
        [3]
    """
    if len(values) < 3:
        return []  # Need at least 3 points for meaningful anomaly detection

    # Convert to float for statistics
    float_values = [float(v) for v in values]

    mean = statistics.mean(float_values)
    std_dev = statistics.stdev(float_values)

    if std_dev == 0:
        return []  # No variation, no anomalies

    anomalies = []
    threshold = float(threshold_std) * std_dev

    for i, value in enumerate(float_values):
        if abs(value - mean) > threshold:
            anomalies.append(i)

    return anomalies


def calculate_seasonal_decomposition(values: List[Decimal], period: int = 7) -> Dict[str, List[Decimal]]:
    """
    Simple seasonal decomposition (additive model)
    Decomposes time series into trend, seasonal, and residual components

    Args:
        values: List of KPI values
        period: Seasonal period (default 7 for weekly patterns)

    Returns:
        Dictionary with 'trend', 'seasonal', 'residual' components

    Note:
        This is a simplified implementation. For production use with large datasets,
        consider using statsmodels library's seasonal_decompose()
    """
    if len(values) < period * 2:
        # Not enough data for meaningful decomposition
        return {"trend": values, "seasonal": [Decimal("0")] * len(values), "residual": [Decimal("0")] * len(values)}

    n = len(values)

    # Calculate trend using centered moving average
    trend = []
    half_window = period // 2

    for i in range(n):
        if i < half_window or i >= n - half_window:
            trend.append(None)
        else:
            window_values = values[i - half_window : i + half_window + 1]
            avg = sum(window_values) / len(window_values)
            trend.append(Decimal(str(round(avg, 4))))

    # Calculate detrended series
    detrended = []
    for i in range(n):
        if trend[i] is not None:
            detrended.append(values[i] - trend[i])
        else:
            detrended.append(None)

    # Calculate seasonal component (average for each position in period)
    seasonal_avg = [Decimal("0")] * period
    seasonal_count = [0] * period

    for i, val in enumerate(detrended):
        if val is not None:
            pos = i % period
            seasonal_avg[pos] += val
            seasonal_count[pos] += 1

    # Average the seasonal components
    for i in range(period):
        if seasonal_count[i] > 0:
            seasonal_avg[i] = seasonal_avg[i] / seasonal_count[i]

    # Extend seasonal pattern to full length
    seasonal = [seasonal_avg[i % period] for i in range(n)]

    # Calculate residual
    residual = []
    for i in range(n):
        if trend[i] is not None:
            res = values[i] - trend[i] - seasonal[i]
            residual.append(Decimal(str(round(res, 4))))
        else:
            residual.append(Decimal("0"))

    # Fill in None values in trend with nearest valid value
    filled_trend = []
    last_valid = values[0]
    for t in trend:
        if t is not None:
            filled_trend.append(t)
            last_valid = t
        else:
            filled_trend.append(last_valid)

    return {"trend": filled_trend, "seasonal": seasonal, "residual": residual}


# =============================================================================
# PURE HELPER FUNCTIONS for Analytics Service
# Phase 1.2: Functions used by AnalyticsService
# =============================================================================


def calculate_trend_direction(values: List[float]) -> Tuple[str, float]:
    """
    Calculate trend direction from a list of values.

    Args:
        values: List of metric values over time

    Returns:
        Tuple of (direction, percentage_change)
        - direction: "improving", "declining", "stable", "insufficient_data"
        - percentage_change: Absolute percentage change from start to end
    """
    if len(values) < 2:
        return ("insufficient_data", 0.0)

    start_value = values[0]
    end_value = values[-1]

    if start_value == 0:
        if end_value > 0:
            return ("improving", 100.0)
        return ("stable", 0.0)

    percentage_change = ((end_value - start_value) / start_value) * 100

    # Threshold for stable: less than 5% change
    if abs(percentage_change) < 5:
        return ("stable", abs(percentage_change))
    elif percentage_change > 0:
        return ("improving", percentage_change)
    else:
        return ("declining", abs(percentage_change))


def get_trend_interpretation(metric: str, direction: str, percentage: float) -> str:
    """
    Generate human-readable interpretation of a trend.

    Args:
        metric: Name of the metric (e.g., "efficiency", "ppm")
        direction: Trend direction from calculate_trend_direction
        percentage: Percentage change

    Returns:
        Human-readable interpretation string
    """
    if direction == "insufficient_data":
        return f"Insufficient data to determine {metric} trend."

    if direction == "stable":
        return f"{metric.title()} is stable (±{percentage:.1f}% change)."

    if direction == "improving":
        return f"{metric.title()} is improving, up {percentage:.1f}%. Continue current practices."
    else:  # declining
        return f"{metric.title()} is declining, down {percentage:.1f}%. Investigation recommended."


def analyze_trend(dates: List[date], values: List[Decimal]) -> TrendResult:
    """
    Comprehensive trend analysis

    Args:
        dates: List of dates
        values: List of KPI values

    Returns:
        TrendResult object with slope, intercept, R-squared, and trend direction

    Example:
        >>> dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        >>> values = [85.0, 86.5, 87.2]
        >>> result = analyze_trend(dates, values)
        >>> print(result.trend_direction)  # 'increasing'
    """
    if len(dates) != len(values):
        raise ValueError("Dates and values must have same length")

    if len(dates) < 2:
        raise ValueError("Need at least 2 data points for trend analysis")

    # Convert dates to day numbers (days since first date)
    first_date = dates[0]
    x_values = [(d - first_date).days for d in dates]

    # Calculate linear regression
    slope, intercept, r_squared = linear_regression(x_values, values)

    # Calculate statistics
    float_values = [float(v) for v in values]
    mean_value = Decimal(str(statistics.mean(float_values)))
    std_dev = Decimal(str(statistics.stdev(float_values))) if len(float_values) > 1 else Decimal("0")

    # Determine trend direction
    direction = determine_trend_direction(slope, r_squared, std_dev, mean_value)

    return TrendResult(slope=slope, intercept=intercept, r_squared=r_squared, trend_direction=direction)

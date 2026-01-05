"""
Prediction and Forecasting Module
Implements exponential smoothing, ARIMA forecasting, and trend extrapolation
"""
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
from datetime import date, timedelta
import statistics
from dataclasses import dataclass


@dataclass
class ForecastResult:
    """Container for forecast results"""
    predictions: List[Decimal]  # Predicted values
    lower_bounds: List[Decimal]  # Lower confidence interval (95%)
    upper_bounds: List[Decimal]  # Upper confidence interval (95%)
    confidence_scores: List[Decimal]  # Confidence for each prediction (0-100)
    method: str  # Forecasting method used
    accuracy_score: Decimal  # Model accuracy (0-100)


def simple_exponential_smoothing(
    values: List[Decimal],
    alpha: Decimal = Decimal("0.3"),
    forecast_periods: int = 7
) -> ForecastResult:
    """
    Simple exponential smoothing for time series forecasting

    Args:
        values: Historical KPI values
        alpha: Smoothing parameter (0 < alpha <= 1), default 0.3
        forecast_periods: Number of periods to forecast

    Returns:
        ForecastResult with predictions and confidence intervals

    Example:
        >>> values = [85.0, 86.5, 84.2, 87.1, 88.0]
        >>> result = simple_exponential_smoothing(values, Decimal("0.3"), 7)
        >>> print(result.predictions)  # Next 7 forecasted values
    """
    if not (Decimal("0") < alpha <= Decimal("1")):
        raise ValueError("Alpha must be between 0 and 1")

    if len(values) < 2:
        raise ValueError("Need at least 2 historical values for forecasting")

    # Initialize with first value
    smoothed = [values[0]]

    # Calculate smoothed values for historical data
    for i in range(1, len(values)):
        new_smoothed = alpha * values[i] + (Decimal("1") - alpha) * smoothed[-1]
        smoothed.append(new_smoothed)

    # Forecast future values (constant forecast = last smoothed value)
    last_smoothed = smoothed[-1]
    predictions = [last_smoothed] * forecast_periods

    # Calculate prediction intervals based on historical error
    errors = [abs(values[i] - smoothed[i]) for i in range(len(values))]
    mae = sum(errors) / len(errors)  # Mean Absolute Error

    # 95% confidence interval (approximately 2 * MAE)
    confidence_margin = mae * Decimal("2")

    lower_bounds = [p - confidence_margin for p in predictions]
    upper_bounds = [p + confidence_margin for p in predictions]

    # Confidence decreases with forecast horizon
    base_confidence = Decimal("85.0")
    confidence_decay = Decimal("2.0")  # Lose 2% per period
    confidence_scores = [
        max(Decimal("50.0"), base_confidence - (confidence_decay * i))
        for i in range(forecast_periods)
    ]

    # Calculate accuracy score (based on historical fit)
    mape = sum(abs((values[i] - smoothed[i]) / values[i]) for i in range(len(values)) if values[i] != 0)
    mape = (mape / len(values)) * 100
    accuracy_score = max(Decimal("0"), Decimal("100") - mape)

    return ForecastResult(
        predictions=[Decimal(str(round(p, 4))) for p in predictions],
        lower_bounds=[Decimal(str(round(lb, 4))) for lb in lower_bounds],
        upper_bounds=[Decimal(str(round(ub, 4))) for ub in upper_bounds],
        confidence_scores=[Decimal(str(round(c, 2))) for c in confidence_scores],
        method="simple_exponential_smoothing",
        accuracy_score=Decimal(str(round(accuracy_score, 2)))
    )


def double_exponential_smoothing(
    values: List[Decimal],
    alpha: Decimal = Decimal("0.3"),
    beta: Decimal = Decimal("0.1"),
    forecast_periods: int = 7
) -> ForecastResult:
    """
    Double exponential smoothing (Holt's method) for trending data

    Args:
        values: Historical KPI values
        alpha: Level smoothing parameter (0 < alpha <= 1)
        beta: Trend smoothing parameter (0 < beta <= 1)
        forecast_periods: Number of periods to forecast

    Returns:
        ForecastResult with predictions accounting for trend
    """
    if len(values) < 3:
        # Fall back to simple exponential smoothing
        return simple_exponential_smoothing(values, alpha, forecast_periods)

    # Initialize level and trend
    level = values[0]
    trend = (values[1] - values[0])

    smoothed = [level]
    trends = [trend]

    # Calculate smoothed values and trends
    for i in range(1, len(values)):
        prev_level = level
        level = alpha * values[i] + (Decimal("1") - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (Decimal("1") - beta) * trend

        smoothed.append(level)
        trends.append(trend)

    # Forecast with trend
    predictions = []
    last_level = smoothed[-1]
    last_trend = trends[-1]

    for h in range(1, forecast_periods + 1):
        forecast = last_level + last_trend * h
        predictions.append(forecast)

    # Calculate prediction intervals
    errors = [abs(values[i] - smoothed[i]) for i in range(len(values))]
    mae = sum(errors) / len(errors)

    confidence_margin = mae * Decimal("2.5")  # Slightly wider for trending data

    lower_bounds = [p - confidence_margin for p in predictions]
    upper_bounds = [p + confidence_margin for p in predictions]

    # Confidence scores
    base_confidence = Decimal("82.0")
    confidence_decay = Decimal("2.5")
    confidence_scores = [
        max(Decimal("45.0"), base_confidence - (confidence_decay * i))
        for i in range(forecast_periods)
    ]

    # Accuracy
    mape = sum(abs((values[i] - smoothed[i]) / values[i]) for i in range(len(values)) if values[i] != 0)
    mape = (mape / len(values)) * 100
    accuracy_score = max(Decimal("0"), Decimal("100") - mape)

    return ForecastResult(
        predictions=[Decimal(str(round(p, 4))) for p in predictions],
        lower_bounds=[Decimal(str(round(lb, 4))) for lb in lower_bounds],
        upper_bounds=[Decimal(str(round(ub, 4))) for ub in upper_bounds],
        confidence_scores=[Decimal(str(round(c, 2))) for c in confidence_scores],
        method="double_exponential_smoothing",
        accuracy_score=Decimal(str(round(accuracy_score, 2)))
    )


def linear_trend_extrapolation(
    values: List[Decimal],
    forecast_periods: int = 7
) -> ForecastResult:
    """
    Linear trend extrapolation using least squares regression

    Args:
        values: Historical KPI values
        forecast_periods: Number of periods to forecast

    Returns:
        ForecastResult with linear predictions
    """
    if len(values) < 2:
        raise ValueError("Need at least 2 values for trend extrapolation")

    n = len(values)
    x_values = list(range(n))
    y_values = [float(v) for v in values]

    # Calculate linear regression
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n

    numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        slope = 0
        intercept = y_mean
    else:
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

    # Forecast future values
    predictions = []
    for h in range(n, n + forecast_periods):
        forecast = slope * h + intercept
        predictions.append(Decimal(str(forecast)))

    # Calculate residuals for confidence intervals
    residuals = [y_values[i] - (slope * x_values[i] + intercept) for i in range(n)]
    residual_std = statistics.stdev(residuals) if len(residuals) > 1 else 0

    # Confidence intervals widen with forecast horizon
    lower_bounds = []
    upper_bounds = []

    for h in range(forecast_periods):
        # Widen interval as we go further into future
        margin = Decimal(str(residual_std * 2 * (1 + h * 0.1)))
        lower_bounds.append(predictions[h] - margin)
        upper_bounds.append(predictions[h] + margin)

    # Confidence scores
    r_squared = 1 - (sum(r ** 2 for r in residuals) / sum((y - y_mean) ** 2 for y in y_values))
    base_confidence = Decimal(str(max(50, r_squared * 100)))
    confidence_decay = Decimal("3.0")

    confidence_scores = [
        max(Decimal("40.0"), base_confidence - (confidence_decay * i))
        for i in range(forecast_periods)
    ]

    # Accuracy
    accuracy_score = Decimal(str(round(r_squared * 100, 2)))

    return ForecastResult(
        predictions=[Decimal(str(round(p, 4))) for p in predictions],
        lower_bounds=[Decimal(str(round(lb, 4))) for lb in lower_bounds],
        upper_bounds=[Decimal(str(round(ub, 4))) for ub in upper_bounds],
        confidence_scores=[Decimal(str(round(c, 2))) for c in confidence_scores],
        method="linear_trend_extrapolation",
        accuracy_score=Decimal(str(round(accuracy_score, 2)))
    )


def auto_forecast(
    values: List[Decimal],
    forecast_periods: int = 7
) -> ForecastResult:
    """
    Automatically select best forecasting method based on data characteristics

    Args:
        values: Historical KPI values
        forecast_periods: Number of periods to forecast

    Returns:
        ForecastResult from the best performing method

    Logic:
        - If strong trend detected: Use double exponential smoothing
        - If weak trend or stable: Use simple exponential smoothing
        - If linear pattern: Use linear extrapolation
    """
    if len(values) < 3:
        return simple_exponential_smoothing(values, forecast_periods=forecast_periods)

    # Analyze trend strength
    n = len(values)
    x = list(range(n))
    y = [float(v) for v in values]

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((xi - x_mean) ** 2 for xi in x)

    if denominator != 0:
        slope = numerator / denominator
        residuals = [y[i] - (slope * x[i] + (y_mean - slope * x_mean)) for i in range(n)]
        r_squared = 1 - (sum(r ** 2 for r in residuals) / sum((yi - y_mean) ** 2 for yi in y))
    else:
        slope = 0
        r_squared = 0

    # Decision logic
    if r_squared > 0.7 and abs(slope) > 0.1:
        # Strong linear trend
        if slope > 0.05 or slope < -0.05:
            # Significant trend - use double exponential smoothing
            return double_exponential_smoothing(values, forecast_periods=forecast_periods)
        else:
            # Moderate trend - use linear extrapolation
            return linear_trend_extrapolation(values, forecast_periods=forecast_periods)
    else:
        # Weak trend or high variability - use simple smoothing
        return simple_exponential_smoothing(values, forecast_periods=forecast_periods)


def calculate_forecast_accuracy(
    actual: List[Decimal],
    predicted: List[Decimal]
) -> Dict[str, Decimal]:
    """
    Calculate various forecast accuracy metrics

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        Dictionary with MAE, RMSE, MAPE metrics
    """
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted must have same length")

    if len(actual) == 0:
        return {
            'mae': Decimal("0"),
            'rmse': Decimal("0"),
            'mape': Decimal("0")
        }

    n = len(actual)

    # Mean Absolute Error
    mae = sum(abs(actual[i] - predicted[i]) for i in range(n)) / n

    # Root Mean Squared Error
    mse = sum((actual[i] - predicted[i]) ** 2 for i in range(n)) / n
    rmse = Decimal(str(float(mse) ** 0.5))

    # Mean Absolute Percentage Error
    mape_sum = Decimal("0")
    valid_count = 0
    for i in range(n):
        if actual[i] != 0:
            mape_sum += abs((actual[i] - predicted[i]) / actual[i])
            valid_count += 1

    mape = (mape_sum / valid_count * 100) if valid_count > 0 else Decimal("0")

    return {
        'mae': Decimal(str(round(mae, 4))),
        'rmse': Decimal(str(round(rmse, 4))),
        'mape': Decimal(str(round(mape, 2)))
    }

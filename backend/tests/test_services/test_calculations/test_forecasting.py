"""Phase 1 dual-view orchestrator: Forecast (simple exponential smoothing)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.forecasting import (
    ForecastInputs,
    calculate_forecast,
)


class TestForecast:
    def test_standard_mode_returns_forecast_periods(self):
        history = [Decimal("85"), Decimal("86"), Decimal("84"), Decimal("87"), Decimal("88")]
        result = calculate_forecast(ForecastInputs(historical_values=history, forecast_periods=7))
        assert result.metric_name == "forecast"
        assert len(result.value.predictions) == 7
        assert len(result.value.lower_bounds) == 7
        assert len(result.value.upper_bounds) == 7
        assert len(result.value.confidence_scores) == 7
        assert result.value.method == "simple_exponential_smoothing"

    def test_custom_alpha(self):
        history = [Decimal("100"), Decimal("105"), Decimal("110")]
        result = calculate_forecast(ForecastInputs(historical_values=history, alpha=Decimal("0.5"), forecast_periods=3))
        assert result.inputs_consumed["alpha"] == "0.5"

    def test_alpha_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            ForecastInputs(historical_values=[Decimal("1"), Decimal("2")], alpha=Decimal("1.5"))

    def test_too_few_history_rejected(self):
        with pytest.raises(ValidationError):
            ForecastInputs(historical_values=[Decimal("1")])

    def test_site_adjusted_equals_standard_in_phase_1(self):
        history = [Decimal("85"), Decimal("86"), Decimal("84")]
        inputs = ForecastInputs(historical_values=history, forecast_periods=3)
        std = calculate_forecast(inputs, "standard")
        adj = calculate_forecast(inputs, "site_adjusted")
        assert std.value.predictions == adj.value.predictions

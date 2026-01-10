"""
Phase 5 Predictions Tests
Comprehensive tests for predictive analytics functionality

Tests cover:
- Sample data generator
- KPI history generation
- Prediction endpoints
- Health assessments
- Benchmarks
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
import math

from backend.generators.sample_data_phase5 import (
    generate_kpi_history,
    generate_all_kpi_histories,
    get_kpi_benchmarks,
    calculate_kpi_health_score,
    KPIHistoryGenerator,
    KPITypePhase5,
    KPI_CONFIGS
)
from backend.calculations.predictions import (
    auto_forecast,
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
    calculate_forecast_accuracy,
    ForecastResult
)


class TestKPIHistoryGenerator:
    """Tests for KPI history data generation"""

    def test_generator_initialization(self):
        """Test generator initializes correctly"""
        generator = KPIHistoryGenerator(seed=42)
        assert generator.seed == 42

    def test_generate_efficiency_data(self):
        """Test efficiency KPI data generation"""
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=30,
            seed=42
        )

        assert len(history) == 30
        assert all("date" in d for d in history)
        assert all("value" in d for d in history)
        assert all("kpi_type" in d for d in history)
        assert all(d["kpi_type"] == "efficiency" for d in history)

    def test_generate_all_kpi_types(self):
        """Test generation for all 10 KPI types"""
        for kpi_type in KPITypePhase5:
            history = generate_kpi_history(
                kpi_type=kpi_type.value,
                days=10,
                seed=42
            )
            assert len(history) == 10
            assert all(d["kpi_type"] == kpi_type.value for d in history)

    def test_value_bounds(self):
        """Test generated values are within configured bounds"""
        for kpi_type in KPITypePhase5:
            config = KPI_CONFIGS[kpi_type]
            history = generate_kpi_history(
                kpi_type=kpi_type.value,
                days=100,
                seed=42
            )

            for record in history:
                assert config.min_value <= record["value"] <= config.max_value, \
                    f"{kpi_type.value}: {record['value']} not in [{config.min_value}, {config.max_value}]"

    def test_date_ordering(self):
        """Test dates are in chronological order"""
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=30,
            seed=42
        )

        dates = [d["date"] for d in history]
        assert dates == sorted(dates)

    def test_end_date_parameter(self):
        """Test custom end date is respected"""
        custom_end = date(2024, 6, 15)
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=10,
            end_date=custom_end,
            seed=42
        )

        assert history[-1]["date"] == custom_end

    def test_client_id_assignment(self):
        """Test client_id is assigned when provided"""
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=5,
            client_id="TEST-CLIENT-001",
            seed=42
        )

        assert all(d["client_id"] == "TEST-CLIENT-001" for d in history)

    def test_anomaly_detection(self):
        """Test anomaly flags are generated"""
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=100,
            seed=42
        )

        # With seed=42 and 100 days, we should have some anomalies
        anomaly_count = sum(1 for d in history if d["is_anomaly"])
        # Approximately 5% should be anomalies
        assert 0 <= anomaly_count <= 20

    def test_reproducibility(self):
        """Test same seed produces same data"""
        history1 = generate_kpi_history("efficiency", days=10, seed=42)
        history2 = generate_kpi_history("efficiency", days=10, seed=42)

        for d1, d2 in zip(history1, history2):
            assert d1["value"] == d2["value"]
            assert d1["date"] == d2["date"]

    def test_different_seeds_produce_different_data(self):
        """Test different seeds produce different data"""
        history1 = generate_kpi_history("efficiency", days=10, seed=42)
        history2 = generate_kpi_history("efficiency", days=10, seed=123)

        values1 = [d["value"] for d in history1]
        values2 = [d["value"] for d in history2]

        assert values1 != values2


class TestGenerateAllKPIHistories:
    """Tests for generating all KPIs at once"""

    def test_returns_all_kpis(self):
        """Test all 10 KPIs are returned"""
        all_data = generate_all_kpi_histories(days=10, seed=42)

        expected_kpis = [kpi.value for kpi in KPITypePhase5]
        assert set(all_data.keys()) == set(expected_kpis)

    def test_each_kpi_has_correct_days(self):
        """Test each KPI has the correct number of days"""
        all_data = generate_all_kpi_histories(days=15, seed=42)

        for kpi_type, history in all_data.items():
            assert len(history) == 15


class TestKPIBenchmarks:
    """Tests for KPI benchmark data"""

    def test_all_kpis_have_benchmarks(self):
        """Test all 10 KPIs have benchmark data"""
        benchmarks = get_kpi_benchmarks()

        expected_kpis = [kpi.value for kpi in KPITypePhase5]
        assert set(benchmarks.keys()) == set(expected_kpis)

    def test_benchmark_structure(self):
        """Test benchmark data has required fields"""
        benchmarks = get_kpi_benchmarks()

        required_fields = ["target", "excellent", "good", "fair", "unit", "description"]

        for kpi_type, data in benchmarks.items():
            for field in required_fields:
                assert field in data, f"{kpi_type} missing {field}"

    def test_benchmark_values_are_logical(self):
        """Test benchmark thresholds are logical"""
        benchmarks = get_kpi_benchmarks()

        # For normal KPIs (higher is better)
        for kpi_type in ["efficiency", "performance", "availability", "oee", "fpy", "rty", "otd"]:
            data = benchmarks[kpi_type]
            assert data["excellent"] >= data["good"] >= data["fair"]

        # For inverse KPIs (lower is better)
        for kpi_type in ["ppm", "dpmo", "absenteeism"]:
            data = benchmarks[kpi_type]
            assert data["excellent"] <= data["good"] <= data["fair"]


class TestHealthScoreCalculation:
    """Tests for KPI health score calculation"""

    def test_excellent_health_score(self):
        """Test excellent performance gets high health score"""
        result = calculate_kpi_health_score(
            current_value=95.0,
            predicted_value=96.0,
            kpi_type="efficiency"
        )

        assert result["health_score"] >= 90
        assert result["trend"] == "improving"

    def test_poor_health_score(self):
        """Test poor performance gets low health score"""
        result = calculate_kpi_health_score(
            current_value=50.0,
            predicted_value=48.0,
            kpi_type="efficiency"
        )

        assert result["health_score"] < 60
        assert len(result["recommendations"]) > 0

    def test_inverse_kpi_health_score(self):
        """Test inverse KPIs (lower is better) calculate correctly"""
        # Good PPM (low is good)
        result = calculate_kpi_health_score(
            current_value=500.0,
            predicted_value=450.0,
            kpi_type="ppm"
        )
        assert result["health_score"] > 80

        # Bad PPM (high is bad)
        result = calculate_kpi_health_score(
            current_value=10000.0,
            predicted_value=11000.0,
            kpi_type="ppm"
        )
        assert result["health_score"] < 60

    def test_stable_trend_detection(self):
        """Test stable trend is detected when values are close"""
        result = calculate_kpi_health_score(
            current_value=85.0,
            predicted_value=85.2,
            kpi_type="efficiency"
        )

        assert result["trend"] == "stable"

    def test_declining_trend_detection(self):
        """Test declining trend is detected"""
        result = calculate_kpi_health_score(
            current_value=85.0,
            predicted_value=80.0,
            kpi_type="efficiency"
        )

        assert result["trend"] == "declining"


class TestPredictionAlgorithms:
    """Tests for prediction/forecasting algorithms"""

    @pytest.fixture
    def sample_values(self):
        """Generate sample historical values"""
        return [Decimal(str(80 + i * 0.5)) for i in range(30)]

    def test_simple_exponential_smoothing(self, sample_values):
        """Test simple exponential smoothing forecast"""
        result = simple_exponential_smoothing(sample_values, forecast_periods=7)

        assert isinstance(result, ForecastResult)
        assert len(result.predictions) == 7
        assert len(result.confidence_scores) == 7
        assert result.method == "simple_exponential_smoothing"

    def test_double_exponential_smoothing(self, sample_values):
        """Test double exponential smoothing forecast"""
        result = double_exponential_smoothing(sample_values, forecast_periods=7)

        assert isinstance(result, ForecastResult)
        assert len(result.predictions) == 7
        assert result.method == "double_exponential_smoothing"

    def test_linear_trend_extrapolation(self, sample_values):
        """Test linear trend extrapolation forecast"""
        result = linear_trend_extrapolation(sample_values, forecast_periods=7)

        assert isinstance(result, ForecastResult)
        assert len(result.predictions) == 7
        assert result.method == "linear_trend_extrapolation"

    def test_auto_forecast_selection(self, sample_values):
        """Test auto_forecast selects appropriate method"""
        result = auto_forecast(sample_values, forecast_periods=7)

        assert isinstance(result, ForecastResult)
        assert len(result.predictions) == 7
        assert result.method in [
            "simple_exponential_smoothing",
            "double_exponential_smoothing",
            "linear_trend_extrapolation"
        ]

    def test_confidence_intervals(self, sample_values):
        """Test confidence intervals are logical"""
        result = auto_forecast(sample_values, forecast_periods=7)

        for i in range(7):
            assert result.lower_bounds[i] <= result.predictions[i] <= result.upper_bounds[i]

    def test_confidence_decreases_with_horizon(self, sample_values):
        """Test confidence decreases as forecast horizon increases"""
        result = auto_forecast(sample_values, forecast_periods=14)

        # Confidence should generally decrease over time
        assert result.confidence_scores[0] >= result.confidence_scores[-1]

    def test_forecast_accuracy_calculation(self):
        """Test forecast accuracy metrics calculation"""
        actual = [Decimal("80"), Decimal("82"), Decimal("85")]
        predicted = [Decimal("81"), Decimal("83"), Decimal("84")]

        metrics = calculate_forecast_accuracy(actual, predicted)

        assert "mae" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics
        assert metrics["mae"] > 0
        assert metrics["rmse"] > 0

    def test_minimum_data_requirements(self):
        """Test minimum data requirements are enforced"""
        # Should raise error with insufficient data
        with pytest.raises(ValueError):
            simple_exponential_smoothing([Decimal("80")], forecast_periods=7)


class TestPredictionIntegration:
    """Integration tests combining generation and prediction"""

    def test_generate_and_forecast(self):
        """Test generating history and creating forecast"""
        # Generate history
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=30,
            seed=42
        )

        # Extract values for forecast
        values = [Decimal(str(d["value"])) for d in history]

        # Generate forecast
        result = auto_forecast(values, forecast_periods=7)

        assert len(result.predictions) == 7
        assert float(result.accuracy_score) > 0

    def test_all_kpis_forecastable(self):
        """Test all KPIs can be forecasted"""
        all_data = generate_all_kpi_histories(days=30, seed=42)

        for kpi_type, history in all_data.items():
            values = [Decimal(str(d["value"])) for d in history]
            result = auto_forecast(values, forecast_periods=7)

            assert len(result.predictions) == 7, f"Failed for {kpi_type}"

    def test_health_from_generated_data(self):
        """Test health calculation from generated data"""
        history = generate_kpi_history(
            kpi_type="efficiency",
            days=30,
            seed=42
        )

        current_value = history[-1]["value"]
        values = [Decimal(str(d["value"])) for d in history]
        forecast = auto_forecast(values, forecast_periods=7)
        predicted_avg = sum(float(p) for p in forecast.predictions) / 7

        health = calculate_kpi_health_score(
            current_value=current_value,
            predicted_value=predicted_avg,
            kpi_type="efficiency"
        )

        assert 0 <= health["health_score"] <= 100
        assert health["trend"] in ["improving", "declining", "stable"]


class TestKPIConfigValidation:
    """Tests for KPI configuration validation"""

    def test_all_kpis_have_config(self):
        """Test all KPI types have configuration"""
        for kpi_type in KPITypePhase5:
            assert kpi_type in KPI_CONFIGS

    def test_config_values_are_valid(self):
        """Test configuration values are within valid ranges"""
        for kpi_type, config in KPI_CONFIGS.items():
            assert config.min_value < config.max_value
            assert config.min_value <= config.base_value <= config.max_value
            assert config.volatility > 0
            assert config.weekly_amplitude >= 0

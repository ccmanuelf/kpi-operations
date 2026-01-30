"""
Comprehensive Alert Calculation Tests
Tests all alert generation functions with various scenarios.
Target: Increase calculations/alerts.py coverage from 11% to 85%+
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.calculations.alerts import (
    AlertGenerationResult,
    generate_alert_id,
    check_threshold_breach,
    generate_efficiency_alert,
    generate_otd_risk_alert,
    generate_quality_alert,
    generate_capacity_alert,
    generate_prediction_based_alert,
    generate_attendance_alert,
    generate_hold_alert,
)


class TestAlertGenerationResult:
    """Tests for AlertGenerationResult dataclass."""

    def test_dataclass_creation(self):
        """Test creating AlertGenerationResult with all fields."""
        result = AlertGenerationResult(
            should_alert=True,
            severity="warning",
            title="Test Alert",
            message="Test message",
            recommendation="Take action",
            confidence=Decimal("95.0"),
            current_value=Decimal("75.0"),
            threshold_value=Decimal("80.0"),
            predicted_value=Decimal("70.0"),
            metadata={"key": "value"}
        )

        assert result.should_alert is True
        assert result.severity == "warning"
        assert result.title == "Test Alert"
        assert result.message == "Test message"
        assert result.recommendation == "Take action"
        assert result.confidence == Decimal("95.0")
        assert result.current_value == Decimal("75.0")
        assert result.threshold_value == Decimal("80.0")
        assert result.predicted_value == Decimal("70.0")
        assert result.metadata == {"key": "value"}

    def test_dataclass_optional_fields(self):
        """Test creating with only required fields."""
        result = AlertGenerationResult(
            should_alert=False,
            severity="info",
            title="Info",
            message="Message"
        )

        assert result.should_alert is False
        assert result.recommendation is None
        assert result.metadata is None


class TestGenerateAlertId:
    """Tests for generate_alert_id function."""

    def test_generate_alert_id_format(self):
        """Test alert ID has correct format."""
        alert_id = generate_alert_id()

        assert alert_id.startswith("ALT-")
        parts = alert_id.split("-")
        assert len(parts) == 3
        # Date part should be YYYYMMDD
        assert len(parts[1]) == 8
        assert parts[1].isdigit()
        # UUID part should be 8 hex chars uppercase
        assert len(parts[2]) == 8
        assert parts[2].isalnum()

    def test_generate_alert_id_unique(self):
        """Test alert IDs are unique."""
        ids = [generate_alert_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_alert_id_date_component(self):
        """Test alert ID contains current date."""
        alert_id = generate_alert_id()
        expected_date = datetime.now().strftime('%Y%m%d')
        assert expected_date in alert_id


class TestCheckThresholdBreach:
    """Tests for check_threshold_breach function."""

    def test_higher_is_better_no_breach(self):
        """Test no breach when value is above target (higher is better)."""
        result = check_threshold_breach(
            current_value=Decimal("90"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result is None

    def test_higher_is_better_warning_breach(self):
        """Test warning breach when value is below warning threshold."""
        result = check_threshold_breach(
            current_value=Decimal("78"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "warning"

    def test_higher_is_better_critical_breach(self):
        """Test critical breach when value is below critical threshold."""
        result = check_threshold_breach(
            current_value=Decimal("68"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "critical"

    def test_higher_is_better_urgent_breach(self):
        """Test urgent breach when value is far below target (< 50%)."""
        result = check_threshold_breach(
            current_value=Decimal("40"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "urgent"

    def test_lower_is_better_no_breach(self):
        """Test no breach when value is below target (lower is better)."""
        result = check_threshold_breach(
            current_value=Decimal("500"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result is None

    def test_lower_is_better_warning_breach(self):
        """Test warning breach when value is above warning threshold."""
        result = check_threshold_breach(
            current_value=Decimal("1600"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result == "warning"

    def test_lower_is_better_critical_breach(self):
        """Test critical breach when value is above critical threshold."""
        result = check_threshold_breach(
            current_value=Decimal("2100"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result == "critical"

    def test_lower_is_better_urgent_breach(self):
        """Test urgent breach when value is far above target (> 5x)."""
        result = check_threshold_breach(
            current_value=Decimal("6000"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result == "urgent"

    def test_no_thresholds_provided(self):
        """Test with None thresholds."""
        result = check_threshold_breach(
            current_value=Decimal("50"),
            target=Decimal("85"),
            warning_threshold=None,
            critical_threshold=None,
            higher_is_better=True
        )
        # No thresholds to check against except urgent
        assert result is None or result == "urgent"

    def test_boundary_value_at_warning(self):
        """Test at exact warning threshold."""
        result = check_threshold_breach(
            current_value=Decimal("80"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "warning"

    def test_boundary_value_at_critical(self):
        """Test at exact critical threshold."""
        result = check_threshold_breach(
            current_value=Decimal("70"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "critical"


class TestGenerateEfficiencyAlert:
    """Tests for generate_efficiency_alert function."""

    def test_no_alert_above_target(self):
        """Test no alert when efficiency is above target."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("90"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )
        assert result is None

    def test_warning_alert(self):
        """Test warning alert below warning threshold."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("78"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity == "warning"
        assert "Warning" in result.title
        assert result.current_value == Decimal("78")

    def test_critical_alert(self):
        """Test critical alert below critical threshold."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("65"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.severity == "critical"
        assert "Critical" in result.title
        assert result.recommendation is not None

    def test_urgent_alert(self):
        """Test urgent alert far below target."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("40"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.severity == "urgent"
        assert "URGENT" in result.title

    def test_declining_trend_alert(self):
        """Test alert for 5 consecutive declining values."""
        historical = [
            Decimal("95"), Decimal("93"), Decimal("90"),
            Decimal("88"), Decimal("86"), Decimal("84"), Decimal("82")
        ]

        result = generate_efficiency_alert(
            current_efficiency=Decimal("82"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            historical_values=historical
        )

        assert result is not None
        assert result.severity == "warning"
        assert "Declining Trend" in result.title
        assert result.metadata["trend"] == "declining"

    def test_no_trend_alert_not_enough_data(self):
        """Test no trend alert with insufficient historical data."""
        historical = [Decimal("90"), Decimal("88"), Decimal("86")]  # Only 3 values

        result = generate_efficiency_alert(
            current_efficiency=Decimal("88"),
            target=Decimal("85"),
            historical_values=historical
        )

        assert result is None  # Above threshold and not enough data for trend

    def test_with_client_name(self):
        """Test alert includes client name in context."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("65"),
            target=Decimal("85"),
            client_name="Test Client"
        )

        assert result is not None
        assert "Test Client" in result.title

    def test_metadata_includes_thresholds(self):
        """Test metadata includes threshold values."""
        result = generate_efficiency_alert(
            current_efficiency=Decimal("78"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.metadata["warning"] == Decimal("80")
        assert result.metadata["critical"] == Decimal("70")


class TestGenerateOtdRiskAlert:
    """Tests for generate_otd_risk_alert function."""

    def test_no_alert_on_track(self):
        """Test no alert when order is on track."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=14),
            current_completion_percent=Decimal("50"),
            planned_completion_percent=Decimal("50"),
            days_remaining=14
        )
        assert result is None

    def test_warning_alert_slightly_behind(self):
        """Test warning alert when slightly behind schedule."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=10),
            current_completion_percent=Decimal("40"),
            planned_completion_percent=Decimal("55"),
            days_remaining=10
        )

        assert result is not None
        assert result.should_alert is True
        # Gap is 15%, risk should be moderate
        assert result.severity in ["warning", "critical"]

    def test_critical_alert_behind_schedule(self):
        """Test critical alert when significantly behind schedule."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=5),
            current_completion_percent=Decimal("30"),
            planned_completion_percent=Decimal("60"),
            days_remaining=5
        )

        assert result is not None
        assert result.severity in ["critical", "urgent"]
        assert "Behind Schedule" in result.title or "Risk" in result.title

    def test_urgent_alert_deadline_imminent(self):
        """Test urgent alert when deadline is imminent."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=1),
            current_completion_percent=Decimal("50"),
            planned_completion_percent=Decimal("90"),
            days_remaining=1
        )

        assert result is not None
        assert result.severity == "urgent"
        assert "URGENT" in result.title

    def test_risk_score_in_metadata(self):
        """Test risk score is included in metadata."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=3),
            current_completion_percent=Decimal("20"),
            planned_completion_percent=Decimal("70"),
            days_remaining=3
        )

        assert result is not None
        assert "risk_score" in result.metadata
        assert result.metadata["work_order_id"] == "WO-001"
        assert result.metadata["client_name"] == "Test Client"

    def test_confidence_based_on_risk(self):
        """Test confidence is inverse of risk score."""
        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=5),
            current_completion_percent=Decimal("30"),
            planned_completion_percent=Decimal("60"),
            days_remaining=5
        )

        assert result is not None
        # Confidence = 100 - risk_score
        assert result.confidence is not None
        assert result.confidence + Decimal(str(result.metadata["risk_score"])) == Decimal("100")


class TestGenerateQualityAlert:
    """Tests for generate_quality_alert function."""

    def test_fpy_no_alert_above_target(self):
        """Test no alert when FPY is above target."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("98"),
            target=Decimal("95")
        )
        assert result is None

    def test_fpy_warning_alert(self):
        """Test warning alert for FPY below warning threshold."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("89"),
            target=Decimal("95"),
            warning_threshold=Decimal("90"),
            critical_threshold=Decimal("85")
        )

        assert result is not None
        assert result.severity == "warning"
        assert "First Pass Yield" in result.title
        assert result.metadata["kpi_type"] == "fpy"

    def test_fpy_critical_alert(self):
        """Test critical alert for FPY below critical threshold."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("82"),
            target=Decimal("95"),
            warning_threshold=Decimal("90"),
            critical_threshold=Decimal("85")
        )

        assert result is not None
        assert result.severity == "critical"

    def test_fpy_urgent_alert(self):
        """Test urgent alert for FPY far below target."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("40"),
            target=Decimal("95")
        )

        assert result is not None
        assert result.severity == "urgent"
        assert "URGENT" in result.title

    def test_dpmo_no_alert_below_target(self):
        """Test no alert when DPMO is below target (lower is better)."""
        result = generate_quality_alert(
            kpi_type="dpmo",
            current_value=Decimal("500"),
            target=Decimal("1000")
        )
        assert result is None

    def test_dpmo_warning_alert(self):
        """Test warning alert when DPMO exceeds warning threshold."""
        result = generate_quality_alert(
            kpi_type="dpmo",
            current_value=Decimal("1600"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000")
        )

        assert result is not None
        assert result.severity == "warning"
        assert "DPMO" in result.title or "Defects Per Million" in result.title

    def test_dpmo_critical_alert(self):
        """Test critical alert when DPMO exceeds critical threshold."""
        result = generate_quality_alert(
            kpi_type="dpmo",
            current_value=Decimal("2500"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000")
        )

        assert result is not None
        assert result.severity == "critical"

    def test_ppm_urgent_alert(self):
        """Test urgent alert for PPM far above target."""
        result = generate_quality_alert(
            kpi_type="ppm",
            current_value=Decimal("6000"),
            target=Decimal("1000")
        )

        assert result is not None
        assert result.severity == "urgent"

    def test_rty_alert(self):
        """Test RTY alert (higher is better like FPY)."""
        result = generate_quality_alert(
            kpi_type="rty",
            current_value=Decimal("75"),
            target=Decimal("90"),
            warning_threshold=Decimal("85"),
            critical_threshold=Decimal("80")
        )

        assert result is not None
        assert result.severity == "critical"
        assert "Rolled Throughput Yield" in result.title

    def test_declining_trend_info_alert(self):
        """Test info alert for declining trend without threshold breach."""
        historical = [Decimal("97"), Decimal("96"), Decimal("94")]

        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("94"),
            target=Decimal("90"),
            historical_values=historical
        )

        assert result is not None
        assert result.severity == "info"
        assert result.metadata["trend"] == "declining"

    def test_improving_trend_no_alert(self):
        """Test no alert for improving trend."""
        historical = [Decimal("88"), Decimal("90"), Decimal("92")]

        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("94"),
            target=Decimal("90"),
            historical_values=historical
        )

        assert result is None

    def test_with_product_line(self):
        """Test alert includes product line in context."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("75"),
            target=Decimal("95"),
            product_line="Assembly Line A"
        )

        assert result is not None
        assert "Assembly Line A" in result.title

    def test_default_thresholds(self):
        """Test default thresholds are calculated correctly."""
        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("80"),
            target=Decimal("90")
        )

        # Default warning = 90 * 0.95 = 85.5
        # Default critical = 90 * 0.90 = 81
        # 80 < 81 = critical
        assert result is not None
        assert result.severity == "critical"


class TestGenerateCapacityAlert:
    """Tests for generate_capacity_alert function."""

    def test_optimal_load_no_alert(self):
        """Test no alert when load is in optimal range."""
        result = generate_capacity_alert(
            load_percent=Decimal("90")
        )
        assert result is None

    def test_severe_underutilization_alert(self):
        """Test warning alert for severe underutilization."""
        result = generate_capacity_alert(
            load_percent=Decimal("60")
        )

        assert result is not None
        assert result.severity == "warning"
        assert "Underutilization" in result.title
        assert result.metadata["status"] == "underutilized"

    def test_below_optimal_info_alert(self):
        """Test info alert when below optimal range."""
        result = generate_capacity_alert(
            load_percent=Decimal("82")
        )

        assert result is not None
        assert result.severity == "info"
        assert "Below Optimal" in result.title

    def test_near_maximum_warning(self):
        """Test warning alert near maximum capacity."""
        result = generate_capacity_alert(
            load_percent=Decimal("100")
        )

        assert result is not None
        assert result.severity == "warning"
        assert "Near Maximum" in result.title
        assert result.metadata["status"] == "near_max"

    def test_overloaded_critical_alert(self):
        """Test critical alert when overloaded."""
        result = generate_capacity_alert(
            load_percent=Decimal("115")
        )

        assert result is not None
        assert result.severity == "critical"
        assert "Overloaded" in result.title
        assert result.metadata["status"] == "overloaded"

    def test_optimal_with_bottleneck(self):
        """Test info alert for optimal load with bottleneck."""
        result = generate_capacity_alert(
            load_percent=Decimal("90"),
            bottleneck_station="Assembly Station 3"
        )

        assert result is not None
        assert result.severity == "info"
        assert "Bottleneck" in result.title
        assert "Assembly Station 3" in result.message

    def test_with_idle_days_prediction(self):
        """Test message includes predicted idle days."""
        result = generate_capacity_alert(
            load_percent=Decimal("60"),
            predicted_idle_days=3
        )

        assert result is not None
        assert "idle days: 3" in result.message.lower()
        assert result.metadata["idle_days"] == 3

    def test_with_overtime_hours(self):
        """Test message includes overtime hours needed."""
        result = generate_capacity_alert(
            load_percent=Decimal("110"),
            overtime_hours_needed=Decimal("24")
        )

        assert result is not None
        assert "Overtime needed" in result.message
        assert result.metadata["overtime_hours"] == 24.0

    def test_custom_optimal_range(self):
        """Test with custom optimal range."""
        result = generate_capacity_alert(
            load_percent=Decimal("80"),
            optimal_min=Decimal("90"),
            optimal_max=Decimal("98")
        )

        assert result is not None
        assert result.severity == "info"  # Below custom optimal_min


class TestGeneratePredictionBasedAlert:
    """Tests for generate_prediction_based_alert function."""

    def test_insufficient_historical_data(self):
        """Test no alert with insufficient data."""
        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=[Decimal("90"), Decimal("88")],
            target=Decimal("85")
        )
        assert result is None

    @patch('backend.calculations.alerts.auto_forecast')
    def test_prediction_warning_alert(self, mock_forecast):
        """Test warning alert based on prediction."""
        mock_result = MagicMock()
        mock_result.predictions = [Decimal("82"), Decimal("80"), Decimal("78")]
        mock_result.confidence_scores = [Decimal("90"), Decimal("85"), Decimal("80")]
        mock_result.method = "linear"
        mock_result.accuracy_score = Decimal("0.92")
        mock_forecast.return_value = mock_result

        historical = [Decimal("90"), Decimal("88"), Decimal("86"), Decimal("84"), Decimal("82")]

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            forecast_periods=3
        )

        assert result is not None
        assert result.should_alert is True
        # 78 < 80 (warning) and within 3 days → escalated to critical
        assert result.severity in ["warning", "critical"]

    @patch('backend.calculations.alerts.auto_forecast')
    def test_prediction_urgent_near_term(self, mock_forecast):
        """Test urgent alert for near-term critical prediction."""
        mock_result = MagicMock()
        mock_result.predictions = [Decimal("65"), Decimal("60"), Decimal("55")]
        mock_result.confidence_scores = [Decimal("95"), Decimal("90"), Decimal("85")]
        mock_result.method = "exponential"
        mock_result.accuracy_score = Decimal("0.88")
        mock_forecast.return_value = mock_result

        historical = [Decimal("85"), Decimal("82"), Decimal("78"), Decimal("74"), Decimal("70")]

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            forecast_periods=3
        )

        assert result is not None
        # 65 < 70 (critical) and within 3 days → urgent
        assert result.severity == "urgent"

    @patch('backend.calculations.alerts.auto_forecast')
    def test_prediction_lower_is_better(self, mock_forecast):
        """Test prediction alert for lower-is-better metric."""
        mock_result = MagicMock()
        mock_result.predictions = [Decimal("2200"), Decimal("2500"), Decimal("2800")]
        mock_result.confidence_scores = [Decimal("90"), Decimal("85"), Decimal("80")]
        mock_result.method = "linear"
        mock_result.accuracy_score = Decimal("0.90")
        mock_forecast.return_value = mock_result

        historical = [Decimal("1000"), Decimal("1200"), Decimal("1500"), Decimal("1800"), Decimal("2000")]

        result = generate_prediction_based_alert(
            kpi_key="dpmo",
            historical_values=historical,
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )

        assert result is not None
        assert result.should_alert is True

    @patch('backend.calculations.alerts.auto_forecast')
    def test_no_alert_predictions_within_target(self, mock_forecast):
        """Test no alert when predictions stay within target."""
        mock_result = MagicMock()
        mock_result.predictions = [Decimal("88"), Decimal("87"), Decimal("86")]
        mock_result.confidence_scores = [Decimal("95"), Decimal("92"), Decimal("89")]
        mock_result.method = "linear"
        mock_result.accuracy_score = Decimal("0.95")
        mock_forecast.return_value = mock_result

        historical = [Decimal("92"), Decimal("91"), Decimal("90"), Decimal("89"), Decimal("88")]

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is None

    @patch('backend.calculations.alerts.auto_forecast')
    def test_forecast_exception_returns_none(self, mock_forecast):
        """Test exception during forecast returns None."""
        mock_forecast.side_effect = Exception("Forecast error")

        historical = [Decimal("90"), Decimal("88"), Decimal("86"), Decimal("84"), Decimal("82")]

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("85")
        )

        assert result is None

    @patch('backend.calculations.alerts.auto_forecast')
    def test_metadata_includes_forecast_info(self, mock_forecast):
        """Test metadata includes forecast method and accuracy."""
        mock_result = MagicMock()
        mock_result.predictions = [Decimal("75"), Decimal("72"), Decimal("69")]
        mock_result.confidence_scores = [Decimal("90"), Decimal("85"), Decimal("80")]
        mock_result.method = "exponential_smoothing"
        mock_result.accuracy_score = Decimal("0.91")
        mock_forecast.return_value = mock_result

        historical = [Decimal("88"), Decimal("85"), Decimal("82"), Decimal("79"), Decimal("76")]

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.metadata["forecast_method"] == "exponential_smoothing"
        assert result.metadata["forecast_accuracy"] == 0.91
        assert "worst_period_days" in result.metadata


class TestGenerateAttendanceAlert:
    """Tests for generate_attendance_alert function."""

    def test_no_alert_below_target(self):
        """Test no alert when absenteeism is below target."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("3")
        )
        assert result is None

    def test_warning_alert(self):
        """Test warning alert above warning threshold."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("9"),
            target_rate=Decimal("5"),
            warning_threshold=Decimal("8"),
            critical_threshold=Decimal("12")
        )

        assert result is not None
        assert result.severity == "warning"
        assert "Elevated Absenteeism" in result.title

    def test_critical_alert(self):
        """Test critical alert above critical threshold."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("14"),
            target_rate=Decimal("5"),
            warning_threshold=Decimal("8"),
            critical_threshold=Decimal("12")
        )

        assert result is not None
        assert result.severity == "critical"
        assert "High Absenteeism" in result.title

    def test_urgent_alert(self):
        """Test urgent alert far above target."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("30"),  # Far above 5% target * 5 = 25%
            target_rate=Decimal("5")
        )

        assert result is not None
        assert result.severity == "urgent"
        assert "URGENT" in result.title

    def test_coverage_gap_in_message(self):
        """Test coverage gap is included in message."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("14"),
            floating_pool_available=3,
            coverage_needed=10
        )

        assert result is not None
        assert "Coverage gap: 7 workers short" in result.message
        assert result.metadata["coverage_gap"] == 7

    def test_floating_pool_can_cover(self):
        """Test message when floating pool can cover."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("14"),
            floating_pool_available=15,
            coverage_needed=10
        )

        assert result is not None
        assert "Floating pool can cover" in result.message

    def test_critical_with_large_coverage_gap_urgent_title(self):
        """Test critical with large coverage gap gets urgent title."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("14"),
            critical_threshold=Decimal("12"),
            floating_pool_available=0,
            coverage_needed=10
        )

        assert result is not None
        # Coverage gap > 5 triggers urgent title but severity stays critical
        assert "URGENT" in result.title
        assert result.severity == "critical"

    def test_metadata_includes_coverage_info(self):
        """Test metadata includes coverage information."""
        result = generate_attendance_alert(
            absenteeism_rate=Decimal("10"),
            floating_pool_available=5,
            coverage_needed=8
        )

        assert result is not None
        assert result.metadata["floating_pool_available"] == 5
        assert result.metadata["coverage_needed"] == 8
        assert result.metadata["coverage_gap"] == 3


class TestGenerateHoldAlert:
    """Tests for generate_hold_alert function."""

    def test_no_alert_zero_holds(self):
        """Test no alert when no holds pending."""
        result = generate_hold_alert(
            pending_holds_count=0
        )
        assert result is None

    def test_info_alert_few_holds(self):
        """Test info alert for few holds."""
        result = generate_hold_alert(
            pending_holds_count=2
        )

        assert result is not None
        assert result.severity == "info"
        assert "Require Approval" in result.title

    def test_warning_alert_many_holds(self):
        """Test warning alert for many holds."""
        result = generate_hold_alert(
            pending_holds_count=8
        )

        assert result is not None
        assert result.severity == "warning"
        assert "8 Holds Pending" in result.title

    def test_warning_alert_aging_hold(self):
        """Test warning alert for aging hold."""
        result = generate_hold_alert(
            pending_holds_count=2,
            oldest_hold_hours=12
        )

        assert result is not None
        assert result.severity == "warning"
        assert "Aging" in result.title

    def test_critical_alert_over_24_hours(self):
        """Test critical alert for hold over 24 hours."""
        result = generate_hold_alert(
            pending_holds_count=1,
            oldest_hold_hours=30
        )

        assert result is not None
        assert result.severity == "critical"
        assert "Over 24 Hours" in result.title

    def test_message_includes_oldest_hours(self):
        """Test message includes oldest hold hours."""
        result = generate_hold_alert(
            pending_holds_count=3,
            oldest_hold_hours=16
        )

        assert result is not None
        assert "Oldest pending: 16 hours" in result.message

    def test_message_includes_units_on_hold(self):
        """Test message includes total units on hold."""
        result = generate_hold_alert(
            pending_holds_count=2,
            total_units_on_hold=500
        )

        assert result is not None
        assert "Total units on hold: 500" in result.message

    def test_metadata_includes_hold_info(self):
        """Test metadata includes hold information."""
        result = generate_hold_alert(
            pending_holds_count=3,
            oldest_hold_hours=10,
            total_units_on_hold=250
        )

        assert result is not None
        assert result.metadata["pending_count"] == 3
        assert result.metadata["oldest_hours"] == 10
        assert result.metadata["units_on_hold"] == 250


class TestAlertIntegration:
    """Integration tests for alert combinations."""

    def test_multiple_alerts_different_severities(self):
        """Test generating multiple alerts returns appropriate severities."""
        # Efficiency alert
        eff_alert = generate_efficiency_alert(
            current_efficiency=Decimal("65"),
            target=Decimal("85")
        )

        # Quality alert
        qual_alert = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("80"),
            target=Decimal("95")
        )

        # Attendance alert
        att_alert = generate_attendance_alert(
            absenteeism_rate=Decimal("10")
        )

        assert eff_alert.severity == "critical"
        assert qual_alert.severity == "critical"
        assert att_alert.severity == "warning"

    def test_alert_recommendations_are_actionable(self):
        """Test all alerts have actionable recommendations."""
        alerts = [
            generate_efficiency_alert(Decimal("65"), Decimal("85")),
            generate_quality_alert("fpy", Decimal("75"), Decimal("95")),
            generate_capacity_alert(Decimal("120")),
            generate_attendance_alert(Decimal("15")),
            generate_hold_alert(10, 48, 1000),
        ]

        for alert in alerts:
            assert alert is not None
            assert alert.recommendation is not None
            assert len(alert.recommendation) > 10  # Meaningful recommendation

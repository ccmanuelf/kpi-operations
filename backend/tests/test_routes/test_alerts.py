"""
Tests for Alert Calculations and Schemas
Phase 10.3: Intelligent Alerting System
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal


class TestAlertCalculations:
    """Test suite for alert calculation functions"""

    def test_generate_alert_id_format(self):
        """Test alert ID generation format"""
        from backend.calculations.alerts import generate_alert_id

        alert_id = generate_alert_id()
        assert alert_id.startswith("ALT-")
        assert len(alert_id) > 10

    def test_generate_alert_id_uniqueness(self):
        """Test alert IDs are unique"""
        from backend.calculations.alerts import generate_alert_id

        ids = [generate_alert_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_check_threshold_breach_higher_is_better(self):
        """Test threshold breach detection when higher values are better"""
        from backend.calculations.alerts import check_threshold_breach

        # Below critical
        result = check_threshold_breach(
            current_value=Decimal("65"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "critical"

        # Below warning
        result = check_threshold_breach(
            current_value=Decimal("75"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "warning"

        # Above warning (ok)
        result = check_threshold_breach(
            current_value=Decimal("82"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result is None

    def test_check_threshold_breach_lower_is_better(self):
        """Test threshold breach detection when lower values are better"""
        from backend.calculations.alerts import check_threshold_breach

        # Above critical (bad)
        result = check_threshold_breach(
            current_value=Decimal("5000"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result == "critical"

        # Above warning
        result = check_threshold_breach(
            current_value=Decimal("1700"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result == "warning"

        # Below warning (ok)
        result = check_threshold_breach(
            current_value=Decimal("1200"),
            target=Decimal("1000"),
            warning_threshold=Decimal("1500"),
            critical_threshold=Decimal("2000"),
            higher_is_better=False
        )
        assert result is None

    def test_check_threshold_breach_urgent(self):
        """Test urgent severity detection"""
        from backend.calculations.alerts import check_threshold_breach

        # Far below target (higher is better)
        result = check_threshold_breach(
            current_value=Decimal("30"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )
        assert result == "urgent"

    def test_generate_efficiency_alert_critical(self):
        """Test efficiency alert generation at critical level"""
        from backend.calculations.alerts import generate_efficiency_alert

        result = generate_efficiency_alert(
            current_efficiency=Decimal("65"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity == "critical"
        assert "65" in result.message
        assert result.current_value == Decimal("65")

    def test_generate_efficiency_alert_warning(self):
        """Test efficiency alert generation at warning level"""
        from backend.calculations.alerts import generate_efficiency_alert

        result = generate_efficiency_alert(
            current_efficiency=Decimal("75"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity == "warning"

    def test_generate_efficiency_alert_ok(self):
        """Test efficiency alert returns None when above thresholds"""
        from backend.calculations.alerts import generate_efficiency_alert

        result = generate_efficiency_alert(
            current_efficiency=Decimal("88"),
            target=Decimal("85"),
            warning_threshold=Decimal("80"),
            critical_threshold=Decimal("70")
        )

        assert result is None

    def test_generate_efficiency_alert_declining_trend(self):
        """Test efficiency alert detects declining trend"""
        from backend.calculations.alerts import generate_efficiency_alert

        # 5 consecutive declining values
        historical = [
            Decimal("90"), Decimal("89"), Decimal("88"),
            Decimal("87"), Decimal("86")
        ]

        result = generate_efficiency_alert(
            current_efficiency=Decimal("86"),
            target=Decimal("85"),
            historical_values=historical
        )

        assert result is not None
        assert result.should_alert is True
        assert "declin" in result.title.lower() or "declin" in result.message.lower()

    def test_generate_otd_risk_alert_high_risk(self):
        """Test OTD risk alert for work order behind schedule"""
        from backend.calculations.alerts import generate_otd_risk_alert

        result = generate_otd_risk_alert(
            work_order_id="WO-001",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=2),
            current_completion_percent=Decimal("40"),
            planned_completion_percent=Decimal("80"),
            days_remaining=2
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity in ["urgent", "critical", "warning"]
        assert "WO-001" in result.title

    def test_generate_otd_risk_alert_on_track(self):
        """Test OTD risk alert returns None when on track"""
        from backend.calculations.alerts import generate_otd_risk_alert

        result = generate_otd_risk_alert(
            work_order_id="WO-002",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=14),
            current_completion_percent=Decimal("50"),
            planned_completion_percent=Decimal("50"),
            days_remaining=14
        )

        # Should be None since on track
        assert result is None

    def test_generate_otd_risk_alert_metadata(self):
        """Test OTD risk alert includes metadata"""
        from backend.calculations.alerts import generate_otd_risk_alert

        result = generate_otd_risk_alert(
            work_order_id="WO-003",
            client_name="Test Client",
            due_date=datetime.now() + timedelta(days=1),
            current_completion_percent=Decimal("20"),
            planned_completion_percent=Decimal("90"),
            days_remaining=1
        )

        assert result is not None
        assert result.metadata is not None
        assert "risk_score" in result.metadata
        assert result.metadata["work_order_id"] == "WO-003"

    def test_generate_quality_alert_fpy_critical(self):
        """Test quality alert for low FPY"""
        from backend.calculations.alerts import generate_quality_alert

        result = generate_quality_alert(
            kpi_type="fpy",
            current_value=Decimal("85"),
            target=Decimal("98"),
            warning_threshold=Decimal("95"),
            critical_threshold=Decimal("90")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity in ["critical", "urgent"]
        assert "First Pass Yield" in result.title or "FPY" in result.title

    def test_generate_quality_alert_dpmo_high(self):
        """Test quality alert for high DPMO (lower is better)"""
        from backend.calculations.alerts import generate_quality_alert

        result = generate_quality_alert(
            kpi_type="dpmo",
            current_value=Decimal("5000"),
            target=Decimal("1000"),
            warning_threshold=Decimal("2000"),
            critical_threshold=Decimal("3000")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity in ["critical", "urgent"]

    def test_generate_quality_alert_rty(self):
        """Test quality alert for RTY"""
        from backend.calculations.alerts import generate_quality_alert

        result = generate_quality_alert(
            kpi_type="rty",
            current_value=Decimal("88"),
            target=Decimal("95"),
            warning_threshold=Decimal("92"),
            critical_threshold=Decimal("90")
        )

        assert result is not None
        assert result.severity in ["critical", "warning"]

    def test_generate_capacity_alert_overloaded(self):
        """Test capacity alert when overloaded"""
        from backend.calculations.alerts import generate_capacity_alert

        result = generate_capacity_alert(
            load_percent=Decimal("115"),
            optimal_min=Decimal("85"),
            optimal_max=Decimal("95")
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity == "critical"
        assert "overload" in result.title.lower() or "CANNOT" in result.message

    def test_generate_capacity_alert_underutilized(self):
        """Test capacity alert when underutilized"""
        from backend.calculations.alerts import generate_capacity_alert

        result = generate_capacity_alert(
            load_percent=Decimal("60"),
            predicted_idle_days=5
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity == "warning"

    def test_generate_capacity_alert_optimal(self):
        """Test no capacity alert when optimal"""
        from backend.calculations.alerts import generate_capacity_alert

        result = generate_capacity_alert(
            load_percent=Decimal("90")
        )

        assert result is None

    def test_generate_capacity_alert_with_bottleneck(self):
        """Test capacity alert includes bottleneck info"""
        from backend.calculations.alerts import generate_capacity_alert

        result = generate_capacity_alert(
            load_percent=Decimal("90"),
            bottleneck_station="Station 12"
        )

        assert result is not None
        assert "Station 12" in result.message

    def test_generate_attendance_alert_high_absenteeism(self):
        """Test attendance alert for high absenteeism"""
        from backend.calculations.alerts import generate_attendance_alert

        result = generate_attendance_alert(
            absenteeism_rate=Decimal("15"),
            target_rate=Decimal("5"),
            warning_threshold=Decimal("8"),
            critical_threshold=Decimal("12"),
            floating_pool_available=3,
            coverage_needed=8
        )

        assert result is not None
        assert result.should_alert is True
        assert result.severity in ["critical", "urgent"]
        assert "15" in result.message

    def test_generate_attendance_alert_ok(self):
        """Test no attendance alert when rate is acceptable"""
        from backend.calculations.alerts import generate_attendance_alert

        result = generate_attendance_alert(
            absenteeism_rate=Decimal("4"),
            target_rate=Decimal("5"),
            warning_threshold=Decimal("8"),
            critical_threshold=Decimal("12")
        )

        assert result is None

    def test_generate_hold_alert_pending(self):
        """Test hold alert for pending approvals"""
        from backend.calculations.alerts import generate_hold_alert

        result = generate_hold_alert(
            pending_holds_count=3,
            oldest_hold_hours=12,
            total_units_on_hold=150
        )

        assert result is not None
        assert result.should_alert is True
        assert "3" in result.message or "3" in result.title

    def test_generate_hold_alert_urgent(self):
        """Test hold alert escalates to critical after 24 hours"""
        from backend.calculations.alerts import generate_hold_alert

        result = generate_hold_alert(
            pending_holds_count=1,
            oldest_hold_hours=30,
            total_units_on_hold=50
        )

        assert result is not None
        assert result.severity == "critical"
        assert "24" in result.title.lower() or "hour" in result.title.lower()

    def test_generate_hold_alert_none_pending(self):
        """Test no hold alert when no holds pending"""
        from backend.calculations.alerts import generate_hold_alert

        result = generate_hold_alert(
            pending_holds_count=0
        )

        assert result is None


class TestPredictionBasedAlerts:
    """Test suite for prediction-based alerts"""

    def test_generate_prediction_based_alert_insufficient_data(self):
        """Test prediction alert with insufficient historical data"""
        from backend.calculations.alerts import generate_prediction_based_alert

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=[Decimal("85"), Decimal("84")],  # Only 2 values
            target=Decimal("85")
        )

        assert result is None  # Need at least 5 values

    def test_generate_prediction_based_alert_stable(self):
        """Test prediction alert with stable values"""
        from backend.calculations.alerts import generate_prediction_based_alert

        # Stable historical values
        historical = [Decimal("85")] * 10

        result = generate_prediction_based_alert(
            kpi_key="efficiency",
            historical_values=historical,
            target=Decimal("80"),
            warning_threshold=Decimal("75"),
            critical_threshold=Decimal("70"),
            higher_is_better=True
        )

        # Should be None since stable and above thresholds
        assert result is None


class TestAlertSchemas:
    """Test suite for alert Pydantic schemas"""

    def test_alert_create_schema(self):
        """Test AlertCreate schema validation"""
        from backend.schemas.alert import AlertCreate, AlertCategory, AlertSeverity

        alert = AlertCreate(
            category=AlertCategory.OTD,
            severity=AlertSeverity.CRITICAL,
            title="Test Alert",
            message="This is a test alert message",
            recommendation="Take action",
            client_id="CLIENT-001",
            kpi_key="otd",
            current_value=Decimal("75"),
            threshold_value=Decimal("95")
        )

        assert alert.category == AlertCategory.OTD
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.title == "Test Alert"

    def test_alert_summary_schema(self):
        """Test AlertSummary schema"""
        from backend.schemas.alert import AlertSummary

        summary = AlertSummary(
            total_active=10,
            by_severity={"critical": 3, "warning": 5, "info": 2},
            by_category={"otd": 4, "quality": 6},
            critical_count=3,
            urgent_count=0
        )

        assert summary.total_active == 10
        assert summary.critical_count == 3
        assert summary.by_severity["warning"] == 5

    def test_alert_filter_schema(self):
        """Test AlertFilter schema"""
        from backend.schemas.alert import AlertFilter, AlertCategory, AlertSeverity, AlertStatus

        filter_params = AlertFilter(
            client_id="CLIENT-001",
            category=AlertCategory.QUALITY,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE
        )

        assert filter_params.category == AlertCategory.QUALITY
        assert filter_params.status == AlertStatus.ACTIVE

    def test_alert_status_enum(self):
        """Test AlertStatus enum values"""
        from backend.schemas.alert import AlertStatus

        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.DISMISSED.value == "dismissed"

    def test_alert_category_enum(self):
        """Test AlertCategory enum values"""
        from backend.schemas.alert import AlertCategory

        assert AlertCategory.OTD.value == "otd"
        assert AlertCategory.QUALITY.value == "quality"
        assert AlertCategory.EFFICIENCY.value == "efficiency"
        assert AlertCategory.CAPACITY.value == "capacity"

    def test_alert_severity_enum(self):
        """Test AlertSeverity enum values"""
        from backend.schemas.alert import AlertSeverity

        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.URGENT.value == "urgent"


class TestAlertModels:
    """Test suite for alert SQLAlchemy models"""

    def test_alert_model_creation(self):
        """Test Alert model can be instantiated"""
        from backend.models.alert import Alert

        alert = Alert(
            alert_id="ALT-20260126-TEST001",
            category="otd",
            severity="critical",
            status="active",
            title="Test Alert",
            message="Test message",
            client_id="CLIENT-001"
        )

        assert alert.alert_id == "ALT-20260126-TEST001"
        assert alert.category == "otd"
        assert alert.status == "active"

    def test_alert_config_model_creation(self):
        """Test AlertConfig model can be instantiated"""
        from backend.models.alert import AlertConfig

        config = AlertConfig(
            config_id="ACF-TEST001",
            alert_type="otd",
            enabled=True,
            warning_threshold=80.0,
            critical_threshold=70.0,
            notification_email=True,
            check_frequency_minutes=30
        )

        assert config.config_id == "ACF-TEST001"
        assert config.enabled is True
        assert config.check_frequency_minutes == 30

    def test_alert_history_model_creation(self):
        """Test AlertHistory model can be instantiated"""
        from backend.models.alert import AlertHistory
        from datetime import datetime

        history = AlertHistory(
            history_id="AHT-TEST001",
            alert_id="ALT-TEST001",
            predicted_value=85.0,
            actual_value=82.0,
            prediction_date=datetime.now()
        )

        assert history.history_id == "AHT-TEST001"
        assert history.predicted_value == 85.0

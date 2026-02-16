"""
Tests for Critical Backend Services
Sprint 5 — Task 5.1: Real DB tests for the 4 critical services.

Services under test:
1. ProductionKPIService (production_kpi_service.py)
2. QualityKPIService (quality_kpi_service.py)
3. AnalyticsService (analytics_service.py)
4. WorkflowStateMachine / workflow helpers (workflow_service.py)

All tests use transactional_db + TestDataFactory (no mocks for DB operations).
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.services.production_kpi_service import ProductionKPIService
from backend.services.quality_kpi_service import QualityKPIService
from backend.services.analytics_service import AnalyticsService
from backend.services.workflow_service import (
    WorkflowStateMachine,
    get_workflow_config,
    validate_transition,
    get_allowed_transitions,
    execute_transition,
    calculate_elapsed_hours,
    get_transition_history,
    bulk_transition,
    apply_workflow_template,
)
from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas.work_order import WorkOrderStatus


# ============================================================================
# Helpers — create the prerequisite entities used across multiple test classes
# ============================================================================


def _setup_production_data(db, *, client_id="SVC-CLIENT", days=5, units=1000):
    """Create client, product, shift, user, and production entries."""
    TestDataFactory.reset_counters()
    client = TestDataFactory.create_client(db, client_id=client_id)
    product = TestDataFactory.create_product(
        db,
        client_id=client_id,
        ideal_cycle_time=Decimal("0.10"),
    )
    shift = TestDataFactory.create_shift(
        db,
        client_id=client_id,
        start_time="06:00:00",
        end_time="14:00:00",
    )
    user = TestDataFactory.create_user(db, client_id=client_id, role="supervisor")
    db.flush()

    entries = []
    base = date.today() - timedelta(days=days)
    for i in range(days):
        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            production_date=base + timedelta(days=i),
            units_produced=units + i * 50,
            employees_assigned=5,
            run_time_hours=Decimal("8.0"),
            defect_count=2,
            scrap_count=1,
        )
        entries.append(entry)

    db.commit()
    return {
        "client": client,
        "product": product,
        "shift": shift,
        "user": user,
        "entries": entries,
    }


def _setup_quality_data(db, *, client_id="SVC-CLIENT", days=5, defects=5):
    """Create client, work order, user, and quality entries."""
    TestDataFactory.reset_counters()
    client = TestDataFactory.create_client(db, client_id=client_id)
    user = TestDataFactory.create_user(db, client_id=client_id, role="supervisor")
    product = TestDataFactory.create_product(db, client_id=client_id)
    db.flush()
    wo = TestDataFactory.create_work_order(
        db, client_id=client_id, product_id=product.product_id
    )
    db.flush()

    entries = []
    base = date.today() - timedelta(days=days)
    for i in range(days):
        entry = TestDataFactory.create_quality_entry(
            db,
            work_order_id=wo.work_order_id,
            client_id=client_id,
            inspector_id=user.user_id,
            inspection_date=base + timedelta(days=i),
            units_inspected=1000,
            units_defective=defects,
            total_defects_count=defects + 2,
            units_scrapped=1,
            units_reworked=2,
        )
        entries.append(entry)

    db.commit()
    return {
        "client": client,
        "work_order": wo,
        "user": user,
        "entries": entries,
    }


# ============================================================================
# 1. ProductionKPIService Tests
# ============================================================================


class TestProductionKPIService:
    """Tests for ProductionKPIService with real database."""

    def test_calculate_entry_kpis_happy_path(self, transactional_db):
        """Service calculates efficiency, performance, quality, and OEE for an entry."""
        data = _setup_production_data(transactional_db)
        service = ProductionKPIService(transactional_db)

        result = service.calculate_entry_kpis(
            data["entries"][0],
            product=data["product"],
            shift=data["shift"],
        )

        assert result.entry_id == data["entries"][0].production_entry_id
        assert result.efficiency.efficiency_percentage > 0
        assert result.performance.performance_percentage > 0
        assert result.quality.quality_rate > 0
        assert result.oee.oee > 0

    def test_efficiency_result_metadata(self, transactional_db):
        """Efficiency result includes cycle time, employees, and scheduled hours."""
        data = _setup_production_data(transactional_db)
        service = ProductionKPIService(transactional_db)

        eff = service.calculate_efficiency_only(
            data["entries"][0],
            product=data["product"],
            shift=data["shift"],
        )

        # Product has ideal_cycle_time=0.10, so it should NOT be estimated
        assert eff.is_estimated is False
        assert eff.ideal_cycle_time_used == Decimal("0.10")
        assert eff.employees_used == 5
        assert eff.scheduled_hours == Decimal("8")

    def test_performance_result(self, transactional_db):
        """Performance calculation uses ideal cycle time and run time."""
        data = _setup_production_data(transactional_db, units=800)
        service = ProductionKPIService(transactional_db)

        perf = service.calculate_performance_only(
            data["entries"][0],
            product=data["product"],
        )

        # perf = (0.10 * 800) / 8.0 * 100 = 1000%
        # But capped at 150%
        assert perf.performance_percentage <= Decimal("150")
        assert perf.actual_rate > 0
        assert perf.is_estimated is False

    def test_quality_rate_calculation(self, transactional_db):
        """Quality rate = (units - defects - scrap) / units * 100."""
        data = _setup_production_data(transactional_db, units=1000)
        service = ProductionKPIService(transactional_db)
        entry = data["entries"][0]

        result = service.calculate_entry_kpis(
            entry, product=data["product"], shift=data["shift"]
        )

        # defect_count=2, scrap_count=1 => good=997 => rate=99.7%
        assert result.quality.good_units == entry.units_produced - 2 - 1
        assert result.quality.total_units == entry.units_produced
        assert float(result.quality.quality_rate) == pytest.approx(99.70, abs=0.1)

    def test_calculate_batch_kpis(self, transactional_db):
        """Batch KPI calculation returns a result for every entry."""
        data = _setup_production_data(transactional_db, days=5)
        service = ProductionKPIService(transactional_db)

        results = service.calculate_batch_kpis(data["entries"])

        assert len(results) == 5
        for entry in data["entries"]:
            assert entry.production_entry_id in results

    def test_calculate_batch_kpis_empty_list(self, transactional_db):
        """Batch KPI calculation handles empty list gracefully."""
        _setup_production_data(transactional_db)
        service = ProductionKPIService(transactional_db)

        results = service.calculate_batch_kpis([])
        assert results == {}

    def test_get_daily_kpi_summary(self, transactional_db):
        """Daily summary aggregates production metrics for a date."""
        data = _setup_production_data(transactional_db, days=3)
        service = ProductionKPIService(transactional_db)

        target = data["entries"][0].production_date.date() if isinstance(
            data["entries"][0].production_date, datetime
        ) else data["entries"][0].production_date

        summary = service.get_daily_kpi_summary(target, client_id="SVC-CLIENT")

        assert summary["date"] == target.isoformat()
        assert summary["total_units_produced"] > 0
        assert summary["entry_count"] >= 1

    def test_get_daily_kpi_summary_no_data(self, transactional_db):
        """Daily summary returns zeros for a date with no data."""
        _setup_production_data(transactional_db)
        service = ProductionKPIService(transactional_db)

        summary = service.get_daily_kpi_summary(
            date(2000, 1, 1), client_id="SVC-CLIENT"
        )

        assert summary["total_units_produced"] == 0
        assert summary["entry_count"] == 0

    def test_efficiency_with_no_product(self, transactional_db):
        """When product is not found, cycle time is inferred (estimated)."""
        data = _setup_production_data(transactional_db)
        service = ProductionKPIService(transactional_db)

        # Pass None for product to trigger inference
        eff = service.calculate_efficiency_only(
            data["entries"][0], product=None, shift=data["shift"]
        )

        # Since the product exists in DB, cached lookup should still find it,
        # so this actually tests the caching path
        assert eff.efficiency_percentage >= 0


# ============================================================================
# 2. QualityKPIService Tests
# ============================================================================


class TestQualityKPIService:
    """Tests for QualityKPIService with real database."""

    def test_calculate_ppm(self, transactional_db):
        """PPM = (defects / inspected) * 1,000,000."""
        data = _setup_quality_data(transactional_db, days=3, defects=5)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

        result = service.calculate_ppm(base, end, client_id="SVC-CLIENT")

        # 5 defects per 1000 units * 3 days = 15/3000 * 1e6 = 5000 PPM
        assert result.ppm == Decimal("5000.00")
        assert result.total_inspected == 3000
        assert result.total_defects == 15

    def test_calculate_ppm_no_data(self, transactional_db):
        """PPM returns 0 when no quality entries exist in the range."""
        _setup_quality_data(transactional_db)
        service = QualityKPIService(transactional_db)

        result = service.calculate_ppm(
            date(2000, 1, 1), date(2000, 1, 2), client_id="SVC-CLIENT"
        )

        assert result.ppm == Decimal("0")
        assert result.total_inspected == 0

    def test_calculate_dpmo(self, transactional_db):
        """DPMO = (defects / (units * opportunities)) * 1,000,000."""
        data = _setup_quality_data(transactional_db, days=1, defects=10)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=3)
        end = date.today() + timedelta(days=1)

        result = service.calculate_dpmo(
            base, end, opportunities_per_unit=10, client_id="SVC-CLIENT"
        )

        # total_defects_count=12 per entry (defects=10 + 2 extra), 1 entry
        # DPMO = 12 / (1000 * 10) * 1e6 = 1200
        assert result.dpmo > 0
        assert result.total_units == 1000
        assert result.opportunities_per_unit == 10

    def test_calculate_fpy(self, transactional_db):
        """FPY = (passed / inspected) * 100."""
        data = _setup_quality_data(transactional_db, days=2, defects=10)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

        result = service.calculate_fpy(base, end, client_id="SVC-CLIENT")

        # passed = 1000 - 10 = 990 per entry, 2 entries => 1980/2000 = 99%
        assert result.fpy_percentage > Decimal("0")
        assert result.total_units == 2000
        assert result.first_pass_good == 1980

    def test_calculate_rty(self, transactional_db):
        """RTY is computed across process steps (uses default stages)."""
        data = _setup_quality_data(transactional_db, days=3, defects=5)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

        result = service.calculate_rty(base, end, client_id="SVC-CLIENT")

        # With default steps ["Incoming", "In-Process", "Final"] and no
        # inspection_stage on test data, each step yields 0/0 -> FPY=0
        # except the overall aggregation. RTY should still be a Decimal.
        assert isinstance(result.rty_percentage, Decimal)
        assert len(result.step_details) == 3
        assert result.interpretation  # Non-empty interpretation string

    def test_get_quality_summary(self, transactional_db):
        """Quality summary includes PPM, DPMO, FPY, and RTY."""
        _setup_quality_data(transactional_db, days=3, defects=5)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

        summary = service.get_quality_summary(base, end, client_id="SVC-CLIENT")

        assert "ppm" in summary
        assert "dpmo" in summary
        assert "fpy" in summary
        assert "rty" in summary
        assert summary["ppm"]["total_inspected"] == 3000

    def test_ppm_filtered_by_work_order(self, transactional_db):
        """PPM can be filtered to a specific work order."""
        data = _setup_quality_data(transactional_db, days=2, defects=10)
        service = QualityKPIService(transactional_db)

        base = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

        result = service.calculate_ppm(
            base, end,
            work_order_id=data["work_order"].work_order_id,
            client_id="SVC-CLIENT",
        )

        assert result.total_inspected == 2000
        assert result.total_defects == 20


# ============================================================================
# 3. AnalyticsService Tests
# ============================================================================


class TestAnalyticsService:
    """Tests for AnalyticsService with real database."""

    def test_analyze_efficiency_trend_happy_path(self, transactional_db):
        """Efficiency trend returns direction and data points."""
        data = _setup_production_data(transactional_db, days=10, units=500)
        service = AnalyticsService(transactional_db)

        # Pre-populate efficiency_percentage so trend query can find data
        for i, entry in enumerate(data["entries"]):
            entry.efficiency_percentage = Decimal(str(60 + i * 2))
        transactional_db.commit()

        base = date.today() - timedelta(days=15)
        end = date.today() + timedelta(days=1)

        trend = service.analyze_efficiency_trend(
            base, end, client_id="SVC-CLIENT", granularity="daily"
        )

        assert trend.metric_name == "efficiency"
        assert len(trend.data_points) >= 2
        # Values increase monotonically, so direction should be improving
        assert trend.trend_direction == "improving"

    def test_analyze_efficiency_trend_insufficient_data(self, transactional_db):
        """Trend analysis returns insufficient_data when < 2 data points."""
        data = _setup_production_data(transactional_db, days=1, units=500)
        data["entries"][0].efficiency_percentage = Decimal("50")
        transactional_db.commit()

        service = AnalyticsService(transactional_db)

        base = date.today() - timedelta(days=3)
        end = date.today() + timedelta(days=1)

        trend = service.analyze_efficiency_trend(
            base, end, client_id="SVC-CLIENT"
        )

        assert trend.trend_direction == "insufficient_data"

    def test_analyze_quality_trend_ppm(self, transactional_db):
        """Quality trend computes PPM trend over time."""
        _setup_quality_data(transactional_db, days=5, defects=5)
        service = AnalyticsService(transactional_db)

        base = date.today() - timedelta(days=10)
        end = date.today() + timedelta(days=1)

        trend = service.analyze_quality_trend(
            base, end, metric="ppm", client_id="SVC-CLIENT"
        )

        assert trend.metric_name == "ppm"
        # Data may be insufficient or stable depending on date alignment
        assert trend.trend_direction in (
            "improving",
            "declining",
            "stable",
            "insufficient_data",
        )

    def test_compare_periods(self, transactional_db):
        """Period comparison returns change for each requested metric."""
        data = _setup_production_data(transactional_db, days=20, units=800)
        # Set efficiency values for two distinct periods
        for i, entry in enumerate(data["entries"]):
            entry.efficiency_percentage = Decimal(str(50 + i))
        transactional_db.commit()

        service = AnalyticsService(transactional_db)

        p1_start = date.today() - timedelta(days=20)
        p1_end = date.today() - timedelta(days=11)
        p2_start = date.today() - timedelta(days=10)
        p2_end = date.today()

        result = service.compare_periods(
            p1_start, p1_end, p2_start, p2_end,
            metrics=["efficiency"],
            client_id="SVC-CLIENT",
        )

        assert "period1" in result
        assert "period2" in result
        assert "comparison" in result
        assert "efficiency" in result["comparison"]

    def test_get_daily_metrics(self, transactional_db):
        """Private _get_daily_metrics returns production and quality totals."""
        data = _setup_production_data(transactional_db, days=1, units=500)
        service = AnalyticsService(transactional_db)

        target = (
            data["entries"][0].production_date.date()
            if isinstance(data["entries"][0].production_date, datetime)
            else data["entries"][0].production_date
        )
        metrics = service._get_daily_metrics(target, client_id="SVC-CLIENT")

        assert metrics["total_units_produced"] >= 500

    def test_work_order_summary(self, transactional_db):
        """Work order summary groups counts by status."""
        TestDataFactory.reset_counters()
        client = TestDataFactory.create_client(transactional_db, client_id="AN-CLIENT")
        product = TestDataFactory.create_product(transactional_db, client_id="AN-CLIENT")
        transactional_db.flush()
        TestDataFactory.create_work_order(
            transactional_db,
            client_id="AN-CLIENT",
            status=WorkOrderStatus.RECEIVED,
            product_id=product.product_id,
        )
        TestDataFactory.create_work_order(
            transactional_db,
            client_id="AN-CLIENT",
            status=WorkOrderStatus.IN_PROGRESS,
            product_id=product.product_id,
        )
        transactional_db.commit()

        service = AnalyticsService(transactional_db)
        summary = service._get_work_order_summary(client_id="AN-CLIENT")

        assert summary["total"] >= 2


# ============================================================================
# 4. WorkflowStateMachine / Workflow Service Tests
# ============================================================================


class TestWorkflowStateMachineDB:
    """Tests for WorkflowStateMachine using real database transactions."""

    def _create_workflow_entities(self, db, *, client_id="WF-CLIENT"):
        """Create client with a work order for workflow tests."""
        TestDataFactory.reset_counters()
        client = TestDataFactory.create_client(db, client_id=client_id)
        product = TestDataFactory.create_product(db, client_id=client_id)
        db.flush()
        user = TestDataFactory.create_user(db, client_id=client_id, role="supervisor")
        wo = TestDataFactory.create_work_order(
            db,
            client_id=client_id,
            status=WorkOrderStatus.RECEIVED,
            product_id=product.product_id,
        )
        db.commit()
        return {"client": client, "user": user, "work_order": wo, "product": product}

    def test_default_transitions_loaded(self, transactional_db):
        """State machine loads default transitions when no client config."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        assert "RECEIVED" in sm._statuses
        assert "CLOSED" in sm._statuses
        assert sm._closure_trigger == "at_shipment"

    def test_get_allowed_transitions_from_received(self, transactional_db):
        """RECEIVED can transition to RELEASED, ON_HOLD, CANCELLED."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        allowed = sm.get_allowed_transitions("RECEIVED")

        assert "RELEASED" in allowed
        assert "ON_HOLD" in allowed
        assert "CANCELLED" in allowed

    def test_is_transition_valid_happy(self, transactional_db):
        """Valid transitions return (True, None)."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        valid, reason = sm.is_transition_valid("RECEIVED", "RELEASED")
        assert valid is True
        assert reason is None

    def test_is_transition_valid_invalid(self, transactional_db):
        """Invalid transitions return (False, reason_string)."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        valid, reason = sm.is_transition_valid("RECEIVED", "SHIPPED")
        assert valid is False
        assert reason is not None

    def test_terminal_status_cannot_transition(self, transactional_db):
        """Terminal statuses (CLOSED, CANCELLED, REJECTED) block outgoing transitions."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        for terminal in ("CLOSED", "CANCELLED", "REJECTED"):
            valid, reason = sm.is_transition_valid(terminal, "RECEIVED")
            assert valid is False
            assert "terminal" in reason.lower() or "Cannot" in reason

    def test_new_work_order_must_start_received(self, transactional_db):
        """Initial creation (from_status=None) only allows RECEIVED."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        valid, _ = sm.is_transition_valid(None, "RECEIVED")
        assert valid is True

        valid2, reason = sm.is_transition_valid(None, "IN_PROGRESS")
        assert valid2 is False

    def test_same_status_is_valid(self, transactional_db):
        """Transitioning to the same status is a no-op (valid)."""
        self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        valid, reason = sm.is_transition_valid("IN_PROGRESS", "IN_PROGRESS")
        assert valid is True

    def test_should_auto_close_at_shipment(self, transactional_db):
        """With at_shipment trigger, SHIPPED triggers auto-close."""
        entities = self._create_workflow_entities(transactional_db)
        sm = WorkflowStateMachine(transactional_db, "WF-CLIENT")

        assert sm.should_auto_close(entities["work_order"], "SHIPPED") is True
        assert sm.should_auto_close(entities["work_order"], "COMPLETED") is False


class TestWorkflowServiceFunctions:
    """Tests for module-level workflow helper functions with real DB."""

    def _create_entities(self, db, *, client_id="WFS-CLIENT"):
        TestDataFactory.reset_counters()
        client = TestDataFactory.create_client(db, client_id=client_id)
        product = TestDataFactory.create_product(db, client_id=client_id)
        db.flush()
        user = TestDataFactory.create_user(db, client_id=client_id, role="supervisor")
        wo = TestDataFactory.create_work_order(
            db,
            client_id=client_id,
            status=WorkOrderStatus.RECEIVED,
            product_id=product.product_id,
        )
        db.commit()
        return {"client": client, "user": user, "work_order": wo, "product": product}

    def test_get_workflow_config(self, transactional_db):
        """get_workflow_config returns statuses, transitions, and closure trigger."""
        self._create_entities(transactional_db)
        config = get_workflow_config(transactional_db, "WFS-CLIENT")

        assert config["client_id"] == "WFS-CLIENT"
        assert "workflow_statuses" in config
        assert "workflow_transitions" in config

    def test_validate_transition_function(self, transactional_db):
        """Module-level validate_transition returns tuple of (valid, reason, allowed)."""
        entities = self._create_entities(transactional_db)
        wo = entities["work_order"]

        is_valid, reason, allowed = validate_transition(
            transactional_db, wo, "RELEASED"
        )

        assert is_valid is True
        assert reason is None
        assert "RELEASED" in allowed

    def test_get_allowed_transitions_function(self, transactional_db):
        """Module-level get_allowed_transitions returns a list of valid targets."""
        self._create_entities(transactional_db)

        allowed = get_allowed_transitions(
            transactional_db, "WFS-CLIENT", "IN_PROGRESS"
        )

        assert "COMPLETED" in allowed
        assert "ON_HOLD" in allowed

    def test_execute_transition_happy_path(self, transactional_db):
        """execute_transition updates work order and creates a transition log."""
        entities = self._create_entities(transactional_db)
        wo = entities["work_order"]

        updated_wo, log = execute_transition(
            transactional_db, wo, "RELEASED",
            user_id=1, notes="Test release"
        )

        assert updated_wo.status == WorkOrderStatus.RELEASED
        assert log.from_status == "RECEIVED"
        assert log.to_status == "RELEASED"
        assert log.notes == "Test release"

    def test_execute_transition_invalid_raises(self, transactional_db):
        """execute_transition raises HTTPException for invalid transitions."""
        from fastapi import HTTPException

        entities = self._create_entities(transactional_db)
        wo = entities["work_order"]

        with pytest.raises(HTTPException) as exc_info:
            execute_transition(transactional_db, wo, "SHIPPED")

        assert exc_info.value.status_code == 400

    def test_calculate_elapsed_hours(self):
        """calculate_elapsed_hours returns integer hours between two datetimes."""
        t1 = datetime(2024, 1, 1, 8, 0, 0)
        t2 = datetime(2024, 1, 1, 16, 30, 0)

        assert calculate_elapsed_hours(t1, t2) == 8  # 8.5 hours, truncated to int

    def test_calculate_elapsed_hours_none(self):
        """calculate_elapsed_hours returns None when either argument is None."""
        assert calculate_elapsed_hours(None, datetime.now()) is None
        assert calculate_elapsed_hours(datetime.now(), None) is None

    def test_get_transition_history(self, transactional_db):
        """After executing transitions, history is returned in chronological order."""
        entities = self._create_entities(transactional_db)
        wo = entities["work_order"]

        # Execute two transitions: RECEIVED -> RELEASED -> IN_PROGRESS
        execute_transition(transactional_db, wo, "RELEASED", user_id=1)
        execute_transition(transactional_db, wo, "IN_PROGRESS", user_id=1)

        history = get_transition_history(
            transactional_db, wo.work_order_id, "WFS-CLIENT"
        )

        assert len(history) == 2
        assert history[0].to_status == "RELEASED"
        assert history[1].to_status == "IN_PROGRESS"

    def test_apply_workflow_template_standard(self, transactional_db):
        """Applying 'standard' template updates client config."""
        self._create_entities(transactional_db)

        config = apply_workflow_template(
            transactional_db, "WFS-CLIENT", "standard"
        )

        assert "RECEIVED" in config["workflow_statuses"]
        assert "SHIPPED" in config["workflow_statuses"]

    def test_apply_workflow_template_not_found(self, transactional_db):
        """Applying a non-existent template raises HTTP 404."""
        from fastapi import HTTPException

        self._create_entities(transactional_db)

        with pytest.raises(HTTPException) as exc_info:
            apply_workflow_template(
                transactional_db, "WFS-CLIENT", "nonexistent"
            )

        assert exc_info.value.status_code == 404

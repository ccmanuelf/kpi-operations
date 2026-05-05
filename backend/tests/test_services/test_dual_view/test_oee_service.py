"""
OEECalculationService — Phase 3 dual-view tests.

Spec § Phase 3 Tests required: for each of 3 metrics (OEE here), verify:
  - Standard mode produces the textbook result
  - Site-adjusted mode produces a different result when assumptions differ from
    defaults
  - Site-adjusted mode equals standard mode when no site-specific assumptions
    are configured
  - The assumptions snapshot stored in metric_calculation_results matches what
    was used at calculation time

Real DB via transactional_db; no mocks.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.services.assumption_service import AssumptionService
from backend.services.dual_view.oee_service import OEECalculationService, OEERawInputs
from backend.tests.fixtures.factories import TestDataFactory


PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_users(db):
    client = TestDataFactory.create_client(db, client_id="DV-OEE-CLIENT")
    admin = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(db, role="poweruser", client_id=client.client_id)
    db.commit()
    return client, admin, poweruser


def _baseline_inputs() -> OEERawInputs:
    """Realistic inputs: 90% availability, 95% performance, ~94% quality → ~80% OEE."""
    return OEERawInputs(
        scheduled_hours=Decimal("80"),
        downtime_hours=Decimal("8"),  # 72/80 = 90% availability
        setup_minutes=Decimal("60"),  # 1 hour
        scheduled_maintenance_hours=Decimal("4"),
        units_produced=900,
        run_time_hours=Decimal("72"),
        ideal_cycle_time_hours=Decimal("0.076"),  # ~95% performance
        rolling_90_day_cycle_time_hours=Decimal("0.080"),  # would yield ~100% perf
        demonstrated_best_cycle_time_hours=Decimal("0.072"),  # would yield ~90% perf
        defect_count=30,
        scrap_count=20,  # (900-30-20)/900 = 94.44% quality
        units_reworked=15,
    )


def _approve(db, poweruser, admin, client_id, name, value):
    record = AssumptionService(db, poweruser).propose(client_id=client_id, assumption_name=name, value=value)
    AssumptionService(db, admin).approve(record.assumption_id)
    return record


class TestStandardMode:
    def test_textbook_result(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # Availability: (80-8)/80 = 90%
        # Performance: (0.076 × 900) / 72 × 100 = 95%
        # Quality: (900-30-20)/900 = 94.44%
        # OEE: 0.90 × 0.95 × 0.9444 × 100 ≈ 80.74%
        assert Decimal("80") < result.standard_value < Decimal("82")


class TestSiteAdjustedEqualsStandardWhenNoAssumptions:
    def test_no_active_assumptions_means_no_divergence(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        assert result.standard_value == result.site_adjusted_value
        assert result.delta == 0
        assert result.assumptions_applied == []
        assert result.assumptions_snapshot == {}


class TestSiteAdjustedDivergesWithAssumptions:
    def test_setup_treatment_changes_availability(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(transactional_db, poweruser, admin, client.client_id, "setup_treatment", "exclude_from_availability")

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # Standard: scheduled=80, downtime=8 → 90% availability
        # Adjusted: scheduled=79 (80 - 1h setup), downtime=7 (8 - 1h setup)
        #         → 72/79 = 91.14% availability → higher OEE
        assert result.site_adjusted_value > result.standard_value
        assert any(a.name == "setup_treatment" for a in result.assumptions_applied)

    def test_scrap_rework_counted_as_good_raises_quality(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db, poweruser, admin, client.client_id, "scrap_classification_rule", "rework_counted_as_good"
        )

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # Standard quality: (900-30-20)/900 = 94.44%
        # Adjusted: defect_count = max(0, 30-15) = 15 → (900-15-20)/900 = 96.11%
        # Higher quality → higher OEE
        assert result.site_adjusted_value > result.standard_value

    def test_ideal_cycle_time_source_rolling(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db, poweruser, admin, client.client_id, "ideal_cycle_time_source", "rolling_90_day_average"
        )

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # Standard performance: (0.076 × 900) / 72 × 100 = 95%
        # Adjusted: cycle_time bumped to 0.080 → (0.080 × 900) / 72 × 100 = 100%
        # Higher performance → higher OEE
        assert result.site_adjusted_value > result.standard_value

    def test_planned_production_time_basis_excludes_maintenance(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db,
            poweruser,
            admin,
            client.client_id,
            "planned_production_time_basis",
            "exclude_scheduled_maintenance",
        )

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # scheduled_hours: 80 → 76 (subtract 4 maintenance hours)
        # availability: 72/76 = 94.74% (vs 90% standard) → higher OEE
        assert result.site_adjusted_value > result.standard_value


class TestSnapshotPersistence:
    def test_snapshot_matches_active_assumptions(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        approved = _approve(
            transactional_db,
            poweruser,
            admin,
            client.client_id,
            "scrap_classification_rule",
            "rework_counted_as_bad",
        )

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=True,
        )

        assert result.result_id is not None

        # Re-fetch from DB and verify the persisted row matches.
        row = (
            transactional_db.query(MetricCalculationResult)
            .filter(MetricCalculationResult.result_id == result.result_id)
            .first()
        )
        assert row is not None
        assert row.metric_name == "oee"
        assert row.client_id == client.client_id

        snapshot = json.loads(row.assumptions_snapshot)
        assert "scrap_classification_rule" in snapshot
        assert snapshot["scrap_classification_rule"]["value"] == "rework_counted_as_bad"
        assert snapshot["scrap_classification_rule"]["assumption_id"] == approved.assumption_id
        assert snapshot["scrap_classification_rule"]["approved_by"] == admin.user_id

    def test_snapshot_empty_when_no_assumptions(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=True,
        )
        row = (
            transactional_db.query(MetricCalculationResult)
            .filter(MetricCalculationResult.result_id == result.result_id)
            .first()
        )
        assert json.loads(row.assumptions_snapshot) == {}
        assert json.loads(row.standard_value_json) == json.loads(row.site_adjusted_value_json)

    def test_delta_columns_populated(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db, poweruser, admin, client.client_id, "scrap_classification_rule", "rework_counted_as_good"
        )

        svc = OEECalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=True,
        )
        row = (
            transactional_db.query(MetricCalculationResult)
            .filter(MetricCalculationResult.result_id == result.result_id)
            .first()
        )
        assert row.delta is not None
        assert row.delta > 0  # site_adjusted > standard for this assumption
        assert row.delta_pct is not None

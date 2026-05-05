"""FPYCalculationService — Phase 3 dual-view tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.services.assumption_service import AssumptionService
from backend.services.dual_view.fpy_service import FPYCalculationService, FPYRawInputs
from backend.tests.fixtures.factories import TestDataFactory


PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_users(db):
    client = TestDataFactory.create_client(db, client_id="DV-FPY-CLIENT")
    admin = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(db, role="poweruser", client_id=client.client_id)
    db.commit()
    return client, admin, poweruser


def _baseline_inputs() -> FPYRawInputs:
    # 100 inspected: 80 first-pass good, 10 reworked, 10 unrecovered defects/scrap
    return FPYRawInputs(total_inspected=100, units_passed_first_time=80, units_reworked=10)


def _approve(db, poweruser, admin, client_id, name, value):
    record = AssumptionService(db, poweruser).propose(client_id=client_id, assumption_name=name, value=value)
    AssumptionService(db, admin).approve(record.assumption_id)
    return record


class TestStandardFPY:
    def test_textbook_excludes_rework(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # 80 / 100 = 80%
        assert result.standard_value == Decimal("80.00")


class TestNoAssumptions:
    def test_site_adjusted_equals_standard(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        assert result.standard_value == result.site_adjusted_value
        assert result.assumptions_applied == []


class TestRuleDiverges:
    def test_rework_counted_as_good_raises_fpy(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db, poweruser, admin, client.client_id, "scrap_classification_rule", "rework_counted_as_good"
        )

        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # Standard 80 / 100 = 80%; adjusted (80+10) / 100 = 90%
        assert result.standard_value == Decimal("80.00")
        assert result.site_adjusted_value == Decimal("90.00")
        assert result.delta == 10.0

    def test_rework_counted_as_partial_half_credit(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db,
            poweruser,
            admin,
            client.client_id,
            "scrap_classification_rule",
            "rework_counted_as_partial",
        )

        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # (80 + 10/2) / 100 = 85%
        assert result.site_adjusted_value == Decimal("85.00")

    def test_rework_counted_as_bad_equals_standard(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(
            transactional_db, poweruser, admin, client.client_id, "scrap_classification_rule", "rework_counted_as_bad"
        )

        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        assert result.standard_value == result.site_adjusted_value


class TestSnapshotPersistence:
    def test_persisted_row_has_rule_snapshot(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        approved = _approve(
            transactional_db, poweruser, admin, client.client_id, "scrap_classification_rule", "rework_counted_as_good"
        )

        svc = FPYCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=True,
        )

        assert result.result_id is not None
        row = (
            transactional_db.query(MetricCalculationResult)
            .filter(MetricCalculationResult.result_id == result.result_id)
            .first()
        )
        assert row.metric_name == "fpy"
        snapshot = json.loads(row.assumptions_snapshot)
        assert snapshot["scrap_classification_rule"]["value"] == "rework_counted_as_good"
        assert snapshot["scrap_classification_rule"]["assumption_id"] == approved.assumption_id

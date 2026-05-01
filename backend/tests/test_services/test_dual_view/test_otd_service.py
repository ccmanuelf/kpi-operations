"""OTDCalculationService — Phase 3 dual-view tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.services.assumption_service import AssumptionService
from backend.services.dual_view.otd_service import (
    OrderDelay,
    OTDCalculationService,
    OTDRawInputs,
)
from backend.tests.fixtures.factories import TestDataFactory


PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_users(db):
    client = TestDataFactory.create_client(db, client_id="DV-OTD-CLIENT")
    admin = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(db, role="poweruser", client_id=client.client_id)
    db.commit()
    return client, admin, poweruser


def _baseline_inputs() -> OTDRawInputs:
    """10 orders: 7 on-time/early, 2 late by 3% lead-time, 1 late by 10%."""
    delays = (
        [Decimal("0.0")] * 5
        + [Decimal("-0.05")] * 2  # 5% early
        + [Decimal("0.03")] * 2   # 3% late
        + [Decimal("0.10")] * 1   # 10% late
    )
    return OTDRawInputs(orders=[OrderDelay(delay_pct=d) for d in delays])


def _approve(db, poweruser, admin, client_id, name, value):
    record = AssumptionService(db, poweruser).propose(
        client_id=client_id, assumption_name=name, value=value
    )
    AssumptionService(db, admin).approve(record.assumption_id)
    return record


class TestStandardOTD:
    def test_textbook_only_counts_zero_or_negative_delays(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # 7 on-time-or-early out of 10 = 70%
        assert result.standard_value == Decimal("70.00")


class TestNoAssumptions:
    def test_site_adjusted_equals_standard(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        assert result.standard_value == result.site_adjusted_value
        assert result.assumptions_applied == []
        assert result.assumptions_snapshot == {}


class TestBufferDiverges:
    def test_5pct_buffer_includes_3pct_late_orders(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(transactional_db, poweruser, admin, client.client_id,
                 "otd_carrier_buffer_pct", 5)

        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # With 5% buffer, the 2 orders late by 3% become on-time → 9/10 = 90%
        assert result.standard_value == Decimal("70.00")
        assert result.site_adjusted_value == Decimal("90.00")
        assert result.delta == 20.0

    def test_15pct_buffer_includes_all_orders(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        _approve(transactional_db, poweruser, admin, client.client_id,
                 "otd_carrier_buffer_pct", 15)

        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=False,
        )
        # With 15% buffer, all 10 orders are on-time → 100%
        assert result.site_adjusted_value == Decimal("100.00")


class TestSnapshotPersistence:
    def test_persisted_row_has_buffer_snapshot(self, transactional_db):
        client, admin, poweruser = _make_users(transactional_db)
        approved = _approve(transactional_db, poweruser, admin, client.client_id,
                            "otd_carrier_buffer_pct", 5)

        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=_baseline_inputs(),
            persist=True,
        )

        assert result.result_id is not None
        row = transactional_db.query(MetricCalculationResult).filter(
            MetricCalculationResult.result_id == result.result_id
        ).first()
        assert row.metric_name == "otd"
        snapshot = json.loads(row.assumptions_snapshot)
        assert snapshot["otd_carrier_buffer_pct"]["value"] == 5
        assert snapshot["otd_carrier_buffer_pct"]["assumption_id"] == approved.assumption_id


class TestEmptyInputs:
    def test_no_orders_returns_zero(self, transactional_db):
        client, admin, _ = _make_users(transactional_db)
        svc = OTDCalculationService(transactional_db, admin)
        result = svc.calculate(
            client_id=client.client_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            raw_inputs=OTDRawInputs(orders=[]),
            persist=False,
        )
        assert result.standard_value == Decimal("0.00")

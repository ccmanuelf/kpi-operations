"""
F.4 — scheduled dual-view calculation runner.

Verifies the per-client orchestration: aggregator → service → persisted row,
for each of OEE/OTD/FPY. Doesn't exercise APScheduler itself (that's a
third-party concern); we call the public entrypoints directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.tasks.dual_view_calculation import (
    _previous_day_window,
    run_for_client,
    run_nightly_dual_view_calculations,
)
from backend.tests.fixtures.factories import TestDataFactory


def _seed_admin(db, client_id="DV-CRON-CLIENT"):
    client = TestDataFactory.create_client(db, client_id=client_id)
    admin = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    db.commit()
    return client, admin


class TestPreviousDayWindow:
    def test_previous_day_is_full_24h(self):
        now = datetime(2026, 5, 15, 12, 30, tzinfo=timezone.utc)
        start, end = _previous_day_window(now)
        assert start.date() == datetime(2026, 5, 14).date()
        assert start.hour == 0 and start.minute == 0
        assert end.date() == datetime(2026, 5, 14).date()
        assert end.hour == 23 and end.minute == 59


class TestRunForClient:
    def test_persists_three_rows_one_per_metric(self, transactional_db):
        client, admin = _seed_admin(transactional_db)
        period_start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc)

        results = run_for_client(
            db=transactional_db,
            client_id=client.client_id,
            period_start=period_start,
            period_end=period_end,
            user=admin,
        )
        assert set(results.keys()) == {"oee", "otd", "fpy"}
        assert all(rid is not None for rid in results.values())

        rows = (
            transactional_db.query(MetricCalculationResult)
            .filter(MetricCalculationResult.client_id == client.client_id)
            .all()
        )
        assert len(rows) == 3
        assert {r.metric_name for r in rows} == {"oee", "otd", "fpy"}


class TestRunNightly:
    def test_iterates_active_clients_only(self, transactional_db):
        active = TestDataFactory.create_client(transactional_db, client_id="ACTIVE-1")
        inactive = TestDataFactory.create_client(
            transactional_db, client_id="INACTIVE-1", is_active=False
        )
        TestDataFactory.create_user(transactional_db, role="admin", client_id=active.client_id)
        transactional_db.commit()

        # Patch SessionLocal so the runner uses our transactional_db.
        with patch("backend.tasks.dual_view_calculation.SessionLocal") as mock_session_local:
            mock_session_local.return_value = transactional_db
            # Prevent the runner from closing our shared session
            with patch.object(transactional_db, "close"):
                summary = run_nightly_dual_view_calculations()

        assert active.client_id in summary
        assert inactive.client_id not in summary
        # Each metric should have a result_id
        for metric in ("oee", "otd", "fpy"):
            assert summary[active.client_id][metric] is not None

    def test_raises_when_no_admin_user(self, transactional_db):
        TestDataFactory.create_client(transactional_db, client_id="NO-ADMIN-CLIENT")
        # Deliberately no admin user — only a leader.
        TestDataFactory.create_user(
            transactional_db, role="leader", client_id="NO-ADMIN-CLIENT"
        )
        transactional_db.commit()

        with patch("backend.tasks.dual_view_calculation.SessionLocal") as mock_session_local:
            mock_session_local.return_value = transactional_db
            with patch.object(transactional_db, "close"):
                try:
                    run_nightly_dual_view_calculations()
                except RuntimeError as exc:
                    assert "No admin user" in str(exc)
                else:
                    raise AssertionError("Expected RuntimeError when no admin exists")

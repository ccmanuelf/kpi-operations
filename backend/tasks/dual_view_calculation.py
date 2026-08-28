"""
Scheduled dual-view calculation runner — F.4.

Runs daily after production data is in for the previous calendar day.
For each active client × each of the 3 dual-view metrics (OEE, OTD, FPY):
  - Aggregates raw inputs from production data
  - Runs the dual-view service in both modes
  - Persists a `METRIC_CALCULATION_RESULT` row

The inspector UI can then load the most recent persisted row per
(client × metric × period) without triggering a fresh calculation.

Pattern matches `backend/tasks/daily_reports.py` (APScheduler + cron trigger).
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.orm.client import Client
from backend.orm.user import User
from backend.services.dual_view.aggregators import (
    aggregate_fpy_inputs,
    aggregate_oee_inputs,
    aggregate_otd_inputs,
)
from backend.services.dual_view.fpy_service import FPYCalculationService
from backend.services.dual_view.oee_service import OEECalculationService
from backend.services.dual_view.otd_service import OTDCalculationService

logger = logging.getLogger(__name__)


def _previous_day_window(now_utc: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) covering the previous calendar day in UTC."""

    now = now_utc or datetime.now(tz=timezone.utc)
    yesterday = (now - timedelta(days=1)).date()
    period_start = datetime.combine(yesterday, time.min, tzinfo=timezone.utc)
    period_end = datetime.combine(yesterday, time.max, tzinfo=timezone.utc)
    return period_start, period_end


def _system_user(db: Session) -> User:
    """
    Resolve a "system" user to attribute scheduled calculations to.

    Falls back to the first admin if no dedicated system user exists. The
    `calculated_by` field on METRIC_CALCULATION_RESULT is for auditability
    only — the scheduled run is read-only over the assumption registry.
    """

    admin = db.query(User).filter(User.role == "admin").order_by(User.user_id).first()
    if admin is None:
        raise RuntimeError("No admin user found to attribute scheduled dual-view runs to.")
    return admin


def run_for_client(
    db: Session,
    client_id: str,
    period_start: datetime,
    period_end: datetime,
    user: User,
) -> dict[str, int | None]:
    """
    Run all 3 dual-view calculations for one client × period. Returns a
    dict mapping metric_name → persisted result_id (or None on failure).
    """

    results: dict[str, int | None] = {"oee": None, "otd": None, "fpy": None}

    try:
        oee_inputs = aggregate_oee_inputs(db, client_id, period_start, period_end)
        oee_result = OEECalculationService(db, user).calculate(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            raw_inputs=oee_inputs,
            persist=True,
        )
        results["oee"] = oee_result.result_id
    except Exception as exc:
        logger.exception("Scheduled OEE failed for client=%s: %s", client_id, exc)

    try:
        otd_inputs = aggregate_otd_inputs(db, client_id, period_start, period_end)
        otd_result = OTDCalculationService(db, user).calculate(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            raw_inputs=otd_inputs,
            persist=True,
        )
        results["otd"] = otd_result.result_id
    except Exception as exc:
        logger.exception("Scheduled OTD failed for client=%s: %s", client_id, exc)

    try:
        fpy_inputs = aggregate_fpy_inputs(db, client_id, period_start, period_end)
        fpy_result = FPYCalculationService(db, user).calculate(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            raw_inputs=fpy_inputs,
            persist=True,
        )
        results["fpy"] = fpy_result.result_id
    except Exception as exc:
        logger.exception("Scheduled FPY failed for client=%s: %s", client_id, exc)

    return results


def run_nightly_dual_view_calculations(db: Optional[Session] = None) -> dict[str, dict[str, int | None]]:
    """
    Iterate all active clients and run all 3 dual-view metrics for the
    previous calendar day. Returns {client_id: {metric: result_id}}.

    Public entrypoint for both the scheduler and the manual-trigger route.

    `db`: an existing session to use, e.g. a request's injected `get_db`
    session. When provided, this function does NOT close it -- the caller
    that opened it owns its lifecycle. When omitted (the scheduler's cron
    path has no request-scoped session to reuse), opens its own
    `SessionLocal()` and closes it before returning.

    FIX: this function used to always open its own `SessionLocal()`
    regardless of caller context, so `POST /api/metrics/calculate/
    run-nightly` silently escaped the request's injected session and wrote
    to the AMBIENT database configured by `settings.DATABASE_URL` --
    including, under a test harness that overrides FastAPI's `get_db` to
    point at a disposable seeded DB, the real ambient database instead of
    that disposable one. Measured before this fix: running the contract
    suite against this repo's own dev DB left 12 new rows (4 active
    clients x 3 metrics) in the ambient METRIC_CALCULATION_RESULT table --
    exactly the outcome `tests/contract/conftest.py`'s "a seeded throwaway
    database ... never the VM, never a real client" promise rules out.
    """

    period_start, period_end = _previous_day_window()
    summary: dict[str, dict[str, int | None]] = {}

    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        user = _system_user(db)
        active_clients = db.query(Client).filter(Client.is_active == 1).all()
        logger.info(
            "Nightly dual-view: %d clients, period=[%s, %s]",
            len(active_clients),
            period_start,
            period_end,
        )

        for client in active_clients:
            summary[client.client_id] = run_for_client(
                db=db,
                client_id=client.client_id,
                period_start=period_start,
                period_end=period_end,
                user=user,
            )
    finally:
        if owns_session:
            db.close()

    logger.info("Nightly dual-view complete. Summary: %s", summary)
    return summary


class DualViewCalculationScheduler:
    """APScheduler wrapper. Mirrors backend/tasks/daily_reports.DailyReportScheduler."""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        # Cron: 02:00 UTC every day. Override via DUAL_VIEW_CRON_HOUR /
        # DUAL_VIEW_CRON_MINUTE settings if needed.
        self.cron_hour = getattr(settings, "DUAL_VIEW_CRON_HOUR", 2)
        self.cron_minute = getattr(settings, "DUAL_VIEW_CRON_MINUTE", 0)
        self.enabled = getattr(settings, "DUAL_VIEW_SCHEDULER_ENABLED", True)

    def start(self) -> None:
        if not self.enabled:
            logger.info("Dual-view scheduler disabled by config")
            return
        self.scheduler.add_job(
            func=run_nightly_dual_view_calculations,
            trigger=CronTrigger(hour=self.cron_hour, minute=self.cron_minute),
            id="nightly_dual_view_calculations",
            name="Nightly Dual-View Calculations",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(
            "Dual-view scheduler started (cron: %02d:%02d UTC)",
            self.cron_hour,
            self.cron_minute,
        )

    def stop(self) -> None:
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("Dual-view scheduler stopped")
        except Exception as exc:
            logger.warning("Dual-view scheduler stop failed: %s", exc)


# Module-level singleton, mirroring daily_reports.scheduler.
scheduler = DualViewCalculationScheduler()

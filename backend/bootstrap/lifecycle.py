"""Application lifecycle: startup/shutdown units + the FastAPI lifespan."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import FastAPI

from backend.database import engine
from backend.db.migrate import SchemaRebuildError
from backend.events import register_all_handlers, get_event_bus
from backend.orm.event_store import create_event_persistence_handler

logger = logging.getLogger(__name__)

# Optional scheduler import for lifecycle events. Typed as Optional[Any]
# because the apscheduler-backed scheduler is import-shielded — the
# type can't be resolved when apscheduler isn't installed (e.g. in
# slim test images), and the only call sites (`.start()` / `.stop()`)
# already guard with `if report_scheduler is not None`.
report_scheduler: Optional[Any] = None
try:
    from backend.tasks.daily_reports import scheduler as _imported_scheduler

    report_scheduler = _imported_scheduler
except ImportError:
    pass

# Dual-view nightly calculation scheduler (F.4). Same import-shield pattern
# so projects without apscheduler still boot.
dual_view_scheduler: Optional[Any] = None
try:
    from backend.tasks.dual_view_calculation import scheduler as _imported_dv_scheduler

    dual_view_scheduler = _imported_dv_scheduler
except ImportError:
    pass


def _auto_seed_demo_data() -> None:
    """
    Auto-seed demo data if the database is empty or incomplete (DEMO_MODE only).

    FORCE_RESEED=true: always drop and re-seed (one-time migration).
    Otherwise: smart detection — re-seed only if data is missing/stale.

    The re-seed path executes a destructive rebuild_schema(); the DEMO_MODE gate
    must stay the first statement so a non-demo deployment can never reach it
    (Run 7 C-1). Guarded by backend/tests/test_demo_seed_gate.py.
    """
    from backend.config import settings

    if not settings.DEMO_MODE:
        logger.info("DEMO_MODE disabled — skipping demo data auto-seed")
        return

    try:
        import os
        from backend.database import SessionLocal
        from backend.orm.client import Client

        EXPECTED_CLIENTS = {"ACME-MFG", "TEXTILE-PRO", "FASHION-WORKS", "QUALITY-STITCH", "GLOBAL-APPAREL"}
        force_reseed = os.environ.get("FORCE_RESEED", "").lower() in ("1", "true", "yes")

        db = SessionLocal()
        try:
            existing_clients = {c.client_id for c in db.query(Client.client_id).all()}
            client_count = len(existing_clients)
        finally:
            db.close()

        # Determine if re-seed is needed
        if force_reseed:
            logger.info(
                "FORCE_RESEED enabled — dropping all tables and re-seeding (%d clients existed)",
                client_count,
            )
            need_seed = True
        elif client_count == 0:
            logger.info("Empty database detected — seeding demo data...")
            need_seed = True
        elif not EXPECTED_CLIENTS.issubset(existing_clients):
            missing = EXPECTED_CLIENTS - existing_clients
            logger.info(
                "Incomplete demo data detected (missing clients: %s) — re-seeding...",
                ", ".join(sorted(missing)),
            )
            need_seed = True
        else:
            need_seed = False

        if need_seed:
            # Drop and rebuild the schema first if there's stale data to replace.
            # rebuild_schema is DESTRUCTIVE and FATAL on failure: a half-rebuilt
            # database must crash the boot, not serve 500s. Its SchemaRebuildError
            # is deliberately re-raised past the best-effort except below.
            if client_count > 0:
                from backend.db.migrate import rebuild_schema

                rebuild_schema()

            # Single canonical demo seeder (Run 8 unification). init_database
            # creates the schema + seeds all demo data and is pure app code (no
            # test-only deps), so it runs in every environment including the
            # Docker image — the old demo_seeder fallback was unreachable and is
            # removed. Any failure is caught below and by run_best_effort.
            from backend.scripts.init_demo_database import init_database

            init_database()
            logger.info("Auto-seeding complete")
        else:
            logger.info("Database OK (%d clients, all expected clients present)", client_count)
    except SchemaRebuildError:
        # A destructive rebuild failed partway — fatal. Never swallow as a
        # best-effort seed error; let it propagate so the boot crashes.
        raise
    except Exception as e:
        logger.warning("Auto-seed check failed: %s", e)


def run_best_effort(name: str, fn: Callable[[], None]) -> None:
    """Run a best-effort startup/shutdown step; log and swallow any exception."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - best-effort by design
        logger.warning("%s failed: %s", name, e)


def run_best_effort_unless(name: str, fn: Callable[[], None], fatal_exc: type[BaseException]) -> None:
    """Best-effort, EXCEPT ``fatal_exc`` which is re-raised.

    Ordinary failures are logged and swallowed (same semantic as
    run_best_effort); a fatal exception (e.g. SchemaRebuildError from a
    half-completed destructive rebuild) must crash the boot instead.
    """
    try:
        fn()
    except fatal_exc:
        raise
    except Exception as e:  # noqa: BLE001 - best-effort by design
        logger.warning("%s failed: %s", name, e)


def run_startup_migrations() -> None:
    """FATAL: bring the schema to Alembic head (the ONLY schema mechanism).

    Gated by RUN_MIGRATIONS_ON_STARTUP — false in multi-worker prod where the
    container entrypoint runs the upgrade exactly once before workers start.
    """
    from backend.config import settings
    from backend.db.migrate import upgrade_to_head

    if not settings.RUN_MIGRATIONS_ON_STARTUP:
        logger.info("RUN_MIGRATIONS_ON_STARTUP disabled — entrypoint owns migrations")
        return
    upgrade_to_head()
    logger.info("Alembic migrations applied (head)")


def init_event_infrastructure() -> None:
    """Register domain-event handlers + wire persistence."""
    from backend.database import SessionLocal

    register_all_handlers()
    event_bus = get_event_bus()
    event_bus.set_persistence_handler(create_event_persistence_handler(SessionLocal))
    logger.info("Domain events infrastructure initialized")


def start_schedulers() -> None:
    """Start the report + dual-view schedulers (each None-guarded AND isolated:
    one scheduler's start failure must not skip the other — matches the original's
    two separate try/excepts)."""
    run_best_effort("report scheduler start", lambda: report_scheduler.start() if report_scheduler else None)
    run_best_effort("dual-view scheduler start", lambda: dual_view_scheduler.start() if dual_view_scheduler else None)


def stop_schedulers() -> None:
    """Stop the dual-view then report schedulers (each None-guarded AND isolated)."""
    run_best_effort("dual-view scheduler stop", lambda: dual_view_scheduler.stop() if dual_view_scheduler else None)
    run_best_effort("report scheduler stop", lambda: report_scheduler.stop() if report_scheduler else None)


def seed_metric_dependencies_step() -> None:
    """Idempotently seed the metric→assumption dependency map."""
    from backend.database import SessionLocal
    from backend.services.calculations.assumption_catalog import seed_metric_dependencies

    dep_db = SessionLocal()
    try:
        inserted = seed_metric_dependencies(dep_db)
        if inserted:
            logger.info("Seeded %d metric->assumption dependency rows", inserted)
    finally:
        dep_db.close()


def dispose_engine() -> None:
    """Dispose the DB engine connection pool."""
    engine.dispose()
    logger.info("Database engine disposed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup then shutdown, preserving order + failure semantics."""
    # STARTUP — fatal steps unwrapped; best-effort steps via run_best_effort
    run_startup_migrations()  # fatal
    run_best_effort("event infrastructure init", init_event_infrastructure)
    start_schedulers()  # per-scheduler isolation lives inside (see its definition)
    # Demo seeding is best-effort EXCEPT a failed destructive rebuild
    # (SchemaRebuildError), which is fatal: a half-rebuilt DB must crash the boot.
    run_best_effort_unless("demo data seed", _auto_seed_demo_data, SchemaRebuildError)
    run_best_effort("metric dependency seed", seed_metric_dependencies_step)

    yield

    # SHUTDOWN — all best-effort
    stop_schedulers()
    run_best_effort("engine dispose", dispose_engine)

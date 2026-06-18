"""
Manufacturing KPI Platform - FastAPI Backend
Main application with modular routes

API Versioning:
  The canonical API prefix is /api/v1/. A path-rewriting middleware
  strips the /v1 segment so existing route handlers (mounted at /api/)
  continue to work unchanged.  Clients may use either prefix:
    - /api/v1/health/live  (canonical, versioned)
    - /api/health/live     (legacy, backward-compatible)
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI
from datetime import datetime, timezone
import logging

from backend.config import settings
from backend.database import engine, Base

# Domain Events Infrastructure (Phase 3)
from backend.events import register_all_handlers, get_event_bus
from backend.orm.event_store import create_event_persistence_handler
from backend.bootstrap.openapi import tags_metadata
from backend.bootstrap.routers import register_routers
from backend.bootstrap.app_config import configure_middleware, register_exception_handlers

_logger = logging.getLogger(__name__)

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


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================


def _auto_seed_demo_data() -> None:
    """
    Auto-seed demo data if the database is empty or incomplete (DEMO_MODE only).

    FORCE_RESEED=true: always drop and re-seed (one-time migration).
    Otherwise: smart detection — re-seed only if data is missing/stale.

    The re-seed path executes Base.metadata.drop_all(); the DEMO_MODE gate must
    stay the first statement so a non-demo deployment can never reach it
    (Run 7 C-1). Guarded by backend/tests/test_demo_seed_gate.py.
    """
    if not settings.DEMO_MODE:
        _logger.info("DEMO_MODE disabled — skipping demo data auto-seed")
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
            _logger.info(
                "FORCE_RESEED enabled — dropping all tables and re-seeding (%d clients existed)",
                client_count,
            )
            need_seed = True
        elif client_count == 0:
            _logger.info("Empty database detected — seeding demo data...")
            need_seed = True
        elif not EXPECTED_CLIENTS.issubset(existing_clients):
            missing = EXPECTED_CLIENTS - existing_clients
            _logger.info(
                "Incomplete demo data detected (missing clients: %s) — re-seeding...",
                ", ".join(sorted(missing)),
            )
            need_seed = True
        else:
            need_seed = False

        if need_seed:
            # Drop and recreate if there's stale data to replace
            if client_count > 0:
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)

            try:
                # Prefer the dev seeder (has TestDataFactory for richer data)
                from backend.scripts.init_demo_database import init_database

                init_database()
            except ImportError:
                # Docker image doesn't include backend.tests — use Docker seeder
                _logger.info("Using Docker-safe demo seeder (test fixtures not available)")
                from backend.db.migrations.demo_seeder import DemoDataSeeder

                seed_db = SessionLocal()
                try:
                    seeder = DemoDataSeeder(seed_db)
                    seeder.seed_all()
                    seed_db.commit()
                finally:
                    seed_db.close()
            _logger.info("Auto-seeding complete")
        else:
            _logger.info("Database OK (%d clients, all expected clients present)", client_count)
    except Exception as e:
        _logger.warning("Auto-seed check failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown logic."""
    # ------------------------------------------------------------------
    # STARTUP
    # ------------------------------------------------------------------

    # Ensure all tables exist (idempotent — safe on pre-populated databases)
    Base.metadata.create_all(bind=engine)

    # Safety check: warn if ORM model registry looks incomplete.
    # The project has 51 tables as of the deployment-readiness audit (2026-02-23).
    # If fewer than 45 appear, a model file was likely added to backend/orm/
    # but not imported in backend/orm/__init__.py.
    _actual_table_count = len(Base.metadata.tables)
    if _actual_table_count < 45:
        _logger.warning(
            "Schema registry may be incomplete: expected >=45 tables, got %d. "
            "Check that all ORM models are imported in backend/orm/__init__.py.",
            _actual_table_count,
        )

    from backend.db.migrations.capacity_planning_tables import create_capacity_tables

    create_capacity_tables()

    # Initialize Domain Events Infrastructure (Phase 3)
    try:
        # Register all event handlers
        register_all_handlers()

        # Set up event persistence to EVENT_STORE
        from backend.database import SessionLocal

        event_bus = get_event_bus()
        event_bus.set_persistence_handler(create_event_persistence_handler(SessionLocal))
        _logger.info("Domain events infrastructure initialized")
    except Exception as e:
        _logger.warning("Failed to initialize event infrastructure: %s", e)

    # Start daily report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.start()
        except Exception as e:
            _logger.warning("Failed to start report scheduler: %s", e)

    # Start nightly dual-view calculation scheduler (F.4).
    if dual_view_scheduler is not None:
        try:
            dual_view_scheduler.start()
        except Exception as e:
            _logger.warning("Failed to start dual-view scheduler: %s", e)

    # Auto-seed demo data (no-op unless DEMO_MODE is enabled)
    _auto_seed_demo_data()

    # Idempotently seed the canonical metric→assumption dependency map (Phase 2
    # dual-view architecture). Static engineering-curated reference data; safe
    # to call on every startup because seed_metric_dependencies() inserts only
    # missing rows.
    try:
        from backend.database import SessionLocal
        from backend.services.calculations.assumption_catalog import (
            seed_metric_dependencies,
        )

        dep_db = SessionLocal()
        try:
            inserted = seed_metric_dependencies(dep_db)
            if inserted:
                _logger.info("Seeded %d metric→assumption dependency rows", inserted)
        finally:
            dep_db.close()
    except Exception as e:
        _logger.warning("Failed to seed metric_assumption_dependencies: %s", e)

    yield

    # ------------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------------

    # Stop dual-view scheduler (F.4)
    if dual_view_scheduler is not None:
        try:
            dual_view_scheduler.stop()
        except Exception as e:
            _logger.warning("Failed to stop dual-view scheduler: %s", e)

    # Stop report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.stop()
        except Exception as e:
            _logger.warning("Failed to stop report scheduler: %s", e)

    # Dispose database engine to clean up connection pool
    try:
        engine.dispose()
        _logger.info("Database engine disposed")
    except Exception as e:
        _logger.warning("Failed to dispose database engine: %s", e)


# Initialize FastAPI app
app = FastAPI(
    title="Manufacturing KPI Platform API",
    description="FastAPI backend for production tracking and KPI calculation",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

configure_middleware(app)
register_exception_handlers(app)


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/")
def root() -> Dict[str, Any]:
    """API health check"""
    return {
        "status": "healthy",
        "service": "Manufacturing KPI Platform API",
        "version": "1.0.0",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ============================================================================
# MODULAR ROUTE REGISTRATION
# ============================================================================
register_routers(app)


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0 is required for Docker / Render container networking;
    # the production entrypoint uses uvicorn via gunicorn in the
    # Dockerfile, this branch is the local-development runner.
    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104

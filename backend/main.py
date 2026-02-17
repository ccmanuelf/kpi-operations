"""
Manufacturing KPI Platform - FastAPI Backend
Main application with modular routes
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone

from backend.config import settings
from backend.database import get_db, engine, Base


# =============================================================================
# V1 Simulation API Deprecation Middleware
# =============================================================================


class V1SimulationDeprecationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add deprecation headers to v1 simulation API responses.

    Adds HTTP headers per IETF deprecation header draft:
    - Deprecation: indicates the API is deprecated
    - Sunset: when the API will be discontinued
    - Link: pointer to the successor API
    """

    V1_SUNSET_DATE = "2026-06-01T00:00:00Z"
    V2_API_URL = "/api/v2/simulation"

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only add deprecation headers for v1 simulation routes
        if request.url.path.startswith("/api/simulation"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self.V1_SUNSET_DATE
            response.headers["Link"] = (
                f'<{self.V2_API_URL}>; rel="successor-version", ' f'</api/docs#/simulation-v2>; rel="deprecation"'
            )
            response.headers["X-API-Deprecation-Info"] = (
                "This API version is deprecated. Please migrate to /api/v2/simulation "
                "for enhanced SimPy-based simulation with multi-product support."
            )

        return response


# Domain Events Infrastructure (Phase 3)
from backend.events import register_all_handlers, get_event_bus
from backend.schemas.event_store import create_event_persistence_handler
from backend.middleware.rate_limit import limiter, configure_rate_limiting, RateLimitConfig
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.audit_log import AuditLogMiddleware

# Ensure all tables exist (idempotent — safe on pre-populated databases)
Base.metadata.create_all(bind=engine)

from backend.db.migrations.capacity_planning_tables import create_capacity_tables

create_capacity_tables()

# Initialize FastAPI app
tags_metadata = [
    {
        "name": "Production",
        "description": "Production data entry, batch tracking, and production metrics",
    },
    {
        "name": "Work Orders",
        "description": "Work order lifecycle management and tracking",
    },
    {
        "name": "KPI Calculations",
        "description": "Key Performance Indicator computations (OEE, OTD, WIP)",
    },
    {
        "name": "KPI Thresholds",
        "description": "Alert threshold configuration for KPI metrics",
    },
    {
        "name": "Alerts",
        "description": "Alert management, acknowledgment, and notification rules",
    },
    {
        "name": "Quality Inspection",
        "description": "Quality inspection results and defect recording",
    },
    {
        "name": "Defect Details",
        "description": "Detailed defect documentation and analysis",
    },
    {
        "name": "Defect Type Catalog",
        "description": "Defect type definitions and catalog management",
    },
    {
        "name": "Downtime Tracking",
        "description": "Machine downtime events and availability metrics",
    },
    {
        "name": "Attendance Tracking",
        "description": "Operator attendance and shift tracking",
    },
    {
        "name": "Workflow",
        "description": "Work order state machine transitions and workflow management",
    },
    {
        "name": "WIP Holds",
        "description": "Work-in-progress hold/resume tracking and aging analysis",
    },
    {
        "name": "Shift Coverage",
        "description": "Shift coverage analysis and gap detection",
    },
    {
        "name": "Floating Pool",
        "description": "Floating pool operator assignments and availability",
    },
    {
        "name": "Employees",
        "description": "Employee records and multi-skill tracking",
    },
    {
        "name": "Jobs",
        "description": "Job definitions and work order job assignments",
    },
    {
        "name": "Part Opportunities",
        "description": "Part opportunity tracking for production optimization",
    },
    {
        "name": "Capacity Planning",
        "description": "Capacity planning workbooks, BOM, MRP analysis, and scenarios",
    },
    {
        "name": "analytics",
        "description": "Production analytics, trend analysis, and bottleneck detection",
    },
    {
        "name": "predictions",
        "description": "Predictive analytics and forecasting endpoints",
    },
    {
        "name": "simulation-v2",
        "description": "Discrete-event manufacturing simulation engine",
    },
    {
        "name": "simulation",
        "description": "Legacy simulation API (deprecated, use simulation-v2)",
    },
    {
        "name": "reports",
        "description": "Report generation (PDF, email notifications)",
    },
    {
        "name": "qr",
        "description": "QR code generation for work orders and parts",
    },
    {
        "name": "Saved Filters",
        "description": "User-saved filter presets for data views",
    },
    {
        "name": "preferences",
        "description": "User preferences and UI settings",
    },
    {
        "name": "cache",
        "description": "Cache management and invalidation",
    },
    {
        "name": "Health",
        "description": "Application health checks, liveness, and readiness probes",
    },
    {
        "name": "Authentication",
        "description": "User authentication, registration, and JWT token management",
    },
    {
        "name": "User Management",
        "description": "User profile management and role assignments",
    },
    {
        "name": "Clients",
        "description": "Multi-tenant client management",
    },
    {
        "name": "Client Configuration",
        "description": "Per-client settings and shift configurations",
    },
    {
        "name": "database-config",
        "description": "Database provider configuration and migration management",
    },
    {
        "name": "Data Completeness",
        "description": "Data quality scoring and completeness analysis",
    },
    {
        "name": "Reference Data",
        "description": "Shared reference data (machines, departments, product types)",
    },
    {
        "name": "my-shift",
        "description": "Current user shift summary and activity",
    },
]

app = FastAPI(
    title="Manufacturing KPI Platform API",
    description="FastAPI backend for production tracking and KPI calculation",
    version="1.0.0",
    openapi_tags=tags_metadata,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# V1 Simulation API Deprecation middleware
app.add_middleware(V1SimulationDeprecationMiddleware)

# Security headers middleware (SEC-010)
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (SEC-001)
configure_rate_limiting(app)

# Audit logging middleware — logs POST/PUT/PATCH/DELETE on /api/ paths
app.add_middleware(AuditLogMiddleware)


# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

import logging

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from backend.exceptions.domain_exceptions import (
    DomainException,
    ResourceNotFoundError,
    ValidationError as DomainValidationError,
)

_logger = logging.getLogger(__name__)


@app.exception_handler(DomainValidationError)
async def domain_validation_error_handler(request: Request, exc: DomainValidationError):
    """Handle domain validation errors -> 400"""
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    """Handle resource not found -> 404"""
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    """Handle all other domain exceptions -> 400"""
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors -> 503"""
    _logger.exception("Database error: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database service temporarily unavailable"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors -> 500 with sanitized message"""
    _logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/")
def root():
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

# Import all routers from routes package
from backend.routes import (
    # Existing routers
    attendance_router,
    coverage_router,
    quality_router,
    defect_router,
    reports_router,
    health_router,
    analytics_router,
    predictions_router,
    qr_router,
    preferences_router,
    filters_router,
    # Newly extracted routers
    auth_router,
    users_router,
    production_router,
    import_logs_router,
    kpi_router,
    kpi_thresholds_router,
    downtime_router,
    availability_router,
    holds_router,
    wip_aging_router,
    jobs_router,
    work_order_jobs_router,
    work_orders_router,
    client_work_orders_router,
    clients_router,
    client_config_router,
    employees_router,
    client_employees_router,
    floating_pool_router,
    client_floating_pool_router,
    part_opportunities_router,
    reference_router,
    data_completeness_router,
    my_shift_router,
    alerts_router,
    workflow_router,
    simulation_router,
    simulation_v2_router,
    # Database configuration router (Phase 12)
    database_config_router,
    # Cache management router (Phase A.1)
    cache_router,
    # Capacity Planning router (Phase B.3)
    capacity_router,
)

# Import defect type catalog router
from backend.routes.defect_type_catalog import router as defect_type_catalog_router

# Import CSV upload endpoints
from backend.endpoints.csv_upload import router as csv_upload_router

# ============================================================================
# Register health check and monitoring routes
# ============================================================================
app.include_router(health_router)

# ============================================================================
# Register authentication routes
# ============================================================================
app.include_router(auth_router)

# ============================================================================
# Register user management routes
# ============================================================================
app.include_router(users_router)

# ============================================================================
# Register production routes
# ============================================================================
app.include_router(production_router)
app.include_router(import_logs_router)

# ============================================================================
# Register KPI routes
# ============================================================================
app.include_router(kpi_router)
app.include_router(kpi_thresholds_router)

# ============================================================================
# Register downtime routes
# ============================================================================
app.include_router(downtime_router)
app.include_router(availability_router)

# ============================================================================
# Register WIP holds routes
# ============================================================================
app.include_router(holds_router)
app.include_router(wip_aging_router)

# ============================================================================
# Register job routes
# ============================================================================
app.include_router(jobs_router)
app.include_router(work_order_jobs_router)

# ============================================================================
# Register work order routes
# ============================================================================
app.include_router(work_orders_router)
app.include_router(client_work_orders_router)

# ============================================================================
# Register client routes
# ============================================================================
app.include_router(clients_router)

# ============================================================================
# Register client configuration routes (Phase 7.2 - Client-Level Overrides)
# ============================================================================
app.include_router(client_config_router)

# ============================================================================
# Register employee routes
# ============================================================================
app.include_router(employees_router)
app.include_router(client_employees_router)

# ============================================================================
# Register floating pool routes
# ============================================================================
app.include_router(floating_pool_router)
app.include_router(client_floating_pool_router)

# ============================================================================
# Register part opportunities routes
# ============================================================================
app.include_router(part_opportunities_router)

# ============================================================================
# Register reference data routes
# ============================================================================
app.include_router(reference_router)

# ============================================================================
# Register data completeness routes
# ============================================================================
app.include_router(data_completeness_router)

# ============================================================================
# Register My Shift routes (operator personalized dashboard)
# ============================================================================
app.include_router(my_shift_router)

# ============================================================================
# Phase 10: Register intelligent alerts routes
# ============================================================================
app.include_router(alerts_router)

# ============================================================================
# Phase 10: Register workflow management routes
# ============================================================================
app.include_router(workflow_router)

# ============================================================================
# Phase 11: Register simulation and capacity planning routes
# ============================================================================
app.include_router(simulation_router)

# ============================================================================
# Simulation v2.0: Ephemeral production line simulation (no DB dependencies)
# ============================================================================
app.include_router(simulation_v2_router)

# ============================================================================
# Register CSV upload routes for all resources
# ============================================================================
app.include_router(csv_upload_router)

# ============================================================================
# Register attendance tracking routes
# ============================================================================
app.include_router(attendance_router)

# ============================================================================
# Register shift coverage routes
# ============================================================================
app.include_router(coverage_router)

# ============================================================================
# Register quality inspection routes
# ============================================================================
app.include_router(quality_router)

# ============================================================================
# Register defect detail routes
# ============================================================================
app.include_router(defect_router)

# ============================================================================
# Register comprehensive report generation routes
# ============================================================================
app.include_router(reports_router)

# ============================================================================
# Register analytics and prediction routes
# ============================================================================
app.include_router(analytics_router)

# ============================================================================
# Phase 5: Register comprehensive predictions routes
# ============================================================================
app.include_router(predictions_router)

# ============================================================================
# Phase 6: Register QR code routes
# ============================================================================
app.include_router(qr_router)

# ============================================================================
# Phase 7: Register user preferences routes
# ============================================================================
app.include_router(preferences_router)

# ============================================================================
# Phase 8: Register saved filters routes
# ============================================================================
app.include_router(filters_router)

# ============================================================================
# Phase 9: Register defect type catalog routes (client-specific defect types)
# ============================================================================
app.include_router(defect_type_catalog_router)

# ============================================================================
# Phase 12: Register database configuration routes (Admin only)
# ============================================================================
app.include_router(database_config_router)

# ============================================================================
# Phase A.1: Register cache management routes
# ============================================================================
app.include_router(cache_router)

# ============================================================================
# Phase B.3: Register capacity planning routes
# ============================================================================
app.include_router(capacity_router)


# ============================================================================
# NOTE: Report routes are now in routes/reports.py with proper authentication
# See: app.include_router(reports_router) at line 248
# ============================================================================

# Optional scheduler import for lifecycle events
try:
    from backend.tasks.daily_reports import scheduler as report_scheduler
except ImportError:
    report_scheduler = None


# ============================================================================
# APPLICATION LIFECYCLE EVENTS
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize application services"""
    # Initialize Domain Events Infrastructure (Phase 3)
    try:
        # Register all event handlers
        register_all_handlers()

        # Set up event persistence to EVENT_STORE
        from backend.database import SessionLocal

        event_bus = get_event_bus()
        event_bus.set_persistence_handler(create_event_persistence_handler(SessionLocal))
        print("[EVENTS] Domain events infrastructure initialized")
    except Exception as e:
        print(f"Warning: Failed to initialize event infrastructure: {e}")

    # Start daily report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.start()
        except Exception as e:
            print(f"Warning: Failed to start report scheduler: {e}")

    # Auto-seed demo data if database is empty
    try:
        from backend.database import SessionLocal
        from backend.schemas.client import Client

        db = SessionLocal()
        try:
            client_count = db.query(Client).count()
        finally:
            db.close()

        if client_count == 0:
            _logger.info("Empty database detected — auto-seeding demo data...")
            from backend.scripts.init_demo_database import init_database

            init_database()
            _logger.info("Auto-seeding complete")
        else:
            _logger.info("Database already populated (%d clients)", client_count)
    except Exception as e:
        _logger.warning("Auto-seed check failed: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application services"""
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

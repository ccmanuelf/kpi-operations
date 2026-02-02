"""
Manufacturing KPI Platform - FastAPI Backend
Main application with modular routes
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel

from backend.config import settings
from backend.database import get_db, engine, Base
from backend.middleware.rate_limit import (
    limiter,
    configure_rate_limiting,
    RateLimitConfig
)

# Create tables (DISABLED - using pre-populated SQLite database with demo data)
# Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Manufacturing KPI Platform API",
    description="FastAPI backend for production tracking and KPI calculation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (SEC-001)
configure_rate_limiting(app)


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
        "timestamp": datetime.utcnow().isoformat()
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
    # Database configuration router (Phase 12)
    database_config_router,
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
    # Start daily report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.start()
        except Exception as e:
            print(f"Warning: Failed to start report scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application services"""
    # Stop report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.stop()
        except Exception as e:
            print(f"Warning: Failed to stop report scheduler: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

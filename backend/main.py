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
    simulation_router
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
# REPORT GENERATION ROUTES (SPRINT 4.2)
# These remain in main.py due to complex dependencies
# ============================================================================

from backend.reports.pdf_generator import PDFReportGenerator
from backend.reports.excel_generator import ExcelReportGenerator
from backend.services.email_service import EmailService
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException

# Optional scheduler import (may not be available in test environment)
try:
    from backend.tasks.daily_reports import scheduler as report_scheduler
except ImportError:
    report_scheduler = None


class ReportEmailRequest(BaseModel):
    """Request model for sending reports via email"""
    client_id: Optional[int] = None
    start_date: date
    end_date: date
    recipient_emails: List[str]
    include_excel: bool = False


@app.get("/api/reports/pdf")
def generate_pdf_report(
    client_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    kpis: Optional[str] = None,  # Comma-separated KPI keys
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder - will be overridden by auth
):
    """
    Generate and download PDF report
    Query params:
    - client_id: Optional client filter
    - start_date: Report start date (default: 30 days ago)
    - end_date: Report end date (default: today)
    - kpis: Comma-separated KPI keys to include (default: all)
    """
    from backend.auth.jwt import get_current_user

    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Parse KPIs
    kpis_to_include = None
    if kpis:
        kpis_to_include = [k.strip() for k in kpis.split(',')]

    try:
        # Generate PDF
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            kpis_to_include=kpis_to_include
        )

        # Determine filename
        client_name = "All_Clients"
        if client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.name.replace(' ', '_')

        filename = f"KPI_Report_{client_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")


@app.get("/api/reports/excel")
def generate_excel_report(
    client_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder
):
    """
    Generate and download Excel report
    Query params:
    - client_id: Optional client filter
    - start_date: Report start date (default: 30 days ago)
    - end_date: Report end date (default: today)
    """
    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    try:
        # Generate Excel
        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date
        )

        # Determine filename
        client_name = "All_Clients"
        if client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.name.replace(' ', '_')

        filename = f"KPI_Report_{client_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")


@app.post("/api/reports/email")
def send_report_via_email(
    request: ReportEmailRequest,
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder
):
    """
    Send KPI report via email
    Body:
    {
        "client_id": 1,  // optional
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "recipient_emails": ["user@example.com"],
        "include_excel": false
    }
    """
    try:
        # Generate PDF
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=request.client_id,
            start_date=request.start_date,
            end_date=request.end_date
        )

        # Get client name
        client_name = "All Clients"
        if request.client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == request.client_id).first()
            if client:
                client_name = client.name

        # Send email
        email_service = EmailService()
        result = email_service.send_kpi_report(
            to_emails=request.recipient_emails,
            client_name=client_name,
            report_date=datetime.now(),
            pdf_content=pdf_buffer.getvalue()
        )

        if result['success']:
            return {
                "message": "Report sent successfully",
                "recipients": request.recipient_emails,
                "client": client_name
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('message', 'Failed to send email'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send report: {str(e)}")


@app.post("/api/reports/schedule/trigger")
def trigger_daily_reports(
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder
):
    """
    Manually trigger daily report generation for all clients
    SECURITY: Admin only
    """
    # Note: Proper auth check would be done via get_current_user dependency
    if report_scheduler is None:
        raise HTTPException(status_code=503, detail="Report scheduler not available")

    try:
        report_scheduler.send_daily_reports()
        return {"message": "Daily reports triggered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger reports: {str(e)}")


@app.get("/api/reports/test-email")
def test_email_configuration(
    test_email: str,
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder
):
    """
    Test email configuration by sending a test email
    SECURITY: Admin only
    """
    try:
        email_service = EmailService()
        result = email_service.send_test_email(test_email)

        if result['success']:
            return {"message": f"Test email sent successfully to {test_email}"}
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to send test email'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email test failed: {str(e)}")


@app.get("/api/reports/daily/{report_date}")
def generate_daily_pdf_report(
    report_date: date,
    db: Session = Depends(get_db),
    current_user = Depends(lambda: None)  # Placeholder
):
    """Generate daily production PDF report"""
    pdf_generator = PDFReportGenerator(db)
    pdf_buffer = pdf_generator.generate_report(
        client_id=None,
        start_date=report_date,
        end_date=report_date
    )

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=daily_report_{report_date}.pdf"
        }
    )


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

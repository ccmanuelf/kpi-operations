"""
Report Generation API Routes
Provides endpoints for PDF and Excel report generation with multi-client support
Also includes email report configuration endpoints
"""

from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)
from typing import Optional, List
from io import BytesIO
from pydantic import BaseModel, EmailStr

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.reports.pdf_generator import PDFReportGenerator
from backend.reports.excel_generator import ExcelReportGenerator
from backend.middleware.client_auth import verify_client_access


# ============================================
# Pydantic models for email configuration
# ============================================


class EmailReportConfig(BaseModel):
    """Email report configuration schema"""

    enabled: bool = False
    frequency: str = "daily"  # daily, weekly, monthly
    report_time: str = "06:00"
    recipients: List[str] = []
    client_id: Optional[str] = None
    include_executive_summary: bool = True
    include_efficiency: bool = True
    include_quality: bool = True
    include_availability: bool = True
    include_attendance: bool = True
    include_predictions: bool = True


class EmailReportConfigResponse(EmailReportConfig):
    """Response model with additional fields"""

    config_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestEmailRequest(BaseModel):
    """Request model for test email"""

    email: str


class ManualReportRequest(BaseModel):
    """Request model for manual report generation"""

    client_id: str
    start_date: str
    end_date: str
    recipient_emails: List[str]


# In-memory storage for email configs (in production, use database table)
_email_configs = {}


router = APIRouter(prefix="/api/reports", tags=["reports"])


# Helper function to parse date strings
def parse_date(date_str: Optional[str], default_days_ago: int = 30) -> date:
    """Parse date string or return default date"""
    if not date_str:
        return (datetime.now(tz=timezone.utc) - timedelta(days=default_days_ago)).date()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")


# Production Reports
@router.get("/production/pdf")
async def generate_production_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional, defaults to all clients)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate production efficiency PDF report

    Returns PDF with:
    - Production metrics (units produced, efficiency, performance)
    - OEE calculations
    - Trend analysis
    - Multi-client filtering
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate PDF
        pdf_generator = PDFReportGenerator(db)

        # Only include production-related KPIs
        production_kpis = ["efficiency", "performance", "availability", "oee"]

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=production_kpis
        )

        # Generate filename with timestamp
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"production_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "production",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate production PDF report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/production/excel")
async def generate_production_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate production efficiency Excel report

    Returns Excel workbook with multiple sheets:
    - Production metrics
    - Efficiency trends
    - OEE calculations
    - Downtime analysis
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate Excel
        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(client_id=client_id, start_date=start, end_date=end)

        # Generate filename
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"production_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "production",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate production Excel report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


# Quality Reports
@router.get("/quality/pdf")
async def generate_quality_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate quality metrics PDF report

    Includes:
    - FPY (First Pass Yield)
    - RTY (Rolled Throughput Yield)
    - PPM (Parts Per Million defects)
    - DPMO (Defects Per Million Opportunities)
    - Quality trends
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Quality-specific KPIs
        quality_kpis = ["fpy", "rty", "ppm", "dpmo"]

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=quality_kpis
        )

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"quality_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "quality",
                "X-Generated-By": current_user.username,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate quality PDF report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/quality/excel")
async def generate_quality_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate quality metrics Excel report with detailed worksheets"""
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(client_id=client_id, start_date=start, end_date=end)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"quality_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "quality",
                "X-Generated-By": current_user.username,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate quality Excel report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


# Attendance Reports
@router.get("/attendance/pdf")
async def generate_attendance_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate attendance and absenteeism PDF report

    Includes:
    - Absenteeism rates
    - Attendance trends
    - Department/shift breakdown
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Attendance-specific KPIs
        attendance_kpis = ["absenteeism"]

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=attendance_kpis
        )

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"attendance_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "attendance",
                "X-Generated-By": current_user.username,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate attendance PDF report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/attendance/excel")
async def generate_attendance_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate attendance and absenteeism Excel report"""
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(client_id=client_id, start_date=start, end_date=end)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"attendance_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "attendance",
                "X-Generated-By": current_user.username,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate attendance Excel report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


# Comprehensive Reports (All KPIs)
@router.get("/comprehensive/pdf")
async def generate_comprehensive_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate comprehensive PDF report with all KPIs

    Includes ALL metrics:
    - Production efficiency and OEE
    - Quality metrics (FPY, RTY, PPM, DPMO)
    - Attendance and absenteeism
    - Downtime analysis
    - On-time delivery
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Generate with all KPIs (default behavior)
        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=None  # None = all KPIs
        )

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"comprehensive_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "comprehensive",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate comprehensive PDF report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/comprehensive/excel")
async def generate_comprehensive_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate comprehensive Excel report with all KPIs and detailed worksheets

    Multi-sheet workbook includes:
    - Executive Summary
    - Production Metrics
    - Quality Metrics
    - Downtime Analysis
    - Attendance Records
    - Trend Charts
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(client_id=client_id, start_date=start, end_date=end)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"comprehensive_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "comprehensive",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate comprehensive Excel report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate report")


# Report Metadata/Info Endpoint
@router.get("/available")
async def get_available_reports(current_user: User = Depends(get_current_user)):
    """
    Get list of available report types and their descriptions
    """
    return {
        "reports": [
            {
                "type": "production",
                "name": "Production Efficiency Report",
                "description": "Production metrics, OEE, efficiency, and performance analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {"pdf": "/api/reports/production/pdf", "excel": "/api/reports/production/excel"},
            },
            {
                "type": "quality",
                "name": "Quality Metrics Report",
                "description": "FPY, RTY, PPM, DPMO, and quality trend analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {"pdf": "/api/reports/quality/pdf", "excel": "/api/reports/quality/excel"},
            },
            {
                "type": "attendance",
                "name": "Attendance & Absenteeism Report",
                "description": "Employee attendance tracking and absenteeism analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {"pdf": "/api/reports/attendance/pdf", "excel": "/api/reports/attendance/excel"},
            },
            {
                "type": "comprehensive",
                "name": "Comprehensive KPI Report",
                "description": "All KPIs in a single comprehensive report",
                "formats": ["pdf", "excel"],
                "endpoints": {"pdf": "/api/reports/comprehensive/pdf", "excel": "/api/reports/comprehensive/excel"},
            },
        ],
        "query_parameters": {
            "client_id": "Optional client ID for multi-client filtering",
            "start_date": "Report start date (YYYY-MM-DD format, defaults to 30 days ago)",
            "end_date": "Report end date (YYYY-MM-DD format, defaults to today)",
        },
        "features": [
            "Multi-client data isolation",
            "Date range filtering",
            "Multiple export formats (PDF/Excel)",
            "Real-time data aggregation",
            "Professional formatting",
            "Automated calculations",
            "Trend analysis",
            "Executive summaries",
        ],
    }


# ============================================
# Email Report Configuration Endpoints
# ============================================


@router.get("/email-config", response_model=EmailReportConfigResponse)
async def get_email_report_config(
    client_id: Optional[str] = Query(None, description="Client ID"), current_user: User = Depends(get_current_user)
):
    """
    Get email report configuration for a client

    Returns the current email report settings including:
    - Enabled status
    - Report frequency
    - Recipients list
    - Report content options
    """
    config_key = client_id or f"user_{current_user.user_id}"

    if config_key in _email_configs:
        return EmailReportConfigResponse(**_email_configs[config_key])

    # Return default configuration if not found
    return EmailReportConfigResponse(
        enabled=False,
        frequency="daily",
        report_time="06:00",
        recipients=[],
        client_id=client_id,
        include_executive_summary=True,
        include_efficiency=True,
        include_quality=True,
        include_availability=True,
        include_attendance=True,
        include_predictions=True,
    )


@router.post("/email-config", response_model=EmailReportConfigResponse)
async def save_email_report_config(config: EmailReportConfig, current_user: User = Depends(get_current_user)):
    """
    Save email report configuration

    Creates or updates email report settings for automated delivery.
    Configuration includes:
    - Report frequency (daily/weekly/monthly)
    - Delivery time
    - Recipient list
    - Report content options
    """
    # Validate recipients
    if config.enabled and len(config.recipients) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="At least one recipient email is required when enabled"
        )

    # Validate frequency
    if config.frequency not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Frequency must be 'daily', 'weekly', or 'monthly'"
        )

    # Store config
    config_key = config.client_id or f"user_{current_user.user_id}"

    config_dict = config.model_dump()
    config_dict["updated_at"] = datetime.now(tz=timezone.utc)
    config_dict["created_at"] = _email_configs.get(config_key, {}).get("created_at", datetime.now(tz=timezone.utc))

    _email_configs[config_key] = config_dict

    return EmailReportConfigResponse(**config_dict)


@router.put("/email-config", response_model=EmailReportConfigResponse)
async def update_email_report_config(config: EmailReportConfig, current_user: User = Depends(get_current_user)):
    """
    Update existing email report configuration

    Partial update of email report settings.
    """
    config_key = config.client_id or f"user_{current_user.user_id}"

    if config_key not in _email_configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email configuration not found. Use POST to create."
        )

    # Validate if enabling
    if config.enabled and len(config.recipients) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="At least one recipient email is required when enabled"
        )

    config_dict = config.model_dump()
    config_dict["updated_at"] = datetime.now(tz=timezone.utc)
    config_dict["created_at"] = _email_configs[config_key].get("created_at", datetime.now(tz=timezone.utc))

    _email_configs[config_key] = config_dict

    return EmailReportConfigResponse(**config_dict)


@router.post("/email-config/test")
async def send_test_email(request: TestEmailRequest, current_user: User = Depends(get_current_user)):
    """
    Send a test email to verify email configuration

    Sends a sample email to verify that email delivery is working correctly.
    """
    try:
        from backend.services.email_service import EmailService

        email_service = EmailService()
        result = email_service.send_test_email(request.email)

        if result.get("success"):
            return {"success": True, "message": f"Test email sent successfully to {request.email}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send test email"),
            )

    except ImportError:
        # Email service not available, simulate success for demo
        return {
            "success": True,
            "message": f"Test email queued for {request.email} (email service not configured)",
            "note": "Email service is not fully configured. In production, configure SMTP or SendGrid.",
        }
    except Exception as e:
        logger.exception("Failed to send test email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send test email"
        )


@router.post("/send-manual")
async def send_manual_report(
    request: ManualReportRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Manually trigger a report to be sent via email

    Generates and sends a KPI report immediately to specified recipients.
    """
    try:
        # SECURITY FIX (VULN-004): Verify client access before generating report
        verify_client_access(current_user, request.client_id)

        # Parse dates
        try:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD")

        if start_date > end_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before end date")

        # Generate PDF report
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=request.client_id, start_date=start_date, end_date=end_date
        )

        # Send email
        try:
            from backend.services.email_service import EmailService
            from backend.schemas.client import Client

            email_service = EmailService()

            # Get client name
            client = db.query(Client).filter(Client.client_id == request.client_id).first()
            client_name = client.name if client else request.client_id

            result = email_service.send_kpi_report(
                to_emails=request.recipient_emails,
                client_name=client_name,
                report_date=datetime.now(tz=timezone.utc),
                pdf_content=pdf_buffer.getvalue(),
                additional_message="This is a manually requested KPI report.",
            )

            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Report sent to {len(request.recipient_emails)} recipient(s)",
                    "recipients": request.recipient_emails,
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("error", "Failed to send report"),
                )

        except ImportError:
            # Email service not configured - return report generation success
            return {
                "success": True,
                "message": "Report generated successfully (email service not configured)",
                "note": "Configure SMTP or SendGrid for email delivery",
                "recipients": request.recipient_emails,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate/send manual report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate report"
        )

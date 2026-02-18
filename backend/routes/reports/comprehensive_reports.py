"""
Reports - Comprehensive KPI Report Endpoints and Report Catalog

Handles comprehensive all-KPI reports in both PDF and Excel formats,
plus the /available endpoint listing all report types.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.reports.pdf_generator import PDFReportGenerator
from backend.reports.excel_generator import ExcelReportGenerator
from backend.middleware.client_auth import verify_client_access
from backend.utils.logging_utils import get_module_logger
from .production_reports import parse_date

logger = get_module_logger(__name__)

comprehensive_reports_router = APIRouter()


@comprehensive_reports_router.get("/comprehensive/pdf")
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
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate with all KPIs (None = all KPIs)
        pdf_buffer = PDFReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=None
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


@comprehensive_reports_router.get("/comprehensive/excel")
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
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_buffer = ExcelReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end
        )

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


@comprehensive_reports_router.get("/available")
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
                "endpoints": {
                    "pdf": "/api/reports/production/pdf",
                    "excel": "/api/reports/production/excel",
                },
            },
            {
                "type": "quality",
                "name": "Quality Metrics Report",
                "description": "FPY, RTY, PPM, DPMO, and quality trend analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/quality/pdf",
                    "excel": "/api/reports/quality/excel",
                },
            },
            {
                "type": "attendance",
                "name": "Attendance & Absenteeism Report",
                "description": "Employee attendance tracking and absenteeism analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/attendance/pdf",
                    "excel": "/api/reports/attendance/excel",
                },
            },
            {
                "type": "comprehensive",
                "name": "Comprehensive KPI Report",
                "description": "All KPIs in a single comprehensive report",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/comprehensive/pdf",
                    "excel": "/api/reports/comprehensive/excel",
                },
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

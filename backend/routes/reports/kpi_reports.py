"""
Reports - Quality and Attendance Report Endpoints

Handles report generation for quality metrics and attendance/absenteeism
in both PDF and Excel formats.
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

kpi_reports_router = APIRouter()


# ============================================================================
# Quality Reports
# ============================================================================


@kpi_reports_router.get("/quality/pdf")
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
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        quality_kpis = ["fpy", "rty", "ppm", "dpmo"]
        pdf_buffer = PDFReportGenerator(db).generate_report(
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


@kpi_reports_router.get("/quality/excel")
async def generate_quality_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate quality metrics Excel report with detailed worksheets"""
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


# ============================================================================
# Attendance Reports
# ============================================================================


@kpi_reports_router.get("/attendance/pdf")
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
        if client_id:
            verify_client_access(current_user, client_id)

        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        attendance_kpis = ["absenteeism"]
        pdf_buffer = PDFReportGenerator(db).generate_report(
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


@kpi_reports_router.get("/attendance/excel")
async def generate_attendance_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate attendance and absenteeism Excel report"""
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

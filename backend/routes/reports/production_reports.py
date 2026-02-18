"""
Reports - Production PDF and Excel Endpoints

Handles report generation for production efficiency in both PDF and Excel formats.
Exports parse_date helper for use by other report sub-modules.
"""

from datetime import date, datetime, timedelta, timezone
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

logger = get_module_logger(__name__)

production_reports_router = APIRouter()


def parse_date(date_str: Optional[str], default_days_ago: int = 30) -> date:
    """Parse date string or return default date"""
    if not date_str:
        return (datetime.now(tz=timezone.utc) - timedelta(days=default_days_ago)).date()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")


@production_reports_router.get("/production/pdf")
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

        # Generate PDF — only include production-related KPIs
        production_kpis = ["efficiency", "performance", "availability", "oee"]
        pdf_buffer = PDFReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end, kpis_to_include=production_kpis
        )

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


@production_reports_router.get("/production/excel")
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

        excel_buffer = ExcelReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end
        )

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

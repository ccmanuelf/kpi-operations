"""
Report Generation API Routes
Provides endpoints for PDF and Excel report generation with multi-client support
"""
from datetime import date, datetime, timedelta
from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.reports.pdf_generator import PDFReportGenerator
from backend.reports.excel_generator import ExcelReportGenerator


router = APIRouter(prefix="/api/reports", tags=["reports"])


# Helper function to parse date strings
def parse_date(date_str: Optional[str], default_days_ago: int = 30) -> date:
    """Parse date string or return default date"""
    if not date_str:
        return (datetime.now() - timedelta(days=default_days_ago)).date()
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
    current_user: User = Depends(get_current_user)
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
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate PDF
        pdf_generator = PDFReportGenerator(db)

        # Only include production-related KPIs
        production_kpis = ['efficiency', 'performance', 'availability', 'oee']

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end,
            kpis_to_include=production_kpis
        )

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"production_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "production",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now().isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF report: {str(e)}")


@router.get("/production/excel")
async def generate_production_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Generate Excel
        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end
        )

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"production_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "production",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now().isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Excel report: {str(e)}")


# Quality Reports
@router.get("/quality/pdf")
async def generate_quality_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Quality-specific KPIs
        quality_kpis = ['fpy', 'rty', 'ppm', 'dpmo']

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end,
            kpis_to_include=quality_kpis
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"quality_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "quality",
                "X-Generated-By": current_user.username
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating quality PDF: {str(e)}")


@router.get("/quality/excel")
async def generate_quality_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate quality metrics Excel report with detailed worksheets"""
    try:
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"quality_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "quality",
                "X-Generated-By": current_user.username
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating quality Excel: {str(e)}")


# Attendance Reports
@router.get("/attendance/pdf")
async def generate_attendance_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate attendance and absenteeism PDF report

    Includes:
    - Absenteeism rates
    - Attendance trends
    - Department/shift breakdown
    """
    try:
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Attendance-specific KPIs
        attendance_kpis = ['absenteeism']

        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end,
            kpis_to_include=attendance_kpis
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"attendance_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "attendance",
                "X-Generated-By": current_user.username
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating attendance PDF: {str(e)}")


@router.get("/attendance/excel")
async def generate_attendance_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate attendance and absenteeism Excel report"""
    try:
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"attendance_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "attendance",
                "X-Generated-By": current_user.username
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating attendance Excel: {str(e)}")


# Comprehensive Reports (All KPIs)
@router.get("/comprehensive/pdf")
async def generate_comprehensive_pdf_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        pdf_generator = PDFReportGenerator(db)

        # Generate with all KPIs (default behavior)
        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end,
            kpis_to_include=None  # None = all KPIs
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"comprehensive_report_{start}_{end}{client_suffix}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "comprehensive",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now().isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating comprehensive PDF: {str(e)}")


@router.get("/comprehensive/excel")
async def generate_comprehensive_excel_report(
    client_id: Optional[str] = Query(None, description="Client ID (optional)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        start = parse_date(start_date, 30)
        end = parse_date(end_date, 0)

        if start > end:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start,
            end_date=end
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_suffix = f"_client_{client_id}" if client_id else "_all_clients"
        filename = f"comprehensive_report_{start}_{end}{client_suffix}_{timestamp}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Report-Type": "comprehensive",
                "X-Generated-By": current_user.username,
                "X-Generated-At": datetime.now().isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating comprehensive Excel: {str(e)}")


# Report Metadata/Info Endpoint
@router.get("/available")
async def get_available_reports(
    current_user: User = Depends(get_current_user)
):
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
                    "excel": "/api/reports/production/excel"
                }
            },
            {
                "type": "quality",
                "name": "Quality Metrics Report",
                "description": "FPY, RTY, PPM, DPMO, and quality trend analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/quality/pdf",
                    "excel": "/api/reports/quality/excel"
                }
            },
            {
                "type": "attendance",
                "name": "Attendance & Absenteeism Report",
                "description": "Employee attendance tracking and absenteeism analysis",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/attendance/pdf",
                    "excel": "/api/reports/attendance/excel"
                }
            },
            {
                "type": "comprehensive",
                "name": "Comprehensive KPI Report",
                "description": "All KPIs in a single comprehensive report",
                "formats": ["pdf", "excel"],
                "endpoints": {
                    "pdf": "/api/reports/comprehensive/pdf",
                    "excel": "/api/reports/comprehensive/excel"
                }
            }
        ],
        "query_parameters": {
            "client_id": "Optional client ID for multi-client filtering",
            "start_date": "Report start date (YYYY-MM-DD format, defaults to 30 days ago)",
            "end_date": "Report end date (YYYY-MM-DD format, defaults to today)"
        },
        "features": [
            "Multi-client data isolation",
            "Date range filtering",
            "Multiple export formats (PDF/Excel)",
            "Real-time data aggregation",
            "Professional formatting",
            "Automated calculations",
            "Trend analysis",
            "Executive summaries"
        ]
    }

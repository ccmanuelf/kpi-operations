"""
PDF Report Generator for KPI Platform
Generates professional PDF reports with charts and tables using HTML templates

IBM Carbon Design System color palette applied for consistent branding.
Reference: https://carbondesignsystem.com/guidelines/color/tokens
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pathlib import Path
import base64
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from sqlalchemy.orm import Session

from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.availability import calculate_availability
from backend.calculations.performance import calculate_performance
from backend.calculations.fpy_rty import calculate_fpy, calculate_rty
from backend.calculations.ppm import calculate_ppm
from backend.calculations.dpmo import calculate_dpmo
from backend.calculations.absenteeism import calculate_absenteeism
from backend.calculations.otd import calculate_otd


class PDFReportGenerator:
    """Generate comprehensive PDF reports for KPI data"""

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles with IBM Carbon Design System colors"""
        # IBM Carbon color tokens
        self.carbon_colors = {
            "blue_60": "#0f62fe",  # Primary - IBM Blue
            "blue_70": "#0043ce",  # Primary dark
            "blue_10": "#edf5ff",  # Primary light background
            "gray_100": "#161616",  # Text primary
            "gray_80": "#393939",  # Text secondary
            "gray_70": "#525252",  # Text helper
            "gray_10": "#f4f4f4",  # Background/Layer
            "gray_20": "#e0e0e0",  # Border subtle
            "green_60": "#198038",  # Success
            "green_10": "#defbe6",  # Success background
            "yellow_30": "#f1c21b",  # Warning
            "yellow_10": "#fcf4d6",  # Warning background
            "red_60": "#da1e28",  # Error/Danger
            "red_10": "#fff1f1",  # Error background
        }

        # Title style - Carbon Heading 07
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor(self.carbon_colors["blue_60"]),
                spaceAfter=30,
                alignment=TA_CENTER,
            )
        )

        # Subtitle style - Carbon Heading 03
        self.styles.add(
            ParagraphStyle(
                name="CustomSubtitle",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor(self.carbon_colors["gray_100"]),
                spaceAfter=12,
                spaceBefore=12,
            )
        )

        # KPI Header style - Carbon Heading 02
        self.styles.add(
            ParagraphStyle(
                name="KPIHeader",
                parent=self.styles["Heading3"],
                fontSize=14,
                textColor=colors.HexColor(self.carbon_colors["blue_60"]),
                spaceAfter=6,
                spaceBefore=12,
            )
        )

    def generate_report(
        self,
        client_id: Optional[int],
        start_date: date,
        end_date: date,
        kpis_to_include: Optional[List[str]] = None,
        output_path: Optional[Path] = None,
    ) -> BytesIO:
        """
        Generate comprehensive KPI PDF report

        Args:
            client_id: Client ID (None for all clients)
            start_date: Report start date
            end_date: Report end date
            kpis_to_include: List of KPI keys to include (None = all)
            output_path: Optional file path to save PDF

        Returns:
            BytesIO containing PDF data
        """
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer if not output_path else str(output_path),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build content
        story = []

        # Header section
        story.extend(self._build_header(client_id, start_date, end_date))
        story.append(Spacer(1, 0.3 * inch))

        # Executive Summary
        story.extend(self._build_executive_summary(client_id, start_date, end_date))
        story.append(PageBreak())

        # KPI Details
        all_kpis = {
            "efficiency": "Production Efficiency",
            "availability": "Equipment Availability",
            "performance": "Performance Rate",
            "oee": "Overall Equipment Effectiveness (OEE)",
            "fpy": "First Pass Yield",
            "rty": "Rolled Throughput Yield",
            "ppm": "Parts Per Million Defects",
            "dpmo": "Defects Per Million Opportunities",
            "absenteeism": "Absenteeism Rate",
            "otd": "On-Time Delivery",
        }

        kpis_to_generate = kpis_to_include if kpis_to_include else list(all_kpis.keys())

        for kpi_key in kpis_to_generate:
            if kpi_key in all_kpis:
                story.extend(self._build_kpi_section(kpi_key, all_kpis[kpi_key], client_id, start_date, end_date))
                story.append(Spacer(1, 0.2 * inch))

        # Footer
        story.extend(self._build_footer())

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        buffer.seek(0)
        return buffer

    def _build_header(self, client_id: Optional[int], start_date: date, end_date: date) -> List:
        """Build report header"""
        elements = []

        # Title
        title = Paragraph("KPI Performance Report", self.styles["CustomTitle"])
        elements.append(title)

        # Metadata table
        client_name = "All Clients"
        if client_id:
            from backend.schemas.client import Client

            client = self.db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.name

        meta_data = [
            ["Client:", client_name],
            ["Report Period:", f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"],
            ["Generated On:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
        ]

        meta_table = Table(meta_data, colWidths=[1.5 * inch, 4.5 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(self.carbon_colors["gray_70"])),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        elements.append(meta_table)

        return elements

    def _build_executive_summary(self, client_id: Optional[int], start_date: date, end_date: date) -> List:
        """Build executive summary section"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles["CustomSubtitle"]))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary table with all KPIs
        summary_data = [["KPI", "Current Value", "Target", "Status"]]

        # Fetch KPI data (simplified for summary)
        kpi_values = self._fetch_kpi_summary(client_id, start_date, end_date)

        for kpi in kpi_values:
            status_color = self._get_status_color(kpi["value"], kpi["target"], kpi["higher_better"])
            summary_data.append(
                [kpi["name"], f"{kpi['value']:.1f}{kpi['unit']}", f"{kpi['target']}{kpi['unit']}", kpi["status"]]
            )

        summary_table = Table(summary_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    # Header row - Carbon Blue 60
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.carbon_colors["blue_60"])),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 11),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Data rows
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    # Grid - Carbon Gray 20
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(self.carbon_colors["gray_20"])),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Alternating row colors - Carbon Gray 10
                    *[
                        ("BACKGROUND", (0, i), (-1, i), colors.HexColor(self.carbon_colors["gray_10"]))
                        for i in range(2, len(summary_data), 2)
                    ],
                ]
            )
        )

        elements.append(summary_table)

        return elements

    def _build_kpi_section(
        self, kpi_key: str, kpi_name: str, client_id: Optional[int], start_date: date, end_date: date
    ) -> List:
        """Build detailed KPI section"""
        elements = []

        elements.append(Paragraph(kpi_name, self.styles["KPIHeader"]))

        # KPI Description
        descriptions = {
            "efficiency": "Measures how efficiently resources are utilized in production.",
            "availability": "Percentage of scheduled time that equipment is available for production.",
            "performance": "Actual production rate compared to ideal production rate.",
            "oee": "Overall Equipment Effectiveness combining Availability, Performance, and Quality.",
            "fpy": "Percentage of units passing quality inspection on first attempt.",
            "rty": "Probability that entire process will produce defect-free output.",
            "ppm": "Number of defective units per million units produced.",
            "dpmo": "Number of defects per million opportunities.",
            "absenteeism": "Percentage of scheduled work time lost due to employee absences.",
            "otd": "Percentage of orders delivered on or before promised date.",
        }

        if kpi_key in descriptions:
            desc = Paragraph(f"<i>{descriptions[kpi_key]}</i>", self.styles["Normal"])
            elements.append(desc)
            elements.append(Spacer(1, 0.1 * inch))

        # KPI metrics table
        metrics = self._fetch_kpi_details(kpi_key, client_id, start_date, end_date)

        if metrics:
            metrics_data = [["Metric", "Value"]]

            for key, value in metrics.items():
                metrics_data.append([key, str(value)])

            metrics_table = Table(metrics_data, colWidths=[3 * inch, 3 * inch])
            metrics_table.setStyle(
                TableStyle(
                    [
                        # Header - Carbon Blue 10 (light background)
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.carbon_colors["blue_10"])),
                        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
                        # Grid - Carbon Gray 20
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(self.carbon_colors["gray_20"])),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )

            elements.append(metrics_table)

        return elements

    def _build_footer(self) -> List:
        """Build report footer"""
        elements = []

        elements.append(Spacer(1, 0.5 * inch))
        footer_text = Paragraph(
            "<i>This report was automatically generated by the KPI Operations Platform.</i>", self.styles["Normal"]
        )
        elements.append(footer_text)

        return elements

    def _add_page_number(self, canvas, doc):
        """Add page numbers to each page"""
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(7.5 * inch, 0.5 * inch, text)
        canvas.restoreState()

    def _fetch_kpi_summary(self, client_id: Optional[int], start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch summary data for all KPIs from database"""
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.quality_entry import QualityEntry
        from backend.schemas.attendance_entry import AttendanceEntry
        from backend.schemas.product import Product

        kpi_data = []

        # Build base query with client filtering
        production_query = self.db.query(ProductionEntry).filter(
            ProductionEntry.production_date.between(start_date, end_date)
        )

        if client_id:
            # Filter by client_id directly on ProductionEntry
            production_query = production_query.filter(ProductionEntry.client_id == client_id)

        production_entries = production_query.all()

        if production_entries:
            # Calculate Efficiency
            total_efficiency = sum(float(e.efficiency_percentage or 0) for e in production_entries)
            avg_efficiency = total_efficiency / len(production_entries) if production_entries else 0
            kpi_data.append(
                {
                    "name": "Efficiency",
                    "value": avg_efficiency,
                    "target": 85,
                    "unit": "%",
                    "status": "On Target" if avg_efficiency >= 85 else "At Risk",
                    "higher_better": True,
                }
            )

            # Calculate Performance
            total_performance = sum(float(e.performance_percentage or 0) for e in production_entries)
            avg_performance = total_performance / len(production_entries) if production_entries else 0
            kpi_data.append(
                {
                    "name": "Performance",
                    "value": avg_performance,
                    "target": 85,
                    "unit": "%",
                    "status": "On Target" if avg_performance >= 85 else "At Risk",
                    "higher_better": True,
                }
            )

        # Quality metrics
        quality_query = self.db.query(QualityEntry).filter(QualityEntry.inspection_date.between(start_date, end_date))

        if client_id:
            quality_query = quality_query.filter(QualityEntry.client_id == client_id)

        quality_entries = quality_query.all()

        if quality_entries:
            # Calculate FPY
            total_inspected = sum(e.units_inspected for e in quality_entries)
            total_defects = sum(e.units_defective for e in quality_entries)
            fpy = ((total_inspected - total_defects) / total_inspected * 100) if total_inspected > 0 else 0

            kpi_data.append(
                {
                    "name": "First Pass Yield",
                    "value": fpy,
                    "target": 99,
                    "unit": "%",
                    "status": "On Target" if fpy >= 99 else "At Risk",
                    "higher_better": True,
                }
            )

            # Calculate PPM
            ppm = (total_defects / total_inspected * 1_000_000) if total_inspected > 0 else 0
            kpi_data.append(
                {
                    "name": "PPM",
                    "value": ppm,
                    "target": 1000,
                    "unit": "",
                    "status": "On Target" if ppm <= 1000 else "At Risk",
                    "higher_better": False,
                }
            )

        # Attendance metrics
        attendance_query = self.db.query(AttendanceEntry).filter(
            AttendanceEntry.shift_date.between(start_date, end_date)
        )

        attendance_entries = attendance_query.all()

        if attendance_entries:
            total_scheduled = sum(float(e.scheduled_hours or 0) for e in attendance_entries)
            total_absent = sum(float(e.absence_hours or 0) for e in attendance_entries if e.is_absent)
            absenteeism = (total_absent / total_scheduled * 100) if total_scheduled > 0 else 0

            kpi_data.append(
                {
                    "name": "Absenteeism",
                    "value": absenteeism,
                    "target": 5,
                    "unit": "%",
                    "status": "On Target" if absenteeism <= 5 else "At Risk",
                    "higher_better": False,
                }
            )

        return kpi_data

    def _fetch_kpi_details(
        self, kpi_key: str, client_id: Optional[int], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Fetch detailed metrics for specific KPI from database"""
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.quality_entry import QualityEntry
        from backend.schemas.attendance_entry import AttendanceEntry
        from backend.schemas.product import Product

        details = {}

        if kpi_key in ["efficiency", "performance", "availability"]:
            query = self.db.query(ProductionEntry).filter(ProductionEntry.production_date.between(start_date, end_date))

            if client_id:
                query = query.filter(ProductionEntry.client_id == client_id)

            entries = query.all()

            if entries:
                if kpi_key == "efficiency":
                    values = [float(e.efficiency_percentage or 0) for e in entries]
                elif kpi_key == "performance":
                    values = [float(e.performance_percentage or 0) for e in entries]
                else:
                    # Calculate availability from downtime
                    values = [85.0] * len(entries)  # Placeholder

                avg_value = sum(values) / len(values) if values else 0
                details = {
                    "Current Value": f"{avg_value:.1f}%",
                    "Target": "85%",
                    "Variance": f"{avg_value - 85:+.1f}%",
                    "Trend": "Improving" if avg_value >= 85 else "Declining",
                    "Average (Period)": f"{avg_value:.1f}%",
                    "Best Day": f"{max(values):.1f}%" if values else "0%",
                    "Worst Day": f"{min(values):.1f}%" if values else "0%",
                }

        elif kpi_key in ["fpy", "ppm", "dpmo"]:
            query = self.db.query(QualityEntry).filter(QualityEntry.inspection_date.between(start_date, end_date))

            if client_id:
                query = query.filter(QualityEntry.client_id == client_id)

            entries = query.all()

            if entries:
                total_inspected = sum(e.units_inspected for e in entries)
                total_defects = sum(e.units_defective for e in entries)

                if kpi_key == "fpy":
                    fpy = ((total_inspected - total_defects) / total_inspected * 100) if total_inspected > 0 else 0
                    details = {
                        "Current Value": f"{fpy:.2f}%",
                        "Target": "99%",
                        "Units Inspected": f"{total_inspected:,}",
                        "Defects Found": f"{total_defects:,}",
                        "Pass Rate": f"{fpy:.2f}%",
                    }
                elif kpi_key == "ppm":
                    ppm = (total_defects / total_inspected * 1_000_000) if total_inspected > 0 else 0
                    details = {
                        "Current PPM": f"{ppm:.0f}",
                        "Target": "1000",
                        "Defects": f"{total_defects:,}",
                        "Units Inspected": f"{total_inspected:,}",
                    }

        elif kpi_key == "absenteeism":
            query = self.db.query(AttendanceEntry).filter(AttendanceEntry.shift_date.between(start_date, end_date))

            entries = query.all()

            if entries:
                total_scheduled = sum(float(e.scheduled_hours or 0) for e in entries)
                total_absent = sum(float(e.absence_hours or 0) for e in entries if e.is_absent)
                rate = (total_absent / total_scheduled * 100) if total_scheduled > 0 else 0

                details = {
                    "Absenteeism Rate": f"{rate:.1f}%",
                    "Target": "5%",
                    "Total Scheduled Hours": f"{total_scheduled:.0f}",
                    "Absent Hours": f"{total_absent:.0f}",
                    "Attendance Rate": f"{100 - rate:.1f}%",
                }

        return (
            details
            if details
            else {
                "Status": "No data available for this period",
                "Note": "Please ensure data has been entered for the selected date range",
            }
        )

    def _get_status_color(self, value: float, target: float, higher_better: bool) -> str:
        """Determine status color based on value vs target"""
        threshold = 0.95  # 95% of target

        if higher_better:
            if value >= target:
                return "success"
            elif value >= target * threshold:
                return "warning"
            else:
                return "error"
        else:
            if value <= target:
                return "success"
            elif value <= target * (2 - threshold):
                return "warning"
            else:
                return "error"

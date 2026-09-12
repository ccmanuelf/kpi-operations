"""
PDF Report Generator for KPI Platform
Generates professional PDF reports with charts and tables using HTML templates

IBM Carbon Design System color palette applied for consistent branding.
Reference: https://carbondesignsystem.com/guidelines/color/tokens
"""

from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER
from sqlalchemy.orm import Session

from backend.reports.measurements import absence_note, recorded
from backend.reports.targets import NOT_RECORDED, Target, load_targets, status_for
from backend.calculations.availability import calculate_availability_pure


def _detail_target(targets: Dict[str, Target], kpi_key: str, unit: str = "%") -> str:
    """The `Target` cell for a detail block, or an em dash when unconfigured."""
    target = targets.get(kpi_key)
    return "\u2014" if target is None else f"{target.value:g}{unit}"


def _detail_variance(targets: Dict[str, Target], kpi_key: str, value: float, unit: str = "%") -> str:
    """Variance against the configured target, not against a literal."""
    target = targets.get(kpi_key)
    return "\u2014" if target is None else f"{value - target.value:+.1f}{unit}"


def _summary_row(
    name: str, value: Optional[float], kpi_key: str, targets: Dict[str, Target], unit: str = "%"
) -> Dict[str, Any]:
    """One executive-summary row, judged against the configured target.

    `target` is None when nothing is configured for this metric, which the table
    renders as an em dash with a "No Target" status rather than inventing a
    number to compare against.

    No `higher_better` key: each row used to carry a direction literal, read only
    by `_get_status_color`, whose return value its single caller discarded -- so
    the PDF never coloured a status cell by it. Direction is now the threshold
    row's `higher_is_better`, and `status_for` applies it, so nothing downstream
    needs to be told which way the metric points.
    """
    target = targets.get(kpi_key)
    return {
        "name": name,
        "value": value,
        "target": target.value if target else None,
        "unit": unit,
        # `value is None` means the measurement was never recorded -- distinct
        # from a recorded zero, which is a finding and must still be judged.
        "status": NOT_RECORDED if value is None else status_for(value, target),
    }


class PDFReportGenerator:
    """Generate comprehensive PDF reports for KPI data"""

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
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
        client_id: Optional[str],
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

    def _build_header(self, client_id: Optional[str], start_date: date, end_date: date) -> List:
        """Build report header"""
        elements = []

        # Title
        title = Paragraph("KPI Performance Report", self.styles["CustomTitle"])
        elements.append(title)

        # Metadata table
        client_name = "All Clients"
        if client_id:
            from backend.orm.client import Client

            client = self.db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.client_name

        meta_data = [
            ["Client:", client_name],
            ["Report Period:", f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"],
            ["Generated On:", datetime.now(tz=timezone.utc).strftime("%B %d, %Y at %I:%M %p")],
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

    def _build_executive_summary(self, client_id: Optional[str], start_date: date, end_date: date) -> List:
        """Build executive summary section"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles["CustomSubtitle"]))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary table with all KPIs
        summary_data = [["KPI", "Current Value", "Target", "Status"]]

        # Fetch KPI data (simplified for summary)
        kpi_values = self._fetch_kpi_summary(client_id, start_date, end_date)

        for kpi in kpi_values:
            # An em dash rather than a number when no target is configured for
            # this metric. Printing a literal here is what made the column
            # judge clients against values they never set.
            target_cell = "\u2014" if kpi["target"] is None else f"{kpi['target']:g}{kpi['unit']}"
            value_cell = "\u2014" if kpi["value"] is None else f"{kpi['value']:.1f}{kpi['unit']}"
            summary_data.append([kpi["name"], value_cell, target_cell, kpi["status"]])

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
        self, kpi_key: str, kpi_name: str, client_id: Optional[str], start_date: date, end_date: date
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

    def _add_page_number(self, canvas: Any, doc: Any) -> None:
        """Add page numbers to each page"""
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(7.5 * inch, 0.5 * inch, text)
        canvas.restoreState()

    def _fetch_kpi_summary(self, client_id: Optional[str], start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch summary data for all KPIs from database"""
        from backend.orm.production_entry import ProductionEntry
        from backend.orm.quality_entry import QualityEntry
        from backend.orm.attendance_entry import AttendanceEntry

        # Targets are configuration, not literals. One lookup for the whole
        # table: this client's rows over the global defaults, per metric.
        targets = load_targets(self.db, client_id)

        kpi_data = []

        # Build base query with client filtering
        production_query = self.db.query(ProductionEntry).filter(
            ProductionEntry.production_date.between(
                datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time())
            )
        )

        if client_id:
            # Filter by client_id directly on ProductionEntry
            production_query = production_query.filter(ProductionEntry.client_id == client_id)

        production_entries = production_query.all()

        if production_entries:
            # Averaged over the entries that actually RECORDED the measurement.
            # `float(x or 0)` counted a NULL as a contributing zero, and for these
            # two columns that is every row in every deployment -- nothing writes
            # them -- so both rows reported 0.0% and "At Risk" where the truth is
            # that nobody measured.
            #
            # The row is still EMITTED, carrying None and a "Not Recorded" status,
            # rather than omitted. Omitting it would make an untracked KPI
            # indistinguishable from one the report never covered, and a reader
            # comparing two periods would not notice a row quietly disappearing.
            # This matches how an unconfigured target renders "No Target" instead
            # of vanishing.
            for label, column, kpi_key in (
                ("Efficiency", "efficiency_percentage", "efficiency"),
                ("Performance", "performance_percentage", "performance"),
            ):
                values = recorded(production_entries, column)
                kpi_data.append(_summary_row(label, sum(values) / len(values) if values else None, kpi_key, targets))

        # Quality metrics
        quality_query = self.db.query(QualityEntry).filter(
            QualityEntry.inspection_date.between(
                datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time())
            )
        )

        if client_id:
            quality_query = quality_query.filter(QualityEntry.client_id == client_id)

        quality_entries = quality_query.all()

        if quality_entries:
            # Calculate FPY
            total_inspected = sum(e.units_inspected for e in quality_entries)
            total_defects = sum(e.units_defective for e in quality_entries)
            fpy = ((total_inspected - total_defects) / total_inspected * 100) if total_inspected > 0 else 0

            kpi_data.append(_summary_row("First Pass Yield", fpy, "fpy", targets))

            # Calculate PPM
            ppm = (total_defects / total_inspected * 1_000_000) if total_inspected > 0 else 0
            kpi_data.append(_summary_row("PPM", ppm, "ppm", targets, unit=""))

        # Attendance metrics
        attendance_query = self.db.query(AttendanceEntry).filter(
            AttendanceEntry.shift_date.between(
                datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time())
            )
        )

        # Scope it, like the production and quality queries above. Without this
        # a client-scoped report computed absenteeism over EVERY tenant's
        # attendance -- the number was both wrong and not the reader's to see.
        if client_id:
            attendance_query = attendance_query.filter(AttendanceEntry.client_id == client_id)

        attendance_entries = attendance_query.all()

        if attendance_entries:
            total_scheduled = sum(float(e.scheduled_hours or 0) for e in attendance_entries)
            total_absent = sum(float(e.absence_hours or 0) for e in attendance_entries if e.is_absent)
            absenteeism = (total_absent / total_scheduled * 100) if total_scheduled > 0 else 0

            kpi_data.append(_summary_row("Absenteeism", absenteeism, "absenteeism", targets))

        return kpi_data

    def _fetch_kpi_details(
        self, kpi_key: str, client_id: Optional[str], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Fetch detailed metrics for specific KPI from database"""
        from backend.orm.production_entry import ProductionEntry
        from backend.orm.quality_entry import QualityEntry
        from backend.orm.attendance_entry import AttendanceEntry

        # The detail blocks carried their own literals, and the first of them
        # served efficiency, performance AND availability off a single "85%" --
        # so two of the three showed a target that was not theirs.
        targets = load_targets(self.db, client_id)

        details = {}

        if kpi_key in ["efficiency", "performance", "availability"]:
            query = self.db.query(ProductionEntry).filter(
                ProductionEntry.production_date.between(
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.max.time()),
                )
            )

            if client_id:
                query = query.filter(ProductionEntry.client_id == client_id)

            entries = query.all()

            if entries:
                if kpi_key == "efficiency":
                    values = recorded(entries, "efficiency_percentage")
                    if not values:
                        return absence_note(entries, "efficiency_percentage", "Efficiency")
                elif kpi_key == "performance":
                    values = recorded(entries, "performance_percentage")
                    if not values:
                        return absence_note(entries, "performance_percentage", "Performance")
                else:
                    values = [
                        float(
                            calculate_availability_pure(
                                Decimal(str(e.run_time_hours or 0)) + Decimal(str(e.downtime_hours or 0)),
                                Decimal(str(e.downtime_hours or 0)),
                            )
                        )
                        for e in entries
                    ]

                avg_value = sum(values) / len(values) if values else 0
                details = {
                    "Current Value": f"{avg_value:.1f}%",
                    # How much of the window the average actually rests on. A
                    # partly-populated column averages over a subset, and without
                    # this the reader cannot tell a figure drawn from 2 entries
                    # from one drawn from 200 -- nor compare it with a period that
                    # measured everything. The pivot engine exposes the same thing
                    # as `excluded_entries`.
                    "Entries Measured": f"{len(values)} of {len(entries)}",
                    "Target": _detail_target(targets, kpi_key),
                    "Variance": _detail_variance(targets, kpi_key, avg_value),
                    "Average (Period)": f"{avg_value:.1f}%",
                    "Best Day": f"{max(values):.1f}%" if values else "0%",
                    "Worst Day": f"{min(values):.1f}%" if values else "0%",
                }

        elif kpi_key in ["fpy", "ppm", "dpmo"]:
            query = self.db.query(QualityEntry).filter(
                QualityEntry.inspection_date.between(
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.max.time()),
                )
            )

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
                        "Target": _detail_target(targets, "fpy"),
                        "Units Inspected": f"{total_inspected:,}",
                        "Defects Found": f"{total_defects:,}",
                        "Pass Rate": f"{fpy:.2f}%",
                    }
                elif kpi_key == "ppm":
                    ppm = (total_defects / total_inspected * 1_000_000) if total_inspected > 0 else 0
                    details = {
                        "Current PPM": f"{ppm:.0f}",
                        "Target": _detail_target(targets, "ppm", unit=""),
                        "Defects": f"{total_defects:,}",
                        "Units Inspected": f"{total_inspected:,}",
                    }

        elif kpi_key == "absenteeism":
            query = self.db.query(AttendanceEntry).filter(
                AttendanceEntry.shift_date.between(
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.max.time()),
                )
            )

            # Same scoping as the summary above, and for the same reason: this
            # is the ONLY section of /reports/attendance/pdf.
            if client_id:
                query = query.filter(AttendanceEntry.client_id == client_id)

            entries = query.all()

            if entries:
                total_scheduled = sum(float(e.scheduled_hours or 0) for e in entries)
                total_absent = sum(float(e.absence_hours or 0) for e in entries if e.is_absent)
                rate = (total_absent / total_scheduled * 100) if total_scheduled > 0 else 0

                details = {
                    "Absenteeism Rate": f"{rate:.1f}%",
                    "Target": _detail_target(targets, "absenteeism"),
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

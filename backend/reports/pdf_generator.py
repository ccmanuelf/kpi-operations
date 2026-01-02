"""
PDF Report Generation
Generate KPI reports using ReportLab
"""
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from sqlalchemy.orm import Session
from backend.crud.production import get_daily_summary, get_production_entries


def generate_daily_report(
    db: Session,
    report_date: date,
    output_path: Optional[str] = None
) -> bytes:
    """
    Generate daily production PDF report

    Args:
        db: Database session
        report_date: Date for report
        output_path: Optional file path to save

    Returns:
        PDF bytes
    """
    # Create buffer
    buffer = io.BytesIO()

    # Create document
    doc = SimpleDocTemplate(
        buffer if output_path is None else output_path,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    # Container for elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    # Title
    title = Paragraph(
        f"Daily Production Report<br/>{report_date.strftime('%B %d, %Y')}",
        title_style
    )
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # Get summary data
    summary = get_daily_summary(db, report_date)

    if summary:
        summary_data = summary[0]

        # Summary table
        summary_table_data = [
            ['Metric', 'Value'],
            ['Total Units Produced', f"{summary_data['total_units']:,}"],
            ['Average Efficiency', f"{summary_data['avg_efficiency']:.2f}%"],
            ['Average Performance', f"{summary_data['avg_performance']:.2f}%"],
            ['Number of Entries', str(summary_data['entry_count'])]
        ]

        summary_table = Table(summary_table_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 0.5 * inch))

    # Detailed entries
    entries = get_production_entries(
        db,
        start_date=report_date,
        end_date=report_date,
        limit=1000
    )

    if entries:
        elements.append(Paragraph("Detailed Entries", styles['Heading2']))
        elements.append(Spacer(1, 0.2 * inch))

        # Entries table
        entries_data = [['WO#', 'Product', 'Shift', 'Units', 'Efficiency%', 'Performance%']]

        for entry in entries:
            entries_data.append([
                entry.work_order_number or 'N/A',
                f"ID:{entry.product_id}",
                f"ID:{entry.shift_id}",
                str(entry.units_produced),
                f"{float(entry.efficiency_percentage or 0):.2f}",
                f"{float(entry.performance_percentage or 0):.2f}"
            ])

        entries_table = Table(
            entries_data,
            colWidths=[1 * inch, 1.2 * inch, 0.8 * inch, 0.8 * inch, 1 * inch, 1 * inch]
        )
        entries_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        elements.append(entries_table)

    # Footer
    elements.append(Spacer(1, 0.5 * inch))
    footer = Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['Normal']
    )
    elements.append(footer)

    # Build PDF
    doc.build(elements)

    # Get PDF bytes
    if output_path is None:
        buffer.seek(0)
        return buffer.read()

    return b""


def generate_monthly_report(
    db: Session,
    year: int,
    month: int,
    output_path: Optional[str] = None
) -> bytes:
    """
    Generate monthly production PDF report

    Args:
        db: Database session
        year: Year
        month: Month (1-12)
        output_path: Optional file path to save

    Returns:
        PDF bytes
    """
    # Implementation similar to daily report but with monthly aggregation
    # Left as exercise for complete implementation
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title = Paragraph(
        f"Monthly Production Report - {year}/{month:02d}",
        styles['Title']
    )
    elements.append(title)

    # Add monthly summary logic here

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

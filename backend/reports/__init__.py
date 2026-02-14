"""
KPI Reports Module

This module provides automated report generation and email delivery.

Available generators:
- PDFReportGenerator: Professional PDF reports
- ExcelReportGenerator: Multi-sheet Excel workbooks

Available services:
- EmailService: Email delivery with attachments
- DailyReportScheduler: Automated report scheduling
"""

from .pdf_generator import PDFReportGenerator
from .excel_generator import ExcelReportGenerator

__all__ = ["PDFReportGenerator", "ExcelReportGenerator"]

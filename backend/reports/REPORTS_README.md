# Report Generation Module

Professional PDF and Excel report generation for KPI Operations Platform with multi-client support and real-time data aggregation.

## Features

- **PDF Reports**: Professional reports using ReportLab with charts, tables, and custom styling
- **Excel Reports**: Multi-sheet workbooks with formulas, formatting, and trend visualizations
- **Multi-Client Support**: Enforced data isolation with client_id filtering
- **Real-Time Data**: Direct database queries for up-to-date KPI calculations
- **Streaming Response**: Efficient file delivery without memory buffering
- **Comprehensive Coverage**: Production, Quality, Attendance, and Comprehensive reports

## Quick Start

### Generate PDF Report

```python
from reports.pdf_generator import PDFReportGenerator
from datetime import date

pdf_gen = PDFReportGenerator(db_session)
pdf_buffer = pdf_gen.generate_report(
    client_id="ABC123",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    kpis_to_include=['efficiency', 'fpy', 'ppm']
)
```

### Generate Excel Report

```python
from reports.excel_generator import ExcelReportGenerator

excel_gen = ExcelReportGenerator(db_session)
excel_buffer = excel_gen.generate_report(
    client_id="ABC123",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)
```

## API Endpoints

All endpoints require authentication and support multi-client filtering.

### Production Reports
- `GET /api/reports/production/pdf` - PDF production report
- `GET /api/reports/production/excel` - Excel production report

### Quality Reports
- `GET /api/reports/quality/pdf` - PDF quality metrics
- `GET /api/reports/quality/excel` - Excel quality metrics

### Attendance Reports
- `GET /api/reports/attendance/pdf` - PDF attendance/absenteeism
- `GET /api/reports/attendance/excel` - Excel attendance tracking

### Comprehensive Reports
- `GET /api/reports/comprehensive/pdf` - Complete PDF with all KPIs
- `GET /api/reports/comprehensive/excel` - Complete Excel with all metrics

### Query Parameters
- `client_id` (optional): Filter by specific client
- `start_date` (optional): YYYY-MM-DD format (defaults to 30 days ago)
- `end_date` (optional): YYYY-MM-DD format (defaults to today)

## Supported KPIs

- Production Efficiency
- Equipment Availability
- Performance Rate
- Overall Equipment Effectiveness (OEE)
- First Pass Yield (FPY)
- Rolled Throughput Yield (RTY)
- Parts Per Million defects (PPM)
- Defects Per Million Opportunities (DPMO)
- Absenteeism Rate
- On-Time Delivery (OTD)

## Documentation

See `/Users/mcampos.cerda/Documents/Programming/kpi-operations/docs/REPORT_GENERATION_IMPLEMENTATION.md` for complete implementation details.

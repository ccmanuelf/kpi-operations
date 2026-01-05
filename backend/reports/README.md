# KPI Reports Module

This module handles automated report generation and email delivery for the KPI Operations Platform.

## Components

### 1. PDF Generator (`pdf_generator.py`)
Generates professional PDF reports using ReportLab.

**Usage**:
```python
from reports.pdf_generator import PDFReportGenerator
from datetime import date, timedelta

pdf_gen = PDFReportGenerator(db_session)
pdf_buffer = pdf_gen.generate_report(
    client_id=1,
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    kpis_to_include=['efficiency', 'quality', 'oee']  # Optional
)

# Save to file
with open('report.pdf', 'wb') as f:
    f.write(pdf_buffer.getvalue())
```

### 2. Excel Generator (`excel_generator.py`)
Creates multi-sheet Excel workbooks with formatted data.

**Usage**:
```python
from reports.excel_generator import ExcelReportGenerator

excel_gen = ExcelReportGenerator(db_session)
excel_buffer = excel_gen.generate_report(
    client_id=1,
    start_date=date.today() - timedelta(days=30),
    end_date=date.today()
)

# Save to file
with open('report.xlsx', 'wb') as f:
    f.write(excel_buffer.getvalue())
```

### 3. Email Service (`../services/email_service.py`)
Handles email delivery with PDF/Excel attachments.

**Usage**:
```python
from services.email_service import EmailService

email_service = EmailService()
result = email_service.send_kpi_report(
    to_emails=['manager@example.com'],
    client_name='Acme Corporation',
    report_date=datetime.now(),
    pdf_content=pdf_buffer.getvalue()
)

if result['success']:
    print("Email sent successfully!")
else:
    print(f"Error: {result['error']}")
```

### 4. Daily Reports Scheduler (`../tasks/daily_reports.py`)
Automated daily report generation and distribution.

**Usage**:
```python
from tasks.daily_reports import scheduler

# Start scheduler (done automatically on app startup)
scheduler.start()

# Manually trigger reports
scheduler.send_daily_reports()

# Stop scheduler
scheduler.stop()
```

## Features

### PDF Reports Include:
- Executive summary with all KPIs
- Color-coded status indicators
- Detailed metrics for each KPI
- Professional formatting
- Page numbers and metadata

### Excel Reports Include:
- Executive Summary sheet
- Production Metrics sheet
- Quality Metrics sheet
- Downtime Analysis sheet
- Attendance sheet
- Trend Charts sheet
- Embedded formulas
- Color-coded cells

### Email Features:
- HTML email templates
- PDF attachments
- Multiple recipients
- Error handling
- SendGrid or SMTP support

### Scheduler Features:
- Configurable daily schedule
- Per-client report generation
- Email to client admins
- Comprehensive logging
- Manual trigger support

## Configuration

Set these in `/backend/config.py` or `.env`:

```python
# Email
SENDGRID_API_KEY = "your_key"  # Or use SMTP
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your_email@gmail.com"
SMTP_PASSWORD = "your_password"
REPORT_FROM_EMAIL = "reports@kpi-platform.com"

# Scheduling
REPORT_EMAIL_ENABLED = True
REPORT_EMAIL_TIME = "06:00"  # HH:MM format
```

## API Endpoints

All endpoints in `/backend/main.py`:

- `GET /api/reports/pdf` - Download PDF report
- `GET /api/reports/excel` - Download Excel report
- `POST /api/reports/email` - Email report
- `POST /api/reports/schedule/trigger` - Trigger daily reports (admin)
- `GET /api/reports/test-email` - Test email config (admin)

## Development

### Adding New KPIs to Reports

1. **PDF Generator**: Update `_fetch_kpi_summary()` and `_fetch_kpi_details()`
2. **Excel Generator**: Add data to appropriate sheet in `_create_*_sheet()` methods
3. **Add to KPI list**: Update `all_kpis` dict in `generate_report()`

### Customizing Email Templates

Edit `_generate_email_template()` in `/backend/services/email_service.py`.

### Modifying Report Schedule

Change `REPORT_EMAIL_TIME` in config or `.env` file.

## Testing

```bash
# Test PDF generation
curl -X GET "http://localhost:8000/api/reports/pdf?client_id=1" \
  -H "Authorization: Bearer TOKEN" -o test.pdf

# Test Excel generation
curl -X GET "http://localhost:8000/api/reports/excel?client_id=1" \
  -H "Authorization: Bearer TOKEN" -o test.xlsx

# Test email
curl -X GET "http://localhost:8000/api/reports/test-email?test_email=your@email.com" \
  -H "Authorization: Bearer TOKEN"
```

## Dependencies

```
reportlab==4.0.8
openpyxl==3.1.2
sendgrid==6.11.0
APScheduler==3.10.4
```

## Troubleshooting

**PDF generation slow**: Check database query performance
**Email not sending**: Verify API key or SMTP credentials
**Scheduler not running**: Check logs for startup errors
**Large file sizes**: Reduce date range or KPI selection

For detailed documentation, see `/docs/REPORTS_IMPLEMENTATION.md`

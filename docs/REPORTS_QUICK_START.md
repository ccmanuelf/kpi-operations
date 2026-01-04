# Reports & Email Delivery - Quick Start Guide

## 1. Installation

```bash
cd backend
pip install sendgrid==6.11.0 APScheduler==3.10.4
```

## 2. Configuration

### Option A: SendGrid (Recommended)

1. Sign up at https://sendgrid.com (free tier: 100 emails/day)
2. Create API key with "Mail Send" permissions
3. Add to `.env`:

```env
SENDGRID_API_KEY=SG.your_api_key_here
REPORT_FROM_EMAIL=reports@yourdomain.com
REPORT_EMAIL_ENABLED=true
REPORT_EMAIL_TIME=06:00
```

### Option B: SMTP (Gmail)

1. Enable 2FA on your Gmail account
2. Generate app-specific password
3. Add to `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
REPORT_FROM_EMAIL=your.email@gmail.com
REPORT_EMAIL_ENABLED=true
REPORT_EMAIL_TIME=06:00
```

## 3. Test the Setup

### Test Email Configuration
```bash
# Start backend
cd backend
python main.py

# In another terminal, test email
curl -X GET "http://localhost:8000/api/reports/test-email?test_email=your@email.com" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test PDF Generation
Navigate to the KPI Dashboard in the frontend and click:
**Reports → Download PDF**

### Test Email Delivery
1. Click **Reports → Email Report**
2. Enter email address
3. Click **Send Report**
4. Check your inbox

## 4. Usage

### Frontend (KPI Dashboard)
1. Select client (optional)
2. Select date range
3. Click **Reports** button
4. Choose action:
   - **Download PDF** - Instant download
   - **Download Excel** - Instant download
   - **Email Report** - Opens dialog to enter recipients

### API Usage

**Download PDF**:
```bash
GET /api/reports/pdf?client_id=1&start_date=2024-01-01&end_date=2024-01-31
```

**Download Excel**:
```bash
GET /api/reports/excel?client_id=1&start_date=2024-01-01&end_date=2024-01-31
```

**Send Email**:
```bash
POST /api/reports/email
{
  "client_id": 1,
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "recipient_emails": ["manager@example.com"]
}
```

## 5. Daily Automated Reports

### How It Works
- Scheduler runs daily at 6:00 AM (configurable)
- Generates reports for all active clients
- Sends to client admins automatically
- Logs all successes and failures

### Manual Trigger (Admin Only)
```bash
POST /api/reports/schedule/trigger
```

### Change Schedule Time
Edit `.env`:
```env
REPORT_EMAIL_TIME=08:30  # 8:30 AM
```

## 6. Troubleshooting

### Emails Not Sending
1. Check API key/credentials in `.env`
2. Test email configuration endpoint
3. Check application logs for errors
4. Verify firewall allows SMTP port 587

### PDF/Excel Generation Fails
1. Ensure all dependencies installed
2. Check database connection
3. Verify sufficient disk space
4. Check logs for specific errors

### Scheduler Not Running
1. Ensure `REPORT_EMAIL_ENABLED=true` in `.env`
2. Check application startup logs
3. Restart backend application

## 7. Report Contents

### PDF Report Includes:
- Executive summary with all 10 KPIs
- Current values vs targets
- Status indicators (On Target/At Risk/Critical)
- Detailed metrics for each KPI
- Client name, date range, generation timestamp

### Excel Report Includes:
- Executive Summary (all KPIs)
- Production Metrics (efficiency, performance, OEE)
- Quality Metrics (FPY, RTY, PPM, DPMO)
- Downtime Analysis (availability, events)
- Attendance (absenteeism rates)
- Trend Charts (placeholder for visualizations)

## 8. Best Practices

1. **Email Recipients**: Add client admins to user table with role 'admin'
2. **Schedule Time**: Choose off-peak hours (early morning)
3. **Date Ranges**: Keep reports to 30-90 days for optimal performance
4. **File Size**: PDF ~500KB, Excel ~200KB for 30-day reports
5. **Testing**: Always test with personal email before production use

## 9. Support

For detailed documentation, see:
- `/docs/REPORTS_IMPLEMENTATION.md` - Full implementation details
- `/backend/reports/README.md` - Module documentation

For issues:
1. Check `/backend/logs` for error details
2. Verify configuration in `.env`
3. Test individual components (PDF, Excel, Email)
4. Contact development team with logs

## 10. Next Steps

- Customize email templates in `/backend/services/email_service.py`
- Add charts to PDF reports
- Implement report history/archive
- Create custom report templates
- Add analytics dashboard for report usage

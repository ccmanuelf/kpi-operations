# 08 — Reports

Generate Excel / PDF deliverables for execs, customers, auditors, and yourself.

## What it is

Pre-formatted exports of your data, computed on demand. The platform produces:

- Excel workbooks (multiple sheets: summary, detail, charts)
- PDF reports (executive summary + visualizations)

You access them via the **Email Reports Dialog** on the Home dashboard, or programmatically via the API.

## The 4 report types

| Report | Excel endpoint | PDF endpoint | What's in it |
|--------|----------------|--------------|--------------|
| **Comprehensive** | `/api/reports/comprehensive/excel` | `/api/reports/comprehensive/pdf` | All KPIs + breakdowns, the "everything" report |
| **Production** | `/api/reports/production/excel` | `/api/reports/production/pdf` | Production data with daily/weekly rollups |
| **Quality** | `/api/reports/quality/excel` | `/api/reports/quality/pdf` | Quality trends, FPY, DPMO, defect Pareto |
| **Attendance** | `/api/reports/attendance/excel` | `/api/reports/attendance/pdf` | Absenteeism, coverage, Bradford factor |

All accept query params:
- `client_id` (optional — defaults to user's assignment)
- `start_date` / `end_date` (defaults: last 30 days)

## Use cases

✅ **Monthly business review**: comprehensive PDF + executive narrative
✅ **Customer scorecard**: production + quality reports per customer client
✅ **Audit / compliance**: comprehensive Excel with the assumption log embedded
✅ **HR review**: attendance report with Bradford factor
✅ **Daily standup deck**: production PDF with yesterday's numbers

## Generating a report

### From the UI

1. Open Home (`/`)
2. Click **Email Reports** (top-right)
3. Choose:
   - Report type
   - Format (Excel / PDF)
   - Date range
   - Recipients (comma-separated emails)
4. **Send Now** OR **Schedule** (daily / weekly / monthly)

### Via API

```bash
curl -O -H "Authorization: Bearer $TOKEN" \
  "https://api.example.com/api/reports/comprehensive/excel?client_id=ACME-MFG&start_date=2026-04-01&end_date=2026-04-30"
```

The response is the Excel file as binary; pipe to `-o filename.xlsx`.

## Report structures

### Comprehensive Excel

Sheets:
- **Summary** — top-level KPIs as cards: efficiency, OEE, FPY, OTD, absenteeism. Color-coded vs targets.
- **Production** — daily rollups: units produced, throughput by product, top performers
- **Quality** — daily FPY + DPMO trends, defect type breakdown
- **Downtime** — total hours, by reason category, top events
- **Attendance** — % present, absences by type, top absentees by Bradford factor
- **Schedule** — current production schedule (if any committed)
- **Assumption Log** — all formulas + parameters used (auditability)

### Production Excel

Sheets:
- **Daily Detail** — per-day per-line per-product
- **Weekly Rollups** — Mon-Sun aggregates
- **Trend Chart** — units produced over time
- **Pareto** — top performers
- **OEE Components** — availability, performance, quality stacked

### Quality Excel

Sheets:
- **FPY Trend** — daily FPY line chart
- **DPMO Trend** — daily DPMO
- **Defect Pareto** — defects by type, sorted descending
- **Defect Detail** — per-WO defect log
- **RTY by Product** — Rolled Throughput Yield per style

### Attendance Excel

Sheets:
- **Daily Coverage** — % present per day
- **Absences** — list with type, reason, employee
- **Bradford Factor** — per-employee score (top 10)
- **Coverage** — who covered whom

## PDF reports

PDF reports are slimmer (5-10 pages typically):
- Page 1: Executive summary (4-card layout: efficiency, quality, OTD, absenteeism)
- Page 2-3: Trend charts
- Page 4-5: Top exceptions / outliers
- Page 6: Assumption log

Use Excel for analysis, PDF for distribution.

## Email scheduling

Click **Schedule** instead of Send Now. Frequency:
- Daily (specify time)
- Weekly (specify day + time)
- Monthly (specify day-of-month + time)

The platform stores the schedule in the JOB queue (`/api/jobs`) and emails on schedule via SendGrid (or SMTP if configured). Configuration:

- `notification_email = true` on the user
- SMTP / SendGrid configured at platform level
- `/api/reports/email-config` exposes the current config (admin only)
- `/api/reports/email-config/test` sends a test email

## Hints & tips

☆ The first few times you generate a report, do it manually with a known date range — verify the numbers match your dashboard before scheduling unattended.

☆ For executive reports, generate as PDF — readable on phone, archivable.

☆ For digging deeper, generate as Excel — pivot tables, formulas, custom charts.

☆ The comprehensive report is HEAVY — for a 30-day window across all clients, it's a multi-MB Excel. Schedule overnight or scope to a single client.

## Interpreting the assumption log

The last sheet of every comprehensive report. Lists:
- Date range used
- Aggregation rules (daily / weekly / monthly)
- Calculation formulas (e.g. "Efficiency = (Earned SAM / Available SAM) × 100")
- Defaults applied (where input was missing)
- Caveats (e.g. "Days with no production entry assumed zero — may understate trend")

⚠ When sharing reports externally (with a customer or auditor), point to the assumption log as the "how we got these numbers" — pre-empts disputes.

## Common pitfalls

⛔ Sending reports without verifying: a stale demo seed or wrong date range produces nonsense. Always sanity-check against `/api/kpi/dashboard`.

⛔ Scheduling with too-wide a date range: a 12-month comprehensive report can take minutes to generate and tens of MB to deliver. Limit to 30-90 days.

⛔ Treating the report as Truth without context. The dashboard is live; the report is a snapshot. Numbers may differ if data is being entered between snapshot and now.

## API endpoints

12 routes under `/api/reports/*`:

| Endpoint | Purpose |
|----------|---------|
| `GET /reports/available` | List available report types |
| `GET /reports/email-config` | Email config (admin) |
| `POST /reports/email-config/test` | Send a test |
| `POST /reports/send-manual` | Manual send |
| `GET /reports/comprehensive/excel` | Comprehensive Excel |
| `GET /reports/comprehensive/pdf` | Comprehensive PDF |
| `GET /reports/production/excel` | Production Excel |
| `GET /reports/production/pdf` | Production PDF |
| `GET /reports/quality/excel` | Quality Excel |
| `GET /reports/quality/pdf` | Quality PDF |
| `GET /reports/attendance/excel` | Attendance Excel |
| `GET /reports/attendance/pdf` | Attendance PDF |

Plus the Excel CSV exports under each entry (`/api/export/{type}`):

| Endpoint | Purpose |
|----------|---------|
| `/api/export/attendance` | Attendance CSV |
| `/api/export/downtime-events` | Downtime CSV |
| `/api/export/employees` | Employees CSV |
| `/api/export/holds` | Holds CSV |
| `/api/export/work-orders` | Work orders CSV |
| (more) | |

## Next

- [02 — Dashboards](02-dashboards.md) (the live view; reports are snapshots of this)
- [09 — Admin](09-admin.md) (email config, schedule management)

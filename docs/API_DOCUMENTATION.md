# API Documentation - Manufacturing KPI Platform v1.0.4

**Base URL**: `http://localhost:8000` (development) | `https://api.yourdomain.com` (production)

**Interactive Documentation**: `/docs` (Swagger UI) | `/redoc` (ReDoc)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Production Endpoints](#production-endpoints)
3. [KPI Calculation Endpoints](#kpi-calculation-endpoints)
4. [Data Entry Endpoints](#data-entry-endpoints)
5. [Report Endpoints](#report-endpoints)
6. [Reference Data Endpoints](#reference-data-endpoints)
7. [Capacity Planning Endpoints](#capacity-planning-endpoints)
8. [Simulation V2 Endpoints](#simulation-v2-endpoints)
9. [Analytics Endpoints](#analytics-endpoints)
10. [Predictions Endpoints](#predictions-endpoints)
11. [Alert Endpoints](#alert-endpoints)
12. [Workflow Endpoints](#workflow-endpoints)
13. [Employee & Floating Pool Endpoints](#employee--floating-pool-endpoints)
14. [User Preferences & Filters Endpoints](#user-preferences--filters-endpoints)
15. [QR Code Endpoints](#qr-code-endpoints)
16. [Administrative Endpoints](#administrative-endpoints)
17. [Error Responses](#error-responses)
18. [Rate Limiting](#rate-limiting)

---

## Authentication

All endpoints except `/` and `/api/auth/*` require JWT authentication.

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### POST /api/auth/login

Authenticate user and receive access token.

**Request Body:**
```json
{
  "username": "operator1",
  "password": "securePassword123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": 5,
    "username": "operator1",
    "email": "operator1@example.com",
    "full_name": "John Operator",
    "role": "operator",
    "client_id": 1,
    "is_active": true,
    "created_at": "2026-01-01T12:00:00"
  }
}
```

### POST /api/auth/register

Register new user account (Admin only).

**Request Body:**
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "full_name": "New User",
  "role": "operator",
  "client_id": 1
}
```

**Response:** `201 Created`
```json
{
  "user_id": 10,
  "username": "newuser",
  "email": "newuser@example.com",
  "full_name": "New User",
  "role": "operator",
  "client_id": 1,
  "is_active": true,
  "created_at": "2026-01-25T12:00:00"
}
```

### GET /api/auth/me

Get current authenticated user information.

**Response:** `200 OK`
```json
{
  "user_id": 5,
  "username": "operator1",
  "email": "operator1@example.com",
  "full_name": "John Operator",
  "role": "operator",
  "client_id": 1,
  "is_active": true,
  "created_at": "2026-01-01T12:00:00"
}
```

### POST /api/auth/refresh

Refresh access token.

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

---

## Production Endpoints

### POST /api/production

Create new production entry with automatic KPI calculation.

**Request Body:**
```json
{
  "job_id": 1,
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2026-01-25",
  "work_order_number": "WO-2026-100",
  "units_produced": 250,
  "run_time_hours": 7.5,
  "employees_assigned": 3,
  "defect_count": 5,
  "scrap_count": 2,
  "notes": "Normal production run"
}
```

**Response:** `201 Created`
```json
{
  "entry_id": 42,
  "job_id": 1,
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2026-01-25",
  "work_order_number": "WO-2026-100",
  "units_produced": 250,
  "run_time_hours": 7.5,
  "employees_assigned": 3,
  "defect_count": 5,
  "scrap_count": 2,
  "efficiency_percentage": 82.35,
  "performance_percentage": 88.24,
  "is_estimated": false,
  "notes": "Normal production run",
  "entered_by": 5,
  "client_id": 1,
  "created_at": "2026-01-25T12:30:00",
  "updated_at": "2026-01-25T12:30:00"
}
```

### GET /api/production

List production entries with filters.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | int | Records to skip (default: 0) |
| `limit` | int | Max records (default: 100, max: 1000) |
| `start_date` | date | Filter by start date (YYYY-MM-DD) |
| `end_date` | date | Filter by end date (YYYY-MM-DD) |
| `product_id` | int | Filter by product |
| `shift_id` | int | Filter by shift |
| `job_id` | int | Filter by job |

**Example:** `GET /api/production?start_date=2026-01-01&end_date=2026-01-31&limit=50`

**Response:** `200 OK`
```json
[
  {
    "entry_id": 42,
    "job_id": 1,
    "product_id": 1,
    "shift_id": 2,
    "production_date": "2026-01-25",
    "work_order_number": "WO-2026-100",
    "units_produced": 250,
    "efficiency_percentage": 82.35,
    "performance_percentage": 88.24,
    "created_at": "2026-01-25T12:30:00"
  }
]
```

### GET /api/production/{entry_id}

Get detailed production entry with full KPI breakdown.

**Response:** `200 OK`
```json
{
  "entry_id": 42,
  "job_id": 1,
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2026-01-25",
  "work_order_number": "WO-2026-100",
  "units_produced": 250,
  "run_time_hours": 7.5,
  "employees_assigned": 3,
  "defect_count": 5,
  "scrap_count": 2,
  "efficiency_percentage": 82.35,
  "performance_percentage": 88.24,
  "quality_rate": 97.2,
  "oee": 70.5,
  "ideal_cycle_time": 0.25,
  "is_inferred": false,
  "confidence_score": 1.0,
  "notes": "Normal production run",
  "product_name": "Widget Standard",
  "shift_name": "Afternoon",
  "entered_by_name": "John Operator",
  "created_at": "2026-01-25T12:30:00",
  "updated_at": "2026-01-25T12:30:00"
}
```

### PUT /api/production/{entry_id}

Update production entry.

**Request Body:** (partial update allowed)
```json
{
  "units_produced": 260,
  "notes": "Updated after verification"
}
```

**Response:** `200 OK` (returns updated entry)

### DELETE /api/production/{entry_id}

Delete production entry (Supervisor/Admin only).

**Response:** `204 No Content`

### POST /api/production/upload/csv

Bulk upload production entries via CSV.

**Request:** `multipart/form-data`
- `file`: CSV file

**CSV Format:**
```csv
job_id,product_id,shift_id,production_date,work_order_number,units_produced,run_time_hours,employees_assigned,defect_count,scrap_count,notes
1,1,1,2026-01-25,WO-2026-001,250,7.5,3,5,2,Example entry
```

**Response:** `200 OK`
```json
{
  "total_rows": 10,
  "successful": 9,
  "failed": 1,
  "errors": [
    {
      "row": 5,
      "error": "Product ID 999 not found",
      "data": {"product_id": 999}
    }
  ],
  "created_entries": [43, 44, 45, 46, 47, 48, 49, 50, 51]
}
```

---

## KPI Calculation Endpoints

### GET /api/kpi/efficiency/{client_id}

Get efficiency KPI trend data.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `days` | int | Days to include (default: 30) |
| `shift_id` | int | Filter by shift |

**Response:** `200 OK`
```json
{
  "kpi_name": "efficiency",
  "client_id": 1,
  "period_days": 30,
  "current_value": 82.5,
  "previous_value": 78.2,
  "change_percent": 5.5,
  "trend": "improving",
  "data": [
    {"date": "2026-01-25", "value": 82.5, "is_estimated": false},
    {"date": "2026-01-24", "value": 81.2, "is_estimated": false}
  ]
}
```

### GET /api/kpi/performance/{client_id}

Get performance KPI trend data.

**Response:** Same structure as efficiency endpoint.

### GET /api/kpi/otd/{client_id}

Get On-Time Delivery KPI data.

**Response:** `200 OK`
```json
{
  "kpi_name": "otd",
  "client_id": 1,
  "period_days": 30,
  "current_value": 94.5,
  "true_otd": 91.2,
  "standard_otd": 94.5,
  "trend": "stable",
  "data": [
    {"date": "2026-01-25", "true_otd": 91.2, "standard_otd": 94.5}
  ]
}
```

### GET /api/kpi/quality/{client_id}

Get quality KPIs (PPM, DPMO, FPY, RTY).

**Response:** `200 OK`
```json
{
  "client_id": 1,
  "period_days": 30,
  "ppm": {
    "value": 2500,
    "trend": "improving"
  },
  "dpmo": {
    "value": 3500,
    "sigma_level": 4.2
  },
  "fpy": {
    "value": 96.5,
    "by_process": [
      {"process": "Assembly", "fpy": 97.2},
      {"process": "Testing", "fpy": 98.1}
    ]
  },
  "rty": {
    "value": 92.3
  }
}
```

### GET /api/kpi/availability/{client_id}

Get availability KPI (uptime vs downtime).

**Response:** `200 OK`
```json
{
  "kpi_name": "availability",
  "client_id": 1,
  "current_value": 87.5,
  "planned_downtime_hours": 4.0,
  "unplanned_downtime_hours": 2.5,
  "total_available_hours": 168.0,
  "trend": "stable"
}
```

### GET /api/kpi/absenteeism/{client_id}

Get absenteeism KPI with Bradford Factor.

**Response:** `200 OK`
```json
{
  "kpi_name": "absenteeism",
  "client_id": 1,
  "period_days": 30,
  "absenteeism_rate": 3.2,
  "employees_total": 50,
  "employees_absent_today": 2,
  "bradford_factor": {
    "average": 45.2,
    "high_risk_count": 3,
    "high_risk_threshold": 250
  },
  "by_department": [
    {"department": "Assembly", "rate": 2.8},
    {"department": "Quality", "rate": 4.1}
  ]
}
```

### GET /api/kpi/wip-aging/{client_id}

Get WIP aging data.

**Response:** `200 OK`
```json
{
  "kpi_name": "wip_aging",
  "client_id": 1,
  "total_wip_items": 45,
  "average_age_days": 3.5,
  "max_age_days": 12,
  "items_on_hold": 5,
  "aging_brackets": [
    {"bracket": "0-2 days", "count": 25},
    {"bracket": "3-5 days", "count": 12},
    {"bracket": "6-10 days", "count": 6},
    {"bracket": "10+ days", "count": 2}
  ]
}
```

### GET /api/kpi/all/{client_id}

Get all 10 KPIs in single request.

**Response:** `200 OK`
```json
{
  "client_id": 1,
  "generated_at": "2026-01-25T12:00:00",
  "period_days": 30,
  "kpis": {
    "efficiency": {"value": 82.5, "trend": "improving"},
    "performance": {"value": 88.2, "trend": "stable"},
    "availability": {"value": 87.5, "trend": "stable"},
    "quality_ppm": {"value": 2500, "trend": "improving"},
    "quality_dpmo": {"value": 3500, "sigma": 4.2},
    "fpy": {"value": 96.5},
    "rty": {"value": 92.3},
    "otd": {"value": 94.5, "true_otd": 91.2},
    "absenteeism": {"value": 3.2},
    "wip_aging": {"average_days": 3.5}
  }
}
```

### GET /api/kpi/predictions/{client_id}

Get KPI predictions with forecasting.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `kpi` | string | KPI to predict (efficiency, performance, etc.) |
| `days` | int | Days to forecast (default: 7, max: 30) |

**Response:** `200 OK`
```json
{
  "kpi": "efficiency",
  "client_id": 1,
  "forecast_days": 7,
  "current_value": 82.5,
  "predictions": [
    {
      "date": "2026-01-26",
      "predicted_value": 83.1,
      "confidence_interval": {"lower": 80.5, "upper": 85.7}
    },
    {
      "date": "2026-01-27",
      "predicted_value": 83.5,
      "confidence_interval": {"lower": 79.8, "upper": 87.2}
    }
  ],
  "model": "exponential_smoothing",
  "accuracy_score": 0.89
}
```

---

## Data Entry Endpoints

### Attendance

#### POST /api/attendance

Record attendance entry.

```json
{
  "employee_id": 10,
  "shift_id": 1,
  "attendance_date": "2026-01-25",
  "clock_in": "06:00:00",
  "clock_out": "14:00:00",
  "status": "present",
  "notes": ""
}
```

#### GET /api/attendance

List attendance records with filters.

### Downtime

#### POST /api/downtime

Record downtime event.

```json
{
  "job_id": 1,
  "machine_id": 5,
  "start_time": "2026-01-25T10:00:00",
  "end_time": "2026-01-25T10:45:00",
  "reason_code": "BREAKDOWN",
  "description": "Conveyor belt malfunction",
  "is_planned": false
}
```

### Quality

#### POST /api/quality

Record quality inspection.

```json
{
  "job_id": 1,
  "product_id": 1,
  "inspection_date": "2026-01-25",
  "units_inspected": 100,
  "units_passed": 97,
  "defect_count": 3,
  "defect_types": [
    {"type": "scratch", "count": 2},
    {"type": "dimension", "count": 1}
  ],
  "inspector_id": 5
}
```

### Hold/Resume

#### POST /api/holds

Place job on hold.

```json
{
  "job_id": 1,
  "hold_reason": "Material shortage",
  "hold_date": "2026-01-25T14:00:00",
  "expected_resume_date": "2026-01-26T08:00:00"
}
```

#### PUT /api/holds/{hold_id}/resume

Resume job from hold.

```json
{
  "resume_date": "2026-01-26T08:30:00",
  "resolution_notes": "Material received"
}
```

---

## Report Endpoints

### GET /api/reports/pdf

Generate PDF report.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `client_id` | int | Filter by client (optional) |
| `start_date` | date | Report start date |
| `end_date` | date | Report end date |
| `kpis` | string | Comma-separated KPI keys |

**Response:** PDF file download

### GET /api/reports/excel

Generate Excel report.

**Query Parameters:** Same as PDF endpoint.

**Response:** Excel file download (.xlsx)

### POST /api/reports/email

Send report via email.

```json
{
  "client_id": 1,
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "recipient_emails": ["manager@example.com", "supervisor@example.com"],
  "include_excel": true
}
```

**Response:** `200 OK`
```json
{
  "message": "Report sent successfully",
  "recipients": ["manager@example.com", "supervisor@example.com"]
}
```

### GET /api/reports/daily/{report_date}

Generate daily production report PDF.

---

## Reference Data Endpoints

### GET /api/clients

List all clients (Admin only).

### GET /api/products

List products for current client.

### GET /api/shifts

List shifts.

```json
[
  {"shift_id": 1, "shift_name": "Morning", "start_time": "06:00", "end_time": "14:00"},
  {"shift_id": 2, "shift_name": "Afternoon", "start_time": "14:00", "end_time": "22:00"},
  {"shift_id": 3, "shift_name": "Night", "start_time": "22:00", "end_time": "06:00"}
]
```

### GET /api/employees

List employees for current client.

### GET /api/work-orders

List work orders with status filtering.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | active, completed, on_hold, cancelled |
| `start_date` | date | Filter by date range |

### GET /api/jobs/{work_order_id}

List jobs for a work order.

---

## Capacity Planning Endpoints

Prefix: `/api/capacity` | Auth: Required

The capacity planning module provides a 13-worksheet workbook pattern with full CRUD for production lines, orders, standards, BOM, stock, scheduling, scenarios, and KPI tracking.

### Calendar

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/calendar` | List calendar entries for client |
| POST | `/api/capacity/calendar` | Create calendar entry |
| GET | `/api/capacity/calendar/{entry_id}` | Get calendar entry by ID |
| PUT | `/api/capacity/calendar/{entry_id}` | Update calendar entry |
| DELETE | `/api/capacity/calendar/{entry_id}` | Delete calendar entry |

### Production Lines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/lines` | List production lines |
| POST | `/api/capacity/lines` | Create production line |
| GET | `/api/capacity/lines/{line_id}` | Get production line by ID |
| PUT | `/api/capacity/lines/{line_id}` | Update production line |
| DELETE | `/api/capacity/lines/{line_id}` | Delete production line |

### Orders

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/orders` | List orders |
| POST | `/api/capacity/orders` | Create order |
| GET | `/api/capacity/orders/scheduling` | List orders with scheduling data |
| GET | `/api/capacity/orders/{order_id}` | Get order by ID |
| PUT | `/api/capacity/orders/{order_id}` | Update order |
| PATCH | `/api/capacity/orders/{order_id}/status` | Update order status only |
| DELETE | `/api/capacity/orders/{order_id}` | Delete order |

### Standards (SAM)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/standards` | List standards |
| POST | `/api/capacity/standards` | Create standard |
| GET | `/api/capacity/standards/style/{style_code}` | Get standards by style code |
| GET | `/api/capacity/standards/style/{style_code}/total-sam` | Get total SAM for style |
| GET | `/api/capacity/standards/{standard_id}` | Get standard by ID |
| PUT | `/api/capacity/standards/{standard_id}` | Update standard |
| DELETE | `/api/capacity/standards/{standard_id}` | Delete standard |

### Bill of Materials (BOM)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/bom` | List BOM headers |
| POST | `/api/capacity/bom` | Create BOM header |
| GET | `/api/capacity/bom/{header_id}` | Get BOM header by ID |
| PUT | `/api/capacity/bom/{header_id}` | Update BOM header |
| DELETE | `/api/capacity/bom/{header_id}` | Delete BOM header |
| GET | `/api/capacity/bom/{header_id}/details` | List BOM detail lines |
| POST | `/api/capacity/bom/{header_id}/details` | Add BOM detail line |
| PUT | `/api/capacity/bom/details/{detail_id}` | Update BOM detail line |
| DELETE | `/api/capacity/bom/details/{detail_id}` | Delete BOM detail line |
| POST | `/api/capacity/bom/explode` | Explode BOM for order requirements |

### Stock Snapshots

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/stock` | List stock snapshots |
| POST | `/api/capacity/stock` | Create stock snapshot |
| GET | `/api/capacity/stock/item/{item_code}/latest` | Get latest snapshot for item |
| GET | `/api/capacity/stock/item/{item_code}/available` | Get available quantity for item |
| GET | `/api/capacity/stock/shortages` | List items with stock shortages |
| GET | `/api/capacity/stock/{snapshot_id}` | Get snapshot by ID |
| PUT | `/api/capacity/stock/{snapshot_id}` | Update snapshot |
| DELETE | `/api/capacity/stock/{snapshot_id}` | Delete snapshot |

### Component Check (MRP)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/capacity/component-check/run` | Run component availability check |
| GET | `/api/capacity/component-check/shortages` | Get component shortage report |

### Analysis

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/capacity/analysis/calculate` | Calculate capacity analysis |
| GET | `/api/capacity/analysis/bottlenecks` | Identify capacity bottlenecks |

### Schedules

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/schedules` | List schedules |
| POST | `/api/capacity/schedules` | Create schedule |
| GET | `/api/capacity/schedules/{schedule_id}` | Get schedule by ID |
| POST | `/api/capacity/schedules/generate` | Auto-generate schedule |
| POST | `/api/capacity/schedules/{schedule_id}/commit` | Commit schedule to production |

### Scenarios (What-If)

Supports 8 scenario types: OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/scenarios` | List scenarios |
| POST | `/api/capacity/scenarios` | Create scenario |
| GET | `/api/capacity/scenarios/{scenario_id}` | Get scenario by ID |
| POST | `/api/capacity/scenarios/{scenario_id}/run` | Run scenario simulation |
| DELETE | `/api/capacity/scenarios/{scenario_id}` | Delete scenario |
| POST | `/api/capacity/scenarios/compare` | Compare multiple scenarios |

### KPI & Workbook

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/capacity/kpi/commitments` | List KPI commitments |
| GET | `/api/capacity/kpi/variance` | Get KPI variance report |
| GET | `/api/capacity/workbook/{client_id}` | Get full 13-worksheet workbook |
| PUT | `/api/capacity/workbook/{client_id}/{worksheet_name}` | Update specific worksheet |

---

## Simulation V2 Endpoints

Prefix: `/api/v2/simulation` | Auth: Required

Ephemeral production-line simulation engine (no database dependencies). Accepts JSON payloads describing lines, products, and parameters; returns simulation results in-memory.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/simulation/` | Get simulation engine info and capabilities |
| POST | `/api/v2/simulation/validate` | Validate simulation input payload |
| POST | `/api/v2/simulation/run` | Run a full simulation and return results |
| GET | `/api/v2/simulation/schema` | Get JSON schema for simulation input |

> **Note:** Simulation V1 (`/api/simulation/*`) is deprecated but still active due to the floating-pool dependency. Prefer V2 for new integrations.

---

## Analytics Endpoints

Prefix: `/api/analytics` | Auth: Required

Cross-KPI analytics with trends, predictions, comparisons, heatmaps, and Pareto analysis.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/trends` | Get KPI trend data over time |
| GET | `/api/analytics/predictions` | Get analytics-based predictions |
| GET | `/api/analytics/comparisons` | Compare KPIs across dimensions |
| GET | `/api/analytics/heatmap` | Get heatmap data (time x dimension) |
| GET | `/api/analytics/pareto` | Get Pareto analysis of defects/issues |

**Common Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `client_id` | int | Required. Client to query |
| `time_range` | string | Period: `7d`, `30d`, `90d`, `1y` |
| `kpi_type` | string | KPI key: `efficiency`, `quality`, `otd`, etc. |
| `group_by` | string | Grouping: `shift`, `product`, `line`, `day` |

---

## Predictions Endpoints

Prefix: `/api/predictions` | Auth: Required

Comprehensive KPI forecasting with confidence intervals, benchmarks, and health assessments.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/predictions/{kpi_type}` | Get prediction for specific KPI type |
| GET | `/api/predictions/dashboard/all` | Get predictions for all KPIs at once |
| GET | `/api/predictions/benchmarks` | Get KPI benchmarks and targets |
| GET | `/api/predictions/health/{kpi_type}` | Get health assessment for a KPI |
| POST | `/api/predictions/demo/seed` | Seed demo prediction data |

---

## Alert Endpoints

Prefix: `/api/alerts` | Auth: Required

Intelligent alert system with automatic generation, acknowledgment workflow, and configuration.

### Alert CRUD & Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/alerts/` | List alerts (filterable by severity, status, type) |
| GET | `/api/alerts/dashboard` | Get alert dashboard summary |
| GET | `/api/alerts/summary` | Get alert counts by severity/status |
| GET | `/api/alerts/{alert_id}` | Get alert by ID |
| POST | `/api/alerts/` | Create manual alert |
| POST | `/api/alerts/{alert_id}/acknowledge` | Acknowledge an alert |
| POST | `/api/alerts/{alert_id}/resolve` | Resolve an alert |
| POST | `/api/alerts/{alert_id}/dismiss` | Dismiss an alert |

### Alert Generation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/alerts/generate/check-all` | Run all alert generation checks |
| POST | `/api/alerts/generate/otd-risk` | Generate OTD risk alerts |
| POST | `/api/alerts/generate/quality` | Generate quality threshold alerts |
| POST | `/api/alerts/generate/capacity` | Generate capacity alerts |

### Alert Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/alerts/config/` | List alert configurations |
| POST | `/api/alerts/config/` | Create/update alert configuration |
| GET | `/api/alerts/history/accuracy` | Get alert prediction accuracy history |

---

## Workflow Endpoints

Prefix: `/api/workflow` | Auth: Required

Work order state machine with configurable transitions, templates, and analytics.

### Work Order Transitions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/workflow/work-orders/{work_order_id}/transition` | Transition work order state |
| POST | `/api/workflow/work-orders/{work_order_id}/validate` | Validate a transition before executing |
| GET | `/api/workflow/work-orders/{work_order_id}/allowed-transitions` | Get allowed transitions |
| GET | `/api/workflow/work-orders/{work_order_id}/history` | Get transition history |
| POST | `/api/workflow/bulk-transition` | Bulk transition multiple work orders |

### Workflow Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflow/config/{client_id}` | Get workflow config for client |
| PUT | `/api/workflow/config/{client_id}` | Update workflow config |
| POST | `/api/workflow/config/{client_id}/apply-template` | Apply workflow template |
| GET | `/api/workflow/templates` | List available workflow templates |

### Workflow Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflow/work-orders/{work_order_id}/elapsed-time` | Get elapsed time in current state |
| GET | `/api/workflow/work-orders/{work_order_id}/transition-times` | Get time per transition |
| GET | `/api/workflow/analytics/{client_id}/average-times` | Average time per workflow stage |
| GET | `/api/workflow/analytics/{client_id}/stage-durations` | Duration distribution per stage |
| GET | `/api/workflow/statistics/{client_id}/transitions` | Transition count statistics |
| GET | `/api/workflow/statistics/{client_id}/status-distribution` | Current status distribution |
| GET | `/api/workflow/transitions/{client_id}` | List all transitions for client |

---

## Employee & Floating Pool Endpoints

### Employees

Prefix: `/api/employees` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/employees` | Create employee |
| GET | `/api/employees` | List employees |
| GET | `/api/employees/floating-pool/list` | List floating pool employees |
| GET | `/api/employees/{employee_id}` | Get employee by ID |
| PUT | `/api/employees/{employee_id}` | Update employee |
| DELETE | `/api/employees/{employee_id}` | Delete employee |
| POST | `/api/employees/{employee_id}/floating-pool/assign` | Add to floating pool |
| POST | `/api/employees/{employee_id}/floating-pool/remove` | Remove from floating pool |
| POST | `/api/employees/{employee_id}/assign-client` | Assign employee to client |
| GET | `/api/clients/{client_id}/employees` | List employees by client |

### Floating Pool

Prefix: `/api/floating-pool` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/floating-pool` | Create floating pool assignment |
| GET | `/api/floating-pool` | List assignments |
| GET | `/api/floating-pool/available/list` | List available pool members |
| GET | `/api/floating-pool/check-availability/{employee_id}` | Check employee availability |
| GET | `/api/floating-pool/summary` | Get pool summary statistics |
| GET | `/api/floating-pool/{pool_id}` | Get assignment by ID |
| PUT | `/api/floating-pool/{pool_id}` | Update assignment |
| DELETE | `/api/floating-pool/{pool_id}` | Delete assignment |
| POST | `/api/floating-pool/assign` | Assign pool member to line |
| POST | `/api/floating-pool/unassign` | Unassign pool member |
| GET | `/api/floating-pool/simulation/insights` | Get simulation insights |
| POST | `/api/floating-pool/simulation/optimize-allocation` | Optimize pool allocation |
| POST | `/api/floating-pool/simulation/shift-coverage` | Simulate shift coverage |
| GET | `/api/clients/{client_id}/floating-pool` | List assignments by client |

---

## User Preferences & Filters Endpoints

### Preferences

Prefix: `/api/preferences` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/preferences/dashboard` | Get dashboard preferences |
| PUT | `/api/preferences/dashboard` | Update dashboard preferences |
| PATCH | `/api/preferences/dashboard` | Partial update dashboard preferences |
| GET | `/api/preferences/defaults/{role}` | Get default preferences for role |
| GET | `/api/preferences/defaults` | Get default preferences |
| POST | `/api/preferences/reset` | Reset preferences to role defaults |

### Saved Filters

Prefix: `/api/filters` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/filters` | List saved filters |
| POST | `/api/filters` | Create saved filter |
| GET | `/api/filters/default/{filter_type}` | Get default filter for type |
| GET | `/api/filters/statistics` | Get filter usage statistics |
| GET | `/api/filters/{filter_id}` | Get filter by ID |
| PUT | `/api/filters/{filter_id}` | Update filter |
| DELETE | `/api/filters/{filter_id}` | Delete filter |
| POST | `/api/filters/{filter_id}/apply` | Apply filter and get results |
| POST | `/api/filters/{filter_id}/set-default` | Set filter as default |
| POST | `/api/filters/{filter_id}/unset-default` | Remove default status |
| POST | `/api/filters/{filter_id}/duplicate` | Duplicate a filter |
| GET | `/api/filters/history/recent` | Get recent filter history |
| POST | `/api/filters/history` | Add filter history entry |
| DELETE | `/api/filters/history` | Clear filter history |

---

## QR Code Endpoints

Prefix: `/api/qr` | Auth: Required

QR code generation and lookup for work orders, products, jobs, and employees.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/qr/lookup` | Look up entity by QR code content |
| GET | `/api/qr/work-order/{work_order_id}/image` | Get QR code image for work order |
| GET | `/api/qr/product/{product_id}/image` | Get QR code image for product |
| GET | `/api/qr/job/{job_id}/image` | Get QR code image for job |
| GET | `/api/qr/employee/{employee_id}/image` | Get QR code image for employee |
| POST | `/api/qr/generate` | Generate QR code data for any entity |
| POST | `/api/qr/generate/image` | Generate and return QR code PNG image |

---

## Administrative Endpoints

### User Management

Prefix: `/api/users` | Auth: Required (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/users` | List all users |
| GET | `/api/users/{user_id}` | Get user by ID |
| POST | `/api/users` | Create user |
| PUT | `/api/users/{user_id}` | Update user |
| DELETE | `/api/users/{user_id}` | Delete user |

### Client Management

Prefix: `/api/clients` | Auth: Required (Admin)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/clients` | Create client |
| GET | `/api/clients` | List all clients |
| GET | `/api/clients/active/list` | List active clients only |
| GET | `/api/clients/{client_id}` | Get client by ID |
| PUT | `/api/clients/{client_id}` | Update client |
| DELETE | `/api/clients/{client_id}` | Delete client |

### Client Configuration

Prefix: `/api/client-config` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/client-config/` | Create client configuration |
| GET | `/api/client-config/defaults` | Get global defaults |
| GET | `/api/client-config/{client_id}` | Get config with defaults |
| GET | `/api/client-config/{client_id}/effective` | Get effective (merged) config |
| PUT | `/api/client-config/{client_id}` | Update client configuration |
| DELETE | `/api/client-config/{client_id}` | Delete client configuration |
| GET | `/api/client-config/` | List all client configurations |
| POST | `/api/client-config/{client_id}/reset-to-defaults` | Reset to defaults |

### Database Administration

Prefix: `/api/admin/database` | Auth: Required (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/database/status` | Get database connection status |
| GET | `/api/admin/database/providers` | List available DB providers |
| POST | `/api/admin/database/test-connection` | Test a database connection |
| POST | `/api/admin/database/migrate` | Start database migration |
| GET | `/api/admin/database/migration/status` | Get migration progress |
| GET | `/api/admin/database/full-status` | Get comprehensive DB status |

### Cache Management

Prefix: `/api/cache` | Auth: Required (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cache/stats` | Get cache statistics |
| POST | `/api/cache/clear` | Clear all caches |
| DELETE | `/api/cache/invalidate/{pattern}` | Invalidate cache by pattern |
| GET | `/api/cache/health` | Get cache health status |

### KPI Thresholds

Prefix: `/api/kpi-thresholds` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/kpi-thresholds` | Get KPI thresholds for client |
| PUT | `/api/kpi-thresholds` | Update KPI thresholds |
| DELETE | `/api/kpi-thresholds/{client_id}/{kpi_key}` | Delete client-specific threshold |

### Data Completeness

Prefix: `/api/data-completeness` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/data-completeness` | Get data completeness scores |
| GET | `/api/data-completeness/summary` | Get completeness summary |
| GET | `/api/data-completeness/categories` | Get completeness by category |

### My Shift (Operator Dashboard)

Prefix: `/api/my-shift` | Auth: Required

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/my-shift/summary` | Get current shift summary for operator |
| GET | `/api/my-shift/stats` | Get operator shift statistics |
| GET | `/api/my-shift/activity` | Get recent activity for operator |

### Health Checks

Prefix: `/health` | Auth: None

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/` | Basic health check |
| GET | `/health/database` | Database connectivity check |
| GET | `/health/pool` | Connection pool status |
| GET | `/health/detailed` | Detailed system health |
| GET | `/health/ready` | Kubernetes readiness probe |
| GET | `/health/live` | Kubernetes liveness probe |

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Validation error: units_produced must be positive"
}
```

### 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden

```json
{
  "detail": "Insufficient permissions"
}
```

### 404 Not Found

```json
{
  "detail": "Production entry not found"
}
```

### 422 Unprocessable Entity

```json
{
  "detail": [
    {
      "loc": ["body", "units_produced"],
      "msg": "value must be greater than 0",
      "type": "value_error"
    }
  ]
}
```

### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

| Endpoint Category | Limit |
|-------------------|-------|
| Authentication (`/api/auth/*`) | 5 requests/minute |
| API endpoints | 100 requests/minute |
| CSV upload | 10 requests/minute |
| Report generation | 5 requests/minute |

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706180400
```

---

## Pagination

List endpoints support pagination:

| Parameter | Description | Default | Max |
|-----------|-------------|---------|-----|
| `skip` | Records to skip | 0 | - |
| `limit` | Records per page | 100 | 1000 |

**Example:**
```
GET /api/production?skip=100&limit=50
```

---

## Additional Resources

- **Swagger UI**: `https://api.yourdomain.com/docs`
- **ReDoc**: `https://api.yourdomain.com/redoc`
- **OpenAPI Spec**: `https://api.yourdomain.com/openapi.json`

---

**Last Updated**: 2026-02-16
**API Version**: 1.0.4

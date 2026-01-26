# API Documentation - Manufacturing KPI Platform v1.0.0

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
7. [Error Responses](#error-responses)
8. [Rate Limiting](#rate-limiting)

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

**Last Updated**: 2026-01-25
**API Version**: 1.0.0

# API Documentation - Manufacturing KPI Platform

Base URL: `http://localhost:8000` (development)

## Authentication

All endpoints except `/` and `/api/auth/*` require JWT authentication.

Include token in request headers:
```
Authorization: Bearer <access_token>
```

### POST /api/auth/register

Register new user account.

**Request Body:**
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "securepassword123",
  "full_name": "John Doe",
  "role": "operator"
}
```

**Response:** `201 Created`
```json
{
  "user_id": 5,
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "role": "operator",
  "is_active": true,
  "created_at": "2025-12-31T12:00:00"
}
```

### POST /api/auth/login

Authenticate user and receive access token.

**Request Body:**
```json
{
  "username": "johndoe",
  "password": "securepassword123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "user_id": 5,
    "username": "johndoe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "role": "operator",
    "is_active": true,
    "created_at": "2025-12-31T12:00:00"
  }
}
```

### GET /api/auth/me

Get current authenticated user information.

**Response:** `200 OK`
```json
{
  "user_id": 5,
  "username": "johndoe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "role": "operator",
  "is_active": true,
  "created_at": "2025-12-31T12:00:00"
}
```

## Production Entries

### POST /api/production

Create new production entry with automatic KPI calculation.

**Request Body:**
```json
{
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2025-12-31",
  "work_order_number": "WO-2025-100",
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
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2025-12-31",
  "work_order_number": "WO-2025-100",
  "units_produced": 250,
  "run_time_hours": 7.5,
  "employees_assigned": 3,
  "defect_count": 5,
  "scrap_count": 2,
  "efficiency_percentage": 82.35,
  "performance_percentage": 88.24,
  "notes": "Normal production run",
  "entered_by": 5,
  "confirmed_by": null,
  "confirmation_timestamp": null,
  "created_at": "2025-12-31T12:30:00",
  "updated_at": "2025-12-31T12:30:00"
}
```

### GET /api/production

List production entries with optional filters.

**Query Parameters:**
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum records to return (default: 100)
- `start_date` (date): Filter by start date (YYYY-MM-DD)
- `end_date` (date): Filter by end date (YYYY-MM-DD)
- `product_id` (int): Filter by product ID
- `shift_id` (int): Filter by shift ID

**Example:** `/api/production?start_date=2025-12-01&end_date=2025-12-31&product_id=1`

**Response:** `200 OK`
```json
[
  {
    "entry_id": 42,
    "product_id": 1,
    "shift_id": 2,
    "production_date": "2025-12-31",
    "work_order_number": "WO-2025-100",
    "units_produced": 250,
    "run_time_hours": 7.5,
    "employees_assigned": 3,
    "efficiency_percentage": 82.35,
    "performance_percentage": 88.24,
    "created_at": "2025-12-31T12:30:00",
    "updated_at": "2025-12-31T12:30:00"
  }
]
```

### GET /api/production/{entry_id}

Get detailed production entry with full KPI breakdown.

**Response:** `200 OK`
```json
{
  "entry_id": 42,
  "product_id": 1,
  "shift_id": 2,
  "production_date": "2025-12-31",
  "work_order_number": "WO-2025-100",
  "units_produced": 250,
  "run_time_hours": 7.5,
  "employees_assigned": 3,
  "defect_count": 5,
  "scrap_count": 2,
  "efficiency_percentage": 82.35,
  "performance_percentage": 88.24,
  "notes": "Normal production run",
  "entered_by": 5,
  "confirmed_by": 2,
  "confirmation_timestamp": "2025-12-31T13:00:00",
  "created_at": "2025-12-31T12:30:00",
  "updated_at": "2025-12-31T13:00:00",
  "product_name": "Widget Standard",
  "shift_name": "Afternoon",
  "ideal_cycle_time": 0.25,
  "inferred_cycle_time": false,
  "total_available_hours": 22.5,
  "quality_rate": 96.8,
  "oee": 81.5
}
```

### PUT /api/production/{entry_id}

Update production entry and recalculate KPIs.

**Request Body:**
```json
{
  "units_produced": 260,
  "run_time_hours": 7.8,
  "notes": "Updated after verification",
  "confirmed_by": 2
}
```

**Response:** `200 OK` (same as GET response)

### DELETE /api/production/{entry_id}

Delete production entry (supervisor/admin only).

**Response:** `204 No Content`

### POST /api/production/upload/csv

Bulk upload production entries via CSV file.

**Request:** `multipart/form-data`
- `file`: CSV file

**CSV Format:**
```csv
product_id,shift_id,production_date,work_order_number,units_produced,run_time_hours,employees_assigned,defect_count,scrap_count,notes
1,1,2025-12-31,WO-2025-001,250,7.5,3,5,2,Example entry
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
      "data": {...}
    }
  ],
  "created_entries": [43, 44, 45, 46, 47, 48, 49, 50, 51]
}
```

## KPI Calculations

### GET /api/kpi/calculate/{entry_id}

Calculate and return KPIs for a specific production entry.

**Response:** `200 OK`
```json
{
  "entry_id": 42,
  "efficiency_percentage": 82.35,
  "performance_percentage": 88.24,
  "quality_rate": 96.8,
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false,
  "calculation_timestamp": "2025-12-31T14:00:00"
}
```

### GET /api/kpi/dashboard

Get aggregated KPI data for dashboard.

**Query Parameters:**
- `start_date` (date): Start date (default: 30 days ago)
- `end_date` (date): End date (default: today)

**Response:** `200 OK`
```json
[
  {
    "date": "2025-12-31",
    "total_units": 1250,
    "avg_efficiency": 84.5,
    "avg_performance": 89.2,
    "entry_count": 8
  },
  {
    "date": "2025-12-30",
    "total_units": 1180,
    "avg_efficiency": 82.1,
    "avg_performance": 87.8,
    "entry_count": 7
  }
]
```

## Reports

### GET /api/reports/daily/{report_date}

Generate and download daily production PDF report.

**Path Parameter:**
- `report_date`: Date in YYYY-MM-DD format

**Response:** `200 OK`
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename=daily_report_2025-12-31.pdf`

## Reference Data

### GET /api/products

List all active products.

**Response:** `200 OK`
```json
[
  {
    "product_id": 1,
    "product_code": "WDG-001",
    "product_name": "Widget Standard",
    "ideal_cycle_time": 0.25
  },
  {
    "product_id": 2,
    "product_code": "WDG-002",
    "product_name": "Widget Premium",
    "ideal_cycle_time": 0.35
  }
]
```

### GET /api/shifts

List all active shifts.

**Response:** `200 OK`
```json
[
  {
    "shift_id": 1,
    "shift_name": "Morning",
    "start_time": "06:00",
    "end_time": "14:00"
  },
  {
    "shift_id": 2,
    "shift_name": "Afternoon",
    "start_time": "14:00",
    "end_time": "22:00"
  }
]
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Validation error message"
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
  "detail": "Resource not found"
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

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

## Rate Limiting

Currently no rate limiting implemented. Consider adding for production:
- Authentication: 5 requests/minute per IP
- API endpoints: 100 requests/minute per user

## Pagination

List endpoints support pagination via `skip` and `limit` parameters:
- Default limit: 100
- Maximum limit: 1000

## Interactive API Documentation

FastAPI provides auto-generated interactive documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

# CSV Upload Endpoints Implementation

## Overview
Implemented 11 comprehensive CSV upload endpoints following the existing production CSV upload pattern. All endpoints include client-id validation, error handling, and security checks.

## Implementation Details

### File Location
- **Main File**: `backend/endpoints/csv_upload.py`
- **Router Registration**: `backend/main.py` (lines 1337-1341)

### Endpoints Implemented

#### 1. Downtime Events Upload
**Endpoint**: `POST /api/downtime/upload/csv`
- Tracks machine downtime events
- Required fields: product_id, shift_id, production_date, downtime_category, downtime_reason, duration_hours
- Optional fields: machine_id, work_order_number, notes, client_id
- Security: Client access validation

#### 2. WIP Hold/Resume Upload
**Endpoint**: `POST /api/holds/upload/csv`
- Tracks work-in-process holds
- Required fields: product_id, shift_id, hold_date, work_order_number, quantity_held, hold_reason, hold_category
- Optional fields: expected_resolution_date, notes, client_id
- Security: Client access validation

#### 3. Attendance Records Upload
**Endpoint**: `POST /api/attendance/upload/csv`
- Employee attendance tracking
- Required fields: employee_id, shift_id, attendance_date, status, scheduled_hours, actual_hours_worked
- Optional fields: absence_reason, notes
- Statuses: Present, Absent, Late, Leave

#### 4. Shift Coverage Upload
**Endpoint**: `POST /api/coverage/upload/csv`
- Shift staffing coverage
- Required fields: shift_id, coverage_date, required_employees, actual_employees
- Optional fields: notes

#### 5. Quality Inspections Upload
**Endpoint**: `POST /api/quality/upload/csv`
- Quality inspection records
- Required fields: product_id, shift_id, inspection_date, units_inspected, inspection_stage
- Optional fields: work_order_number, defects_found, defect_type, defect_category, scrap_units, rework_units, notes, client_id
- Inspection stages: Incoming, In-Process, Final
- Security: Client access validation

#### 6. Defect Details Upload
**Endpoint**: `POST /api/defects/upload/csv`
- Detailed defect tracking
- Required fields: defect_detail_id, quality_entry_id, client_id_fk, defect_type, defect_count
- Optional fields: defect_category, severity, location, description
- Severities: CRITICAL, MAJOR, MINOR
- Security: Client access validation (required)

#### 7. Work Orders Upload
**Endpoint**: `POST /api/work-orders/upload/csv`
- Work order management
- Required fields: work_order_id, client_id, style_model, planned_quantity
- Optional fields: actual_quantity, planned_start_date, actual_start_date, planned_ship_date, required_date, actual_delivery_date, ideal_cycle_time, calculated_cycle_time, status, priority, customer_po_number, notes, internal_notes
- Statuses: ACTIVE, ON_HOLD, COMPLETED, REJECTED, CANCELLED
- Priorities: HIGH, MEDIUM, LOW
- Security: Client access validation (required)

#### 8. Jobs Upload
**Endpoint**: `POST /api/jobs/upload/csv`
- Job line items (work order operations)
- Required fields: job_id, work_order_id, client_id_fk, operation_name, sequence_number
- Optional fields: operation_code, part_number, part_description, planned_quantity, completed_quantity, planned_hours, actual_hours, is_completed, completed_date, assigned_employee_id, assigned_shift_id, notes
- Security: Client access validation (required)

#### 9. Clients Upload (Admin Only)
**Endpoint**: `POST /api/clients/upload/csv`
- Client/customer management
- Required fields: client_id, client_name
- Optional fields: client_contact, client_email, client_phone, location, supervisor_id, planner_id, engineering_id, client_type, timezone, is_active
- Client types: Hourly Rate, Piece Rate, Hybrid, Service, Other
- Security: **ADMIN ONLY**

#### 10. Employees Upload (Admin Only)
**Endpoint**: `POST /api/employees/upload/csv`
- Employee management
- Required fields: employee_code, employee_name
- Optional fields: client_id_assigned (comma-separated), is_floating_pool, contact_phone, contact_email, position, hire_date
- Security: **ADMIN ONLY**

#### 11. Floating Pool Upload (Supervisor Only)
**Endpoint**: `POST /api/floating-pool/upload/csv`
- Floating pool employee assignments
- Required fields: employee_id
- Optional fields: available_from, available_to, current_assignment, notes
- Security: **ADMIN and POWERUSER ONLY**

## Security Features

### Multi-Tenant Isolation
- All endpoints with `client_id` field validate user access using `verify_client_access()`
- Users can only upload data for clients they have access to
- ADMIN and POWERUSER roles bypass client restrictions

### Role-Based Access Control
- **Public endpoints** (1-8): All authenticated users
- **Admin-only endpoints** (9-10): ADMIN role required
- **Supervisor endpoints** (11): ADMIN and POWERUSER roles required

### Error Handling
- Row-level error tracking with detailed error messages
- CSV validation (file extension check)
- Field validation using Pydantic models
- Returns summary with total/successful/failed counts
- Up to 100 errors returned for troubleshooting

## Response Format

All endpoints return `CSVUploadResponse`:

```json
{
  "total_rows": 150,
  "successful": 147,
  "failed": 3,
  "errors": [
    {
      "row": 25,
      "error": "Invalid product_id: 999",
      "data": {"product_id": "999", "shift_id": "1", ...}
    }
  ],
  "created_entries": [101, 102, 103, ...]
}
```

## CSV Format Examples

### Downtime Events CSV
```csv
product_id,shift_id,production_date,downtime_category,downtime_reason,duration_hours,machine_id,client_id
1,1,2024-01-15,Mechanical,Belt failure,2.5,MC-001,CLIENT-A
2,2,2024-01-15,Changeover,Style change,1.0,MC-002,CLIENT-A
```

### Attendance Records CSV
```csv
employee_id,shift_id,attendance_date,status,scheduled_hours,actual_hours_worked,absence_reason
101,1,2024-01-15,Present,8.0,8.0,
102,1,2024-01-15,Absent,8.0,0.0,Sick leave
103,2,2024-01-15,Late,8.0,7.5,Traffic
```

### Work Orders CSV
```csv
work_order_id,client_id,style_model,planned_quantity,status,priority,planned_ship_date
WO-001,CLIENT-A,BOOT-STYLE-X,1000,ACTIVE,HIGH,2024-02-01
WO-002,CLIENT-B,SHOE-MODEL-Y,500,ACTIVE,MEDIUM,2024-02-15
```

## Date/DateTime Formats

### Date Fields
- Format: `YYYY-MM-DD`
- Example: `2024-01-15`

### DateTime Fields
- Primary format: `YYYY-MM-DD HH:MM:SS`
- Fallback format: `YYYY-MM-DD` (time defaults to 00:00:00)
- Example: `2024-01-15 14:30:00`

## Integration with Existing Code

### CRUD Functions Used
- `crud.downtime.create_downtime_event()`
- `crud.hold.create_wip_hold()`
- `crud.attendance.create_attendance_record()`
- `crud.coverage.create_shift_coverage()`
- `crud.quality.create_quality_inspection()`
- `crud.defect_detail.create_defect_detail()`
- `crud.work_order.create_work_order()`
- `crud.job.create_job()`
- `crud.client.create_client()`
- `crud.employee.create_employee()`
- `crud.floating_pool.create_floating_pool_entry()`

### Pydantic Models Used
All endpoints use existing Pydantic Create models for validation:
- DowntimeEventCreate
- WIPHoldCreate
- AttendanceRecordCreate
- ShiftCoverageCreate
- QualityInspectionCreate
- DefectDetailCreate
- WorkOrderCreate
- JobCreate
- ClientCreate
- EmployeeCreate
- FloatingPoolCreate

### Middleware Integration
- `middleware.client_auth.verify_client_access()` - Validates user access to client data
- `auth.jwt.get_current_user()` - Authentication dependency
- `database.get_db()` - Database session management

## Testing Recommendations

### Unit Tests
1. Test valid CSV uploads for each endpoint
2. Test client_id validation for multi-tenant endpoints
3. Test role-based access control (Admin/Supervisor endpoints)
4. Test error handling (invalid data, missing fields)
5. Test date/datetime parsing with multiple formats

### Integration Tests
1. Upload CSV and verify database entries created
2. Upload mixed valid/invalid data and verify error reporting
3. Test cross-user access (User A cannot upload for Client B)
4. Test batch uploads (100+ rows)

### Sample Test CSVs
Create test CSV files in `/tests/fixtures/csv/`:
- `downtime_valid.csv`
- `downtime_invalid.csv`
- `attendance_valid.csv`
- `work_orders_valid.csv`
- etc.

## API Documentation

All endpoints automatically appear in FastAPI Swagger UI:
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Each endpoint includes:
- Complete field documentation
- Required/optional field indicators
- Data type specifications
- Example request/response schemas

## Performance Considerations

### Batch Processing
- CSV uploads process rows sequentially
- Large files (1000+ rows) may take time
- Consider chunking for very large uploads

### Database Optimization
- Each row is committed individually for error isolation
- Consider transaction batching for performance if needed
- Index product_id, shift_id, client_id for faster lookups

### Error Limits
- Maximum 100 errors returned (configurable)
- Prevents overwhelming response for files with many errors
- All errors logged to import_log table

## Future Enhancements

### Potential Improvements
1. **Async Processing**: Queue large CSV uploads for background processing
2. **Progress Tracking**: WebSocket updates for upload progress
3. **Data Validation**: Pre-upload validation endpoint
4. **Template Downloads**: Generate CSV templates for each endpoint
5. **Import History**: Track and display previous uploads
6. **Rollback Support**: Allow reverting failed imports
7. **Duplicate Detection**: Warn about duplicate entries
8. **Bulk Updates**: Support updating existing records via CSV

### Frontend Integration
Existing `CSVUploadDialog` component can be extended:
- Add dropdown to select upload type (Downtime, Attendance, etc.)
- Display type-specific field requirements
- Generate downloadable CSV templates
- Show upload history and statistics

## Maintenance Notes

### Adding New CSV Endpoints
To add a new CSV upload endpoint, follow this pattern:

1. **Create CRUD function** in `backend/crud/{resource}.py`
2. **Create Pydantic model** in `backend/models/{resource}.py`
3. **Add endpoint** to `backend/endpoints/csv_upload.py`:
   - Copy existing endpoint pattern
   - Update field mapping for CSV columns
   - Add client_id validation if needed
   - Add role-based access control if needed
4. **Update documentation** in this file

### Code Consistency
- All endpoints follow the same error handling pattern
- All use `CSVUploadResponse` model
- All validate file extension (.csv)
- All track row numbers starting at 2 (after header)
- All limit errors to 100 entries

## Related Files

- **Implementation**: `backend/endpoints/csv_upload.py`
- **Router Registration**: `backend/main.py`
- **CRUD Functions**: `backend/crud/*.py`
- **Pydantic Models**: `backend/models/*.py`
- **Security Middleware**: `backend/middleware/client_auth.py`
- **Reference Pattern**: `backend/main.py` (lines 510-571 - production CSV upload)

## Version History

- **v1.0.0** (2024-01-03): Initial implementation of 11 CSV upload endpoints
  - Downtime, Holds, Attendance, Coverage, Quality, Defects
  - Work Orders, Jobs, Clients, Employees, Floating Pool
  - Complete security and validation
  - Following existing production CSV pattern

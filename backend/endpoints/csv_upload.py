"""
CSV Upload Endpoints for All Resources
Provides CSV upload functionality for all major entities in the system
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from decimal import Decimal
import io
import csv

from backend.database import get_db
from auth.jwt import get_current_user
from backend.schemas.user import User, UserRole
from middleware.client_auth import verify_client_access
from backend.models.production import CSVUploadResponse

# Import CRUD functions
from crud.downtime import create_downtime_event
from crud.hold import create_wip_hold
from crud.attendance import create_attendance_record
from crud.coverage import create_shift_coverage
from crud.quality import create_quality_inspection
from crud.defect_detail import create_defect_detail
from crud.work_order import create_work_order
from crud.job import create_job
from crud.client import create_client
from crud.employee import create_employee
from crud.floating_pool import create_floating_pool_entry

# Import Pydantic models
from backend.models.downtime import DowntimeEventCreate
from backend.models.hold import WIPHoldCreate
from backend.models.attendance import AttendanceRecordCreate
from backend.models.coverage import ShiftCoverageCreate
from backend.models.quality import QualityInspectionCreate
from backend.models.defect_detail import DefectDetailCreate
from backend.models.work_order import WorkOrderCreate
from backend.models.job import JobCreate
from backend.models.client import ClientCreate
from backend.models.employee import EmployeeCreate
from backend.models.floating_pool import FloatingPoolCreate


router = APIRouter()


# ==================== 1. DOWNTIME EVENTS CSV UPLOAD ====================
@router.post("/api/downtime/upload/csv", response_model=CSVUploadResponse)
async def upload_downtime_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload downtime events via CSV

    Required CSV columns:
    - product_id (int)
    - shift_id (int)
    - production_date (YYYY-MM-DD)
    - downtime_category (str, max 50)
    - downtime_reason (str, max 255)
    - duration_hours (decimal, 0-24)

    Optional columns:
    - machine_id (str, max 50)
    - work_order_number (str, max 50)
    - notes (text)
    - client_id (str, for validation)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    # Read CSV
    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # SECURITY: Validate client_id if present
            if 'client_id' in row and row.get('client_id'):
                verify_client_access(current_user, row['client_id'])

            # Parse CSV row
            entry = DowntimeEventCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                production_date=datetime.strptime(row['production_date'], '%Y-%m-%d').date(),
                downtime_category=row['downtime_category'],
                downtime_reason=row['downtime_reason'],
                duration_hours=Decimal(row['duration_hours']),
                machine_id=row.get('machine_id') or None,
                work_order_number=row.get('work_order_number') or None,
                notes=row.get('notes')
            )

            # Create entry
            created = create_downtime_event(db, entry, current_user)
            created_ids.append(created.downtime_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 2. WIP HOLDS CSV UPLOAD ====================
@router.post("/api/holds/upload/csv", response_model=CSVUploadResponse)
async def upload_holds_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload WIP hold/resume events via CSV

    Required CSV columns:
    - product_id (int)
    - shift_id (int)
    - hold_date (YYYY-MM-DD)
    - work_order_number (str, max 50)
    - quantity_held (int, > 0)
    - hold_reason (str, max 255)
    - hold_category (str, max 50)

    Optional columns:
    - expected_resolution_date (YYYY-MM-DD)
    - notes (text)
    - client_id (str, for validation)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            if 'client_id' in row and row.get('client_id'):
                verify_client_access(current_user, row['client_id'])

            # Parse expected resolution date if present
            expected_date = None
            if row.get('expected_resolution_date'):
                expected_date = datetime.strptime(row['expected_resolution_date'], '%Y-%m-%d').date()

            entry = WIPHoldCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                hold_date=datetime.strptime(row['hold_date'], '%Y-%m-%d').date(),
                work_order_number=row['work_order_number'],
                quantity_held=int(row['quantity_held']),
                hold_reason=row['hold_reason'],
                hold_category=row['hold_category'],
                expected_resolution_date=expected_date,
                notes=row.get('notes')
            )

            created = create_wip_hold(db, entry, current_user)
            created_ids.append(created.hold_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 3. ATTENDANCE RECORDS CSV UPLOAD ====================
@router.post("/api/attendance/upload/csv", response_model=CSVUploadResponse)
async def upload_attendance_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload attendance records via CSV

    Required CSV columns:
    - employee_id (int)
    - shift_id (int)
    - attendance_date (YYYY-MM-DD)
    - status (str: Present, Absent, Late, Leave)
    - scheduled_hours (decimal, 0-24)
    - actual_hours_worked (decimal, 0-24)

    Optional columns:
    - absence_reason (str, max 100)
    - notes (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            entry = AttendanceRecordCreate(
                employee_id=int(row['employee_id']),
                shift_id=int(row['shift_id']),
                attendance_date=datetime.strptime(row['attendance_date'], '%Y-%m-%d').date(),
                status=row['status'],
                scheduled_hours=Decimal(row['scheduled_hours']),
                actual_hours_worked=Decimal(row['actual_hours_worked']),
                absence_reason=row.get('absence_reason'),
                notes=row.get('notes')
            )

            created = create_attendance_record(db, entry, current_user)
            created_ids.append(created.attendance_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 4. SHIFT COVERAGE CSV UPLOAD ====================
@router.post("/api/coverage/upload/csv", response_model=CSVUploadResponse)
async def upload_coverage_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload shift coverage records via CSV

    Required CSV columns:
    - shift_id (int)
    - coverage_date (YYYY-MM-DD)
    - required_employees (int, > 0)
    - actual_employees (int, >= 0)

    Optional columns:
    - notes (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            entry = ShiftCoverageCreate(
                shift_id=int(row['shift_id']),
                coverage_date=datetime.strptime(row['coverage_date'], '%Y-%m-%d').date(),
                required_employees=int(row['required_employees']),
                actual_employees=int(row['actual_employees']),
                notes=row.get('notes')
            )

            created = create_shift_coverage(db, entry, current_user)
            created_ids.append(created.coverage_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 5. QUALITY INSPECTIONS CSV UPLOAD ====================
@router.post("/api/quality/upload/csv", response_model=CSVUploadResponse)
async def upload_quality_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload quality inspection records via CSV

    Required CSV columns:
    - product_id (int)
    - shift_id (int)
    - inspection_date (YYYY-MM-DD)
    - units_inspected (int, > 0)
    - inspection_stage (str: Incoming, In-Process, Final)

    Optional columns:
    - work_order_number (str, max 50)
    - defects_found (int, >= 0)
    - defect_type (str, max 100)
    - defect_category (str, max 50)
    - scrap_units (int, >= 0)
    - rework_units (int, >= 0)
    - notes (text)
    - client_id (str, for validation)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            if 'client_id' in row and row.get('client_id'):
                verify_client_access(current_user, row['client_id'])

            entry = QualityInspectionCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                inspection_date=datetime.strptime(row['inspection_date'], '%Y-%m-%d').date(),
                work_order_number=row.get('work_order_number'),
                units_inspected=int(row['units_inspected']),
                defects_found=int(row.get('defects_found', 0)),
                defect_type=row.get('defect_type'),
                defect_category=row.get('defect_category'),
                scrap_units=int(row.get('scrap_units', 0)),
                rework_units=int(row.get('rework_units', 0)),
                inspection_stage=row['inspection_stage'],
                notes=row.get('notes')
            )

            created = create_quality_inspection(db, entry, current_user)
            created_ids.append(created.inspection_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 6. DEFECT DETAILS CSV UPLOAD ====================
@router.post("/api/defects/upload/csv", response_model=CSVUploadResponse)
async def upload_defects_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload defect detail records via CSV

    Required CSV columns:
    - defect_detail_id (str, max 50)
    - quality_entry_id (str)
    - client_id_fk (str)
    - defect_type (str: Stitching, Fabric Defect, etc.)
    - defect_count (int, >= 0)

    Optional columns:
    - defect_category (str, max 100)
    - severity (str: CRITICAL, MAJOR, MINOR)
    - location (str, max 255)
    - description (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # Validate client access
            verify_client_access(current_user, row['client_id_fk'])

            entry = DefectDetailCreate(
                defect_detail_id=row['defect_detail_id'],
                quality_entry_id=row['quality_entry_id'],
                client_id_fk=row['client_id_fk'],
                defect_type=row['defect_type'],
                defect_category=row.get('defect_category'),
                defect_count=int(row['defect_count']),
                severity=row.get('severity'),
                location=row.get('location'),
                description=row.get('description')
            )

            created = create_defect_detail(db, entry, current_user)
            created_ids.append(created.defect_detail_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 7. WORK ORDERS CSV UPLOAD ====================
@router.post("/api/work-orders/upload/csv", response_model=CSVUploadResponse)
async def upload_work_orders_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload work orders via CSV

    Required CSV columns:
    - work_order_id (str, max 50)
    - client_id (str)
    - style_model (str, max 100)
    - planned_quantity (int, > 0)

    Optional columns:
    - actual_quantity (int, >= 0)
    - planned_start_date (YYYY-MM-DD HH:MM:SS)
    - actual_start_date (YYYY-MM-DD HH:MM:SS)
    - planned_ship_date (YYYY-MM-DD HH:MM:SS)
    - required_date (YYYY-MM-DD HH:MM:SS)
    - actual_delivery_date (YYYY-MM-DD HH:MM:SS)
    - ideal_cycle_time (decimal)
    - calculated_cycle_time (decimal)
    - status (str: ACTIVE, ON_HOLD, COMPLETED, REJECTED, CANCELLED)
    - priority (str: HIGH, MEDIUM, LOW)
    - customer_po_number (str, max 100)
    - notes (text)
    - internal_notes (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # Validate client access
            verify_client_access(current_user, row['client_id'])

            # Parse optional datetime fields
            def parse_datetime(date_str):
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return datetime.strptime(date_str, '%Y-%m-%d')

            entry = WorkOrderCreate(
                work_order_id=row['work_order_id'],
                client_id=row['client_id'],
                style_model=row['style_model'],
                planned_quantity=int(row['planned_quantity']),
                actual_quantity=int(row.get('actual_quantity', 0)),
                planned_start_date=parse_datetime(row.get('planned_start_date')),
                actual_start_date=parse_datetime(row.get('actual_start_date')),
                planned_ship_date=parse_datetime(row.get('planned_ship_date')),
                required_date=parse_datetime(row.get('required_date')),
                actual_delivery_date=parse_datetime(row.get('actual_delivery_date')),
                ideal_cycle_time=Decimal(row['ideal_cycle_time']) if row.get('ideal_cycle_time') else None,
                calculated_cycle_time=Decimal(row['calculated_cycle_time']) if row.get('calculated_cycle_time') else None,
                status=row.get('status', 'ACTIVE'),
                priority=row.get('priority'),
                customer_po_number=row.get('customer_po_number'),
                notes=row.get('notes'),
                internal_notes=row.get('internal_notes')
            )

            created = create_work_order(db, entry, current_user)
            created_ids.append(created.work_order_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 8. JOBS CSV UPLOAD ====================
@router.post("/api/jobs/upload/csv", response_model=CSVUploadResponse)
async def upload_jobs_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload job line items via CSV

    Required CSV columns:
    - job_id (str)
    - work_order_id (str)
    - client_id_fk (str)
    - operation_name (str)
    - sequence_number (int)

    Optional columns:
    - operation_code (str)
    - part_number (str)
    - part_description (str)
    - planned_quantity (int)
    - completed_quantity (int)
    - planned_hours (decimal)
    - actual_hours (decimal)
    - is_completed (int: 0 or 1)
    - completed_date (YYYY-MM-DD HH:MM:SS)
    - assigned_employee_id (int)
    - assigned_shift_id (int)
    - notes (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # Validate client access
            verify_client_access(current_user, row['client_id_fk'])

            # Parse optional datetime
            completed_date = None
            if row.get('completed_date'):
                try:
                    completed_date = datetime.strptime(row['completed_date'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    completed_date = datetime.strptime(row['completed_date'], '%Y-%m-%d')

            entry = JobCreate(
                job_id=row['job_id'],
                work_order_id=row['work_order_id'],
                client_id_fk=row['client_id_fk'],
                operation_name=row['operation_name'],
                operation_code=row.get('operation_code'),
                sequence_number=int(row['sequence_number']),
                part_number=row.get('part_number'),
                part_description=row.get('part_description'),
                planned_quantity=int(row['planned_quantity']) if row.get('planned_quantity') else None,
                completed_quantity=int(row.get('completed_quantity', 0)),
                planned_hours=Decimal(row['planned_hours']) if row.get('planned_hours') else None,
                actual_hours=Decimal(row['actual_hours']) if row.get('actual_hours') else None,
                is_completed=int(row.get('is_completed', 0)),
                completed_date=completed_date,
                assigned_employee_id=int(row['assigned_employee_id']) if row.get('assigned_employee_id') else None,
                assigned_shift_id=int(row['assigned_shift_id']) if row.get('assigned_shift_id') else None,
                notes=row.get('notes')
            )

            created = create_job(db, entry, current_user)
            created_ids.append(created.job_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 9. CLIENTS CSV UPLOAD (ADMIN ONLY) ====================
@router.post("/api/clients/upload/csv", response_model=CSVUploadResponse)
async def upload_clients_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload clients via CSV (Admin only)

    Required CSV columns:
    - client_id (str, max 50)
    - client_name (str, max 255)

    Optional columns:
    - client_contact (str, max 255)
    - client_email (str, max 255)
    - client_phone (str, max 50)
    - location (str, max 255)
    - supervisor_id (str, max 50)
    - planner_id (str, max 50)
    - engineering_id (str, max 50)
    - client_type (str: Hourly Rate, Piece Rate, Hybrid, Service, Other)
    - timezone (str, max 50)
    - is_active (int: 0 or 1)
    """
    # SECURITY: Only ADMIN can create clients
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can upload clients"
        )

    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            entry = ClientCreate(
                client_id=row['client_id'],
                client_name=row['client_name'],
                client_contact=row.get('client_contact'),
                client_email=row.get('client_email'),
                client_phone=row.get('client_phone'),
                location=row.get('location'),
                supervisor_id=row.get('supervisor_id'),
                planner_id=row.get('planner_id'),
                engineering_id=row.get('engineering_id'),
                client_type=row.get('client_type', 'Piece Rate'),
                timezone=row.get('timezone', 'America/New_York'),
                is_active=int(row.get('is_active', 1))
            )

            created = create_client(db, entry, current_user)
            created_ids.append(created.client_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 10. EMPLOYEES CSV UPLOAD (ADMIN ONLY) ====================
@router.post("/api/employees/upload/csv", response_model=CSVUploadResponse)
async def upload_employees_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload employees via CSV (Admin only)

    Required CSV columns:
    - employee_code (str, max 50)
    - employee_name (str, max 255)

    Optional columns:
    - client_id_assigned (str, comma-separated for multi-client)
    - is_floating_pool (int: 0 or 1)
    - contact_phone (str, max 50)
    - contact_email (str, max 255)
    - position (str, max 100)
    - hire_date (YYYY-MM-DD HH:MM:SS)
    """
    # SECURITY: Only ADMIN can create employees
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can upload employees"
        )

    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # Parse hire date
            hire_date = None
            if row.get('hire_date'):
                try:
                    hire_date = datetime.strptime(row['hire_date'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    hire_date = datetime.strptime(row['hire_date'], '%Y-%m-%d')

            entry = EmployeeCreate(
                employee_code=row['employee_code'],
                employee_name=row['employee_name'],
                client_id_assigned=row.get('client_id_assigned'),
                is_floating_pool=int(row.get('is_floating_pool', 0)),
                contact_phone=row.get('contact_phone'),
                contact_email=row.get('contact_email'),
                position=row.get('position'),
                hire_date=hire_date
            )

            created = create_employee(db, entry, current_user)
            created_ids.append(created.employee_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )


# ==================== 11. FLOATING POOL CSV UPLOAD (SUPERVISOR ONLY) ====================
@router.post("/api/floating-pool/upload/csv", response_model=CSVUploadResponse)
async def upload_floating_pool_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload floating pool assignments via CSV (Supervisor/Admin only)

    Required CSV columns:
    - employee_id (int, must be marked as floating pool)

    Optional columns:
    - available_from (YYYY-MM-DD HH:MM:SS)
    - available_to (YYYY-MM-DD HH:MM:SS)
    - current_assignment (str, client_id or NULL)
    - notes (text)
    """
    # SECURITY: Only ADMIN and POWERUSER can manage floating pool
    if current_user.role not in [UserRole.ADMIN, UserRole.POWERUSER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors and administrators can manage floating pool"
        )

    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # Parse datetime fields
            def parse_datetime(date_str):
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return datetime.strptime(date_str, '%Y-%m-%d')

            entry = FloatingPoolCreate(
                employee_id=int(row['employee_id']),
                available_from=parse_datetime(row.get('available_from')),
                available_to=parse_datetime(row.get('available_to')),
                current_assignment=row.get('current_assignment'),
                notes=row.get('notes')
            )

            created = create_floating_pool_entry(db, entry, current_user)
            created_ids.append(created.pool_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
        created_entries=created_ids
    )

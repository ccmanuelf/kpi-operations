"""
Production Entry API Routes
All production CRUD and CSV upload endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import io
import csv
import json

from backend.database import get_db
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryResponse,
    ProductionEntryWithKPIs,
    CSVUploadResponse,
    KPICalculationResponse
)
from backend.models.import_log import BatchImportRequest, BatchImportResponse
from backend.crud.production import (
    create_production_entry,
    get_production_entry,
    get_production_entries,
    update_production_entry,
    delete_production_entry,
    get_production_entry_with_details,
    get_daily_summary
)
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.performance import calculate_performance, calculate_quality_rate
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.schemas.product import Product
from backend.schemas.shift import Shift


router = APIRouter(
    prefix="/api/production",
    tags=["Production"]
)


@router.post("", response_model=ProductionEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    entry: ProductionEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new production entry"""
    # Verify product exists
    product = db.query(Product).filter(Product.product_id == entry.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product ID {entry.product_id} not found"
        )

    # Verify shift exists
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shift ID {entry.shift_id} not found"
        )

    try:
        result = create_production_entry(db, entry, current_user)
        log_operation(logger, "CREATE", "production",
                     resource_id=str(result.production_entry_id),
                     user_id=current_user.user_id,
                     details={"units": entry.units_produced, "product_id": entry.product_id})
        return result
    except Exception as e:
        log_error(logger, "CREATE", "production", e, user_id=current_user.user_id)
        raise


@router.get("", response_model=List[ProductionEntryResponse])
def list_entries(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List production entries with filters"""
    return get_production_entries(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        shift_id=shift_id,
        client_id=client_id
    )


@router.get("/{entry_id}", response_model=ProductionEntryWithKPIs)
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get production entry with full KPI details"""
    entry = get_production_entry_with_details(db, entry_id, current_user)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )
    return entry


@router.put("/{entry_id}", response_model=ProductionEntryResponse)
def update_entry(
    entry_id: int,
    entry_update: ProductionEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update production entry"""
    try:
        updated_entry = update_production_entry(db, entry_id, entry_update, current_user)
        if not updated_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production entry {entry_id} not found"
            )
        log_operation(logger, "UPDATE", "production",
                     resource_id=str(entry_id),
                     user_id=current_user.user_id)
        return updated_entry
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "UPDATE", "production", e,
                 resource_id=str(entry_id), user_id=current_user.user_id)
        raise


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete production entry (supervisor only)"""
    try:
        success = delete_production_entry(db, entry_id, current_user)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production entry {entry_id} not found"
            )
        log_operation(logger, "DELETE", "production",
                     resource_id=str(entry_id),
                     user_id=current_user.user_id)
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "DELETE", "production", e,
                 resource_id=str(entry_id), user_id=current_user.user_id)
        raise


@router.post("/upload/csv", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload production entries via CSV - ALIGNED WITH PRODUCTION_ENTRY SCHEMA

    Required CSV columns:
    - client_id (str) - Multi-tenant isolation
    - product_id (int) - Product reference
    - shift_id (int) - Shift reference
    - production_date (YYYY-MM-DD) - Production date
    - units_produced (int, > 0)
    - run_time_hours (decimal)
    - employees_assigned (int)

    Optional columns:
    - shift_date (YYYY-MM-DD) - Defaults to production_date if not provided
    - work_order_id OR work_order_number (str)
    - job_id (str) - Job-level tracking
    - employees_present (int) - Actual employees present
    - defect_count (int)
    - scrap_count (int)
    - rework_count (int)
    - setup_time_hours (decimal)
    - downtime_hours (decimal)
    - maintenance_hours (decimal)
    - ideal_cycle_time (decimal)
    - notes (text)
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
    created_entries = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # SECURITY: Validate client_id - REQUIRED
            client_id = row.get('client_id')
            if not client_id:
                raise ValueError("client_id is required")
            from backend.middleware.client_auth import verify_client_access
            verify_client_access(current_user, client_id)

            # Parse production_date - REQUIRED
            prod_date_str = row.get('production_date')
            if not prod_date_str:
                raise ValueError("production_date is required")
            production_date = datetime.strptime(prod_date_str, '%Y-%m-%d').date()

            # Build data dict for legacy CSV mapping
            csv_data = {
                'client_id': client_id,
                'product_id': row.get('product_id'),
                'shift_id': row.get('shift_id'),
                'work_order_number': row.get('work_order_number') or row.get('work_order_id'),
                'job_id': row.get('job_id'),
                'production_date': production_date,
                'shift_date': datetime.strptime(row['shift_date'], '%Y-%m-%d').date() if row.get('shift_date') else None,
                'units_produced': row.get('units_produced'),
                'run_time_hours': row.get('run_time_hours'),
                'employees_assigned': row.get('employees_assigned'),
                'employees_present': row.get('employees_present'),
                'defect_count': row.get('defect_count', 0),
                'scrap_count': row.get('scrap_count', 0),
                'rework_count': row.get('rework_count', 0),
                'setup_time_hours': row.get('setup_time_hours'),
                'downtime_hours': row.get('downtime_hours'),
                'maintenance_hours': row.get('maintenance_hours'),
                'ideal_cycle_time': row.get('ideal_cycle_time'),
                'notes': row.get('notes')
            }

            # Use the from_legacy_csv method for proper field mapping
            entry = ProductionEntryCreate.from_legacy_csv(csv_data)

            # Create entry
            created = create_production_entry(db, entry, current_user)
            created_entries.append(created.production_entry_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    log_operation(logger, "CSV_UPLOAD", "production",
                 user_id=current_user.user_id,
                 details={"total": total_rows, "successful": successful, "failed": failed,
                         "filename": file.filename})

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors,
        created_entries=created_entries
    )


@router.post("/batch-import", response_model=BatchImportResponse)
def batch_import_production(
    request: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Batch import production entries after frontend validation.

    This endpoint expects pre-validated data from the CSVUploadDialog component.
    It creates multiple production entries and logs the import for audit purposes.
    """
    total_rows = len(request.entries)
    successful = 0
    failed = 0
    errors = []
    created_entries = []

    # Process each entry
    for idx, row in enumerate(request.entries):
        try:
            # Parse and validate the entry
            entry = ProductionEntryCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                production_date=row['production_date'],
                work_order_number=row.get('work_order_number') or None,
                units_produced=int(row['units_produced']),
                run_time_hours=Decimal(str(row['run_time_hours'])),
                employees_assigned=int(row['employees_assigned']),
                defect_count=int(row.get('defect_count', 0)),
                scrap_count=int(row.get('scrap_count', 0)),
                notes=row.get('notes')
            )

            # Create the entry
            created = create_production_entry(db, entry, current_user)
            created_entries.append(created.entry_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": idx + 1,
                "error": str(e),
                "data": row
            })

    # Create import log entry
    import_log_id = None
    try:
        error_json = json.dumps(errors) if errors else None

        # Insert into import_log table
        from sqlalchemy import text
        result = db.execute(
            text("""
            INSERT INTO import_log
            (user_id, rows_attempted, rows_succeeded, rows_failed, error_details, import_type)
            VALUES (:user_id, :attempted, :succeeded, :failed, :errors, 'batch_import')
            RETURNING log_id
            """),
            {
                'user_id': current_user.user_id,
                'attempted': total_rows,
                'succeeded': successful,
                'failed': failed,
                'errors': error_json
            }
        )

        log_row = result.fetchone()
        if log_row:
            import_log_id = log_row[0]

        db.commit()

    except Exception as log_error:
        # Don't fail the entire import if logging fails
        print(f"Warning: Failed to create import log: {log_error}")
        db.rollback()

    log_operation(logger, "BATCH_IMPORT", "production",
                 user_id=current_user.user_id,
                 details={"total": total_rows, "successful": successful, "failed": failed,
                         "import_log_id": import_log_id})

    return BatchImportResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],  # Limit error list to first 100
        created_entries=created_entries,
        import_log_id=import_log_id,
        import_timestamp=datetime.utcnow()
    )


# Import logs router (separate prefix)
import_logs_router = APIRouter(
    prefix="/api/import-logs",
    tags=["Production"]
)


@import_logs_router.get("")
def get_import_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import logs for the current user"""
    from sqlalchemy import text
    result = db.execute(
        text("""
        SELECT log_id, user_id, import_timestamp, file_name,
               rows_attempted, rows_succeeded, rows_failed,
               error_details, import_type
        FROM import_log
        WHERE user_id = :user_id
        ORDER BY import_timestamp DESC
        LIMIT :limit
        """),
        {'user_id': current_user.user_id, 'limit': limit}
    )

    logs = []
    for row in result:
        logs.append({
            'log_id': row[0],
            'user_id': row[1],
            'import_timestamp': row[2],
            'file_name': row[3],
            'rows_attempted': row[4],
            'rows_succeeded': row[5],
            'rows_failed': row[6],
            'error_details': row[7],
            'import_type': row[8]
        })

    return logs

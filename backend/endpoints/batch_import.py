"""
Batch Import Endpoint
Handles validated batch imports from the frontend CSV upload dialog
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from decimal import Decimal
import json

from backend.database import get_db
from backend.schemas.import_log import BatchImportRequest, BatchImportResponse
from backend.schemas.production import ProductionEntryCreate
from backend.schemas.user import User
from backend.auth.jwt import get_current_user
from backend.crud.production import create_production_entry


router = APIRouter()


@router.post("/api/production/batch-import", response_model=BatchImportResponse)
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
        db.execute(
            """
            INSERT INTO import_log
            (user_id, rows_attempted, rows_succeeded, rows_failed, error_details, import_type)
            VALUES (:user_id, :attempted, :succeeded, :failed, :errors, 'batch_import')
            RETURNING log_id
            """,
            {
                'user_id': current_user.user_id,
                'attempted': total_rows,
                'succeeded': successful,
                'failed': failed,
                'errors': error_json
            }
        )

        result = db.execute("SELECT lastval()")
        import_log_id = result.scalar()
        db.commit()

    except Exception as log_error:
        # Don't fail the entire import if logging fails
        print(f"Warning: Failed to create import log: {log_error}")
        db.rollback()

    return BatchImportResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],  # Limit error list to first 100
        created_entries=created_entries,
        import_log_id=import_log_id,
        import_timestamp=datetime.utcnow()
    )


@router.get("/api/import-logs")
def get_import_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import logs for the current user"""
    result = db.execute(
        """
        SELECT log_id, user_id, import_timestamp, file_name,
               rows_attempted, rows_succeeded, rows_failed,
               error_details, import_type
        FROM import_log
        WHERE user_id = :user_id
        ORDER BY import_timestamp DESC
        LIMIT :limit
        """,
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

"""
Break Times API Routes
CRUD endpoints for managing configurable break periods per shift.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Any, List, Optional

from backend.database import get_db
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)

from backend.schemas.break_time import BreakTimeCreate, BreakTimeUpdate, BreakTimeResponse
from backend.services.break_time_service import (
    create_break_time_record as create_break_time,
    list_break_times_for_shift as list_break_times,
    list_all_break_times_for_client as list_break_times_for_client,
    update_break_time_record as update_break_time,
    deactivate_break_time_record as deactivate_break_time,
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User

router = APIRouter(prefix="/api/break-times", tags=["Break Times"])


@router.get("", response_model=List[BreakTimeResponse])
def list_breaks(
    shift_id: Optional[int] = Query(None, description="Filter by shift ID"),
    client_id: Optional[str] = Query(None, max_length=50, description="Filter by client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List break times, optionally filtered by shift and/or client."""
    if shift_id is not None and client_id is not None:
        return list_break_times(db, shift_id, client_id)
    elif client_id is not None:
        return list_break_times_for_client(db, client_id)
    else:
        # Default: return breaks for the user's assigned client if available
        user_client = getattr(current_user, "client_id_assigned", None)
        if user_client:
            return list_break_times_for_client(db, user_client)
        # Admin with no specific client — return empty (require explicit filter)
        return []


@router.post("", response_model=BreakTimeResponse, status_code=status.HTTP_201_CREATED)
def create_break(
    break_data: BreakTimeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> Any:
    """Create a new break time entry (supervisor or admin required)."""
    try:
        result = create_break_time(db, break_data)
        log_operation(
            logger,
            "CREATE",
            "break_time",
            resource_id=str(result.break_id),
            user_id=current_user.user_id,
            details={"shift_id": break_data.shift_id, "break_name": break_data.break_name},
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "CREATE", "break_time", e, user_id=current_user.user_id)
        raise


@router.put("/{break_id}", response_model=BreakTimeResponse)
def update_break(
    break_id: int,
    break_data: BreakTimeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> Any:
    """Update an existing break time entry (supervisor or admin required)."""
    try:
        result = update_break_time(db, break_id, break_data)
        if not result:
            raise HTTPException(status_code=404, detail="Break time not found")
        log_operation(
            logger,
            "UPDATE",
            "break_time",
            resource_id=str(break_id),
            user_id=current_user.user_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "UPDATE", "break_time", e, resource_id=str(break_id), user_id=current_user.user_id)
        raise


@router.delete("/{break_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_break(
    break_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """Soft-delete a break time entry (supervisor or admin required)."""
    try:
        success = deactivate_break_time(db, break_id)
        if not success:
            raise HTTPException(status_code=404, detail="Break time not found")
        log_operation(
            logger,
            "DELETE",
            "break_time",
            resource_id=str(break_id),
            user_id=current_user.user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "DELETE", "break_time", e, resource_id=str(break_id), user_id=current_user.user_id)
        raise

"""
Shifts API Routes
Manage client-configurable shifts (create, read, update, soft-delete).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.utils.logging_utils import get_module_logger
from backend.schemas.shift import ShiftCreate, ShiftUpdate, ShiftResponse
from backend.services.shift_service import (
    create_shift_record as create_shift,
    list_client_shifts as list_shifts,
    get_shift_by_id as get_shift,
    update_shift_record as update_shift,
    deactivate_shift_record as deactivate_shift,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/shifts", tags=["Shifts"])


@router.get("/", response_model=List[ShiftResponse])
def list_shifts_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ShiftResponse]:
    """
    List active shifts for a client.

    Returns all active shifts ordered by shift_name.
    """
    logger.info("Listing shifts for client_id=%s by user=%s", client_id, current_user.user_id)
    return list_shifts(db, client_id)


@router.post("/", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def create_shift_endpoint(
    data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ShiftResponse:
    """
    Create a new shift for a client.

    Requires supervisor or admin role.
    """
    try:
        result = create_shift(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    logger.info("Created shift '%s' for client '%s'", data.shift_name, data.client_id)
    return result


@router.get("/{shift_id}", response_model=ShiftResponse)
def get_shift_endpoint(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShiftResponse:
    """
    Get a single shift by ID.
    """
    result = get_shift(db, shift_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shift not found")
    return result


@router.put("/{shift_id}", response_model=ShiftResponse)
def update_shift_endpoint(
    shift_id: int,
    data: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ShiftResponse:
    """
    Update a shift entry.

    Requires supervisor or admin role.
    """
    result = update_shift(db, shift_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shift not found")
    return result


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift_endpoint(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Deactivate a shift (soft delete).

    Requires supervisor or admin role.
    """
    success = deactivate_shift(db, shift_id)
    if not success:
        raise HTTPException(status_code=404, detail="Shift not found")

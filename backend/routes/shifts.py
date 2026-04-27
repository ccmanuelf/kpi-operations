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
from backend.schemas.shift import (
    ShiftCreate,
    ShiftUpdate,
    ShiftResponse,
    ShiftResponseWithWarnings,
    OverlapCheckRequest,
    OverlapCheckResponse,
    OverlapInfo,
)
from backend.services.shift_service import (
    create_shift_record as create_shift,
    list_client_shifts as list_shifts,
    get_shift_by_id as get_shift,
    update_shift_record as update_shift,
    deactivate_shift_record as deactivate_shift,
    check_overlaps,
    format_overlap_warnings,
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


@router.post("/", response_model=ShiftResponseWithWarnings, status_code=status.HTTP_201_CREATED)
def create_shift_endpoint(
    data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> dict:
    """
    Create a new shift for a client.

    Requires supervisor or admin role.
    The shift is always saved (soft validation). If the new shift overlaps
    with existing shifts, a ``warnings`` list is included in the response.
    """
    # Check for overlaps BEFORE saving (so we can report them)
    overlapping = check_overlaps(db, data.client_id, data.start_time, data.end_time)
    warnings = format_overlap_warnings(overlapping)

    try:
        result = create_shift(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    logger.info("Created shift '%s' for client '%s'", data.shift_name, data.client_id)
    return {"data": ShiftResponse.model_validate(result), "warnings": warnings}


@router.post(
    "/check-overlap",
    response_model=OverlapCheckResponse,
    summary="Check shift overlap",
)
def check_overlap_endpoint(
    body: OverlapCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Check whether a proposed shift time range overlaps with existing shifts.

    This is a read-only pre-validation endpoint. It does NOT create or modify
    any shifts.
    """
    overlapping = check_overlaps(
        db,
        body.client_id,
        body.start_time,
        body.end_time,
        exclude_shift_id=body.exclude_shift_id,
    )
    overlap_infos = [OverlapInfo.model_validate(s) for s in overlapping]
    logger.info(
        "Overlap check for client '%s' (%s-%s): %d overlap(s)",
        body.client_id,
        body.start_time,
        body.end_time,
        len(overlap_infos),
    )
    return {"has_overlaps": len(overlap_infos) > 0, "overlaps": overlap_infos}


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


@router.put("/{shift_id}", response_model=ShiftResponseWithWarnings)
def update_shift_endpoint(
    shift_id: int,
    data: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> dict:
    """
    Update a shift entry.

    Requires supervisor or admin role.
    The shift is always saved (soft validation). If the updated time range
    overlaps with other shifts, a ``warnings`` list is included in the
    response.
    """
    # First fetch the existing shift to determine effective start/end
    existing = get_shift(db, shift_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Shift not found")

    effective_start = data.start_time if data.start_time is not None else existing.start_time
    effective_end = data.end_time if data.end_time is not None else existing.end_time

    # Check overlaps (exclude self)
    overlapping = check_overlaps(db, existing.client_id, effective_start, effective_end, exclude_shift_id=shift_id)
    warnings = format_overlap_warnings(overlapping)

    result = update_shift(db, shift_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shift not found")

    return {"data": ShiftResponse.model_validate(result), "warnings": warnings}


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

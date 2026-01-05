"""
Shift Coverage API Routes
PHASE 3: Shift coverage and capacity tracking
All endpoints enforce multi-tenant client filtering
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from backend.database import get_db
from backend.schemas.coverage import (
    ShiftCoverageCreate,
    ShiftCoverageUpdate,
    ShiftCoverageResponse
)
from crud.coverage import (
    create_shift_coverage,
    get_shift_coverage,
    get_shift_coverages,
    update_shift_coverage,
    delete_shift_coverage
)
from auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/coverage",
    tags=["Shift Coverage"]
)


@router.post("", response_model=ShiftCoverageResponse, status_code=status.HTTP_201_CREATED)
def create_coverage(
    coverage: ShiftCoverageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new shift coverage record
    SECURITY: Enforces client filtering through user authentication
    """
    return create_shift_coverage(db, coverage, current_user)


@router.get("", response_model=List[ShiftCoverageResponse])
def list_coverage(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List shift coverage records with filters
    SECURITY: Returns only coverage for user's authorized clients
    """
    return get_shift_coverages(
        db, current_user=current_user, skip=skip, limit=limit,
        start_date=start_date, end_date=end_date, shift_id=shift_id
    )


@router.get("/{coverage_id}", response_model=ShiftCoverageResponse)
def get_coverage(
    coverage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get shift coverage record by ID
    SECURITY: Verifies user has access to this coverage record
    """
    coverage = get_shift_coverage(db, coverage_id, current_user)
    if not coverage:
        raise HTTPException(status_code=404, detail="Shift coverage not found")
    return coverage


@router.get("/by-shift/{shift_id}", response_model=List[ShiftCoverageResponse])
def get_coverage_by_shift(
    shift_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all coverage records for a specific shift
    SECURITY: Returns only coverage for user's authorized clients
    """
    return get_shift_coverages(
        db,
        current_user=current_user,
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )


@router.put("/{coverage_id}", response_model=ShiftCoverageResponse)
def update_coverage(
    coverage_id: int,
    coverage_update: ShiftCoverageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update shift coverage record
    SECURITY: Verifies user has access to this coverage record
    """
    updated = update_shift_coverage(db, coverage_id, coverage_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Shift coverage not found")
    return updated


@router.delete("/{coverage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coverage(
    coverage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete shift coverage record (supervisor only)
    SECURITY: Supervisor/admin only, verifies client access
    """
    success = delete_shift_coverage(db, coverage_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Shift coverage not found")

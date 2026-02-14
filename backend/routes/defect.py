"""
Defect Detail API Routes
Detailed defect tracking for quality inspections
All endpoints enforce multi-tenant client filtering
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.database import get_db
from backend.models.defect_detail import (
    DefectDetailCreate,
    DefectDetailUpdate,
    DefectDetailResponse,
    DefectSummaryResponse,
)
from backend.crud.defect_detail import (
    create_defect_detail,
    get_defect_detail,
    get_defect_details,
    get_defect_details_by_quality_entry,
    update_defect_detail,
    delete_defect_detail,
    get_defect_summary_by_type,
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(prefix="/api/defects", tags=["Defect Details"])


@router.post("", response_model=DefectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_defect(
    defect: DefectDetailCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create new defect detail record
    SECURITY: Enforces client filtering - user must have access to client_id_fk
    """
    defect_data = defect.model_dump()
    return create_defect_detail(db, defect_data, current_user)


@router.get("", response_model=List[DefectDetailResponse])
def list_defects(
    quality_entry_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List defect details with optional quality entry filter
    SECURITY: Returns only defects for user's authorized clients
    """
    return get_defect_details(db, current_user, quality_entry_id, skip, limit)


@router.get("/{defect_detail_id}", response_model=DefectDetailResponse)
def get_defect(defect_detail_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get defect detail by ID
    SECURITY: Verifies user has access to defect's client
    """
    defect = get_defect_detail(db, defect_detail_id, current_user)
    if not defect:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")
    return defect


@router.get("/by-quality-entry/{quality_entry_id}", response_model=List[DefectDetailResponse])
def get_quality_entry_defects(
    quality_entry_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all defect details for a specific quality entry
    SECURITY: Returns only defects for user's authorized clients
    """
    return get_defect_details_by_quality_entry(db, quality_entry_id, current_user)


@router.put("/{defect_detail_id}", response_model=DefectDetailResponse)
def update_defect(
    defect_detail_id: str,
    defect_update: DefectDetailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update defect detail record
    SECURITY: Verifies user has access to defect's client
    """
    defect_data = defect_update.model_dump(exclude_unset=True)
    updated = update_defect_detail(db, defect_detail_id, defect_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")
    return updated


@router.delete("/{defect_detail_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_defect(
    defect_detail_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete defect detail record (supervisor only)
    SECURITY: Only deletes if user has access to defect's client
    """
    success = delete_defect_detail(db, defect_detail_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")


@router.get("/summary/by-type", response_model=List[DefectSummaryResponse])
def get_defect_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get defect summary grouped by type with optional date filtering
    SECURITY: Returns only defects for user's authorized clients
    Useful for Pareto analysis and identifying top defect categories
    """
    return get_defect_summary_by_type(db, current_user, start_date, end_date)

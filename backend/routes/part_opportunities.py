"""
Part Opportunities API Routes
All part opportunities CRUD endpoints (KPI #5: DPMO Calculation)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.database import get_db
from backend.models.part_opportunities import (
    PartOpportunityCreate,
    PartOpportunityUpdate,
    PartOpportunityResponse,
    BulkImportRequest,
    BulkImportResponse
)
from backend.crud.part_opportunities import (
    create_part_opportunity,
    get_part_opportunity,
    get_part_opportunities,
    get_part_opportunities_by_category,
    update_part_opportunity,
    delete_part_opportunity,
    bulk_import_opportunities
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/part-opportunities",
    tags=["Part Opportunities"]
)


@router.post("", response_model=PartOpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_part_opportunity_endpoint(
    part: PartOpportunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new part opportunity record
    SECURITY: Enforces client filtering
    """
    part_data = part.model_dump()
    return create_part_opportunity(db, part_data, current_user)


@router.get("", response_model=List[PartOpportunityResponse])
def list_part_opportunities(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List part opportunities
    SECURITY: Returns only part opportunities for user's authorized clients
    """
    return get_part_opportunities(db, current_user, skip, limit)


@router.get("/category/{category}", response_model=List[PartOpportunityResponse])
def get_part_opportunities_by_category_endpoint(
    category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all part opportunities for a specific category
    SECURITY: Returns only part opportunities for user's authorized clients
    """
    return get_part_opportunities_by_category(db, category, current_user)


@router.get("/{part_number}", response_model=PartOpportunityResponse)
def get_part_opportunity_endpoint(
    part_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get part opportunity by part number
    SECURITY: Verifies user has access to part's client
    """
    part = get_part_opportunity(db, part_number, current_user)
    if not part:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")
    return part


@router.put("/{part_number}", response_model=PartOpportunityResponse)
def update_part_opportunity_endpoint(
    part_number: str,
    part_update: PartOpportunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update part opportunity
    SECURITY: Verifies user has access to part's client
    """
    part_data = part_update.model_dump(exclude_unset=True)
    updated = update_part_opportunity(db, part_number, part_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")
    return updated


@router.delete("/{part_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part_opportunity_endpoint(
    part_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete part opportunity (supervisor only)
    SECURITY: Only deletes if user has access to part's client
    """
    success = delete_part_opportunity(db, part_number, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_part_opportunities(
    import_request: BulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk import part opportunities (for CSV imports)
    SECURITY: Validates client_id_fk for all records
    """
    opportunities_list = [opp.model_dump() for opp in import_request.opportunities]
    result = bulk_import_opportunities(db, opportunities_list, current_user)

    return BulkImportResponse(
        success_count=result["success_count"],
        failure_count=result["failure_count"],
        errors=result["errors"],
        total_processed=result["success_count"] + result["failure_count"]
    )

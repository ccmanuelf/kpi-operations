"""
Capacity Planning - Standards Endpoints

Production standards (SAM data) CRUD operations.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE
from backend.crud.capacity import standards

from ._models import (
    StandardCreate,
    StandardUpdate,
    StandardResponse,
    TotalSAMResponse,
    MessageResponse,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

standards_router = APIRouter()


@standards_router.get("/standards", response_model=List[StandardResponse])
def list_standards(
    client_id: str = Query(..., description="Client ID"),
    department: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get production standards for a client."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards(db, client_id, skip, limit, department)


@standards_router.post("/standards", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_standard(
    standard: StandardCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new production standard."""
    verify_client_access(current_user, client_id, db)
    return standards.create_standard(
        db,
        client_id,
        standard.style_code,
        standard.operation_code,
        standard.sam_minutes,
        standard.operation_name,
        standard.department,
        standard.setup_time_minutes,
        standard.machine_time_minutes,
        standard.manual_time_minutes,
        standard.notes,
    )


@standards_router.get("/standards/style/{style_code}", response_model=List[StandardResponse])
def get_standards_by_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all standards for a specific style."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards_by_style(db, client_id, style_code)


@standards_router.get("/standards/style/{style_code}/total-sam", response_model=TotalSAMResponse)
def get_total_sam_for_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total SAM minutes for a style."""
    verify_client_access(current_user, client_id, db)
    total = standards.get_total_sam_for_style(db, client_id, style_code, department)
    return {"style_code": style_code, "total_sam_minutes": total, "department": department}


@standards_router.get("/standards/{standard_id}", response_model=StandardResponse, responses={404: {"description": "Standard not found"}})
def get_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.get_standard(db, client_id, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@standards_router.put("/standards/{standard_id}", response_model=StandardResponse, responses={404: {"description": "Standard not found"}})
def update_standard(
    standard_id: int,
    update: StandardUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.update_standard(db, client_id, standard_id, **update.model_dump(exclude_unset=True))
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@standards_router.delete("/standards/{standard_id}", response_model=MessageResponse, responses={404: {"description": "Standard not found"}})
def delete_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a production standard."""
    verify_client_access(current_user, client_id, db)
    if not standards.delete_standard(db, client_id, standard_id):
        raise HTTPException(status_code=404, detail="Standard not found")
    return {"message": "Standard deleted"}

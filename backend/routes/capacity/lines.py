"""
Capacity Planning - Production Lines Endpoints

Production line CRUD operations (capacity specifications, efficiency factors).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE
from backend.crud.capacity import production_lines

from ._models import (
    ProductionLineCreate,
    ProductionLineUpdate,
    ProductionLineResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)

lines_router = APIRouter()


@lines_router.get("/lines", response_model=List[ProductionLineResponse])
def list_production_lines(
    client_id: str = Query(..., description="Client ID"),
    include_inactive: bool = False,
    department: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get production lines for a client."""
    verify_client_access(current_user, client_id, db)
    if department:
        return production_lines.get_lines_by_department(db, client_id, department, not include_inactive)
    return production_lines.get_production_lines(db, client_id, skip, limit, include_inactive)


@lines_router.post("/lines", response_model=ProductionLineResponse, status_code=status.HTTP_201_CREATED)
def create_production_line(
    line: ProductionLineCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new production line."""
    verify_client_access(current_user, client_id, db)
    return production_lines.create_production_line(
        db,
        client_id,
        line.line_code,
        line.line_name,
        line.department,
        line.standard_capacity_units_per_hour,
        line.max_operators,
        line.efficiency_factor,
        line.absenteeism_factor,
        line.is_active,
        line.notes,
    )


@lines_router.get("/lines/{line_id}", response_model=ProductionLineResponse, responses={404: {"description": "Production line not found"}})
def get_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.get_production_line(db, client_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@lines_router.put("/lines/{line_id}", response_model=ProductionLineResponse, responses={404: {"description": "Production line not found"}})
def update_production_line(
    line_id: int,
    update: ProductionLineUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.update_production_line(db, client_id, line_id, **update.model_dump(exclude_unset=True))
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@lines_router.delete("/lines/{line_id}", response_model=MessageResponse, responses={404: {"description": "Production line not found"}})
def delete_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a production line."""
    verify_client_access(current_user, client_id, db)
    if not production_lines.delete_production_line(db, client_id, line_id, soft_delete):
        raise HTTPException(status_code=404, detail="Production line not found")
    return {"message": "Production line deleted"}

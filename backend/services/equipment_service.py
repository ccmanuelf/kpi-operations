"""
Equipment Service
Thin service layer wrapping Equipment CRUD operations.
Routes should import from this module instead of backend.crud.equipment directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.crud.equipment import (
    create_equipment,
    list_equipment,
    list_shared_equipment,
    get_equipment,
    update_equipment,
    deactivate_equipment,
    get_equipment_by_code,
)
from backend.orm.equipment import Equipment
from backend.schemas.equipment import EquipmentCreate, EquipmentUpdate


def create_equipment_record(db: Session, data: EquipmentCreate) -> Equipment:
    """Create a new equipment record."""
    return create_equipment(db, data)


def list_equipment_records(
    db: Session,
    client_id: str,
    line_id: Optional[int] = None,
    include_inactive: bool = False,
) -> List[Equipment]:
    """List equipment for a client, optionally filtered by production line."""
    return list_equipment(db, client_id, line_id=line_id, include_inactive=include_inactive)


def list_shared_equipment_records(db: Session, client_id: str) -> List[Equipment]:
    """List shared equipment for a client."""
    return list_shared_equipment(db, client_id)


def get_equipment_by_id(db: Session, equipment_id: int) -> Optional[Equipment]:
    """Get equipment by ID."""
    return get_equipment(db, equipment_id)


def update_equipment_record(db: Session, equipment_id: int, data: EquipmentUpdate) -> Optional[Equipment]:
    """Update an equipment record."""
    return update_equipment(db, equipment_id, data)


def deactivate_equipment_record(db: Session, equipment_id: int) -> bool:
    """Deactivate an equipment record."""
    return deactivate_equipment(db, equipment_id)


def get_equipment_record_by_code(db: Session, client_id: str, equipment_code: str) -> Optional[Equipment]:
    """Get equipment by code within a client."""
    return get_equipment_by_code(db, client_id, equipment_code)

"""
Production Line Service
Thin service layer wrapping Production Line CRUD operations.
Routes should import from this module instead of backend.crud.production_line directly.
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from backend.crud.production_line import (
    count_active_lines,
    create_production_line,
    list_production_lines,
    get_production_line,
    get_production_line_tree,
    update_production_line,
    deactivate_production_line,
    link_to_capacity_line,
    unlink_from_capacity_line,
    auto_sync_lines,
    get_unlinked_lines,
)
from backend.orm.production_line import ProductionLine
from backend.schemas.production_line import ProductionLineCreate, ProductionLineUpdate


def count_active_production_lines(db: Session, client_id: str) -> int:
    """Count active production lines for a client."""
    return count_active_lines(db, client_id)


def create_line(db: Session, data: ProductionLineCreate) -> ProductionLine:
    """Create a new production line."""
    return create_production_line(db, data)


def list_lines(db: Session, client_id: str, include_inactive: bool = False) -> List[ProductionLine]:
    """List production lines for a client."""
    return list_production_lines(db, client_id, include_inactive)


def get_line(db: Session, line_id: int) -> Optional[ProductionLine]:
    """Get a production line by ID."""
    return get_production_line(db, line_id)


def get_line_tree(db: Session, client_id: str) -> List[ProductionLine]:
    """Get production line tree for a client."""
    return get_production_line_tree(db, client_id)


def update_line(db: Session, line_id: int, data: ProductionLineUpdate) -> Optional[ProductionLine]:
    """Update a production line."""
    return update_production_line(db, line_id, data)


def deactivate_line(db: Session, line_id: int) -> bool:
    """Deactivate a production line."""
    return deactivate_production_line(db, line_id)


def link_line_to_capacity(db: Session, line_id: int, capacity_line_id: int) -> Optional[ProductionLine]:
    """Link a production line to a capacity line."""
    return link_to_capacity_line(db, line_id, capacity_line_id)


def unlink_line_from_capacity(db: Session, line_id: int) -> Optional[ProductionLine]:
    """Unlink a production line from its capacity line."""
    return unlink_from_capacity_line(db, line_id)


def auto_sync_capacity_lines(db: Session, client_id: str) -> Dict[str, list]:
    """Auto-sync production lines with capacity lines."""
    return auto_sync_lines(db, client_id)


def list_unlinked_lines(db: Session, client_id: str) -> List[ProductionLine]:
    """Get production lines not linked to capacity lines."""
    return get_unlinked_lines(db, client_id)

"""
CRUD operations for Capacity Production Lines

Provides operations for managing production line capacity specifications
including operators, efficiency factors, and department assignments.

Multi-tenant: All operations enforce client_id isolation.
"""

from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.utils.tenant_guard import ensure_client_id


def create_production_line(
    db: Session,
    client_id: str,
    line_code: str,
    line_name: str,
    department: Optional[str] = None,
    standard_capacity_units_per_hour: float = 0,
    max_operators: int = 10,
    efficiency_factor: float = 0.85,
    absenteeism_factor: float = 0.05,
    is_active: bool = True,
    notes: Optional[str] = None,
) -> CapacityProductionLine:
    """
    Create a new production line.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        line_code: Unique line code identifier
        line_name: Human-readable line name
        department: Department (CUTTING, SEWING, FINISHING, etc.)
        standard_capacity_units_per_hour: Base capacity per hour
        max_operators: Maximum number of operators
        efficiency_factor: Efficiency multiplier (0-1, default 0.85)
        absenteeism_factor: Expected absenteeism rate (0-1, default 0.05)
        is_active: Whether line is active
        notes: Additional notes

    Returns:
        Created CapacityProductionLine
    """
    ensure_client_id(client_id, "production line creation")

    line = CapacityProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=line_name,
        department=department,
        standard_capacity_units_per_hour=Decimal(str(standard_capacity_units_per_hour)),
        max_operators=max_operators,
        efficiency_factor=Decimal(str(efficiency_factor)),
        absenteeism_factor=Decimal(str(absenteeism_factor)),
        is_active=is_active,
        notes=notes,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def get_production_lines(
    db: Session, client_id: str, skip: int = 0, limit: int = 100, include_inactive: bool = False
) -> List[CapacityProductionLine]:
    """
    Get all production lines for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        include_inactive: Whether to include inactive lines

    Returns:
        List of CapacityProductionLine entries
    """
    ensure_client_id(client_id, "production lines query")

    query = db.query(CapacityProductionLine).filter(CapacityProductionLine.client_id == client_id)

    if not include_inactive:
        query = query.filter(CapacityProductionLine.is_active == True)

    return query.order_by(CapacityProductionLine.line_code).offset(skip).limit(limit).all()


def get_production_line(db: Session, client_id: str, line_id: int) -> Optional[CapacityProductionLine]:
    """
    Get a specific production line by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        line_id: Production line ID

    Returns:
        CapacityProductionLine or None if not found
    """
    ensure_client_id(client_id, "production line query")
    return (
        db.query(CapacityProductionLine)
        .filter(and_(CapacityProductionLine.client_id == client_id, CapacityProductionLine.id == line_id))
        .first()
    )


def get_production_line_by_code(db: Session, client_id: str, line_code: str) -> Optional[CapacityProductionLine]:
    """
    Get a specific production line by code.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        line_code: Production line code

    Returns:
        CapacityProductionLine or None if not found
    """
    ensure_client_id(client_id, "production line query")
    return (
        db.query(CapacityProductionLine)
        .filter(and_(CapacityProductionLine.client_id == client_id, CapacityProductionLine.line_code == line_code))
        .first()
    )


def update_production_line(db: Session, client_id: str, line_id: int, **updates) -> Optional[CapacityProductionLine]:
    """
    Update a production line.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        line_id: Production line ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityProductionLine or None if not found
    """
    line = get_production_line(db, client_id, line_id)
    if not line:
        return None

    # Convert float fields to Decimal
    decimal_fields = ["standard_capacity_units_per_hour", "efficiency_factor", "absenteeism_factor"]
    for key, value in updates.items():
        if hasattr(line, key) and value is not None:
            if key in decimal_fields:
                value = Decimal(str(value))
            setattr(line, key, value)

    db.commit()
    db.refresh(line)
    return line


def delete_production_line(db: Session, client_id: str, line_id: int, soft_delete: bool = True) -> bool:
    """
    Delete a production line.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        line_id: Production line ID to delete
        soft_delete: If True, set is_active=False; otherwise hard delete

    Returns:
        True if deleted/deactivated, False if not found
    """
    line = get_production_line(db, client_id, line_id)
    if not line:
        return False

    if soft_delete:
        line.is_active = False
        db.commit()
    else:
        db.delete(line)
        db.commit()

    return True


def get_active_lines(db: Session, client_id: str) -> List[CapacityProductionLine]:
    """
    Get all active production lines for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation

    Returns:
        List of active CapacityProductionLine entries
    """
    ensure_client_id(client_id, "active lines query")
    return (
        db.query(CapacityProductionLine)
        .filter(and_(CapacityProductionLine.client_id == client_id, CapacityProductionLine.is_active == True))
        .order_by(CapacityProductionLine.line_code)
        .all()
    )


def get_lines_by_department(
    db: Session, client_id: str, department: str, active_only: bool = True
) -> List[CapacityProductionLine]:
    """
    Get production lines by department.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        department: Department to filter by (CUTTING, SEWING, etc.)
        active_only: Whether to return only active lines

    Returns:
        List of CapacityProductionLine entries for the department
    """
    ensure_client_id(client_id, "lines by department query")

    filters = [CapacityProductionLine.client_id == client_id, CapacityProductionLine.department == department]

    if active_only:
        filters.append(CapacityProductionLine.is_active == True)

    return db.query(CapacityProductionLine).filter(and_(*filters)).order_by(CapacityProductionLine.line_code).all()


def get_total_capacity_per_hour(db: Session, client_id: str, department: Optional[str] = None) -> float:
    """
    Calculate total effective capacity per hour.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        department: Optional department filter

    Returns:
        Total effective capacity units per hour
    """
    if department:
        lines = get_lines_by_department(db, client_id, department, active_only=True)
    else:
        lines = get_active_lines(db, client_id)

    return sum(line.effective_capacity_per_hour() for line in lines)


def bulk_update_efficiency_factors(
    db: Session, client_id: str, efficiency_factor: float, department: Optional[str] = None
) -> int:
    """
    Bulk update efficiency factors for lines.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        efficiency_factor: New efficiency factor to apply
        department: Optional department filter

    Returns:
        Number of lines updated
    """
    ensure_client_id(client_id, "bulk efficiency update")

    filters = [CapacityProductionLine.client_id == client_id, CapacityProductionLine.is_active == True]

    if department:
        filters.append(CapacityProductionLine.department == department)

    result = (
        db.query(CapacityProductionLine)
        .filter(and_(*filters))
        .update(
            {CapacityProductionLine.efficiency_factor: Decimal(str(efficiency_factor))}, synchronize_session="fetch"
        )
    )

    db.commit()
    return result

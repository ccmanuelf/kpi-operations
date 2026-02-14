"""
CRUD operations for Capacity Production Standards

Provides operations for managing SAM (Standard Allowed Minutes) data
by style and operation for capacity calculations.

Multi-tenant: All operations enforce client_id isolation.
"""

from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.schemas.capacity.standards import CapacityProductionStandard
from backend.utils.tenant_guard import ensure_client_id


def create_standard(
    db: Session,
    client_id: str,
    style_code: str,
    operation_code: str,
    sam_minutes: float,
    operation_name: Optional[str] = None,
    department: Optional[str] = None,
    setup_time_minutes: float = 0,
    machine_time_minutes: float = 0,
    manual_time_minutes: float = 0,
    notes: Optional[str] = None,
) -> CapacityProductionStandard:
    """
    Create a new production standard.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style/product code
        operation_code: Operation code
        sam_minutes: Standard Allowed Minutes (total)
        operation_name: Human-readable operation name
        department: Department (CUTTING, SEWING, etc.)
        setup_time_minutes: Setup time component
        machine_time_minutes: Machine time component
        manual_time_minutes: Manual time component
        notes: Additional notes

    Returns:
        Created CapacityProductionStandard
    """
    ensure_client_id(client_id, "production standard creation")

    standard = CapacityProductionStandard(
        client_id=client_id,
        style_code=style_code,
        operation_code=operation_code,
        operation_name=operation_name,
        department=department,
        sam_minutes=Decimal(str(sam_minutes)),
        setup_time_minutes=Decimal(str(setup_time_minutes)),
        machine_time_minutes=Decimal(str(machine_time_minutes)),
        manual_time_minutes=Decimal(str(manual_time_minutes)),
        notes=notes,
    )
    db.add(standard)
    db.commit()
    db.refresh(standard)
    return standard


def get_standards(
    db: Session, client_id: str, skip: int = 0, limit: int = 100, department: Optional[str] = None
) -> List[CapacityProductionStandard]:
    """
    Get all production standards for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        department: Optional department to filter by

    Returns:
        List of CapacityProductionStandard entries
    """
    ensure_client_id(client_id, "production standards query")
    query = db.query(CapacityProductionStandard).filter(CapacityProductionStandard.client_id == client_id)
    if department:
        query = query.filter(CapacityProductionStandard.department == department)
    return (
        query.order_by(CapacityProductionStandard.style_code, CapacityProductionStandard.operation_code)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_standard(db: Session, client_id: str, standard_id: int) -> Optional[CapacityProductionStandard]:
    """
    Get a specific production standard by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        standard_id: Standard ID

    Returns:
        CapacityProductionStandard or None if not found
    """
    ensure_client_id(client_id, "production standard query")
    return (
        db.query(CapacityProductionStandard)
        .filter(and_(CapacityProductionStandard.client_id == client_id, CapacityProductionStandard.id == standard_id))
        .first()
    )


def get_standard_by_style_operation(
    db: Session, client_id: str, style_code: str, operation_code: str
) -> Optional[CapacityProductionStandard]:
    """
    Get a specific standard by style and operation codes.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code
        operation_code: Operation code

    Returns:
        CapacityProductionStandard or None if not found
    """
    ensure_client_id(client_id, "production standard query")
    return (
        db.query(CapacityProductionStandard)
        .filter(
            and_(
                CapacityProductionStandard.client_id == client_id,
                CapacityProductionStandard.style_code == style_code,
                CapacityProductionStandard.operation_code == operation_code,
            )
        )
        .first()
    )


def update_standard(db: Session, client_id: str, standard_id: int, **updates) -> Optional[CapacityProductionStandard]:
    """
    Update a production standard.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        standard_id: Standard ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityProductionStandard or None if not found
    """
    standard = get_standard(db, client_id, standard_id)
    if not standard:
        return None

    # Convert float fields to Decimal
    decimal_fields = ["sam_minutes", "setup_time_minutes", "machine_time_minutes", "manual_time_minutes"]
    for key, value in updates.items():
        if hasattr(standard, key) and value is not None:
            if key in decimal_fields:
                value = Decimal(str(value))
            setattr(standard, key, value)

    db.commit()
    db.refresh(standard)
    return standard


def delete_standard(db: Session, client_id: str, standard_id: int) -> bool:
    """
    Delete a production standard.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        standard_id: Standard ID to delete

    Returns:
        True if deleted, False if not found
    """
    standard = get_standard(db, client_id, standard_id)
    if not standard:
        return False

    db.delete(standard)
    db.commit()
    return True


def get_standards_by_style(db: Session, client_id: str, style_code: str) -> List[CapacityProductionStandard]:
    """
    Get all production standards for a style.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code to filter by

    Returns:
        List of CapacityProductionStandard entries for the style
    """
    ensure_client_id(client_id, "standards by style query")
    return (
        db.query(CapacityProductionStandard)
        .filter(
            and_(CapacityProductionStandard.client_id == client_id, CapacityProductionStandard.style_code == style_code)
        )
        .order_by(CapacityProductionStandard.operation_code)
        .all()
    )


def get_standards_by_department(db: Session, client_id: str, department: str) -> List[CapacityProductionStandard]:
    """
    Get all production standards for a department.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        department: Department to filter by

    Returns:
        List of CapacityProductionStandard entries for the department
    """
    ensure_client_id(client_id, "standards by department query")
    return (
        db.query(CapacityProductionStandard)
        .filter(
            and_(CapacityProductionStandard.client_id == client_id, CapacityProductionStandard.department == department)
        )
        .order_by(CapacityProductionStandard.style_code, CapacityProductionStandard.operation_code)
        .all()
    )


def get_total_sam_for_style(db: Session, client_id: str, style_code: str, department: Optional[str] = None) -> float:
    """
    Calculate total SAM for a style (sum of all operations).

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code
        department: Optional department filter

    Returns:
        Total SAM in minutes for the style
    """
    ensure_client_id(client_id, "total SAM query")

    filters = [CapacityProductionStandard.client_id == client_id, CapacityProductionStandard.style_code == style_code]
    if department:
        filters.append(CapacityProductionStandard.department == department)

    result = db.query(func.sum(CapacityProductionStandard.sam_minutes)).filter(and_(*filters)).scalar()

    return float(result) if result else 0.0


def get_sam_by_department_for_style(db: Session, client_id: str, style_code: str) -> dict:
    """
    Get SAM breakdown by department for a style.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code

    Returns:
        Dictionary mapping department to total SAM
    """
    ensure_client_id(client_id, "SAM by department query")

    results = (
        db.query(
            CapacityProductionStandard.department, func.sum(CapacityProductionStandard.sam_minutes).label("total_sam")
        )
        .filter(
            and_(CapacityProductionStandard.client_id == client_id, CapacityProductionStandard.style_code == style_code)
        )
        .group_by(CapacityProductionStandard.department)
        .all()
    )

    return {dept: float(sam) for dept, sam in results if dept}


def bulk_create_standards(db: Session, client_id: str, standards: List[dict]) -> List[CapacityProductionStandard]:
    """
    Bulk create production standards.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        standards: List of standard dictionaries

    Returns:
        List of created CapacityProductionStandard entries
    """
    ensure_client_id(client_id, "bulk standards create")

    created = []
    for std_data in standards:
        # Convert float fields to Decimal
        decimal_fields = ["sam_minutes", "setup_time_minutes", "machine_time_minutes", "manual_time_minutes"]
        for field in decimal_fields:
            if field in std_data and std_data[field] is not None:
                std_data[field] = Decimal(str(std_data[field]))

        standard = CapacityProductionStandard(client_id=client_id, **std_data)
        db.add(standard)
        created.append(standard)

    db.commit()
    for std in created:
        db.refresh(std)

    return created


def get_unique_styles(db: Session, client_id: str) -> List[str]:
    """
    Get list of unique style codes with standards defined.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation

    Returns:
        List of unique style codes
    """
    ensure_client_id(client_id, "unique styles query")

    results = (
        db.query(CapacityProductionStandard.style_code)
        .filter(CapacityProductionStandard.client_id == client_id)
        .distinct()
        .all()
    )

    return [r[0] for r in results]

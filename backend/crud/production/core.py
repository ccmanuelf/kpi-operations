"""
CRUD core operations for Production Entry
Create, Read, Update, Delete with KPI calculations
SECURITY: Multi-tenant client filtering enabled

Phase 1.3: Decoupled from direct calculation imports.
KPI calculations are now handled by ProductionKPIService.
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.user import User
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
)
from backend.middleware.client_auth import verify_client_access
from backend.utils.soft_delete import soft_delete


def _calculate_entry_kpis(db: Session, entry: ProductionEntry, product: Optional[Product] = None):
    """
    Internal helper to calculate and update KPIs for an entry.
    Uses ProductionKPIService for calculation logic.

    Phase 1.3: Encapsulates KPI calculation to single location in CRUD.
    """
    from backend.services.production_kpi_service import ProductionKPIService

    service = ProductionKPIService(db)
    result = service.calculate_entry_kpis(entry, product=product)

    entry.efficiency_percentage = result.efficiency.efficiency_percentage
    entry.performance_percentage = result.performance.performance_percentage

    return result


def create_production_entry(
    db: Session,
    entry: ProductionEntryCreate,
    current_user: User,
    skip_kpi_calculation: bool = False
) -> ProductionEntry:
    """
    Create new production entry with automatic KPI calculation
    SECURITY: Verifies user has access to the specified client

    Phase 1.3: Added skip_kpi_calculation parameter for batch imports.
    KPI calculations are now handled by ProductionKPIService.

    Args:
        db: Database session
        entry: Production entry data
        current_user: Authenticated user (changed from entered_by: int)
        skip_kpi_calculation: If True, skip KPI calculation (for batch imports)

    Returns:
        Created production entry with calculated KPIs

    Raises:
        ClientAccessError: If user doesn't have access to entry.client_id
    """
    # SECURITY: Verify user has access to this client
    if hasattr(entry, 'client_id') and entry.client_id:
        verify_client_access(current_user, entry.client_id)

    # Generate unique production_entry_id
    entry_id = f"PE-{uuid.uuid4().hex[:8].upper()}"

    # Create entry
    db_entry = ProductionEntry(
        production_entry_id=entry_id,
        product_id=entry.product_id,
        shift_id=entry.shift_id,
        production_date=entry.production_date,
        shift_date=entry.shift_date,
        work_order_id=entry.work_order_id,
        units_produced=entry.units_produced,
        run_time_hours=entry.run_time_hours,
        employees_assigned=entry.employees_assigned,
        defect_count=entry.defect_count,
        scrap_count=entry.scrap_count,
        notes=entry.notes,
        entered_by=current_user.user_id  # Use user_id from current_user
    )

    # Set client_id if provided
    if hasattr(entry, 'client_id') and entry.client_id:
        db_entry.client_id = entry.client_id

    db.add(db_entry)
    db.flush()  # Get entry_id without committing

    # Calculate KPIs unless skipped (for batch imports)
    if not skip_kpi_calculation:
        product = db.query(Product).filter(Product.product_id == entry.product_id).first()
        _calculate_entry_kpis(db, db_entry, product)

    db.commit()
    db.refresh(db_entry)

    return db_entry


def get_production_entry(
    db: Session,
    entry_id: int,
    current_user: User
) -> Optional[ProductionEntry]:
    """
    Get production entry by ID
    SECURITY: Verifies user has access to the entry's client

    Args:
        db: Database session
        entry_id: Production entry ID
        current_user: Authenticated user

    Returns:
        Production entry or None if not found

    Raises:
        HTTPException 404: If entry not found
        ClientAccessError: If user doesn't have access to entry's client
    """
    # First, try to find the entry
    entry = db.query(ProductionEntry).filter(
        ProductionEntry.production_entry_id == entry_id
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Production entry not found")

    # SECURITY: Verify user has access to this entry's client
    if hasattr(entry, 'client_id') and entry.client_id:
        verify_client_access(current_user, entry.client_id)

    return entry


def update_production_entry(
    db: Session,
    entry_id: int,
    entry_update: ProductionEntryUpdate,
    current_user: User
) -> Optional[ProductionEntry]:
    """
    Update production entry and recalculate KPIs
    SECURITY: Verifies user has access to the entry's client

    Args:
        db: Database session
        entry_id: Entry ID to update
        entry_update: Update data
        current_user: Authenticated user (ADDED for authorization)

    Returns:
        Updated production entry or None if not found

    Raises:
        HTTPException 404: If entry not found
        ClientAccessError: If user doesn't have access to entry's client
    """
    db_entry = db.query(ProductionEntry).filter(
        ProductionEntry.production_entry_id == entry_id
    ).first()

    if not db_entry:
        raise HTTPException(status_code=404, detail="Production entry not found")

    # SECURITY: Verify user has access to this entry's client BEFORE updating
    if hasattr(db_entry, 'client_id') and db_entry.client_id:
        verify_client_access(current_user, db_entry.client_id)

    # Update fields
    update_data = entry_update.dict(exclude_unset=True)

    # Track if recalculation needed
    recalc_needed = any(
        field in update_data
        for field in ["units_produced", "run_time_hours", "employees_assigned"]
    )

    for field, value in update_data.items():
        setattr(db_entry, field, value)

    # Handle confirmation
    if entry_update.confirmed_by is not None:
        db_entry.confirmation_timestamp = datetime.utcnow()

    # Recalculate KPIs if metrics changed (using service layer)
    if recalc_needed:
        product = db.query(Product).filter(
            Product.product_id == db_entry.product_id
        ).first()
        _calculate_entry_kpis(db, db_entry, product)

    db.commit()
    db.refresh(db_entry)

    return db_entry


def delete_production_entry(
    db: Session,
    entry_id: int,
    current_user: User
) -> bool:
    """
    Soft delete production entry (sets is_active = False)
    SECURITY: Verifies user has access to the entry's client

    Args:
        db: Database session
        entry_id: Entry ID to delete
        current_user: Authenticated user (ADDED for authorization)

    Returns:
        True if soft deleted, False if not found

    Raises:
        HTTPException 404: If entry not found
        ClientAccessError: If user doesn't have access to entry's client
    """
    db_entry = db.query(ProductionEntry).filter(
        ProductionEntry.production_entry_id == entry_id
    ).first()

    if not db_entry:
        raise HTTPException(status_code=404, detail="Production entry not found")

    # SECURITY: Verify user has access to this entry's client BEFORE deleting
    if hasattr(db_entry, 'client_id') and db_entry.client_id:
        verify_client_access(current_user, db_entry.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_entry)

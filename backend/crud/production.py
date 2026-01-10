"""
CRUD operations for Production Entry
Create, Read, Update, Delete with KPI calculations
SECURITY: Multi-tenant client filtering enabled
"""
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.user import User
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryWithKPIs
)
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.performance import (
    calculate_performance,
    calculate_quality_rate,
    calculate_oee
)
from middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.utils.soft_delete import soft_delete


def create_production_entry(
    db: Session,
    entry: ProductionEntryCreate,
    current_user: User
) -> ProductionEntry:
    """
    Create new production entry with automatic KPI calculation
    SECURITY: Verifies user has access to the specified client

    Args:
        db: Database session
        entry: Production entry data
        current_user: Authenticated user (changed from entered_by: int)

    Returns:
        Created production entry with calculated KPIs

    Raises:
        ClientAccessError: If user doesn't have access to entry.client_id
    """
    # SECURITY: Verify user has access to this client
    if hasattr(entry, 'client_id') and entry.client_id:
        verify_client_access(current_user, entry.client_id)

    # Create entry
    db_entry = ProductionEntry(
        product_id=entry.product_id,
        shift_id=entry.shift_id,
        production_date=entry.production_date,
        work_order_number=entry.work_order_number,
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

    # Calculate KPIs
    product = db.query(Product).filter(Product.product_id == entry.product_id).first()

    efficiency, _, _ = calculate_efficiency(db, db_entry, product)
    performance, _, _ = calculate_performance(db, db_entry, product)

    db_entry.efficiency_percentage = efficiency
    db_entry.performance_percentage = performance

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


def get_production_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None
) -> List[ProductionEntry]:
    """
    Get production entries with filtering
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user (ADDED for client filtering)
        skip: Number of records to skip
        limit: Maximum records to return
        start_date: Filter by start date
        end_date: Filter by end date
        product_id: Filter by product
        shift_id: Filter by shift

    Returns:
        List of production entries (filtered by user's client access)
    """
    query = db.query(ProductionEntry)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, ProductionEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if start_date:
        query = query.filter(ProductionEntry.production_date >= start_date)
    if end_date:
        query = query.filter(ProductionEntry.production_date <= end_date)
    if product_id:
        query = query.filter(ProductionEntry.product_id == product_id)
    if shift_id:
        query = query.filter(ProductionEntry.shift_id == shift_id)

    return query.order_by(
        ProductionEntry.production_date.desc(),
        ProductionEntry.production_entry_id.desc()
    ).offset(skip).limit(limit).all()


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

    # Recalculate KPIs if metrics changed
    if recalc_needed:
        product = db.query(Product).filter(
            Product.product_id == db_entry.product_id
        ).first()

        efficiency, _, _ = calculate_efficiency(db, db_entry, product)
        performance, _, _ = calculate_performance(db, db_entry, product)

        db_entry.efficiency_percentage = efficiency
        db_entry.performance_percentage = performance

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


def get_production_entry_with_details(
    db: Session,
    entry_id: int,
    current_user: User
) -> Optional[ProductionEntryWithKPIs]:
    """
    Get production entry with full details and KPI breakdown
    SECURITY: Verifies user has access to the entry's client

    Args:
        db: Database session
        entry_id: Entry ID
        current_user: Authenticated user (ADDED for authorization)

    Returns:
        Production entry with detailed KPI information

    Raises:
        HTTPException 404: If entry not found
        ClientAccessError: If user doesn't have access to entry's client
    """
    entry = db.query(ProductionEntry).filter(
        ProductionEntry.production_entry_id == entry_id
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Production entry not found")

    # SECURITY: Verify user has access to this entry's client
    if hasattr(entry, 'client_id') and entry.client_id:
        verify_client_access(current_user, entry.client_id)

    # Get related data
    product = db.query(Product).filter(Product.product_id == entry.product_id).first()
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()

    # Calculate additional metrics
    efficiency, ideal_time, inferred = calculate_efficiency(db, entry, product)
    performance, _, _ = calculate_performance(db, entry, product)
    quality = calculate_quality_rate(entry)
    oee, _ = calculate_oee(db, entry, product)

    # Build response
    total_hours = entry.employees_assigned * float(entry.run_time_hours)

    return ProductionEntryWithKPIs(
        entry_id=entry.production_entry_id,
        product_id=entry.product_id,
        shift_id=entry.shift_id,
        production_date=entry.production_date,
        work_order_number=entry.work_order_id if hasattr(entry, 'work_order_id') else None,
        units_produced=entry.units_produced,
        run_time_hours=entry.run_time_hours,
        employees_assigned=entry.employees_assigned,
        defect_count=entry.defect_count,
        scrap_count=entry.scrap_count,
        efficiency_percentage=entry.efficiency_percentage,
        performance_percentage=entry.performance_percentage,
        notes=entry.notes,
        entered_by=entry.entered_by,
        confirmed_by=entry.confirmed_by,
        confirmation_timestamp=entry.confirmation_timestamp,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        product_name=product.product_name if product else "Unknown",
        shift_name=shift.shift_name if shift else "Unknown",
        ideal_cycle_time=ideal_time,
        inferred_cycle_time=inferred,
        total_available_hours=Decimal(str(total_hours)),
        quality_rate=quality,
        oee=oee
    )


def get_daily_summary(
    db: Session,
    current_user: User,
    start_date: date,
    end_date: Optional[date] = None
) -> List[dict]:
    """
    Get daily production summary
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user (ADDED for client filtering)
        start_date: Start date
        end_date: End date (defaults to start_date)

    Returns:
        List of daily summaries (filtered by user's client access)
    """
    if end_date is None:
        end_date = start_date

    query = db.query(
        ProductionEntry.production_date,
        func.sum(ProductionEntry.units_produced).label("total_units"),
        func.avg(ProductionEntry.efficiency_percentage).label("avg_efficiency"),
        func.avg(ProductionEntry.performance_percentage).label("avg_performance"),
        func.count(ProductionEntry.production_entry_id).label("entry_count")
    )

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, ProductionEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply date filtering
    query = query.filter(
        and_(
            ProductionEntry.production_date >= start_date,
            ProductionEntry.production_date <= end_date
        )
    ).group_by(
        ProductionEntry.production_date
    )

    results = query.all()

    return [
        {
            "date": result.production_date,
            "total_units": result.total_units,
            "avg_efficiency": float(result.avg_efficiency) if result.avg_efficiency else 0,
            "avg_performance": float(result.avg_performance) if result.avg_performance else 0,
            "entry_count": result.entry_count
        }
        for result in results
    ]


def batch_create_entries(
    db: Session,
    entries: List[ProductionEntryCreate],
    current_user: User
) -> List[ProductionEntry]:
    """
    Batch create production entries (for CSV upload)
    SECURITY: Verifies user has access to each entry's client

    Args:
        db: Database session
        entries: List of production entries
        current_user: Authenticated user (CHANGED from entered_by: int)

    Returns:
        List of created entries

    Raises:
        ClientAccessError: If user doesn't have access to any entry's client
    """
    created_entries = []

    for entry_data in entries:
        try:
            # create_production_entry now handles authorization
            entry = create_production_entry(db, entry_data, current_user)
            created_entries.append(entry)
        except Exception as e:
            # Log error but continue with other entries
            print(f"Error creating entry: {e}")
            continue

    return created_entries

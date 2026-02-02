"""
CRUD KPI-related operations for Production Entry
Detailed entry with KPI breakdown
SECURITY: Multi-tenant client filtering enabled
"""
from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.user import User
from backend.models.production import ProductionEntryWithKPIs
from backend.middleware.client_auth import verify_client_access


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

    # Calculate KPIs using service layer
    from backend.services.production_kpi_service import ProductionKPIService
    service = ProductionKPIService(db)
    kpi_result = service.calculate_entry_kpis(entry, product, shift)

    # Extract values for response
    efficiency = kpi_result.efficiency.efficiency_percentage
    ideal_time = kpi_result.efficiency.ideal_cycle_time_used
    inferred = kpi_result.efficiency.is_estimated
    performance = kpi_result.performance.performance_percentage
    quality = kpi_result.quality.quality_rate
    oee = kpi_result.oee.oee

    # Build response
    total_hours = entry.employees_assigned * float(entry.run_time_hours)

    return ProductionEntryWithKPIs(
        production_entry_id=entry.production_entry_id,
        client_id=entry.client_id,
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

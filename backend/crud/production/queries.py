"""
CRUD query operations for Production Entry
List, filter, and summary queries
SECURITY: Multi-tenant client filtering enabled
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause


def get_production_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
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
        client_id: Filter by specific client (must be within user's authorized clients)

    Returns:
        List of production entries (filtered by user's client access)
    """
    query = db.query(ProductionEntry)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, ProductionEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply specific client filter (within user's authorized clients)
    if client_id:
        verify_client_access(current_user, client_id)
        query = query.filter(ProductionEntry.client_id == client_id)

    # Apply additional filters
    if start_date:
        query = query.filter(ProductionEntry.production_date >= start_date)
    if end_date:
        query = query.filter(ProductionEntry.production_date <= end_date)
    if product_id:
        query = query.filter(ProductionEntry.product_id == product_id)
    if shift_id:
        query = query.filter(ProductionEntry.shift_id == shift_id)

    return (
        query.order_by(ProductionEntry.production_date.desc(), ProductionEntry.production_entry_id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_daily_summary(
    db: Session, current_user: User, start_date: date, end_date: Optional[date] = None, client_id: Optional[str] = None
) -> List[dict]:
    """
    Get daily production summary
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user (ADDED for client filtering)
        start_date: Start date
        end_date: End date (defaults to start_date)
        client_id: Filter by specific client (must be within user's authorized clients)

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
        func.count(ProductionEntry.production_entry_id).label("entry_count"),
    )

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, ProductionEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply specific client filter (within user's authorized clients)
    if client_id:
        verify_client_access(current_user, client_id)
        query = query.filter(ProductionEntry.client_id == client_id)

    # Apply date filtering
    query = query.filter(
        and_(ProductionEntry.production_date >= start_date, ProductionEntry.production_date <= end_date)
    ).group_by(ProductionEntry.production_date)

    results = query.all()

    return [
        {
            "date": result.production_date,
            "total_units": result.total_units,
            "avg_efficiency": float(result.avg_efficiency) if result.avg_efficiency else 0,
            "avg_performance": float(result.avg_performance) if result.avg_performance else 0,
            "entry_count": result.entry_count,
        }
        for result in results
    ]

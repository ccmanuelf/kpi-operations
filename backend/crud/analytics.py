"""
Analytics CRUD operations
Database queries for retrieving analytics data with multi-tenant filtering
"""
from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, select, and_, or_, case
from backend.middleware.client_auth import build_client_filter_clause, get_user_client_filter
from backend.schemas.user import User


def get_kpi_time_series_data(
    db: Session,
    client_id: str,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User
) -> List[Tuple[date, Decimal]]:
    """
    Retrieve time series KPI data for trend analysis

    Args:
        db: Database session
        client_id: Client ID to filter
        kpi_type: Type of KPI ('efficiency', 'performance', 'quality', etc.)
        start_date: Start date for data retrieval
        end_date: End date for data retrieval
        current_user: Current authenticated user (for access control)

    Returns:
        List of (date, value) tuples ordered by date

    Raises:
        ClientAccessError: If user doesn't have access to this client
    """
    from backend.middleware.client_auth import verify_client_access
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.work_order import WorkOrder

    # Verify client access
    verify_client_access(current_user, client_id)

    # Map KPI type to column
    kpi_column_map = {
        'efficiency': ProductionEntry.efficiency_percentage,
        'performance': ProductionEntry.performance_percentage,
        # Quality rate = (units_produced - defect_count) / units_produced
        'quality': ((ProductionEntry.units_produced - ProductionEntry.defect_count) /
                    ProductionEntry.units_produced * 100),
    }

    if kpi_type not in kpi_column_map:
        raise ValueError(f"Unknown KPI type: {kpi_type}")

    kpi_column = kpi_column_map[kpi_type]

    # Query with client filtering via work order
    query = select(
        ProductionEntry.production_date,
        func.avg(kpi_column).label('avg_value')
    ).join(
        WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id
    ).where(
        and_(
            WorkOrder.client_id == client_id,
            ProductionEntry.production_date >= start_date,
            ProductionEntry.production_date <= end_date,
            kpi_column.isnot(None)
        )
    ).group_by(
        ProductionEntry.production_date
    ).order_by(
        ProductionEntry.production_date
    )

    results = db.execute(query).all()

    return [(row.production_date, Decimal(str(row.avg_value))) for row in results]


def get_shift_heatmap_data(
    db: Session,
    client_id: str,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User
) -> List[Tuple[date, str, str, Optional[Decimal]]]:
    """
    Retrieve KPI data grouped by date and shift for heatmap visualization

    Args:
        db: Database session
        client_id: Client ID to filter
        kpi_type: Type of KPI
        start_date: Start date
        end_date: End date
        current_user: Current authenticated user

    Returns:
        List of (date, shift_id, shift_name, avg_value) tuples
    """
    from backend.middleware.client_auth import verify_client_access
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.shift import Shift

    verify_client_access(current_user, client_id)

    kpi_column_map = {
        'efficiency': ProductionEntry.efficiency_percentage,
        'performance': ProductionEntry.performance_percentage,
        'quality': ((ProductionEntry.units_produced - ProductionEntry.defect_count) /
                    ProductionEntry.units_produced * 100),
    }

    if kpi_type not in kpi_column_map:
        raise ValueError(f"Unknown KPI type: {kpi_type}")

    kpi_column = kpi_column_map[kpi_type]

    query = select(
        ProductionEntry.production_date,
        Shift.shift_id,
        Shift.shift_name,
        func.avg(kpi_column).label('avg_value')
    ).join(
        WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id
    ).join(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).where(
        and_(
            WorkOrder.client_id == client_id,
            ProductionEntry.production_date >= start_date,
            ProductionEntry.production_date <= end_date
        )
    ).group_by(
        ProductionEntry.production_date,
        Shift.shift_id,
        Shift.shift_name
    ).order_by(
        ProductionEntry.production_date,
        Shift.shift_id
    )

    results = db.execute(query).all()

    return [
        (
            row.production_date,
            str(row.shift_id),
            row.shift_name,
            Decimal(str(row.avg_value)) if row.avg_value else None
        )
        for row in results
    ]


def get_client_comparison_data(
    db: Session,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User
) -> List[Tuple[str, str, Decimal, int]]:
    """
    Retrieve KPI comparison data across all accessible clients

    Args:
        db: Database session
        kpi_type: Type of KPI
        start_date: Start date
        end_date: End date
        current_user: Current authenticated user

    Returns:
        List of (client_id, client_name, avg_value, data_points) tuples
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Get user's client filter
    user_clients = get_user_client_filter(current_user)

    kpi_column_map = {
        'efficiency': ProductionEntry.efficiency_percentage,
        'performance': ProductionEntry.performance_percentage,
        'quality': ((ProductionEntry.units_produced - ProductionEntry.defect_count) /
                    ProductionEntry.units_produced * 100),
    }

    if kpi_type not in kpi_column_map:
        raise ValueError(f"Unknown KPI type: {kpi_type}")

    kpi_column = kpi_column_map[kpi_type]

    # Build query
    query = select(
        Client.client_id,
        Client.client_name,
        func.avg(kpi_column).label('avg_value'),
        func.count(ProductionEntry.production_entry_id).label('data_points')
    ).join(
        WorkOrder, Client.client_id == WorkOrder.client_id
    ).join(
        ProductionEntry, WorkOrder.work_order_id == ProductionEntry.work_order_id
    ).where(
        and_(
            ProductionEntry.production_date >= start_date,
            ProductionEntry.production_date <= end_date,
            kpi_column.isnot(None)
        )
    )

    # Apply client filtering
    if user_clients is not None:
        query = query.where(Client.client_id.in_(user_clients))

    query = query.group_by(
        Client.client_id,
        Client.client_name
    ).order_by(
        func.avg(kpi_column).desc()
    )

    results = db.execute(query).all()

    return [
        (row.client_id, row.client_name, Decimal(str(row.avg_value)), row.data_points)
        for row in results
    ]


def get_defect_pareto_data(
    db: Session,
    client_id: str,
    start_date: date,
    end_date: date,
    current_user: User
) -> List[Tuple[str, int]]:
    """
    Retrieve defect data grouped by type for Pareto analysis

    Args:
        db: Database session
        client_id: Client ID to filter
        start_date: Start date
        end_date: End date
        current_user: Current authenticated user

    Returns:
        List of (defect_type, total_count) tuples ordered by count descending
    """
    from backend.middleware.client_auth import verify_client_access
    from backend.schemas.defect_detail import DefectDetail
    from backend.schemas.quality_entry import QualityEntry

    verify_client_access(current_user, client_id)

    query = select(
        DefectDetail.defect_type,
        func.sum(DefectDetail.defect_count).label('total_count')
    ).join(
        QualityEntry, DefectDetail.quality_entry_id == QualityEntry.quality_entry_id
    ).where(
        and_(
            DefectDetail.client_id_fk == client_id,
            QualityEntry.inspection_date >= start_date,
            QualityEntry.inspection_date <= end_date
        )
    ).group_by(
        DefectDetail.defect_type
    ).order_by(
        func.sum(DefectDetail.defect_count).desc()
    )

    results = db.execute(query).all()

    return [(row.defect_type, int(row.total_count)) for row in results]


def get_all_shifts(db: Session) -> List[Tuple[str, str]]:
    """
    Get all shifts for heatmap axis

    Returns:
        List of (shift_id, shift_name) tuples
    """
    from backend.models.job import Shift

    query = select(
        Shift.shift_id,
        Shift.shift_name
    ).order_by(Shift.shift_id)

    results = db.execute(query).all()

    return [(str(row.shift_id), row.shift_name) for row in results]


def get_client_info(db: Session, client_id: str) -> Optional[Tuple[str, str]]:
    """
    Get client name for a given client ID

    Args:
        db: Database session
        client_id: Client ID

    Returns:
        Tuple of (client_id, client_name) or None if not found
    """
    from backend.models.client import Client

    query = select(
        Client.client_id,
        Client.client_name
    ).where(Client.client_id == client_id)

    result = db.execute(query).first()

    return (result.client_id, result.client_name) if result else None


def get_date_range_data_availability(
    db: Session,
    client_id: str,
    current_user: User
) -> Tuple[Optional[date], Optional[date], int]:
    """
    Get available date range and total records for a client

    Args:
        db: Database session
        client_id: Client ID
        current_user: Current authenticated user

    Returns:
        Tuple of (min_date, max_date, total_records)
    """
    from backend.middleware.client_auth import verify_client_access
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.work_order import WorkOrder

    verify_client_access(current_user, client_id)

    query = select(
        func.min(ProductionEntry.production_date).label('min_date'),
        func.max(ProductionEntry.production_date).label('max_date'),
        func.count(ProductionEntry.production_entry_id).label('total_records')
    ).join(
        WorkOrder, ProductionEntry.work_order_id == WorkOrder.work_order_id
    ).where(
        WorkOrder.client_id == client_id
    )

    result = db.execute(query).first()

    if result and result.total_records > 0:
        return (result.min_date, result.max_date, result.total_records)
    else:
        return (None, None, 0)

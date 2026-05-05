"""
Analytics CRUD Service
Thin service layer wrapping Analytics CRUD query functions.
Routes should import from this module instead of backend.crud.analytics directly.

Note: The AnalyticsService class in backend.services.analytics_service provides
higher-level trend analysis. This module handles CRUD query passthrough.
"""

from typing import Any
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.analytics import (
    get_kpi_time_series_data,
    get_shift_heatmap_data,
    get_client_comparison_data,
    get_defect_pareto_data,
    get_all_shifts,
    get_client_info,
    get_date_range_data_availability,
)


def get_time_series(
    db: Session,
    client_id: str,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User,
) -> Any:
    """Get KPI time series data."""
    return get_kpi_time_series_data(db, client_id, kpi_type, start_date, end_date, current_user)


def get_heatmap(
    db: Session,
    client_id: str,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User,
) -> Any:
    """Get shift performance heatmap data."""
    return get_shift_heatmap_data(db, client_id, kpi_type, start_date, end_date, current_user)


def get_comparison(
    db: Session,
    kpi_type: str,
    start_date: date,
    end_date: date,
    current_user: User,
) -> Any:
    """Get client comparison data."""
    return get_client_comparison_data(db, kpi_type, start_date, end_date, current_user)


def get_pareto(
    db: Session,
    client_id: str,
    start_date: date,
    end_date: date,
    current_user: User,
) -> Any:
    """Get defect Pareto data."""
    return get_defect_pareto_data(db, client_id, start_date, end_date, current_user)


def list_all_shifts(db: Session) -> Any:
    """Get all shifts."""
    return get_all_shifts(db)


def get_client_details(db: Session, client_id: str) -> Any:
    """Get client info for analytics."""
    return get_client_info(db, client_id)


def get_data_availability(db: Session, client_id: str, current_user: User) -> Any:
    """Get date range data availability."""
    return get_date_range_data_availability(db, client_id, current_user)

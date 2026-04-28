"""
Quality Service
Service layer for Quality Inspection operations.
Coordinates CRUD operations with business logic and KPI calculations.

Phase 2: Service Layer Enforcement
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.orm.user import User
from backend.orm.quality_entry import QualityEntry
from backend.services.quality_kpi_service import QualityKPIService
from backend.crud.analytics import get_defect_pareto_data
from backend.middleware.client_auth import verify_client_access
from backend.database import get_db


class QualityService:
    """
    Service layer for Quality operations.

    Wraps quality CRUD operations with business logic:
    - PPM and DPMO calculations
    - Defect tracking and analysis
    - Quality rate monitoring
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.kpi_service = QualityKPIService(db)

    def calculate_quality_metrics(
        self, client_id: str, user: User, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate quality metrics (PPM/DPMO/FPY/RTY) for a client over a window.

        Args:
            client_id: Client ID
            user: Authenticated user (used for tenant access check)
            start_date: Filter start date (defaults to 30 days ago)
            end_date: Filter end date (defaults to today)

        Returns:
            Dictionary with quality metrics (PPM, DPMO, FPY, RTY).
        """
        verify_client_access(user, client_id)

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        return self.kpi_service.get_quality_summary(start_date, end_date, client_id=client_id)

    def get_defect_pareto(
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get defect Pareto analysis (top defect types).

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date (defaults to 30 days ago)
            end_date: Filter end date (defaults to today)
            limit: Maximum defect types to return

        Returns:
            List of defect types with counts ordered by count descending.
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        # crud.analytics.get_defect_pareto_data returns List[Tuple[str, int]]
        # and already runs verify_client_access internally.
        rows = get_defect_pareto_data(self.db, client_id, start_date, end_date, user)
        return [{"defect_type": defect_type, "count": count} for defect_type, count in rows[:limit]]

    def get_quality_trend(self, client_id: str, user: User, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily FPY trend for the trailing `days` days.

        Args:
            client_id: Client ID
            user: Authenticated user
            days: Number of trailing days (default 30)

        Returns:
            List of {date, fpy_percentage} entries ordered ascending by date.
        """
        verify_client_access(user, client_id)

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        rows = (
            self.db.query(
                func.date(QualityEntry.shift_date).label("date"),
                func.sum(QualityEntry.units_passed).label("passed"),
                func.sum(QualityEntry.units_inspected).label("inspected"),
            )
            .filter(
                QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
                QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
                QualityEntry.client_id == client_id,
            )
            .group_by(func.date(QualityEntry.shift_date))
            .order_by(func.date(QualityEntry.shift_date))
            .all()
        )

        return [
            {
                "date": str(r.date),
                "fpy_percentage": (
                    round((r.passed / r.inspected) * 100, 2) if r.inspected and r.inspected > 0 else 0.0
                ),
            }
            for r in rows
        ]


def get_quality_service(db: Session = Depends(get_db)) -> QualityService:
    """
    FastAPI dependency to get QualityService instance.
    """
    return QualityService(db)

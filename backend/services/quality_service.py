"""
Quality Service
Service layer for Quality Inspection operations.
Coordinates CRUD operations with business logic and KPI calculations.

Phase 2: Service Layer Enforcement
"""
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.user import User
from backend.services.quality_kpi_service import QualityKPIService
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
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """
        Calculate quality metrics for a client.

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            Dictionary with quality metrics (PPM, DPMO, etc.)
        """
        return self.kpi_service.calculate_quality_metrics(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date
        )

    def get_defect_pareto(
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Get defect Pareto analysis (top defect types).

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date
            end_date: Filter end date
            limit: Maximum defect types to return

        Returns:
            List of defect types with counts and percentages
        """
        return self.kpi_service.get_defect_pareto(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

    def get_quality_trend(
        self,
        client_id: str,
        user: User,
        days: int = 30
    ) -> List[dict]:
        """
        Get quality trend over time.

        Args:
            client_id: Client ID
            user: Authenticated user
            days: Number of days for trend

        Returns:
            List of daily quality rates
        """
        return self.kpi_service.get_quality_trend(
            client_id=client_id,
            days=days
        )


def get_quality_service(db: Session = Depends(get_db)) -> QualityService:
    """
    FastAPI dependency to get QualityService instance.
    """
    return QualityService(db)

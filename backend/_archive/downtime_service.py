"""
Downtime Service
Service layer for Downtime operations.
Coordinates CRUD operations with availability calculations.

Phase 2: Service Layer Enforcement
"""
from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.user import User
from backend.crud.downtime import (
    create_downtime_event,
    get_downtime_event,
    get_downtime_events,
    update_downtime_event,
    delete_downtime_event,
)
from backend.database import get_db


class DowntimeService:
    """
    Service layer for Downtime operations.

    Wraps downtime CRUD with business logic:
    - Availability calculations
    - Downtime categorization
    - Equipment uptime tracking
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_downtime(
        self,
        data: dict,
        user: User
    ):
        """
        Create a downtime record.

        Args:
            data: Downtime data
            user: Authenticated user

        Returns:
            Created downtime record
        """
        return create_downtime_event(self.db, data, user)

    def get_downtime(
        self,
        downtime_id: str,
        user: User
    ):
        """
        Get a downtime record by ID.

        Args:
            downtime_id: Downtime ID
            user: Authenticated user

        Returns:
            Downtime record or None
        """
        return get_downtime_event(self.db, downtime_id, user)

    def list_downtime(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        client_id: Optional[str] = None,
        equipment_id: Optional[int] = None
    ) -> List:
        """
        List downtime records with filtering.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records
            start_date: Filter start date
            end_date: Filter end date
            client_id: Filter by client
            equipment_id: Filter by equipment

        Returns:
            List of downtime records
        """
        return get_downtime_events(
            self.db, user, skip, limit,
            start_date, end_date, client_id
        )

    def update_downtime(
        self,
        downtime_id: str,
        data: dict,
        user: User
    ):
        """
        Update a downtime record.

        Args:
            downtime_id: Downtime ID
            data: Update data
            user: Authenticated user

        Returns:
            Updated downtime record
        """
        return update_downtime_event(self.db, downtime_id, data, user)

    def delete_downtime(
        self,
        downtime_id: str,
        user: User
    ) -> bool:
        """
        Delete a downtime record.

        Args:
            downtime_id: Downtime ID
            user: Authenticated user

        Returns:
            True if deleted
        """
        return delete_downtime_event(self.db, downtime_id, user)

    def calculate_availability(
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        total_scheduled_hours: Optional[Decimal] = None
    ) -> dict:
        """
        Calculate equipment availability for a client.

        Availability = (Scheduled Time - Downtime) / Scheduled Time

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date
            end_date: Filter end date
            total_scheduled_hours: Total scheduled hours for the period

        Returns:
            Dictionary with availability statistics
        """
        # Get downtime records for the period
        records = self.list_downtime(
            user=user,
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Get all records
        )

        # Sum total downtime hours
        total_downtime_hours = Decimal("0")
        for record in records:
            if hasattr(record, 'duration_hours') and record.duration_hours:
                total_downtime_hours += Decimal(str(record.duration_hours))

        # Calculate availability
        if total_scheduled_hours and total_scheduled_hours > 0:
            availability = (
                (total_scheduled_hours - total_downtime_hours) / total_scheduled_hours
            ) * 100
        else:
            availability = Decimal("100.00")  # No scheduled time means 100% available

        return {
            "client_id": client_id,
            "total_downtime_hours": float(total_downtime_hours),
            "total_scheduled_hours": float(total_scheduled_hours) if total_scheduled_hours else None,
            "availability_percentage": float(max(Decimal("0"), min(availability, Decimal("100")))),
            "downtime_events": len(records)
        }

    def get_downtime_by_category(
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[dict]:
        """
        Get downtime grouped by category (Pareto analysis).

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            List of categories with total hours and counts
        """
        records = self.list_downtime(
            user=user,
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        # Group by category
        categories = {}
        for record in records:
            category = getattr(record, 'category', 'Unknown')
            if category not in categories:
                categories[category] = {
                    "category": category,
                    "total_hours": Decimal("0"),
                    "event_count": 0
                }

            if hasattr(record, 'duration_hours') and record.duration_hours:
                categories[category]["total_hours"] += Decimal(str(record.duration_hours))
            categories[category]["event_count"] += 1

        # Sort by total hours descending
        sorted_categories = sorted(
            categories.values(),
            key=lambda x: x["total_hours"],
            reverse=True
        )

        # Convert Decimals to floats for JSON serialization
        return [
            {
                "category": c["category"],
                "total_hours": float(c["total_hours"]),
                "event_count": c["event_count"]
            }
            for c in sorted_categories
        ]


def get_downtime_service(db: Session = Depends(get_db)) -> DowntimeService:
    """
    FastAPI dependency to get DowntimeService instance.
    """
    return DowntimeService(db)

"""
Hold Service
Service layer for WIP Hold operations.
Coordinates CRUD operations with hold/resume workflow and aging tracking.

Phase 2: Service Layer Enforcement
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.user import User
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
    TotalHoldDurationResponse,
)
from backend.crud.hold import (
    create_wip_hold,
    get_wip_hold,
    get_wip_holds,
    update_wip_hold,
    delete_wip_hold,
    resume_hold,
    release_hold,
    get_total_hold_duration,
    get_holds_by_work_order,
    bulk_update_aging,
)
from backend.database import get_db


class HoldService:
    """
    Service layer for WIP Hold operations.

    Wraps hold CRUD with business logic:
    - Hold/resume workflow management
    - Duration auto-calculation (P2-001)
    - Aging tracking and bulk updates
    - Approval workflow enforcement
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_hold(self, data: WIPHoldCreate, user: User) -> WIPHoldResponse:
        """
        Create a new WIP hold.

        Enforces approval workflow:
        - Operators create with PENDING_HOLD_APPROVAL status
        - Supervisors/Admins create with ON_HOLD status (auto-approved)

        Args:
            data: Hold creation data
            user: Authenticated user

        Returns:
            Created hold with initial status
        """
        return create_wip_hold(self.db, data, user)

    def get_hold(self, hold_id: str, user: User) -> Optional[WIPHoldResponse]:
        """
        Get a hold by ID.

        Args:
            hold_id: Hold entry ID
            user: Authenticated user

        Returns:
            Hold entry or None
        """
        hold = get_wip_hold(self.db, hold_id, user)
        return WIPHoldResponse.model_validate(hold) if hold else None

    def list_holds(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        client_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        released: Optional[bool] = None,
        hold_reason_category: Optional[str] = None,
    ) -> List:
        """
        List holds with filtering.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records
            start_date: Filter start date
            end_date: Filter end date
            client_id: Filter by client
            work_order_id: Filter by work order
            released: Filter by release status
            hold_reason_category: Filter by reason category

        Returns:
            List of holds
        """
        return get_wip_holds(
            self.db, user, skip, limit, start_date, end_date, client_id, work_order_id, released, hold_reason_category
        )

    def update_hold(self, hold_id: int, data: WIPHoldUpdate, user: User) -> Optional[WIPHoldResponse]:
        """
        Update a hold.

        Args:
            hold_id: Hold ID to update
            data: Update data
            user: Authenticated user

        Returns:
            Updated hold
        """
        return update_wip_hold(self.db, hold_id, data, user)

    def delete_hold(self, hold_id: int, user: User) -> bool:
        """
        Soft delete a hold.

        Args:
            hold_id: Hold ID to delete
            user: Authenticated user

        Returns:
            True if deleted
        """
        return delete_wip_hold(self.db, hold_id, user)

    def resume_hold(self, hold_id: int, user: User, notes: Optional[str] = None) -> Optional[WIPHoldResponse]:
        """
        Resume a hold (mark as RESUMED).

        Auto-calculates hold duration (P2-001).

        Args:
            hold_id: Hold ID to resume
            user: Authenticated user
            notes: Optional notes

        Returns:
            Updated hold with calculated duration
        """
        return resume_hold(self.db, hold_id, user.user_id, user, notes)

    def release_hold(
        self,
        hold_id: int,
        user: User,
        quantity_released: Optional[int] = None,
        quantity_scrapped: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[WIPHoldResponse]:
        """
        Release a hold with quantities.

        Args:
            hold_id: Hold ID to release
            user: Authenticated user
            quantity_released: Quantity released
            quantity_scrapped: Quantity scrapped
            notes: Optional notes

        Returns:
            Updated hold
        """
        return release_hold(self.db, hold_id, user, quantity_released, quantity_scrapped, notes)

    def get_total_hold_duration(self, work_order_number: str, user: Optional[User] = None) -> TotalHoldDurationResponse:
        """
        Get total hold duration for a work order.

        Required for WIP aging adjustment (P2-001).

        Args:
            work_order_number: Work order number
            user: Optional user for filtering

        Returns:
            Total duration across all holds
        """
        return get_total_hold_duration(self.db, work_order_number, user)

    def get_holds_by_work_order(self, work_order_number: str, user: User) -> List[WIPHoldResponse]:
        """
        Get all holds for a work order.

        Args:
            work_order_number: Work order number
            user: Authenticated user

        Returns:
            List of holds
        """
        return get_holds_by_work_order(self.db, work_order_number, user)

    def bulk_update_aging(self, user: User) -> int:
        """
        Bulk update aging for all unreleased holds.

        Used for scheduled batch jobs.

        Args:
            user: Authenticated user

        Returns:
            Number of holds updated
        """
        return bulk_update_aging(self.db, user)


def get_hold_service(db: Session = Depends(get_db)) -> HoldService:
    """
    FastAPI dependency to get HoldService instance.
    """
    return HoldService(db)

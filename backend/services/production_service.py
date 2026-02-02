"""
Production Service
Service layer for Production Entry operations.
Coordinates CRUD operations with business logic and KPI calculations.

Phase 2: Service Layer Enforcement
"""
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.user import User
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryWithKPIs
)
from backend.crud.production import (
    create_production_entry,
    get_production_entry,
    get_production_entries,
    update_production_entry,
    delete_production_entry,
    get_production_entry_with_details,
    get_daily_summary,
    batch_create_entries,
)
from backend.services.production_kpi_service import ProductionKPIService
from backend.database import get_db


class ProductionService:
    """
    Service layer for Production operations.

    Wraps CRUD operations with business logic:
    - Automatic KPI calculation on create/update
    - Batch imports with validation
    - Entry details with KPI breakdown
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.kpi_service = ProductionKPIService(db)

    def create_entry(
        self,
        data: ProductionEntryCreate,
        user: User
    ) -> ProductionEntry:
        """
        Create a production entry with automatic KPI calculation.

        Args:
            data: Production entry creation data
            user: Authenticated user

        Returns:
            Created production entry with calculated KPIs
        """
        return create_production_entry(self.db, data, user)

    def get_entry(
        self,
        entry_id: int,
        user: User
    ) -> Optional[ProductionEntry]:
        """
        Get a production entry by ID.

        Args:
            entry_id: Production entry ID
            user: Authenticated user

        Returns:
            Production entry or None
        """
        return get_production_entry(self.db, entry_id, user)

    def get_entry_with_kpis(
        self,
        entry_id: int,
        user: User
    ) -> Optional[ProductionEntryWithKPIs]:
        """
        Get a production entry with full KPI breakdown.

        Args:
            entry_id: Production entry ID
            user: Authenticated user

        Returns:
            Production entry with detailed KPIs
        """
        return get_production_entry_with_details(self.db, entry_id, user)

    def list_entries(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        product_id: Optional[int] = None,
        shift_id: Optional[int] = None,
        client_id: Optional[str] = None
    ) -> List[ProductionEntry]:
        """
        List production entries with filtering.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records
            start_date: Filter by start date
            end_date: Filter by end date
            product_id: Filter by product
            shift_id: Filter by shift
            client_id: Filter by client

        Returns:
            List of production entries
        """
        return get_production_entries(
            self.db, user, skip, limit,
            start_date, end_date, product_id, shift_id, client_id
        )

    def update_entry(
        self,
        entry_id: int,
        data: ProductionEntryUpdate,
        user: User
    ) -> Optional[ProductionEntry]:
        """
        Update a production entry with KPI recalculation.

        Args:
            entry_id: Entry ID to update
            data: Update data
            user: Authenticated user

        Returns:
            Updated production entry
        """
        return update_production_entry(self.db, entry_id, data, user)

    def delete_entry(
        self,
        entry_id: int,
        user: User
    ) -> bool:
        """
        Soft delete a production entry.

        Args:
            entry_id: Entry ID to delete
            user: Authenticated user

        Returns:
            True if deleted
        """
        return delete_production_entry(self.db, entry_id, user)

    def get_daily_summary(
        self,
        user: User,
        start_date: date,
        end_date: Optional[date] = None,
        client_id: Optional[str] = None
    ) -> List[dict]:
        """
        Get daily production summary.

        Args:
            user: Authenticated user
            start_date: Start date
            end_date: End date
            client_id: Filter by client

        Returns:
            List of daily summaries
        """
        return get_daily_summary(self.db, user, start_date, end_date, client_id)

    def batch_import(
        self,
        entries: List[ProductionEntryCreate],
        user: User
    ) -> List[ProductionEntry]:
        """
        Batch import production entries (CSV upload).

        Args:
            entries: List of entry data
            user: Authenticated user

        Returns:
            List of created entries
        """
        return batch_create_entries(self.db, entries, user)


def get_production_service(db: Session = Depends(get_db)) -> ProductionService:
    """
    FastAPI dependency to get ProductionService instance.

    Usage:
        @router.post("/entries")
        def create_entry(
            data: ProductionEntryCreate,
            service: ProductionService = Depends(get_production_service),
            current_user: User = Depends(get_current_user)
        ):
            return service.create_entry(data, current_user)
    """
    return ProductionService(db)

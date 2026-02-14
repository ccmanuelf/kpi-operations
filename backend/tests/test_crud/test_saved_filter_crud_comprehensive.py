"""
Comprehensive Saved Filter CRUD Tests
Tests CRUD operations with real database transactions.
Target: Increase crud/saved_filter.py coverage from 20% to 85%+
"""

import pytest
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from backend.database import Base
from backend.schemas import ClientType
from backend.models.filters import (
    FilterType,
    SavedFilterCreate,
    SavedFilterUpdate,
    FilterConfig,
    DateRangeConfig,
    DateRangeType,
)
from backend.crud import saved_filter as saved_filter_crud
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture(scope="function")
def filter_db():
    """Create a fresh database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def filter_setup(filter_db):
    """Create standard test data for filter tests."""
    db = filter_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="FILTER-TEST", client_name="Filter Test Client", client_type=ClientType.HOURLY_RATE
    )

    # Create users
    user1 = TestDataFactory.create_user(
        db, user_id="filter-user-001", username="filter_user1", role="supervisor", client_id=client.client_id
    )

    user2 = TestDataFactory.create_user(
        db, user_id="filter-user-002", username="filter_user2", role="supervisor", client_id=client.client_id
    )

    db.commit()

    return {
        "db": db,
        "client": client,
        "user1": user1,
        "user2": user2,
    }


class TestCreateSavedFilter:
    """Tests for create_saved_filter function."""

    def test_create_saved_filter_success(self, filter_setup):
        """Test creating a saved filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        filter_config = FilterConfig(
            date_range=DateRangeConfig(type=DateRangeType.RELATIVE, relative_days=7),
            status_filter=["RECEIVED", "IN_PROGRESS"],
        )
        filter_data = SavedFilterCreate(
            filter_name="My Production Filter",
            filter_type=FilterType.PRODUCTION,
            filter_config=filter_config,
            is_default=False,
        )

        result = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        assert result is not None
        assert result.filter_name == "My Production Filter"
        assert result.filter_type == "production"
        assert result.user_id == user.user_id
        assert result.usage_count == 0

    def test_create_saved_filter_as_default(self, filter_setup):
        """Test creating a filter as default."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        filter_data = SavedFilterCreate(
            filter_name="Default Filter",
            filter_type=FilterType.DASHBOARD,
            filter_config=FilterConfig(),
            is_default=True,
        )

        result = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        assert result.is_default is True

    def test_create_saved_filter_duplicate_name_error(self, filter_setup):
        """Test error when duplicate name exists."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        filter_data = SavedFilterCreate(
            filter_name="Duplicate Filter",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(),
            is_default=False,
        )

        # Create first filter
        saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail.lower()


class TestGetSavedFilters:
    """Tests for get_saved_filters function."""

    def test_get_saved_filters_empty(self, filter_setup):
        """Test getting filters when none exist."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        results = saved_filter_crud.get_saved_filters(db, user.user_id)

        assert len(results) == 0

    def test_get_saved_filters_multiple(self, filter_setup):
        """Test getting multiple filters."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create multiple filters
        for i in range(3):
            filter_data = SavedFilterCreate(
                filter_name=f"Filter {i}",
                filter_type=FilterType.PRODUCTION,
                filter_config=FilterConfig(),
                is_default=False,
            )
            saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        results = saved_filter_crud.get_saved_filters(db, user.user_id)

        assert len(results) == 3

    def test_get_saved_filters_by_type(self, filter_setup):
        """Test filtering by type."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filters of different types
        filter_types = [
            (FilterType.PRODUCTION, "Prod Filter 1"),
            (FilterType.DASHBOARD, "Dashboard Filter"),
            (FilterType.PRODUCTION, "Prod Filter 2"),
        ]
        for ftype, name in filter_types:
            filter_data = SavedFilterCreate(
                filter_name=name, filter_type=ftype, filter_config=FilterConfig(), is_default=False
            )
            saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        results = saved_filter_crud.get_saved_filters(db, user.user_id, filter_type="production")

        assert len(results) == 2

    def test_get_saved_filters_user_isolation(self, filter_setup):
        """Test users only see their own filters."""
        db = filter_setup["db"]
        user1 = filter_setup["user1"]
        user2 = filter_setup["user2"]

        # Create filter for user1
        filter_data = SavedFilterCreate(
            filter_name="User1 Filter",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(),
            is_default=False,
        )
        saved_filter_crud.create_saved_filter(db, user1.user_id, filter_data)

        # User2 should not see user1's filter
        results = saved_filter_crud.get_saved_filters(db, user2.user_id)

        assert len(results) == 0


class TestGetSavedFilter:
    """Tests for get_saved_filter function."""

    def test_get_saved_filter_found(self, filter_setup):
        """Test getting a specific filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filter
        filter_data = SavedFilterCreate(
            filter_name="Specific Filter",
            filter_type=FilterType.QUALITY,
            filter_config=FilterConfig(kpi_min_efficiency=50.0),
            is_default=False,
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        result = saved_filter_crud.get_saved_filter(db, created.filter_id, user.user_id)

        assert result is not None
        assert result.filter_name == "Specific Filter"

    def test_get_saved_filter_not_found(self, filter_setup):
        """Test getting non-existent filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        with pytest.raises(HTTPException) as exc_info:
            saved_filter_crud.get_saved_filter(db, 99999, user.user_id)

        assert exc_info.value.status_code == 404

    def test_get_saved_filter_wrong_user(self, filter_setup):
        """Test user cannot access another user's filter."""
        db = filter_setup["db"]
        user1 = filter_setup["user1"]
        user2 = filter_setup["user2"]

        # Create filter for user1
        filter_data = SavedFilterCreate(
            filter_name="User1 Private",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(),
            is_default=False,
        )
        created = saved_filter_crud.create_saved_filter(db, user1.user_id, filter_data)

        # User2 tries to access it
        with pytest.raises(HTTPException) as exc_info:
            saved_filter_crud.get_saved_filter(db, created.filter_id, user2.user_id)

        assert exc_info.value.status_code == 403


class TestUpdateSavedFilter:
    """Tests for update_saved_filter function."""

    def test_update_saved_filter_name(self, filter_setup):
        """Test updating filter name."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filter
        filter_data = SavedFilterCreate(
            filter_name="Original Name",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(),
            is_default=False,
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Update
        update_data = SavedFilterUpdate(filter_name="Updated Name")
        result = saved_filter_crud.update_saved_filter(db, created.filter_id, user.user_id, update_data)

        assert result.filter_name == "Updated Name"

    def test_update_saved_filter_set_default(self, filter_setup):
        """Test setting filter as default."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create two filters
        for i in range(2):
            filter_data = SavedFilterCreate(
                filter_name=f"Filter {i}",
                filter_type=FilterType.PRODUCTION,
                filter_config=FilterConfig(),
                is_default=(i == 0),  # First one is default
            )
            saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Get filters
        filters = saved_filter_crud.get_saved_filters(db, user.user_id)
        second_filter = [f for f in filters if f.filter_name == "Filter 1"][0]

        # Set second filter as default
        update_data = SavedFilterUpdate(is_default=True)
        saved_filter_crud.update_saved_filter(db, second_filter.filter_id, user.user_id, update_data)

        # Verify new default
        default = saved_filter_crud.get_default_filter(db, user.user_id, "production")
        assert default.filter_name == "Filter 1"

    def test_update_saved_filter_duplicate_name_error(self, filter_setup):
        """Test error when updating to duplicate name."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create two filters
        filter1 = SavedFilterCreate(
            filter_name="Filter A", filter_type=FilterType.PRODUCTION, filter_config=FilterConfig(), is_default=False
        )
        filter2 = SavedFilterCreate(
            filter_name="Filter B", filter_type=FilterType.PRODUCTION, filter_config=FilterConfig(), is_default=False
        )
        saved_filter_crud.create_saved_filter(db, user.user_id, filter1)
        created2 = saved_filter_crud.create_saved_filter(db, user.user_id, filter2)

        # Try to rename filter2 to filter1's name
        update_data = SavedFilterUpdate(filter_name="Filter A")

        with pytest.raises(HTTPException) as exc_info:
            saved_filter_crud.update_saved_filter(db, created2.filter_id, user.user_id, update_data)

        assert exc_info.value.status_code == 400


class TestDeleteSavedFilter:
    """Tests for delete_saved_filter function."""

    def test_delete_saved_filter_success(self, filter_setup):
        """Test deleting a filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filter
        filter_data = SavedFilterCreate(
            filter_name="To Delete", filter_type=FilterType.PRODUCTION, filter_config=FilterConfig(), is_default=False
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Delete
        result = saved_filter_crud.delete_saved_filter(db, created.filter_id, user.user_id)

        assert result is True

        # Verify deleted
        with pytest.raises(HTTPException) as exc_info:
            saved_filter_crud.get_saved_filter(db, created.filter_id, user.user_id)
        assert exc_info.value.status_code == 404


class TestApplyFilter:
    """Tests for apply_filter function."""

    def test_apply_filter_updates_usage(self, filter_setup):
        """Test applying filter updates usage statistics."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filter
        filter_data = SavedFilterCreate(
            filter_name="Usage Test", filter_type=FilterType.PRODUCTION, filter_config=FilterConfig(), is_default=False
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        assert created.usage_count == 0
        assert created.last_used_at is None

        # Apply filter
        result = saved_filter_crud.apply_filter(db, created.filter_id, user.user_id)

        assert result.usage_count == 1
        assert result.last_used_at is not None


class TestGetDefaultFilter:
    """Tests for get_default_filter function."""

    def test_get_default_filter_found(self, filter_setup):
        """Test getting default filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create default filter
        filter_data = SavedFilterCreate(
            filter_name="Default Production",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(),
            is_default=True,
        )
        saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        result = saved_filter_crud.get_default_filter(db, user.user_id, "production")

        assert result is not None
        assert result.filter_name == "Default Production"

    def test_get_default_filter_not_found(self, filter_setup):
        """Test getting default when none exists."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        result = saved_filter_crud.get_default_filter(db, user.user_id, "production")

        assert result is None


class TestSetDefaultFilter:
    """Tests for set_default_filter function."""

    def test_set_default_filter_success(self, filter_setup):
        """Test setting a filter as default."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create non-default filter
        filter_data = SavedFilterCreate(
            filter_name="Make Default", filter_type=FilterType.QUALITY, filter_config=FilterConfig(), is_default=False
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Set as default
        result = saved_filter_crud.set_default_filter(db, created.filter_id, user.user_id)

        assert result.is_default is True


class TestUnsetDefaultFilter:
    """Tests for unset_default_filter function."""

    def test_unset_default_filter_success(self, filter_setup):
        """Test unsetting default status."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create default filter
        filter_data = SavedFilterCreate(
            filter_name="Was Default", filter_type=FilterType.PRODUCTION, filter_config=FilterConfig(), is_default=True
        )
        created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Unset default
        result = saved_filter_crud.unset_default_filter(db, created.filter_id, user.user_id)

        assert result.is_default is False


class TestFilterHistory:
    """Tests for filter history functions."""

    def test_add_to_filter_history(self, filter_setup):
        """Test adding to filter history."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        filter_config = FilterConfig(date_range=DateRangeConfig(type=DateRangeType.RELATIVE, relative_days=1))

        result = saved_filter_crud.add_to_filter_history(db, user.user_id, filter_config)

        assert result is not None
        assert result.user_id == user.user_id

    def test_get_filter_history(self, filter_setup):
        """Test getting filter history."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Add some history
        for i in range(3):
            filter_config = FilterConfig(date_range=DateRangeConfig(type=DateRangeType.RELATIVE, relative_days=i + 1))
            saved_filter_crud.add_to_filter_history(db, user.user_id, filter_config)

        results = saved_filter_crud.get_filter_history(db, user.user_id)

        assert len(results) == 3

    def test_clear_filter_history_no_entries(self, filter_setup):
        """Test clearing filter history when empty."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Clear when empty
        deleted_count = saved_filter_crud.clear_filter_history(db, user.user_id)

        assert deleted_count == 0


class TestFilterStatistics:
    """Tests for get_filter_statistics function."""

    def test_get_filter_statistics_empty(self, filter_setup):
        """Test statistics with no filters."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        stats = saved_filter_crud.get_filter_statistics(db, user.user_id)

        assert stats["total_filters"] == 0
        assert stats["total_usage_count"] == 0

    def test_get_filter_statistics_with_data(self, filter_setup):
        """Test statistics with filters."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create filters
        for i, ftype in enumerate([FilterType.PRODUCTION, FilterType.QUALITY]):
            filter_data = SavedFilterCreate(
                filter_name=f"Filter {i}", filter_type=ftype, filter_config=FilterConfig(), is_default=False
            )
            created = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)
            # Apply to increase usage
            saved_filter_crud.apply_filter(db, created.filter_id, user.user_id)

        stats = saved_filter_crud.get_filter_statistics(db, user.user_id)

        assert stats["total_filters"] == 2
        assert stats["total_usage_count"] == 2
        assert "production" in stats["filters_by_type"]


class TestDuplicateFilter:
    """Tests for duplicate_filter function."""

    def test_duplicate_filter_success(self, filter_setup):
        """Test duplicating a filter."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create original
        filter_data = SavedFilterCreate(
            filter_name="Original",
            filter_type=FilterType.PRODUCTION,
            filter_config=FilterConfig(date_range=DateRangeConfig(type=DateRangeType.RELATIVE, relative_days=7)),
            is_default=True,
        )
        original = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Duplicate
        duplicate = saved_filter_crud.duplicate_filter(db, original.filter_id, user.user_id)

        assert duplicate.filter_name == "Copy of Original"
        assert duplicate.filter_type == original.filter_type
        assert duplicate.is_default is False  # Duplicates are not default
        assert duplicate.usage_count == 0

    def test_duplicate_filter_custom_name(self, filter_setup):
        """Test duplicating with custom name."""
        db = filter_setup["db"]
        user = filter_setup["user1"]

        # Create original
        filter_data = SavedFilterCreate(
            filter_name="Original", filter_type=FilterType.QUALITY, filter_config=FilterConfig(), is_default=False
        )
        original = saved_filter_crud.create_saved_filter(db, user.user_id, filter_data)

        # Duplicate with custom name
        duplicate = saved_filter_crud.duplicate_filter(db, original.filter_id, user.user_id, new_name="Custom Name")

        assert duplicate.filter_name == "Custom Name"

"""
Tests for Hold Status and Hold Reason Catalog CRUD operations.
Uses real database sessions — no mocks for DB layer.
"""

import pytest
from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.hold_catalog import (
    create_hold_status,
    list_hold_statuses,
    update_hold_status,
    deactivate_hold_status,
    validate_hold_status_for_client,
    create_hold_reason,
    list_hold_reasons,
    update_hold_reason,
    deactivate_hold_reason,
    validate_hold_reason_for_client,
    seed_defaults,
    DEFAULT_HOLD_STATUSES,
    DEFAULT_HOLD_REASONS,
)
from backend.schemas.hold_catalog import (
    HoldStatusCatalogCreate,
    HoldStatusCatalogUpdate,
    HoldReasonCatalogCreate,
    HoldReasonCatalogUpdate,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _seed_client(db, client_id="CAT-TEST-C1"):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="Catalog Test Client")
    db.commit()
    return client


# ============================================================================
# TestSeedDefaults
# ============================================================================
class TestSeedDefaults:
    """Tests for seed_defaults function."""

    def test_seed_defaults_creates_statuses_and_reasons(self, transactional_db):
        """seed_defaults creates all 7 statuses and 11 reasons for a new client."""
        db = transactional_db
        _seed_client(db, "SEED-C1")

        result = seed_defaults(db, "SEED-C1")

        assert result["statuses_created"] == len(DEFAULT_HOLD_STATUSES)
        assert result["reasons_created"] == len(DEFAULT_HOLD_REASONS)
        assert result["skipped"] == 0

        # Verify counts in DB
        statuses = list_hold_statuses(db, "SEED-C1")
        reasons = list_hold_reasons(db, "SEED-C1")
        assert len(statuses) == 7
        assert len(reasons) == 11

    def test_seed_defaults_is_idempotent(self, transactional_db):
        """Running seed_defaults twice does not create duplicates."""
        db = transactional_db
        _seed_client(db, "SEED-C2")

        first = seed_defaults(db, "SEED-C2")
        second = seed_defaults(db, "SEED-C2")

        assert first["statuses_created"] == 7
        assert first["reasons_created"] == 11
        assert second["statuses_created"] == 0
        assert second["reasons_created"] == 0
        assert second["skipped"] == 18  # 7 + 11

    def test_seed_defaults_client_isolation(self, transactional_db):
        """Seeding for one client does not affect another."""
        db = transactional_db
        _seed_client(db, "SEED-ISO-A")
        _seed_client(db, "SEED-ISO-B")

        seed_defaults(db, "SEED-ISO-A")

        # Client B should have zero entries
        statuses_b = list_hold_statuses(db, "SEED-ISO-B")
        reasons_b = list_hold_reasons(db, "SEED-ISO-B")
        assert len(statuses_b) == 0
        assert len(reasons_b) == 0


# ============================================================================
# TestHoldStatusCatalogCRUD
# ============================================================================
class TestHoldStatusCatalogCRUD:
    """Tests for hold status catalog CRUD operations."""

    def test_create_hold_status(self, transactional_db):
        """Create a custom hold status for a client."""
        db = transactional_db
        _seed_client(db, "STS-C1")

        data = HoldStatusCatalogCreate(
            client_id="STS-C1",
            status_code="CUSTOM_STATUS",
            display_name="My Custom Status",
            sort_order=99,
        )
        result = create_hold_status(db, data)

        assert result.catalog_id is not None
        assert result.status_code == "CUSTOM_STATUS"
        assert result.display_name == "My Custom Status"
        assert result.is_active is True
        assert result.is_default is False

    def test_create_duplicate_status_raises(self, transactional_db):
        """Creating a duplicate (client_id, status_code) raises ValueError."""
        db = transactional_db
        _seed_client(db, "STS-C2")

        data = HoldStatusCatalogCreate(
            client_id="STS-C2",
            status_code="DUPLICATE",
            display_name="First",
        )
        create_hold_status(db, data)

        with pytest.raises(ValueError, match="already exists"):
            create_hold_status(db, data)

    def test_list_hold_statuses_excludes_inactive(self, transactional_db):
        """list_hold_statuses excludes inactive entries by default."""
        db = transactional_db
        _seed_client(db, "STS-C3")
        seed_defaults(db, "STS-C3")

        # Deactivate the first status
        statuses = list_hold_statuses(db, "STS-C3")
        deactivate_hold_status(db, statuses[0].catalog_id)

        active = list_hold_statuses(db, "STS-C3")
        all_entries = list_hold_statuses(db, "STS-C3", include_inactive=True)
        assert len(active) == 6  # 7 - 1
        assert len(all_entries) == 7

    def test_update_hold_status(self, transactional_db):
        """Update display_name and sort_order of a status."""
        db = transactional_db
        _seed_client(db, "STS-C4")

        data = HoldStatusCatalogCreate(
            client_id="STS-C4",
            status_code="EDITABLE",
            display_name="Before",
            sort_order=1,
        )
        created = create_hold_status(db, data)

        updated = update_hold_status(
            db,
            created.catalog_id,
            HoldStatusCatalogUpdate(display_name="After", sort_order=99),
        )
        assert updated.display_name == "After"
        assert updated.sort_order == 99

    def test_update_nonexistent_returns_none(self, transactional_db):
        """Updating a nonexistent catalog_id returns None."""
        result = update_hold_status(
            transactional_db,
            999999,
            HoldStatusCatalogUpdate(display_name="Ghost"),
        )
        assert result is None

    def test_deactivate_nonexistent_returns_false(self, transactional_db):
        """Deactivating a nonexistent catalog_id returns False."""
        assert deactivate_hold_status(transactional_db, 999999) is False

    def test_validate_hold_status_for_client(self, transactional_db):
        """validate_hold_status_for_client returns True/False correctly."""
        db = transactional_db
        _seed_client(db, "STS-C5")
        seed_defaults(db, "STS-C5")

        assert validate_hold_status_for_client(db, "STS-C5", "ON_HOLD") is True
        assert validate_hold_status_for_client(db, "STS-C5", "NONEXISTENT") is False


# ============================================================================
# TestHoldReasonCatalogCRUD
# ============================================================================
class TestHoldReasonCatalogCRUD:
    """Tests for hold reason catalog CRUD operations."""

    def test_create_hold_reason(self, transactional_db):
        """Create a custom hold reason for a client."""
        db = transactional_db
        _seed_client(db, "RSN-C1")

        data = HoldReasonCatalogCreate(
            client_id="RSN-C1",
            reason_code="CUSTOM_REASON",
            display_name="My Custom Reason",
            sort_order=99,
        )
        result = create_hold_reason(db, data)

        assert result.catalog_id is not None
        assert result.reason_code == "CUSTOM_REASON"
        assert result.display_name == "My Custom Reason"
        assert result.is_active is True

    def test_create_duplicate_reason_raises(self, transactional_db):
        """Creating a duplicate (client_id, reason_code) raises ValueError."""
        db = transactional_db
        _seed_client(db, "RSN-C2")

        data = HoldReasonCatalogCreate(
            client_id="RSN-C2",
            reason_code="DUPLICATE",
            display_name="First",
        )
        create_hold_reason(db, data)

        with pytest.raises(ValueError, match="already exists"):
            create_hold_reason(db, data)

    def test_list_hold_reasons_ordered_by_sort(self, transactional_db):
        """list_hold_reasons returns entries ordered by sort_order."""
        db = transactional_db
        _seed_client(db, "RSN-C3")
        seed_defaults(db, "RSN-C3")

        reasons = list_hold_reasons(db, "RSN-C3")
        sort_orders = [r.sort_order for r in reasons]
        assert sort_orders == sorted(sort_orders)

    def test_update_hold_reason(self, transactional_db):
        """Update display_name of a reason."""
        db = transactional_db
        _seed_client(db, "RSN-C4")

        data = HoldReasonCatalogCreate(
            client_id="RSN-C4",
            reason_code="EDITABLE",
            display_name="Before",
        )
        created = create_hold_reason(db, data)

        updated = update_hold_reason(
            db,
            created.catalog_id,
            HoldReasonCatalogUpdate(display_name="After"),
        )
        assert updated.display_name == "After"

    def test_deactivate_hold_reason(self, transactional_db):
        """Deactivate a reason and verify it's excluded from default listing."""
        db = transactional_db
        _seed_client(db, "RSN-C5")

        data = HoldReasonCatalogCreate(
            client_id="RSN-C5",
            reason_code="TO_DEACTIVATE",
            display_name="Will Be Removed",
        )
        created = create_hold_reason(db, data)
        assert deactivate_hold_reason(db, created.catalog_id) is True

        active = list_hold_reasons(db, "RSN-C5")
        codes = [r.reason_code for r in active]
        assert "TO_DEACTIVATE" not in codes

    def test_validate_hold_reason_for_client(self, transactional_db):
        """validate_hold_reason_for_client returns True/False correctly."""
        db = transactional_db
        _seed_client(db, "RSN-C6")
        seed_defaults(db, "RSN-C6")

        assert validate_hold_reason_for_client(db, "RSN-C6", "QUALITY_ISSUE") is True
        assert validate_hold_reason_for_client(db, "RSN-C6", "NONEXISTENT") is False

    def test_validate_inactive_reason_returns_false(self, transactional_db):
        """An inactive reason should not validate."""
        db = transactional_db
        _seed_client(db, "RSN-C7")

        data = HoldReasonCatalogCreate(
            client_id="RSN-C7",
            reason_code="TEMP",
            display_name="Temp",
        )
        created = create_hold_reason(db, data)
        deactivate_hold_reason(db, created.catalog_id)

        assert validate_hold_reason_for_client(db, "RSN-C7", "TEMP") is False

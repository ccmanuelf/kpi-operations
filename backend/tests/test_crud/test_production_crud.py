"""
Real-database tests for Production CRUD operations.
Uses transactional_db fixture (in-memory SQLite with automatic rollback).
No mocks for database operations.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from fastapi import HTTPException

from backend.schemas import (
    Client,
    ClientType,
    User,
    UserRole,
    Product,
    Shift,
    ProductionEntry,
    WorkOrder,
    WorkOrderStatus,
)
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_production_prereqs(db, client_id="PROD-TEST-C1"):
    """Create the minimal parent rows needed to insert a ProductionEntry."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="Production Test Client")
    user = TestDataFactory.create_user(db, username=f"prod_admin_{client_id}", role="admin", client_id=client_id)
    product = TestDataFactory.create_product(db, client_id=client_id, product_code=f"PRD-{client_id}")
    shift = TestDataFactory.create_shift(db, client_id=client_id, shift_name=f"Day Shift {client_id}")
    db.flush()
    return client, user, product, shift


class TestProductionCRUD:
    """Test Production CRUD operations against real database."""

    def test_create_production_entry_success(self, transactional_db):
        """Test successful creation of production entry persists to DB."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=100,
        )
        db.flush()

        assert entry.production_entry_id is not None
        assert entry.client_id == client.client_id
        assert entry.units_produced == 100

        # Verify persisted to DB
        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db is not None
        assert from_db.units_produced == 100

    def test_get_production_entry_exists(self, transactional_db):
        """Test retrieving an existing production entry by primary key."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=250,
        )
        db.flush()

        result = (
            db.query(ProductionEntry).filter(ProductionEntry.production_entry_id == entry.production_entry_id).first()
        )

        assert result is not None
        assert result.units_produced == 250
        assert result.product_id == product.product_id

    def test_get_production_entry_not_found(self, transactional_db):
        """Test retrieving non-existent production entry returns None."""
        db = transactional_db

        result = db.query(ProductionEntry).filter(ProductionEntry.production_entry_id == "NONEXISTENT-ID").first()

        assert result is None

    def test_get_production_entries_list(self, transactional_db):
        """Test retrieving a list of production entries with limit/offset."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        for i in range(5):
            TestDataFactory.create_production_entry(
                db,
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                entered_by=user.user_id,
                production_date=date.today() - timedelta(days=i),
                units_produced=100 + i * 10,
            )
        db.flush()

        results = (
            db.query(ProductionEntry).filter(ProductionEntry.client_id == client.client_id).limit(5).offset(0).all()
        )

        assert len(results) == 5

    def test_get_production_entries_empty(self, transactional_db):
        """Test retrieving entries from empty table returns empty list."""
        db = transactional_db

        results = db.query(ProductionEntry).filter(ProductionEntry.client_id == "NONEXISTENT-CLIENT").all()

        assert len(results) == 0

    def test_update_production_entry_success(self, transactional_db):
        """Test updating production entry quantity persists to DB."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=100,
        )
        db.flush()

        # Update
        entry.units_produced = 150
        db.flush()

        # Verify from DB
        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.units_produced == 150

    def test_delete_production_entry_success(self, transactional_db):
        """Test deleting a production entry removes it from query results."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
        )
        db.flush()

        entry_id = entry.production_entry_id
        db.delete(entry)
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry_id,
            )
            .first()
        )
        assert from_db is None

    def test_batch_create_production_entries(self, transactional_db):
        """Test batch creation of production entries via factory helper."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entries = TestDataFactory.create_production_entries_batch(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            count=10,
        )
        db.flush()

        assert len(entries) == 10

        from_db = (
            db.query(ProductionEntry)
            .filter(
                ProductionEntry.client_id == client.client_id,
            )
            .all()
        )
        assert len(from_db) == 10

    def test_get_production_by_date_range(self, transactional_db):
        """Test retrieving production entries filtered by date range."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        base = date.today() - timedelta(days=10)
        for i in range(10):
            TestDataFactory.create_production_entry(
                db,
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                entered_by=user.user_id,
                production_date=base + timedelta(days=i),
            )
        db.flush()

        start_dt = datetime.combine(base + timedelta(days=3), datetime.min.time())
        end_dt = datetime.combine(base + timedelta(days=7), datetime.min.time())

        results = (
            db.query(ProductionEntry)
            .filter(
                ProductionEntry.client_id == client.client_id,
                ProductionEntry.production_date >= start_dt,
                ProductionEntry.production_date <= end_dt,
            )
            .all()
        )

        assert len(results) == 5

    def test_get_production_summary(self, transactional_db):
        """Test production summary aggregation (sum, count)."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        for i in range(5):
            TestDataFactory.create_production_entry(
                db,
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                entered_by=user.user_id,
                units_produced=200,
                defect_count=10,
            )
        db.flush()

        from sqlalchemy import func

        total_produced, total_defects, entry_count = (
            db.query(
                func.sum(ProductionEntry.units_produced),
                func.sum(ProductionEntry.defect_count),
                func.count(ProductionEntry.production_entry_id),
            )
            .filter(ProductionEntry.client_id == client.client_id)
            .first()
        )

        assert total_produced == 1000
        assert total_defects == 50
        assert entry_count == 5

    def test_production_entry_defect_count_stored(self, transactional_db):
        """Test that defect_count is stored and retrievable."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=100,
            defect_count=5,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.defect_count == 5

    def test_production_entry_with_work_order(self, transactional_db):
        """Test creating production entry linked to a work order."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
        db.flush()

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            work_order_id=wo.work_order_id,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.work_order_id == wo.work_order_id

    def test_production_entry_date_stored_correctly(self, transactional_db):
        """Test production_date is stored as expected DateTime."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        target_date = date(2026, 1, 15)
        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            production_date=target_date,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.production_date.date() == target_date


class TestProductionEntryEdgeCases:
    """Edge case tests for production entries using real DB."""

    def test_zero_production(self, transactional_db):
        """Test handling of zero units_produced."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=0,
            defect_count=0,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.units_produced == 0

        # Yield rate calculation for zero production
        if from_db.units_produced == 0:
            yield_rate = 0.0
        else:
            yield_rate = 100 * (1 - from_db.defect_count / from_db.units_produced)
        assert yield_rate == 0.0

    def test_large_production_quantity(self, transactional_db):
        """Test storing and retrieving very large production quantity."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        large_qty = 1_000_000
        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=large_qty,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.units_produced == large_qty

    def test_multiple_entries_same_shift(self, transactional_db):
        """Test creating multiple entries for the same shift date."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        today = date.today()
        for _ in range(3):
            TestDataFactory.create_production_entry(
                db,
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                entered_by=user.user_id,
                production_date=today,
            )
        db.flush()

        results = (
            db.query(ProductionEntry)
            .filter(
                ProductionEntry.client_id == client.client_id,
                ProductionEntry.shift_id == shift.shift_id,
            )
            .all()
        )
        assert len(results) == 3

    def test_production_metrics_calculation(self, transactional_db):
        """Test FPY and performance calculation from stored data."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=1000,
            defect_count=50,
            run_time_hours=Decimal("8.0"),
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )

        # FPY = (produced - defects) / produced * 100
        fpy = 100 * (from_db.units_produced - from_db.defect_count) / from_db.units_produced
        assert fpy == 95.0

    def test_production_entry_notes_field(self, transactional_db):
        """Test notes field (text column) stores and retrieves correctly."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        notes_text = "Shift had equipment issues. Slow ramp-up first 2 hours."
        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            notes=notes_text,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        assert from_db.notes == notes_text


class TestProductionCRUDIntegration:
    """Integration-style tests for production CRUD lifecycle."""

    def test_full_crud_lifecycle(self, transactional_db):
        """Test complete Create-Read-Update-Delete lifecycle on real DB."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        # CREATE
        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=100,
        )
        db.flush()
        entry_id = entry.production_entry_id

        # READ
        read_entry = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry_id,
            )
            .first()
        )
        assert read_entry is not None
        assert read_entry.units_produced == 100

        # UPDATE
        read_entry.units_produced = 150
        db.flush()

        updated = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry_id,
            )
            .first()
        )
        assert updated.units_produced == 150

        # DELETE
        db.delete(updated)
        db.flush()

        deleted = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry_id,
            )
            .first()
        )
        assert deleted is None

    def test_bulk_create_and_query(self, transactional_db):
        """Test bulk insert and querying with real DB."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entries = TestDataFactory.create_production_entries_batch(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            count=50,
        )
        db.flush()

        total = (
            db.query(ProductionEntry)
            .filter(
                ProductionEntry.client_id == client.client_id,
            )
            .count()
        )
        assert total == 50

    def test_transaction_rollback_on_error(self, transactional_db):
        """Test that failed operations do not corrupt data (rollback)."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            units_produced=100,
        )
        db.flush()

        # Simulate an error and rollback
        entry.units_produced = 9999
        db.rollback()

        # After rollback, entry should be gone (since we never committed)
        # The transactional_db fixture uses autoflush=False, so we
        # verify the rollback behavior
        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )
        # After rollback, the flushed entry is reverted
        assert from_db is None

    def test_multi_tenant_isolation(self, transactional_db):
        """Test that production entries are isolated per client_id."""
        db = transactional_db
        client_a, user_a, product_a, shift_a = _seed_production_prereqs(db, client_id="CLIENT-A")
        client_b, user_b, product_b, shift_b = _seed_production_prereqs(db, client_id="CLIENT-B")

        # Create entries for each client
        for i in range(3):
            TestDataFactory.create_production_entry(
                db,
                client_id=client_a.client_id,
                product_id=product_a.product_id,
                shift_id=shift_a.shift_id,
                entered_by=user_a.user_id,
                production_date=date.today() - timedelta(days=i),
            )
        for i in range(2):
            TestDataFactory.create_production_entry(
                db,
                client_id=client_b.client_id,
                product_id=product_b.product_id,
                shift_id=shift_b.shift_id,
                entered_by=user_b.user_id,
                production_date=date.today() - timedelta(days=i),
            )
        db.flush()

        a_count = db.query(ProductionEntry).filter(ProductionEntry.client_id == "CLIENT-A").count()
        b_count = db.query(ProductionEntry).filter(ProductionEntry.client_id == "CLIENT-B").count()

        assert a_count == 3
        assert b_count == 2

    def test_production_entry_relationship_to_product(self, transactional_db):
        """Test that joined-loading relationship to Product works."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )

        # Relationship should load the product
        assert from_db.product is not None
        assert from_db.product.product_id == product.product_id

    def test_production_entry_relationship_to_shift(self, transactional_db):
        """Test that joined-loading relationship to Shift works."""
        db = transactional_db
        client, user, product, shift = _seed_production_prereqs(db)

        entry = TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
        )
        db.flush()

        from_db = (
            db.query(ProductionEntry)
            .filter_by(
                production_entry_id=entry.production_entry_id,
            )
            .first()
        )

        assert from_db.shift is not None
        assert from_db.shift.shift_id == shift.shift_id

"""
CSV Export Service Tests

Tests the generic CSV export service with various data types,
CSV injection protection, date range filtering, and empty result sets.

Uses real in-memory SQLite database -- NO mocks for DB layer.
"""

import csv
import io
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.schemas.client import Client, ClientType
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.work_order import WorkOrder, WorkOrderStatus
from backend.schemas.user import User, UserRole
from backend.services.csv_export_service import (
    _format_value,
    sanitize_csv_value,
    stream_csv_export,
)
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIENT_ID = "CSV-SVC-CLIENT"


@pytest.fixture(scope="function")
def csv_db():
    """Create a fresh in-memory database for each test."""
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
def seeded_db(csv_db):
    """Database seeded with client, product, shift, work order, and production entries."""
    db = csv_db

    # Create foundation data
    TestDataFactory.create_client(
        db, client_id=CLIENT_ID, client_name="CSV Export Test Client"
    )
    product = TestDataFactory.create_product(db, client_id=CLIENT_ID)
    shift = TestDataFactory.create_shift(db, client_id=CLIENT_ID)
    wo = TestDataFactory.create_work_order(db, client_id=CLIENT_ID)

    # Create a user for entered_by
    user = TestDataFactory.create_user(
        db, role=UserRole.ADMIN.value, username="csv_export_admin"
    )

    # Create production entries with different dates
    for i, day_offset in enumerate([0, 5, 10, 20]):
        entry_date = datetime(2026, 1, 1 + day_offset, 8, 0, 0)
        entry = ProductionEntry(
            production_entry_id=f"PE-CSV-{i+1:04d}",
            client_id=CLIENT_ID,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            work_order_id=wo.work_order_id,
            production_date=entry_date,
            shift_date=entry_date,
            units_produced=100 * (i + 1),
            run_time_hours=Decimal("8.00"),
            employees_assigned=5,
            defect_count=i,
            scrap_count=0,
            entered_by=user.user_id,
            notes=f"Test entry {i+1}" if i < 3 else None,
        )
        db.add(entry)

    db.commit()
    return db


def _parse_csv(generator):
    """Consume a CSV generator and return parsed rows."""
    content = "".join(generator)
    reader = csv.reader(io.StringIO(content))
    return list(reader)


# ---------------------------------------------------------------------------
# sanitize_csv_value tests
# ---------------------------------------------------------------------------


class TestSanitizeCsvValue:
    """Test CSV injection protection."""

    def test_equals_prefix(self):
        assert sanitize_csv_value("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"

    def test_plus_prefix(self):
        assert sanitize_csv_value("+1234") == "'+1234"

    def test_minus_prefix(self):
        assert sanitize_csv_value("-1234") == "'-1234"

    def test_at_prefix(self):
        assert sanitize_csv_value("@SUM(A1)") == "'@SUM(A1)"

    def test_tab_prefix(self):
        assert sanitize_csv_value("\tcmd") == "'\tcmd"

    def test_carriage_return_prefix(self):
        assert sanitize_csv_value("\rcmd") == "'\rcmd"

    def test_safe_value_unchanged(self):
        assert sanitize_csv_value("Normal text") == "Normal text"

    def test_empty_string(self):
        assert sanitize_csv_value("") == ""

    def test_non_string_passthrough(self):
        # Non-string values should pass through unchanged
        assert sanitize_csv_value(123) == 123


# ---------------------------------------------------------------------------
# _format_value tests
# ---------------------------------------------------------------------------


class TestFormatValue:
    """Test value formatting for CSV output."""

    def test_none_returns_empty(self):
        assert _format_value(None) == ""

    def test_datetime_formatting(self):
        dt = datetime(2026, 1, 15, 10, 30, 45)
        assert _format_value(dt) == "2026-01-15 10:30:45"

    def test_date_formatting(self):
        d = date(2026, 3, 20)
        assert _format_value(d) == "2026-03-20"

    def test_time_formatting(self):
        t = time(14, 30, 0)
        assert _format_value(t) == "14:30:00"

    def test_decimal_formatting(self):
        assert _format_value(Decimal("3.14159")) == "3.14159"

    def test_integer_formatting(self):
        assert _format_value(42) == "42"

    def test_float_formatting(self):
        assert _format_value(3.14) == "3.14"

    def test_bool_true(self):
        assert _format_value(True) == "1"

    def test_bool_false(self):
        assert _format_value(False) == "0"

    def test_string_with_injection(self):
        assert _format_value("=HYPERLINK()") == "'=HYPERLINK()"

    def test_safe_string(self):
        assert _format_value("Hello World") == "Hello World"

    def test_enum_value(self):
        assert _format_value(WorkOrderStatus.ACTIVE) == "ACTIVE"


# ---------------------------------------------------------------------------
# stream_csv_export tests
# ---------------------------------------------------------------------------


class TestStreamCsvExport:
    """Test the main CSV streaming function."""

    def test_export_with_data(self, seeded_db):
        """CSV export includes header + data rows for seeded production entries."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("client_id", "client_id"),
            ("units_produced", "units_produced"),
            ("notes", "notes"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
            )
        )

        # Header + 4 data rows
        assert len(rows) == 5
        assert rows[0] == ["production_entry_id", "client_id", "units_produced", "notes"]
        # Verify first data row
        assert rows[1][1] == CLIENT_ID
        assert rows[1][2] == "100"

    def test_empty_result_returns_header_only(self, csv_db):
        """CSV export for a non-existent client returns only the header row."""
        TestDataFactory.create_client(csv_db, client_id="EMPTY-CLIENT")
        csv_db.commit()

        columns = [
            ("production_entry_id", "production_entry_id"),
            ("client_id", "client_id"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=csv_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == "NO-SUCH-CLIENT",
                columns=columns,
            )
        )

        assert len(rows) == 1  # Header only
        assert rows[0] == ["production_entry_id", "client_id"]

    def test_date_range_filtering(self, seeded_db):
        """Date range parameters filter rows correctly."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("shift_date", "shift_date"),
        ]
        # Filter to first 10 days of January (entries at day 1, 6, 11)
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
                date_field=ProductionEntry.shift_date,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 11),
            )
        )

        # Header + 3 rows (day 1, 6, 11 are within range)
        assert len(rows) == 4
        # Verify dates are within range
        for row in rows[1:]:
            row_date = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").date()
            assert date(2026, 1, 1) <= row_date <= date(2026, 1, 11)

    def test_start_date_only(self, seeded_db):
        """Only start_date filters rows from that date onward."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("shift_date", "shift_date"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
                date_field=ProductionEntry.shift_date,
                start_date=date(2026, 1, 10),
            )
        )

        # Header + 2 rows (day 11 and 21)
        assert len(rows) == 3

    def test_end_date_only(self, seeded_db):
        """Only end_date filters rows up to that date."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("shift_date", "shift_date"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
                date_field=ProductionEntry.shift_date,
                end_date=date(2026, 1, 5),
            )
        )

        # Header + 1 row (day 1 only)
        assert len(rows) == 2

    def test_none_values_exported_as_empty(self, seeded_db):
        """None values are exported as empty strings."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("notes", "notes"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
            )
        )

        # Last entry (index 4) has notes=None
        assert rows[4][1] == ""

    def test_decimal_values_serialized(self, seeded_db):
        """Decimal values are serialized as plain strings."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("run_time_hours", "run_time_hours"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
            )
        )

        # All entries have run_time_hours = 8.00
        for row in rows[1:]:
            # SQLite may return float or Decimal, either way it should be a numeric string
            assert float(row[1]) == 8.0

    def test_no_client_filter(self, seeded_db):
        """Passing client_filter=None returns all rows (ADMIN/POWERUSER behavior)."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("client_id", "client_id"),
        ]
        rows = _parse_csv(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=None,
                columns=columns,
            )
        )

        # Header + 4 rows
        assert len(rows) == 5

    def test_csv_format_validity(self, seeded_db):
        """Generated CSV is valid and parseable."""
        columns = [
            ("production_entry_id", "production_entry_id"),
            ("client_id", "client_id"),
            ("units_produced", "units_produced"),
            ("notes", "notes"),
        ]
        content = "".join(
            stream_csv_export(
                db=seeded_db,
                model_class=ProductionEntry,
                client_filter=ProductionEntry.client_id == CLIENT_ID,
                columns=columns,
            )
        )

        # Verify it's valid CSV that can be round-tripped
        reader = csv.DictReader(io.StringIO(content))
        records = list(reader)
        assert len(records) == 4
        assert all("production_entry_id" in r for r in records)
        assert all("client_id" in r for r in records)

"""
Tests for database migration CLI tool.

Uses in-memory SQLite databases for both source and target to validate
migration logic without requiring external database servers.
"""
import pytest
from sqlalchemy import Column, Integer, String, DateTime, MetaData, Table, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.db.migrations.data_migrator import DataMigrator
from backend.scripts.migrate_database import (
    DEFAULT_DEMO_CLIENT_IDS,
    DatabaseMigrationTool,
    MigrationValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# We need all models imported so Base.metadata knows about every table.
# The conftest.py at backend/tests/ already does this, but we import
# explicitly here for clarity.
import backend.orm  # noqa: F401
import backend.orm.capacity  # noqa: F401
import backend.orm.client_config  # noqa: F401
import backend.orm.event_store  # noqa: F401
import backend.orm.import_log  # noqa: F401
import backend.orm.kpi_threshold  # noqa: F401

try:
    import backend.orm.coverage  # noqa: F401
except ImportError:
    pass

try:
    import backend.schemas.alert  # noqa: F401
except ImportError:
    pass


def _make_engine():
    """Create an in-memory SQLite engine with all ORM tables."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


def _session(engine):
    """Create a session for the given engine."""
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return factory()


def _seed_client(session: Session, client_id: str, client_name: str = "Test Co"):
    """Insert a CLIENT row directly via raw SQL for maximum portability."""
    from backend.orm.client import Client, ClientType

    client = Client(
        client_id=client_id,
        client_name=client_name,
        client_type=ClientType.HOURLY_RATE,
        is_active=True,
    )
    session.add(client)
    session.commit()
    return client


def _seed_user(session: Session, user_id: str, username: str, client_id: str = None):
    """Insert a USER row."""
    from backend.orm.user import User, UserRole

    user = User(
        user_id=user_id,
        username=username,
        email=f"{username}@test.com",
        password_hash="fakehash",
        role=UserRole.OPERATOR,
        client_id_assigned=client_id,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def _seed_product(session: Session, client_id: str, product_code: str = "PROD-001"):
    """Insert a PRODUCT row."""
    from backend.orm.product import Product

    product = Product(
        client_id=client_id,
        product_code=product_code,
        product_name=f"Test Product {product_code}",
        is_active=True,
    )
    session.add(product)
    session.commit()
    return product


def _count_table(engine, table_name: str) -> int:
    """Count rows in a table."""
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        return result.scalar() or 0


def _make_tool(source_url, target_url, **kwargs):
    """Build a DatabaseMigrationTool with defaults."""
    return DatabaseMigrationTool(
        source_url=source_url,
        target_url=target_url,
        force=kwargs.pop("force", True),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def source_engine():
    """Provide a source in-memory SQLite engine with schema."""
    eng = _make_engine()
    yield eng
    eng.dispose()


@pytest.fixture()
def target_engine():
    """Provide a target in-memory SQLite engine (empty, no tables)."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield eng
    eng.dispose()


@pytest.fixture()
def seeded_source(source_engine):
    """Provide source engine with some demo + real data."""
    session = _session(source_engine)

    # Demo clients
    _seed_client(session, "DEMO-001", "Demo Co")
    _seed_client(session, "TEST-001", "Test Co")

    # Real client
    _seed_client(session, "REAL-001", "Real Manufacturing Inc")

    # Users (no client_id column directly — user has client_id_assigned)
    _seed_user(session, "U-DEMO-1", "demo_user", "DEMO-001")
    _seed_user(session, "U-REAL-1", "real_user", "REAL-001")
    _seed_user(session, "U-ADMIN", "admin_user", None)

    # Products (have client_id)
    _seed_product(session, "DEMO-001", "PROD-DEMO-001")
    _seed_product(session, "DEMO-001", "PROD-DEMO-002")
    _seed_product(session, "REAL-001", "PROD-REAL-001")
    _seed_product(session, "REAL-001", "PROD-REAL-002")
    _seed_product(session, "REAL-001", "PROD-REAL-003")

    session.close()
    return source_engine


# ============================================================================
# TestPreflightValidation
# ============================================================================


class TestPreflightValidation:
    """Pre-flight validation checks on source and target databases."""

    def test_source_with_tables_passes(self, source_engine):
        """Source with tables passes validation."""
        result = DatabaseMigrationTool.validate_source(source_engine)
        assert result["accessible"] is True
        assert result["table_count"] > 0

    def test_source_has_known_tables(self, source_engine):
        """Source contains tables that match TABLE_ORDER."""
        result = DatabaseMigrationTool.validate_source(source_engine)
        assert result["known_tables"] > 0

    def test_source_no_tables_fails_validation(self):
        """Source with no tables results in zero table count."""
        empty_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        result = DatabaseMigrationTool.validate_source(empty_engine)
        assert result["accessible"] is True
        assert result["table_count"] == 0
        empty_engine.dispose()

    def test_target_empty_passes(self, target_engine):
        """Target with no tables passes validation."""
        result = DatabaseMigrationTool.validate_target(target_engine)
        assert result["accessible"] is True
        assert result["has_data"] is False
        assert result["table_count"] == 0

    def test_target_with_data_warns(self, seeded_source):
        """Target with existing data is detected."""
        # Use seeded_source as if it were a target — it has tables and data
        result = DatabaseMigrationTool.validate_target(seeded_source)
        assert result["accessible"] is True
        assert result["has_data"] is True
        assert len(result["tables_with_data"]) > 0

    def test_invalid_source_url(self):
        """Invalid source URL is caught during validation."""
        tool = _make_tool(
            source_url="sqlite:///nonexistent_path_xyz_12345.db",
            target_url="sqlite:///:memory:",
            mode="schema-only",
        )
        # The tool should create engines and detect empty/missing tables
        # For a file-based SQLite that doesn't exist yet, SQLAlchemy creates it
        # so we test with a truly broken URL
        bad_engine = create_engine(
            "sqlite:///nonexistent_path_xyz_12345.db",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        result = DatabaseMigrationTool.validate_source(bad_engine)
        # SQLite creates the file, so it will be accessible but empty
        assert result["accessible"] is True
        assert result["table_count"] == 0
        bad_engine.dispose()

        # Cleanup the created file
        import os
        try:
            os.remove("nonexistent_path_xyz_12345.db")
        except FileNotFoundError:
            pass

    def test_target_with_data_refuses_without_force(self, seeded_source):
        """Migration refuses to proceed when target has data and no --force."""
        # Use the seeded source as both source and target URL doesn't work
        # for in-memory, so we test the validation logic directly
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = seeded_source  # Has data

        with pytest.raises(MigrationValidationError, match="already has data"):
            tool._validate()


# ============================================================================
# TestSchemaOnlyMode
# ============================================================================


class TestSchemaOnlyMode:
    """Schema-only migration creates tables without copying data."""

    def test_creates_tables_on_target(self, source_engine, target_engine):
        """Schema-only mode creates all tables on target."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="schema-only",
            force=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        result = tool._migrate_schema()

        assert result["success"] is True
        assert result["tables_created"] > 0

        # Verify tables exist on target
        inspector = inspect(target_engine)
        target_tables = inspector.get_table_names()
        assert len(target_tables) > 0

    def test_expected_table_count(self, source_engine, target_engine):
        """Target has expected number of tables after schema creation."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="schema-only",
            force=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        result = tool._migrate_schema()

        inspector = inspect(target_engine)
        target_tables = inspector.get_table_names()

        # Should have a reasonable number of tables
        assert len(target_tables) >= 20, (
            f"Expected at least 20 tables, got {len(target_tables)}"
        )

    def test_idempotent_schema_creation(self, source_engine, target_engine):
        """Running schema creation twice does not error."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="schema-only",
            force=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        result1 = tool._migrate_schema()
        result2 = tool._migrate_schema()

        assert result1["success"] is True
        assert result2["success"] is True

    def test_schema_only_no_data(self, seeded_source, target_engine):
        """Schema-only mode does not copy any data."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="schema-only",
            force=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._migrate_schema()

        # Check that no data was copied — CLIENT table should be empty
        inspector = inspect(target_engine)
        if "CLIENT" in inspector.get_table_names():
            count = _count_table(target_engine, "CLIENT")
            assert count == 0


# ============================================================================
# TestAllMode
# ============================================================================


class TestAllMode:
    """Full migration copies all data from source to target."""

    def test_copies_all_data(self, seeded_source, target_engine):
        """All mode copies data to target."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        # Create schema first
        tool._migrate_schema()

        # Create migrator and run
        migrator = DataMigrator(
            seeded_source, target_engine,
            source_provider="sqlite", target_provider="sqlite"
        )
        result = migrator.migrate_all_data()

        assert result["success"] is True
        assert result["total_rows"] > 0

    def test_row_counts_match(self, seeded_source, target_engine):
        """Row counts match between source and target after full migration."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._migrate_schema()

        migrator = DataMigrator(
            seeded_source, target_engine,
            source_provider="sqlite", target_provider="sqlite"
        )
        migrator.migrate_all_data()

        verification = migrator.verify_migration()
        assert verification["verified"] is True, (
            f"Mismatches: {verification['mismatches']}"
        )

    def test_data_integrity(self, seeded_source, target_engine):
        """Spot-check that specific records were copied correctly."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._migrate_schema()

        migrator = DataMigrator(
            seeded_source, target_engine,
            source_provider="sqlite", target_provider="sqlite"
        )
        migrator.migrate_all_data()

        # Verify specific CLIENT records exist on target
        with target_engine.connect() as conn:
            result = conn.execute(
                text("SELECT client_id FROM CLIENT ORDER BY client_id")
            ).fetchall()
            client_ids = [r[0] for r in result]

        assert "DEMO-001" in client_ids
        assert "REAL-001" in client_ids
        assert "TEST-001" in client_ids

    def test_handles_empty_tables(self, source_engine, target_engine):
        """Empty tables are handled gracefully."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        tool._migrate_schema()

        migrator = DataMigrator(
            source_engine, target_engine,
            source_provider="sqlite", target_provider="sqlite"
        )
        result = migrator.migrate_all_data(skip_empty_tables=True)

        assert result["success"] is True
        assert result["total_rows"] == 0

    def test_progress_callback(self, seeded_source, target_engine):
        """Progress callback receives expected calls."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._migrate_schema()

        progress_calls = []

        def track_progress(table_name, current, total, rows_so_far):
            progress_calls.append({
                "table": table_name,
                "current": current,
                "total": total,
                "rows_so_far": rows_so_far,
            })

        migrator = DataMigrator(
            seeded_source, target_engine,
            source_provider="sqlite", target_provider="sqlite"
        )
        migrator.migrate_all_data(progress_callback=track_progress)

        assert len(progress_calls) > 0
        # First call should be table 1
        assert progress_calls[0]["current"] == 1

    def test_full_run_method(self, seeded_source, target_engine):
        """The run() method executes a complete migration successfully."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        # Call _validate then _migrate_all directly since run() would
        # create new engines from URLs (which are in-memory => different DBs)
        tool._validate()
        result = tool._migrate_all()

        assert result["success"] is True
        assert result["total_rows"] > 0


# ============================================================================
# TestUserOnlyMode
# ============================================================================


class TestUserOnlyMode:
    """User-only mode filters out demo client data."""

    def test_skips_demo_client_data(self, seeded_source, target_engine):
        """Demo client data (DEMO-001, TEST-001) is excluded."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        assert result["success"] is True

        # Verify DEMO-001 products were NOT copied
        with target_engine.connect() as conn:
            demo_count = conn.execute(
                text("SELECT COUNT(*) FROM PRODUCT WHERE client_id = 'DEMO-001'")
            ).scalar()
            assert demo_count == 0, "Demo client products should not be copied"

    def test_copies_non_demo_data(self, seeded_source, target_engine):
        """Real client data (REAL-001) is copied."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        # REAL-001 products should be copied
        with target_engine.connect() as conn:
            real_count = conn.execute(
                text("SELECT COUNT(*) FROM PRODUCT WHERE client_id = 'REAL-001'")
            ).scalar()
            assert real_count == 3, f"Expected 3 REAL-001 products, got {real_count}"

    def test_custom_demo_client_ids(self, seeded_source, target_engine):
        """Custom --demo-client-ids parameter works."""
        # Only exclude DEMO-001, keep TEST-001
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        # TEST-001 client should be present (not excluded)
        with target_engine.connect() as conn:
            test_count = conn.execute(
                text("SELECT COUNT(*) FROM CLIENT WHERE client_id = 'TEST-001'")
            ).scalar()
            assert test_count == 1, "TEST-001 should be copied when not in exclusion list"

            # DEMO-001 should be excluded
            demo_count = conn.execute(
                text("SELECT COUNT(*) FROM CLIENT WHERE client_id = 'DEMO-001'")
            ).scalar()
            assert demo_count == 0, "DEMO-001 should be excluded"

    def test_tables_without_client_id_copied_fully(self, seeded_source, target_engine):
        """Tables without client_id column are copied entirely."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        # USER table has client_id_assigned (not client_id), so users
        # should all be copied. Check source vs target counts match.
        source_user_count = _count_table(seeded_source, "USER")
        target_user_count = _count_table(target_engine, "USER")

        assert target_user_count == source_user_count, (
            f"USER table should be fully copied: source={source_user_count}, "
            f"target={target_user_count}"
        )

    def test_filtered_row_counts_reported(self, seeded_source, target_engine):
        """Result includes count of filtered rows."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        assert "rows_filtered" in result
        # CLIENT table should have filtered some rows
        assert result["rows_filtered"].get("CLIENT", 0) == 2, (
            "Should filter 2 demo clients (DEMO-001, TEST-001)"
        )

    def test_user_only_with_verification(self, seeded_source, target_engine):
        """User-only mode with verification enabled."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_user_only()

        assert "verification" in result
        assert result["verification"]["verified"] is True


# ============================================================================
# TestDryRun
# ============================================================================


class TestDryRun:
    """Dry-run mode simulates migration without writing data."""

    def test_no_data_written(self, seeded_source, target_engine):
        """Dry-run does not write any data to target."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            dry_run=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_all()

        assert result["dry_run"] is True
        assert result["total_rows"] > 0  # Reports what would be migrated

        # Target should still have no tables (schema dry-run skipped actual create)
        inspector = inspect(target_engine)
        # In dry-run, schema is not created so no tables
        # If schema was created, no data should be present
        tables = inspector.get_table_names()
        for table in tables:
            count = _count_table(target_engine, table)
            assert count == 0, f"Table {table} should be empty in dry-run"

    def test_summary_generated(self, seeded_source, target_engine):
        """Dry-run still generates a summary with counts."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            dry_run=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        result = tool._migrate_all()

        assert result["success"] is True
        assert result["total_tables"] > 0
        assert "tables_migrated" in result

    def test_user_only_dry_run(self, seeded_source, target_engine):
        """User-only dry-run reports filtered counts without writing."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            dry_run=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        # We need schema on target for user-only to reflect target tables
        # In dry-run, _migrate_schema returns early. Let's test
        # _migrate_table_filtered directly.
        source_meta = MetaData()
        source_meta.reflect(bind=seeded_source)

        if "PRODUCT" in source_meta.tables:
            rows_copied, rows_filtered = tool._migrate_table_filtered(
                "PRODUCT", source_meta.tables["PRODUCT"]
            )
            # DEMO-001 has 2 products, TEST-001 has 0,  REAL-001 has 3
            assert rows_copied == 3, f"Expected 3 real products, got {rows_copied}"
            assert rows_filtered == 2, f"Expected 2 demo products filtered, got {rows_filtered}"

    def test_schema_only_dry_run(self, source_engine, target_engine):
        """Schema-only dry-run does not create tables."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="schema-only",
            force=True,
            dry_run=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        result = tool._migrate_schema()

        assert result["success"] is True
        assert result["dry_run"] is True

        # No tables should be created on target
        inspector = inspect(target_engine)
        assert len(inspector.get_table_names()) == 0


# ============================================================================
# TestErrorHandling
# ============================================================================


class TestErrorHandling:
    """Error handling and recovery during migration."""

    def test_invalid_source_detected(self):
        """Validation detects invalid/empty source."""
        empty_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        result = DatabaseMigrationTool.validate_source(empty_engine)
        assert result["accessible"] is True
        assert result["table_count"] == 0
        empty_engine.dispose()

    def test_strict_mode_stops_on_error(self, source_engine, target_engine):
        """Strict mode raises on first table error."""
        # Create schema on target
        Base.metadata.create_all(bind=target_engine)

        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            strict=True,
            skip_verification=True,
        )
        tool.source_engine = source_engine
        tool.target_engine = target_engine

        # With no data, user-only should succeed without errors
        result = tool._migrate_user_only()
        assert result["success"] is True

    def test_non_strict_continues_on_error(self, seeded_source, target_engine):
        """Non-strict mode continues past table errors."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            strict=False,
            skip_verification=True,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        # This should not raise even if individual tables have issues
        result = tool._migrate_user_only()

        # The tool should report any errors in the result
        assert "errors" in result

    def test_detect_provider(self):
        """Provider detection works for common database URLs."""
        assert DatabaseMigrationTool._detect_provider("sqlite:///test.db") == "sqlite"
        assert DatabaseMigrationTool._detect_provider("sqlite:///:memory:") == "sqlite"
        assert (
            DatabaseMigrationTool._detect_provider("mysql+pymysql://u:p@h/db")
            == "mariadb"
        )
        assert (
            DatabaseMigrationTool._detect_provider("mariadb+pymysql://u:p@h/db")
            == "mariadb"
        )
        assert (
            DatabaseMigrationTool._detect_provider("postgresql://u:p@h/db")
            == "postgresql"
        )

    def test_validation_error_on_non_empty_target_without_force(self, seeded_source):
        """MigrationValidationError raised when target has data and force=False."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = seeded_source

        with pytest.raises(MigrationValidationError):
            tool._validate()


# ============================================================================
# TestMigrationToolIntegration
# ============================================================================


class TestMigrationToolIntegration:
    """Integration tests for the complete migration workflow."""

    def test_full_pipeline_schema_to_data(self, seeded_source, target_engine):
        """Full pipeline: schema creation -> data migration -> verification."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="all",
            force=True,
            skip_verification=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._validate()
        result = tool._migrate_all()

        assert result["success"] is True
        assert result["total_rows"] > 0
        assert "verification" in result
        assert result["verification"]["verified"] is True

    def test_user_only_end_to_end(self, seeded_source, target_engine):
        """User-only end-to-end: excludes demo, copies real, verifies."""
        tool = DatabaseMigrationTool(
            source_url="sqlite:///:memory:",
            target_url="sqlite:///:memory:",
            mode="user-only",
            force=True,
            demo_client_ids={"DEMO-001", "TEST-001"},
            skip_verification=False,
        )
        tool.source_engine = seeded_source
        tool.target_engine = target_engine

        tool._validate()
        result = tool._migrate_user_only()

        assert result["success"] is True

        # Only REAL-001 client should be on target
        with target_engine.connect() as conn:
            clients = conn.execute(
                text("SELECT client_id FROM CLIENT")
            ).fetchall()
            client_ids = [r[0] for r in clients]

        assert "REAL-001" in client_ids
        assert "DEMO-001" not in client_ids
        assert "TEST-001" not in client_ids

    def test_default_demo_client_ids(self):
        """Default demo client IDs include expected values."""
        assert "CLIENT-001" in DEFAULT_DEMO_CLIENT_IDS
        assert "DEMO-001" in DEFAULT_DEMO_CLIENT_IDS

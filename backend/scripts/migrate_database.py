"""
Database Migration CLI Tool

Migrates data between database engines (SQLite -> MariaDB/MySQL).
Supports schema-only, full, and user-only migration modes.

Usage:
    python -m backend.scripts.migrate_database \
        --source "sqlite:///path/to/kpi.db" \
        --target "mysql+pymysql://user:pass@host/dbname" \
        --mode {all|user-only|schema-only} \
        [--dry-run] \
        [--batch-size 1000] \
        [--skip-verification] \
        [--demo-client-ids CLIENT-001 DEMO-001] \
        [--force] \
        [--strict]
"""

import argparse
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from backend.database import Base
from backend.db.migrations.data_migrator import DataMigrationError, DataMigrator
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

DEFAULT_DEMO_CLIENT_IDS = {"CLIENT-001", "DEMO-001", "TEST-001", "SAMPLE-001"}


class MigrationValidationError(Exception):
    """Raised when pre-flight validation fails."""

    pass


class DatabaseMigrationTool:
    """Migrate data between database engines with multiple modes.

    Supports:
    - schema-only: Create schema on target (no data)
    - all: Full data copy from source to target
    - user-only: Copy non-demo data, excluding specified client IDs
    """

    def __init__(
        self,
        source_url: str,
        target_url: str,
        mode: str = "all",
        dry_run: bool = False,
        batch_size: int = 1000,
        skip_verification: bool = False,
        demo_client_ids: Optional[Set[str]] = None,
        force: bool = False,
        strict: bool = False,
        progress_callback: Optional[Callable[[str, int, int, int], None]] = None,
    ):
        """Initialize migration tool.

        Args:
            source_url: SQLAlchemy connection URL for source database.
            target_url: SQLAlchemy connection URL for target database.
            mode: Migration mode (all, user-only, schema-only).
            dry_run: If True, simulate migration without writing data.
            batch_size: Number of rows per batch insert.
            skip_verification: If True, skip post-migration verification.
            demo_client_ids: Client IDs to exclude in user-only mode.
            force: If True, overwrite existing data on target.
            strict: If True, stop on first table migration error.
            progress_callback: Optional callback for progress reporting.
        """
        self.source_url = source_url
        self.target_url = target_url
        self.mode = mode
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.skip_verification = skip_verification
        self.demo_client_ids = demo_client_ids or DEFAULT_DEMO_CLIENT_IDS
        self.force = force
        self.strict = strict
        self.progress_callback = progress_callback

        self.source_engine: Optional[Engine] = None
        self.target_engine: Optional[Engine] = None
        self._results: Dict[str, Any] = {}

    def _create_engine(self, url: str) -> Engine:
        """Create a SQLAlchemy engine from URL.

        Args:
            url: Database connection URL.

        Returns:
            SQLAlchemy Engine instance.
        """
        connect_args = {}
        if "sqlite" in url:
            connect_args["check_same_thread"] = False

        return create_engine(
            url,
            echo=False,
            connect_args=connect_args,
            poolclass=NullPool,
        )

    def run(self) -> Dict[str, Any]:
        """Execute migration based on mode.

        Returns:
            Dict with migration results including counts and timing.

        Raises:
            MigrationValidationError: If pre-flight validation fails.
            DataMigrationError: If migration encounters a critical error.
        """
        start_time = time.time()

        logger.info(
            "Starting database migration",
            extra={"mode": self.mode, "dry_run": self.dry_run},
        )

        # Create engines
        self.source_engine = self._create_engine(self.source_url)
        self.target_engine = self._create_engine(self.target_url)

        try:
            # Pre-flight validation
            self._validate()

            if self.mode == "schema-only":
                result = self._migrate_schema()
            elif self.mode == "all":
                result = self._migrate_all()
            elif self.mode == "user-only":
                result = self._migrate_user_only()
            else:
                raise ValueError(f"Unknown migration mode: {self.mode}")

            elapsed = time.time() - start_time
            result["elapsed_seconds"] = round(elapsed, 2)
            result["mode"] = self.mode
            result["dry_run"] = self.dry_run

            self._results = result
            return result

        finally:
            if self.source_engine:
                self.source_engine.dispose()
            if self.target_engine:
                self.target_engine.dispose()

    def _validate(self) -> None:
        """Run pre-flight validation on source and target.

        Raises:
            MigrationValidationError: If validation fails.
        """
        logger.info("Running pre-flight validation...")

        # Engines are created at the top of run() before _validate is called,
        # so they cannot be None here. Asserts narrow the Optional[Engine]
        # type for downstream calls without runtime cost in -O mode.
        assert self.source_engine is not None
        assert self.target_engine is not None

        # Validate source
        source_info = self.validate_source(self.source_engine)
        if not source_info["accessible"]:
            raise MigrationValidationError(f"Source database is not accessible: {source_info.get('error', 'unknown')}")

        if self.mode != "schema-only" and source_info["table_count"] == 0:
            raise MigrationValidationError("Source database has no tables. Nothing to migrate.")

        logger.info(f"Source validation passed: {source_info['table_count']} tables found")

        # Validate target (skip for schema-only since we create tables)
        target_info = self.validate_target(self.target_engine)
        if not target_info["accessible"]:
            raise MigrationValidationError(f"Target database is not accessible: {target_info.get('error', 'unknown')}")

        if target_info["has_data"] and not self.force:
            raise MigrationValidationError("Target database already has data. Use --force to overwrite.")

        if target_info["table_count"] > 0 and not self.force:
            logger.warning(f"Target already has {target_info['table_count']} tables. " "Use --force to proceed.")

        logger.info("Pre-flight validation passed")

    @staticmethod
    def validate_source(source_engine: Engine) -> Dict[str, Any]:
        """Verify source database is accessible and has expected tables.

        Args:
            source_engine: SQLAlchemy engine for source database.

        Returns:
            Dict with validation results.
        """
        result = {
            "accessible": False,
            "table_count": 0,
            "tables": [],
            "known_tables": 0,
        }

        try:
            inspector = inspect(source_engine)
            tables = inspector.get_table_names()
            result["accessible"] = True
            result["table_count"] = len(tables)
            result["tables"] = tables

            # Check how many tables match the known TABLE_ORDER
            known = set(DataMigrator.TABLE_ORDER)
            matching = [t for t in tables if t in known]
            result["known_tables"] = len(matching)

        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def validate_target(target_engine: Engine) -> Dict[str, Any]:
        """Verify target is accessible and check if it has existing data.

        Args:
            target_engine: SQLAlchemy engine for target database.

        Returns:
            Dict with validation results.
        """
        # Annotate explicitly so mypy permits .append on the list value.
        # Without this, the inferred dict value union (bool | int | list)
        # blocks `result["tables_with_data"].append(...)`.
        result: Dict[str, Any] = {
            "accessible": False,
            "table_count": 0,
            "has_data": False,
            "tables_with_data": [],
        }

        try:
            inspector = inspect(target_engine)
            tables = inspector.get_table_names()
            result["accessible"] = True
            result["table_count"] = len(tables)

            # Check if any tables have data
            for table_name in tables:
                try:
                    with target_engine.connect() as conn:
                        count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
                        if count and count > 0:
                            result["has_data"] = True
                            result["tables_with_data"].append(table_name)
                except Exception:
                    pass  # Skip tables we can't query

        except Exception as e:
            result["error"] = str(e)

        return result

    def _migrate_schema(self) -> Dict[str, Any]:
        """Create schema on target using Base.metadata.create_all.

        Returns:
            Dict with schema creation results.
        """
        logger.info("Creating schema on target database...")

        if self.dry_run:
            logger.info("[DRY RUN] Would create schema on target")
            return {
                "success": True,
                "tables_created": len(Base.metadata.tables),
                "dry_run": True,
            }

        # Import all models to ensure they are registered with Base
        self._import_all_models()

        # run() creates engines before any _migrate_* method is invoked.
        assert self.target_engine is not None
        Base.metadata.create_all(bind=self.target_engine)

        # Verify tables were created
        inspector = inspect(self.target_engine)
        created_tables = inspector.get_table_names()

        logger.info(f"Schema created: {len(created_tables)} tables")

        return {
            "success": True,
            "tables_created": len(created_tables),
            "table_names": created_tables,
        }

    def _migrate_all(self) -> Dict[str, Any]:
        """Copy all data from source to target.

        First creates schema, then migrates all data using DataMigrator.

        Returns:
            Dict with migration results including counts per table.
        """
        logger.info("Starting full data migration...")

        # Create schema first
        schema_result = self._migrate_schema()
        if not schema_result["success"]:
            return schema_result

        # Engines are created at the top of run() before _migrate_* runs.
        assert self.source_engine is not None
        assert self.target_engine is not None

        if self.dry_run:
            logger.info("[DRY RUN] Would copy all data from source to target")
            # Count source rows for summary
            source_meta = MetaData()
            source_meta.reflect(bind=self.source_engine)
            total_rows = 0
            table_counts = {}
            for table_name in source_meta.tables:
                with self.source_engine.connect() as conn:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
                    table_counts[table_name] = count or 0
                    total_rows += count or 0

            return {
                "success": True,
                "dry_run": True,
                "total_tables": len(table_counts),
                "total_rows": total_rows,
                "tables_migrated": table_counts,
                "tables_skipped": [],
            }

        # Determine source/target providers
        source_provider = self._detect_provider(self.source_url)
        target_provider = self._detect_provider(self.target_url)

        # Use existing DataMigrator
        migrator = DataMigrator(
            self.source_engine,
            self.target_engine,
            source_provider=source_provider,
            target_provider=target_provider,
        )

        result = migrator.migrate_all_data(progress_callback=self._default_progress_callback)

        # Verification
        if not self.skip_verification:
            verification = migrator.verify_migration()
            result["verification"] = verification
            if not verification["verified"]:
                logger.warning(f"Verification found {len(verification['mismatches'])} mismatches")

        return result

    def _migrate_user_only(self) -> Dict[str, Any]:
        """Copy non-demo data from source to target.

        Filters out rows belonging to demo client IDs.

        Returns:
            Dict with migration results including counts per table.
        """
        logger.info(f"Starting user-only migration (excluding demo clients: " f"{self.demo_client_ids})...")

        # Create schema first
        schema_result = self._migrate_schema()
        if not schema_result["success"]:
            return schema_result

        # Engines are created at the top of run() before _migrate_* runs.
        assert self.source_engine is not None
        assert self.target_engine is not None

        # Reflect source metadata
        source_meta = MetaData()
        source_meta.reflect(bind=self.source_engine)

        source_tables = set(source_meta.tables.keys())

        # Determine migration order
        tables_to_migrate = [t for t in DataMigrator.TABLE_ORDER if t in source_tables]
        extra_tables = source_tables - set(DataMigrator.TABLE_ORDER)
        if extra_tables:
            tables_to_migrate.extend(sorted(extra_tables))

        total_tables = len(tables_to_migrate)
        total_rows = 0
        migrated_counts: Dict[str, int] = {}
        skipped_tables: List[str] = []
        filtered_counts: Dict[str, int] = {}
        errors: List[Dict[str, str]] = []

        for idx, table_name in enumerate(tables_to_migrate, 1):
            try:
                source_table = source_meta.tables[table_name]

                if self.progress_callback:
                    self.progress_callback(table_name, idx, total_tables, total_rows)
                else:
                    self._default_progress_callback(table_name, idx, total_tables, total_rows)

                rows_copied, rows_filtered = self._migrate_table_filtered(table_name, source_table)

                migrated_counts[table_name] = rows_copied
                filtered_counts[table_name] = rows_filtered
                total_rows += rows_copied

                if rows_copied > 0 or rows_filtered > 0:
                    logger.info(
                        f"  [{idx}/{total_tables}] {table_name}: "
                        f"{rows_copied} rows copied, {rows_filtered} filtered"
                    )
                else:
                    skipped_tables.append(table_name)

            except Exception as e:
                error_msg = f"Failed to migrate table {table_name}: {e}"
                logger.error(error_msg)
                errors.append({"table": table_name, "error": str(e)})

                if self.strict:
                    raise DataMigrationError(error_msg)

        # Verification
        verification = None
        if not self.skip_verification:
            verification = self._verify_user_only_migration(source_meta, migrated_counts)

        result = {
            "success": len(errors) == 0,
            "total_tables": total_tables,
            "total_rows": total_rows,
            "tables_migrated": migrated_counts,
            "tables_skipped": skipped_tables,
            "rows_filtered": filtered_counts,
            "demo_client_ids": list(self.demo_client_ids),
            "errors": errors,
        }

        if verification:
            result["verification"] = verification

        return result

    def _migrate_table_filtered(self, table_name: str, source_table: Table) -> tuple:
        """Migrate a single table, filtering out demo data.

        Args:
            table_name: Name of the table.
            source_table: SQLAlchemy Table object from source.

        Returns:
            Tuple of (rows_copied, rows_filtered).
        """
        columns = [col.name for col in source_table.columns]
        has_client_id = "client_id" in columns

        # Engines are created at the top of run() before any per-table work.
        assert self.source_engine is not None
        assert self.target_engine is not None

        # Fetch all rows
        with self.source_engine.connect() as conn:
            rows = conn.execute(select(source_table)).fetchall()

        if not rows:
            return 0, 0

        if self.dry_run:
            if has_client_id:
                client_id_idx = columns.index("client_id")
                kept = [r for r in rows if r[client_id_idx] not in self.demo_client_ids]
                return len(kept), len(rows) - len(kept)
            return len(rows), 0

        # Filter rows if table has client_id column
        rows_to_insert = []
        rows_filtered = 0

        if has_client_id:
            client_id_idx = columns.index("client_id")
            for row in rows:
                client_id_val = row[client_id_idx]
                if client_id_val in self.demo_client_ids:
                    rows_filtered += 1
                else:
                    rows_to_insert.append(row)
        else:
            # Tables without client_id: copy all rows
            rows_to_insert = list(rows)

        if not rows_to_insert:
            return 0, rows_filtered

        # Create value converter from DataMigrator
        source_provider = self._detect_provider(self.source_url)
        target_provider = self._detect_provider(self.target_url)
        converter = DataMigrator(
            self.source_engine,
            self.target_engine,
            source_provider,
            target_provider,
        )

        # Insert into target
        with self.target_engine.connect() as target_conn:
            is_mysql = target_provider in ("mysql", "mariadb")
            if is_mysql:
                target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            try:
                target_meta = MetaData()
                target_table = Table(table_name, target_meta, autoload_with=self.target_engine)

                for i in range(0, len(rows_to_insert), self.batch_size):
                    batch = rows_to_insert[i : i + self.batch_size]
                    row_dicts = [
                        {col: converter._convert_value(row[idx], col, table_name) for idx, col in enumerate(columns)}
                        for row in batch
                    ]
                    target_conn.execute(target_table.insert(), row_dicts)

                target_conn.commit()

            finally:
                if is_mysql:
                    target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                    target_conn.commit()

        return len(rows_to_insert), rows_filtered

    def _verify_user_only_migration(
        self,
        source_meta: MetaData,
        migrated_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        """Verify user-only migration by comparing expected vs actual counts.

        For tables with client_id, expected = total - demo rows.
        For tables without client_id, expected = total.

        Args:
            source_meta: Source database metadata.
            migrated_counts: Actual rows migrated per table.

        Returns:
            Dict with verification results.
        """
        mismatches: List[Dict[str, Any]] = []

        # Engines are created at the top of run() before verification runs.
        assert self.target_engine is not None

        target_inspector = inspect(self.target_engine)
        target_tables = set(target_inspector.get_table_names())

        for table_name, expected_count in migrated_counts.items():
            if table_name not in target_tables:
                if expected_count > 0:
                    mismatches.append(
                        {
                            "table": table_name,
                            "expected": expected_count,
                            "actual": 0,
                            "reason": "Table not found on target",
                        }
                    )
                continue

            with self.target_engine.connect() as conn:
                # .scalar() returns Optional[Any]; default None to 0 so
                # the int subtraction below is well-typed.
                actual_raw = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
                actual = int(actual_raw or 0)

            if actual != expected_count:
                mismatches.append(
                    {
                        "table": table_name,
                        "expected": expected_count,
                        "actual": actual,
                        "difference": expected_count - actual,
                    }
                )

        return {
            "verified": len(mismatches) == 0,
            "mismatches": mismatches,
        }

    def _default_progress_callback(self, table_name: str, current: int, total: int, rows_so_far: int) -> None:
        """Default progress output.

        Args:
            table_name: Current table being migrated.
            current: Current table index.
            total: Total number of tables.
            rows_so_far: Total rows migrated so far.
        """
        prefix = "[DRY RUN] " if self.dry_run else ""
        print(f"  {prefix}[{current}/{total}] {table_name}...")

    @staticmethod
    def _detect_provider(url: str) -> str:
        """Detect database provider from URL.

        Args:
            url: Database connection URL.

        Returns:
            Provider name string.
        """
        url_lower = url.lower()
        if "mysql" in url_lower or "mariadb" in url_lower:
            return "mariadb"
        if "postgresql" in url_lower or "postgres" in url_lower:
            return "postgresql"
        return "sqlite"

    @staticmethod
    def _import_all_models() -> None:
        """Import all ORM models to register them with Base.metadata."""
        import backend.orm  # noqa: F401
        import backend.orm.capacity  # noqa: F401
        import backend.orm.client_config  # noqa: F401
        import backend.orm.event_store  # noqa: F401
        import backend.orm.import_log  # noqa: F401
        import backend.orm.kpi_threshold  # noqa: F401
        import backend.orm.coverage  # noqa: F401

        try:
            import backend.schemas.alert  # noqa: F401
        except ImportError:
            pass


def print_summary(result: Dict[str, Any]) -> None:
    """Print a human-readable migration summary.

    Args:
        result: Migration results dict.
    """
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"  Mode:            {result.get('mode', 'unknown')}")
    print(f"  Dry Run:         {result.get('dry_run', False)}")
    print(f"  Success:         {result.get('success', False)}")
    print(f"  Elapsed:         {result.get('elapsed_seconds', 0):.2f}s")

    if "tables_created" in result:
        print(f"  Tables Created:  {result['tables_created']}")

    if "total_tables" in result:
        print(f"  Total Tables:    {result['total_tables']}")

    if "total_rows" in result:
        print(f"  Total Rows:      {result['total_rows']}")

    if "tables_skipped" in result and result["tables_skipped"]:
        print(f"  Skipped:         {len(result['tables_skipped'])} empty tables")

    if "demo_client_ids" in result:
        print(f"  Excluded IDs:    {', '.join(result['demo_client_ids'])}")

    if "rows_filtered" in result:
        total_filtered = sum(result["rows_filtered"].values())
        if total_filtered > 0:
            print(f"  Rows Filtered:   {total_filtered} (demo data)")

    if "errors" in result and result["errors"]:
        print(f"\n  ERRORS ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"    - {err['table']}: {err['error']}")

    if "verification" in result:
        v = result["verification"]
        status = "PASSED" if v.get("verified", False) else "FAILED"
        print(f"\n  Verification:    {status}")
        if not v.get("verified", False) and "mismatches" in v:
            for m in v["mismatches"][:5]:
                print(
                    f"    - {m['table']}: expected={m.get('expected', m.get('source_count', '?'))}, "
                    f"actual={m.get('actual', m.get('target_count', '?'))}"
                )

    print("=" * 60)


def main() -> None:
    """CLI entry point for database migration."""
    parser = argparse.ArgumentParser(
        description="Migrate database between engines (SQLite -> MariaDB/MySQL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Schema only
  python -m backend.scripts.migrate_database \\
    --source sqlite:///kpi.db --target mysql+pymysql://u:p@h/db --mode schema-only

  # Full migration
  python -m backend.scripts.migrate_database \\
    --source sqlite:///kpi.db --target mysql+pymysql://u:p@h/db --mode all

  # User data only (exclude demo)
  python -m backend.scripts.migrate_database \\
    --source sqlite:///kpi.db --target mysql+pymysql://u:p@h/db --mode user-only \\
    --demo-client-ids CLIENT-001 DEMO-001

  # Dry run
  python -m backend.scripts.migrate_database \\
    --source sqlite:///kpi.db --target mysql+pymysql://u:p@h/db --mode all --dry-run
""",
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Source database URL (e.g., sqlite:///kpi.db)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target database URL (e.g., mysql+pymysql://user:pass@host/dbname)",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "user-only", "schema-only"],
        default="all",
        help="Migration mode (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without writing data",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows per batch insert (default: 1000)",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip post-migration row count verification",
    )
    parser.add_argument(
        "--demo-client-ids",
        nargs="*",
        default=None,
        help="Client IDs to exclude in user-only mode (default: CLIENT-001, DEMO-001, TEST-001, SAMPLE-001)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing data on target",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Stop on first table migration error",
    )

    args = parser.parse_args()

    # Build demo client IDs set
    demo_ids = None
    if args.demo_client_ids is not None:
        demo_ids = set(args.demo_client_ids)

    tool = DatabaseMigrationTool(
        source_url=args.source,
        target_url=args.target,
        mode=args.mode,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        skip_verification=args.skip_verification,
        demo_client_ids=demo_ids,
        force=args.force,
        strict=args.strict,
    )

    try:
        result = tool.run()
        print_summary(result)

        if not result.get("success", False):
            sys.exit(1)

    except MigrationValidationError as e:
        logger.error(f"Validation failed: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(2)

    except DataMigrationError as e:
        logger.error(f"Migration failed: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(3)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()

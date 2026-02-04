"""
Data Migrator

Copies existing data from source database to target database during RDBMS migration.
Preserves all user data while maintaining referential integrity.
"""
from typing import Callable, Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging

from sqlalchemy import MetaData, Table, select, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class DataMigrator:
    """Migrate data from source to target database.

    Handles copying all existing records from SQLite (or other source)
    to MariaDB/MySQL (or other target) while preserving:
    - All user data
    - Referential integrity (foreign key order)
    - Data types and NULL values
    """

    # Tables in dependency order (parents before children)
    # This ensures foreign key constraints are satisfied
    TABLE_ORDER = [
        # Tier 1: No dependencies
        "CLIENT",
        "USER",
        "SHIFT",

        # Tier 2: Depends on CLIENT
        "EMPLOYEE",
        "PRODUCT",
        "SAVED_FILTER",
        "USER_PREFERENCES",
        "DASHBOARD_WIDGET_DEFAULTS",
        "DEFECT_TYPE_CATALOG",
        "PART_OPPORTUNITIES",
        "KPI_THRESHOLD",

        # Tier 3: Depends on CLIENT, EMPLOYEE
        "WORK_ORDER",
        "FLOATING_POOL",
        "FILTER_HISTORY",

        # Tier 4: Depends on WORK_ORDER
        "JOB",
        "WORKFLOW_TRANSITION_LOG",

        # Tier 5: Depends on EMPLOYEE, SHIFT, WORK_ORDER
        "PRODUCTION_ENTRY",
        "ATTENDANCE_ENTRY",
        "DOWNTIME_ENTRY",
        "QUALITY_ENTRY",
        "HOLD_ENTRY",
        "COVERAGE_ENTRY",

        # Tier 6: Depends on QUALITY_ENTRY
        "DEFECT_DETAIL",

        # Tier 7: Domain events (no FK constraints, but logical dependency)
        "EVENT_STORE",

        # Tier 8: Capacity Planning - Base tables (depend on CLIENT only)
        "capacity_calendar",
        "capacity_production_lines",
        "capacity_production_standards",
        "capacity_stock_snapshot",

        # Tier 9: Capacity Planning - Orders and headers (depend on CLIENT only)
        "capacity_orders",
        "capacity_bom_header",
        "capacity_schedule",

        # Tier 10: Capacity Planning - Child tables with FK to parent capacity tables
        "capacity_bom_detail",          # depends on capacity_bom_header
        "capacity_scenario",            # depends on capacity_schedule (optional FK)
        "capacity_component_check",     # depends on capacity_orders
        "capacity_analysis",            # depends on capacity_production_lines
        "capacity_schedule_detail",     # depends on capacity_schedule, capacity_orders, capacity_production_lines
        "capacity_kpi_commitment",      # depends on capacity_schedule
    ]

    def __init__(
        self,
        source_engine: Engine,
        target_engine: Engine,
        source_provider: str = "sqlite",
        target_provider: str = "mariadb"
    ):
        """Initialize data migrator.

        Args:
            source_engine: SQLAlchemy engine for source database.
            target_engine: SQLAlchemy engine for target database.
            source_provider: Source provider name (for dialect handling).
            target_provider: Target provider name (for dialect handling).
        """
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.source_provider = source_provider
        self.target_provider = target_provider
        self._migrated_counts: Dict[str, int] = {}
        self._skipped_tables: List[str] = []

    def migrate_all_data(
        self,
        progress_callback: Optional[Callable[[str, int, int, int], None]] = None,
        skip_empty_tables: bool = True
    ) -> Dict[str, Any]:
        """Migrate all data from source to target.

        Args:
            progress_callback: Optional callback(table_name, current_table, total_tables, rows_copied).
            skip_empty_tables: If True, skip tables with no data.

        Returns:
            Dict with migration results including counts per table.
        """
        logger.info(f"Starting data migration: {self.source_provider} → {self.target_provider}")

        # Get source metadata
        source_meta = MetaData()
        source_meta.reflect(bind=self.source_engine)

        # Get existing tables in source
        source_tables = set(source_meta.tables.keys())
        logger.info(f"Found {len(source_tables)} tables in source database")

        # Determine migration order (only tables that exist in source)
        tables_to_migrate = [
            t for t in self.TABLE_ORDER
            if t in source_tables
        ]

        # Add any tables not in our predefined order (safety net)
        extra_tables = source_tables - set(self.TABLE_ORDER)
        if extra_tables:
            logger.warning(f"Found tables not in predefined order: {extra_tables}")
            tables_to_migrate.extend(sorted(extra_tables))

        total_tables = len(tables_to_migrate)
        total_rows = 0

        logger.info(f"Migrating {total_tables} tables in dependency order")

        for idx, table_name in enumerate(tables_to_migrate, 1):
            try:
                if progress_callback:
                    progress_callback(table_name, idx, total_tables, total_rows)

                rows_copied = self._migrate_table(
                    table_name,
                    source_meta.tables[table_name],
                    skip_empty_tables
                )

                self._migrated_counts[table_name] = rows_copied
                total_rows += rows_copied

                if rows_copied > 0:
                    logger.info(f"  [{idx}/{total_tables}] {table_name}: {rows_copied} rows")
                elif skip_empty_tables:
                    self._skipped_tables.append(table_name)
                    logger.debug(f"  [{idx}/{total_tables}] {table_name}: skipped (empty)")

            except Exception as e:
                logger.error(f"Failed to migrate table {table_name}: {e}")
                raise DataMigrationError(f"Migration failed at table {table_name}: {e}")

        logger.info(f"Data migration complete: {total_rows} total rows across {total_tables} tables")

        return {
            "success": True,
            "total_tables": total_tables,
            "total_rows": total_rows,
            "tables_migrated": self._migrated_counts,
            "tables_skipped": self._skipped_tables,
        }

    def _migrate_table(
        self,
        table_name: str,
        source_table: Table,
        skip_empty: bool = True
    ) -> int:
        """Migrate a single table.

        Args:
            table_name: Name of the table.
            source_table: SQLAlchemy Table object from source.
            skip_empty: Skip if table has no rows.

        Returns:
            Number of rows copied.
        """
        # Check if table has data
        with self.source_engine.connect() as source_conn:
            count_result = source_conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()

            if count_result == 0 and skip_empty:
                return 0

            # Fetch all rows from source
            rows = source_conn.execute(select(source_table)).fetchall()

        if not rows:
            return 0

        # Get column names
        columns = [col.name for col in source_table.columns]

        # Insert into target
        with self.target_engine.connect() as target_conn:
            # Disable foreign key checks during bulk insert (MySQL/MariaDB)
            if self.target_provider in ("mysql", "mariadb"):
                target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            try:
                # Create target table reference
                target_meta = MetaData()
                target_table = Table(table_name, target_meta, autoload_with=self.target_engine)

                # Batch insert for performance
                batch_size = 1000
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]

                    # Convert rows to dicts
                    row_dicts = [
                        {col: self._convert_value(row[idx], col, table_name)
                         for idx, col in enumerate(columns)}
                        for row in batch
                    ]

                    # Insert batch
                    target_conn.execute(target_table.insert(), row_dicts)

                target_conn.commit()

            finally:
                # Re-enable foreign key checks
                if self.target_provider in ("mysql", "mariadb"):
                    target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                    target_conn.commit()

        return len(rows)

    def _convert_value(self, value: Any, column_name: str, table_name: str) -> Any:
        """Convert value for target database compatibility.

        Handles SQLite → MySQL/MariaDB type differences.

        Args:
            value: Source value.
            column_name: Column name (for type inference).
            table_name: Table name (for context).

        Returns:
            Converted value.
        """
        if value is None:
            return None

        # SQLite stores booleans as 0/1, MySQL expects True/False
        if isinstance(value, int) and column_name.startswith(("is_", "has_", "can_")):
            return bool(value)

        # Handle datetime strings from SQLite
        if isinstance(value, str) and column_name.endswith(("_at", "_date", "_time")):
            try:
                # Try ISO format
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return value

        return value

    def get_table_counts(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Get row counts for source and target tables.

        Returns:
            Tuple of (source_counts, target_counts) dicts.
        """
        source_counts = {}
        target_counts = {}

        source_inspector = inspect(self.source_engine)
        target_inspector = inspect(self.target_engine)

        for table_name in source_inspector.get_table_names():
            with self.source_engine.connect() as conn:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
                source_counts[table_name] = count

        for table_name in target_inspector.get_table_names():
            with self.target_engine.connect() as conn:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
                target_counts[table_name] = count

        return source_counts, target_counts

    def verify_migration(self) -> Dict[str, Any]:
        """Verify data was migrated correctly.

        Compares row counts between source and target.

        Returns:
            Verification result with any mismatches.
        """
        source_counts, target_counts = self.get_table_counts()

        mismatches = []
        for table_name, source_count in source_counts.items():
            target_count = target_counts.get(table_name, 0)
            if source_count != target_count:
                mismatches.append({
                    "table": table_name,
                    "source_count": source_count,
                    "target_count": target_count,
                    "difference": source_count - target_count
                })

        return {
            "verified": len(mismatches) == 0,
            "source_total": sum(source_counts.values()),
            "target_total": sum(target_counts.values()),
            "mismatches": mismatches,
            "source_counts": source_counts,
            "target_counts": target_counts,
        }

    def get_migration_summary(self) -> Dict[str, Any]:
        """Get summary of migration.

        Returns:
            Summary including counts and any skipped tables.
        """
        return {
            "migrated_counts": self._migrated_counts.copy(),
            "skipped_tables": self._skipped_tables.copy(),
            "total_rows": sum(self._migrated_counts.values()),
            "tables_with_data": len([c for c in self._migrated_counts.values() if c > 0]),
        }


class DataMigrationError(Exception):
    """Exception raised when data migration fails."""
    pass


def create_data_migration_handler(
    source_engine: Engine,
    target_engine: Engine,
    source_provider: str = "sqlite",
    target_provider: str = "mariadb"
) -> Callable:
    """Factory to create data migration handler.

    Args:
        source_engine: Source database engine.
        target_engine: Target database engine.
        source_provider: Source provider name.
        target_provider: Target provider name.

    Returns:
        Migration handler function.
    """
    def migrate_data(
        progress_callback: Optional[Callable] = None,
        verify: bool = True
    ) -> Dict[str, Any]:
        """Execute data migration.

        Args:
            progress_callback: Optional progress callback.
            verify: If True, verify migration after completion.

        Returns:
            Migration results.
        """
        migrator = DataMigrator(
            source_engine,
            target_engine,
            source_provider,
            target_provider
        )

        result = migrator.migrate_all_data(progress_callback)

        if verify:
            verification = migrator.verify_migration()
            result["verification"] = verification

        return result

    return migrate_data

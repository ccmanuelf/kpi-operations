"""
Capacity Planning Tables Migration
Creates all tables for the Capacity Planning module.

Tables created (13 total):
- capacity_calendar: Working days, shifts, holidays
- capacity_production_lines: Line capacity specifications
- capacity_orders: Planning orders (separate from Work Orders)
- capacity_production_standards: SAM per operation per style
- capacity_bom_header: Bill of Materials headers
- capacity_bom_detail: Bill of Materials components
- capacity_stock_snapshot: Weekly inventory positions
- capacity_component_check: MRP explosion results
- capacity_analysis: Utilization calculations per line/week
- capacity_schedule: Production schedule headers
- capacity_schedule_detail: Production schedule line items
- capacity_scenario: What-if scenario configurations
- capacity_kpi_commitment: KPI targets and actuals tracking

Usage:
    from backend.db.migrations.capacity_planning_tables import create_capacity_tables
    create_capacity_tables()
"""
from typing import List, Optional, Callable
from sqlalchemy import inspect
import logging

from backend.database import engine, Base

# Import all capacity models to register them with Base.metadata
from backend.schemas.capacity import (
    CapacityCalendar,
    CapacityProductionLine,
    CapacityOrder,
    CapacityProductionStandard,
    CapacityBOMHeader,
    CapacityBOMDetail,
    CapacityStockSnapshot,
    CapacityComponentCheck,
    CapacityAnalysis,
    CapacitySchedule,
    CapacityScheduleDetail,
    CapacityScenario,
    CapacityKPICommitment,
)

logger = logging.getLogger(__name__)

# List of all capacity planning tables in creation order
# (respecting foreign key dependencies)
CAPACITY_TABLES = [
    "capacity_calendar",
    "capacity_production_lines",
    "capacity_orders",
    "capacity_production_standards",
    "capacity_bom_header",
    "capacity_bom_detail",
    "capacity_stock_snapshot",
    "capacity_component_check",
    "capacity_analysis",
    "capacity_schedule",
    "capacity_schedule_detail",
    "capacity_scenario",
    "capacity_kpi_commitment",
]


def create_capacity_tables(
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> List[str]:
    """
    Create all capacity planning tables.

    This function is idempotent - it will only create tables that don't exist.

    Args:
        progress_callback: Optional callback(table_name, current, total) for progress reporting

    Returns:
        List[str]: Names of tables that were created
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    tables_to_create = [t for t in CAPACITY_TABLES if t not in existing_tables]

    if not tables_to_create:
        logger.info("All capacity planning tables already exist")
        return []

    logger.info(f"Creating {len(tables_to_create)} capacity planning tables: {tables_to_create}")

    created_tables = []
    total = len(tables_to_create)

    for idx, table_name in enumerate(tables_to_create, 1):
        if progress_callback:
            progress_callback(table_name, idx, total)

        try:
            if table_name in Base.metadata.tables:
                table = Base.metadata.tables[table_name]
                table.create(bind=engine, checkfirst=True)
                created_tables.append(table_name)
                logger.debug(f"Created table: {table_name}")
            else:
                logger.warning(f"Table {table_name} not found in metadata")
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise

    logger.info(f"Successfully created {len(created_tables)} capacity planning tables")
    return created_tables


def drop_capacity_tables(
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> List[str]:
    """
    Drop all capacity planning tables.

    WARNING: This is destructive! Use with caution.
    Tables are dropped in reverse order to respect foreign key constraints.

    Args:
        progress_callback: Optional callback(table_name, current, total) for progress reporting

    Returns:
        List[str]: Names of tables that were dropped
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # Drop in reverse order to handle foreign keys
    tables_to_drop = [t for t in reversed(CAPACITY_TABLES) if t in existing_tables]

    if not tables_to_drop:
        logger.info("No capacity planning tables to drop")
        return []

    logger.warning(f"Dropping {len(tables_to_drop)} capacity planning tables: {tables_to_drop}")

    dropped_tables = []
    total = len(tables_to_drop)

    for idx, table_name in enumerate(tables_to_drop, 1):
        if progress_callback:
            progress_callback(table_name, idx, total)

        try:
            if table_name in Base.metadata.tables:
                table = Base.metadata.tables[table_name]
                table.drop(bind=engine, checkfirst=True)
                dropped_tables.append(table_name)
                logger.debug(f"Dropped table: {table_name}")
            else:
                logger.warning(f"Table {table_name} not found in metadata")
        except Exception as e:
            logger.warning(f"Failed to drop table {table_name}: {e}")

    logger.info(f"Dropped {len(dropped_tables)} capacity planning tables")
    return dropped_tables


def verify_capacity_tables() -> dict:
    """
    Verify that all capacity planning tables exist.

    Returns:
        dict: Verification result with status and details
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    expected = set(CAPACITY_TABLES)
    present = expected.intersection(existing_tables)
    missing = expected - existing_tables

    return {
        "valid": len(missing) == 0,
        "expected_count": len(expected),
        "present_count": len(present),
        "missing_tables": list(missing),
        "present_tables": list(present),
    }


def get_capacity_table_info() -> dict:
    """
    Get information about capacity planning tables.

    Returns:
        dict: Table information including column counts and row counts
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    info = {}
    for table_name in CAPACITY_TABLES:
        if table_name in existing_tables:
            columns = inspector.get_columns(table_name)
            info[table_name] = {
                "exists": True,
                "column_count": len(columns),
                "columns": [c["name"] for c in columns],
            }
        else:
            info[table_name] = {
                "exists": False,
                "column_count": 0,
                "columns": [],
            }

    return info


if __name__ == "__main__":
    # Configure logging for CLI execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    import argparse

    parser = argparse.ArgumentParser(description="Capacity Planning Tables Migration")
    parser.add_argument(
        "--action",
        choices=["create", "drop", "verify", "info"],
        default="create",
        help="Action to perform (default: create)"
    )

    args = parser.parse_args()

    if args.action == "create":
        created = create_capacity_tables()
        if created:
            print(f"Created tables: {created}")
        else:
            print("All tables already exist")

    elif args.action == "drop":
        confirm = input("Are you sure you want to drop all capacity planning tables? (yes/no): ")
        if confirm.lower() == "yes":
            dropped = drop_capacity_tables()
            print(f"Dropped tables: {dropped}")
        else:
            print("Aborted")

    elif args.action == "verify":
        result = verify_capacity_tables()
        print(f"Verification: {'PASSED' if result['valid'] else 'FAILED'}")
        print(f"  Expected: {result['expected_count']}")
        print(f"  Present: {result['present_count']}")
        if result['missing_tables']:
            print(f"  Missing: {result['missing_tables']}")

    elif args.action == "info":
        info = get_capacity_table_info()
        for table_name, table_info in info.items():
            status = "EXISTS" if table_info["exists"] else "MISSING"
            cols = table_info["column_count"]
            print(f"  {table_name}: {status} ({cols} columns)")

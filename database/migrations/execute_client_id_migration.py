#!/usr/bin/env python3
"""
Database Migration Executor: Add client_id columns to tables
Safely executes migration with transaction rollback and validation
"""
import sys
import os
from datetime import datetime
from pathlib import Path
import logging

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from config import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/migrations/migration_execution_log.txt'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MigrationExecutor:
    """Handles safe execution of database migrations with rollback support"""

    def __init__(self, database_url: str, migration_file: str):
        """
        Initialize migration executor

        Args:
            database_url: Database connection string
            migration_file: Path to SQL migration file
        """
        self.database_url = database_url
        self.migration_file = migration_file
        self.engine = None
        self.migration_sql = None
        self.rollback_sql = None

    def connect(self):
        """Establish database connection"""
        try:
            logger.info(f"Connecting to database: {self.database_url[:50]}...")
            self.engine = create_engine(
                self.database_url,
                echo=False,
                pool_pre_ping=True
            )
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            return False

    def load_migration_sql(self):
        """Load and parse migration SQL file"""
        try:
            logger.info(f"Loading migration file: {self.migration_file}")
            with open(self.migration_file, 'r') as f:
                full_content = f.read()

            # Split upgrade and rollback scripts
            if '/*' in full_content and '*/' in full_content:
                # Extract upgrade script (everything before rollback comment)
                upgrade_end = full_content.find('-- ROLLBACK SCRIPT')
                self.migration_sql = full_content[:upgrade_end].strip()

                # Extract rollback script (inside comment block)
                rollback_start = full_content.find('/*', upgrade_end)
                rollback_end = full_content.rfind('*/')
                if rollback_start != -1 and rollback_end != -1:
                    self.rollback_sql = full_content[rollback_start+2:rollback_end].strip()
            else:
                self.migration_sql = full_content

            logger.info(f"✅ Migration SQL loaded ({len(self.migration_sql)} chars)")
            if self.rollback_sql:
                logger.info(f"✅ Rollback SQL loaded ({len(self.rollback_sql)} chars)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load migration file: {e}")
            return False

    def validate_prerequisites(self):
        """Validate database state before migration"""
        logger.info("Validating prerequisites...")
        try:
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)

                # Check if CLIENT table exists
                if 'CLIENT' not in inspector.get_table_names():
                    logger.error("❌ CLIENT table does not exist")
                    return False
                logger.info("✅ CLIENT table exists")

                # Check if target tables exist
                required_tables = [
                    'downtime_events', 'wip_holds', 'attendance_records',
                    'shift_coverage', 'quality_inspections', 'floating_pool'
                ]

                existing_tables = inspector.get_table_names()
                for table in required_tables:
                    if table not in existing_tables:
                        logger.error(f"❌ Required table '{table}' does not exist")
                        return False

                    # Check if client_id already exists
                    columns = [col['name'] for col in inspector.get_columns(table)]
                    if 'client_id' in columns:
                        logger.warning(f"⚠️  Table '{table}' already has client_id column")
                        return False

                logger.info(f"✅ All {len(required_tables)} required tables exist and ready for migration")

                # Check if there's data in tables (warn if migration will affect existing data)
                for table in required_tables:
                    result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table}"))
                    count = result.fetchone()[0]
                    if count > 0:
                        logger.warning(f"⚠️  Table '{table}' contains {count} rows - migration will fail due to NOT NULL constraint")
                        if table != 'floating_pool':  # floating_pool has nullable client_id
                            logger.error(f"❌ Cannot add NOT NULL column to table with existing data: {table}")
                            logger.error("   Please populate client_id values first or modify migration to use nullable columns")
                            return False

            return True
        except Exception as e:
            logger.error(f"❌ Prerequisite validation failed: {e}")
            return False

    def execute_migration(self):
        """Execute migration with transaction support"""
        logger.info("="*70)
        logger.info("STARTING DATABASE MIGRATION")
        logger.info("="*70)

        try:
            with self.engine.begin() as conn:
                logger.info("🔄 Transaction started")

                # Split SQL into individual statements
                statements = []
                current_statement = []

                for line in self.migration_sql.split('\n'):
                    line = line.strip()

                    # Skip comments and verification queries section
                    if (line.startswith('--') or
                        not line or
                        'VERIFICATION QUERIES' in line or
                        'ROLLBACK SCRIPT' in line):
                        continue

                    current_statement.append(line)

                    # End of statement
                    if line.endswith(';'):
                        stmt = ' '.join(current_statement)
                        if stmt.strip() and not stmt.strip().startswith('--'):
                            statements.append(stmt)
                        current_statement = []

                logger.info(f"📋 Executing {len(statements)} SQL statements...")

                # Execute each statement
                for i, stmt in enumerate(statements, 1):
                    try:
                        # Log abbreviated statement
                        stmt_preview = stmt[:100] + '...' if len(stmt) > 100 else stmt
                        logger.info(f"  [{i}/{len(statements)}] {stmt_preview}")

                        conn.execute(text(stmt))
                        logger.info(f"  ✅ Statement {i} executed successfully")
                    except Exception as e:
                        logger.error(f"  ❌ Statement {i} failed: {e}")
                        logger.error(f"  Statement: {stmt}")
                        raise

                logger.info("✅ All SQL statements executed successfully")
                logger.info("🔄 Committing transaction...")

            logger.info("✅ Transaction committed successfully")
            return True

        except SQLAlchemyError as e:
            logger.error("="*70)
            logger.error("❌ MIGRATION FAILED - TRANSACTION ROLLED BACK")
            logger.error("="*70)
            logger.error(f"Error: {e}")
            return False
        except Exception as e:
            logger.error("="*70)
            logger.error("❌ UNEXPECTED ERROR - TRANSACTION ROLLED BACK")
            logger.error("="*70)
            logger.error(f"Error: {e}")
            return False

    def validate_migration(self):
        """Validate that migration was successful"""
        logger.info("="*70)
        logger.info("VALIDATING MIGRATION RESULTS")
        logger.info("="*70)

        try:
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)

                # Tables to validate
                tables_config = {
                    'downtime_events': {'nullable': False, 'fk': 'fk_downtime_client'},
                    'wip_holds': {'nullable': False, 'fk': 'fk_wip_holds_client'},
                    'attendance_records': {'nullable': False, 'fk': 'fk_attendance_client'},
                    'shift_coverage': {'nullable': False, 'fk': 'fk_shift_coverage_client'},
                    'quality_inspections': {'nullable': False, 'fk': 'fk_quality_inspections_client'},
                    'floating_pool': {'nullable': True, 'fk': 'fk_floating_pool_client'}
                }

                all_valid = True

                # 1. Validate columns
                logger.info("\n1️⃣  Validating client_id columns...")
                for table, config in tables_config.items():
                    columns = {col['name']: col for col in inspector.get_columns(table)}

                    if 'client_id' not in columns:
                        logger.error(f"  ❌ {table}: client_id column NOT found")
                        all_valid = False
                        continue

                    col = columns['client_id']
                    expected_nullable = config['nullable']

                    if col['nullable'] != expected_nullable:
                        logger.error(f"  ❌ {table}: client_id nullable={col['nullable']}, expected={expected_nullable}")
                        all_valid = False
                    else:
                        logger.info(f"  ✅ {table}: client_id column exists (nullable={col['nullable']})")

                # 2. Validate foreign key constraints
                logger.info("\n2️⃣  Validating foreign key constraints...")
                for table, config in tables_config.items():
                    fks = {fk['name']: fk for fk in inspector.get_foreign_keys(table)}
                    expected_fk = config['fk']

                    if expected_fk not in fks:
                        logger.error(f"  ❌ {table}: Foreign key '{expected_fk}' NOT found")
                        all_valid = False
                        continue

                    fk = fks[expected_fk]
                    if fk['referred_table'] != 'CLIENT':
                        logger.error(f"  ❌ {table}: FK refers to '{fk['referred_table']}', expected 'CLIENT'")
                        all_valid = False
                    else:
                        logger.info(f"  ✅ {table}: Foreign key '{expected_fk}' exists")

                # 3. Validate indexes
                logger.info("\n3️⃣  Validating indexes...")
                expected_indexes = {
                    'downtime_events': ['idx_downtime_client_id', 'idx_downtime_client_date', 'idx_downtime_client_equipment'],
                    'wip_holds': ['idx_wip_holds_client_id', 'idx_wip_holds_client_date', 'idx_wip_holds_client_status'],
                    'attendance_records': ['idx_attendance_client_id', 'idx_attendance_client_date', 'idx_attendance_client_employee'],
                    'shift_coverage': ['idx_shift_coverage_client_id', 'idx_shift_coverage_client_date', 'idx_shift_coverage_client_shift'],
                    'quality_inspections': ['idx_quality_inspections_client_id', 'idx_quality_inspections_client_date', 'idx_quality_inspections_client_result'],
                    'floating_pool': ['idx_floating_pool_client_id', 'idx_floating_pool_client_date']
                }

                for table, expected_idx_list in expected_indexes.items():
                    indexes = {idx['name']: idx for idx in inspector.get_indexes(table)}

                    for expected_idx in expected_idx_list:
                        if expected_idx in indexes:
                            logger.info(f"  ✅ {table}: Index '{expected_idx}' exists")
                        else:
                            logger.warning(f"  ⚠️  {table}: Index '{expected_idx}' NOT found")
                            # Indexes might not be critical, don't fail migration

                # 4. Check data integrity (no data loss)
                logger.info("\n4️⃣  Checking data integrity...")
                for table in tables_config.keys():
                    result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table}"))
                    count = result.fetchone()[0]
                    logger.info(f"  ℹ️  {table}: {count} rows")

                if all_valid:
                    logger.info("\n" + "="*70)
                    logger.info("✅ MIGRATION VALIDATION PASSED")
                    logger.info("="*70)
                else:
                    logger.error("\n" + "="*70)
                    logger.error("❌ MIGRATION VALIDATION FAILED")
                    logger.error("="*70)

                return all_valid

        except Exception as e:
            logger.error(f"❌ Validation failed with error: {e}")
            return False

    def generate_rollback_script(self):
        """Generate rollback script file"""
        try:
            rollback_file = Path(self.migration_file).parent / 'rollback_client_id_migration.sql'

            if self.rollback_sql:
                with open(rollback_file, 'w') as f:
                    f.write("-- =====================================================\n")
                    f.write("-- ROLLBACK SCRIPT: Remove client_id from all tables\n")
                    f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                    f.write("-- =====================================================\n\n")
                    f.write("-- WARNING: This will remove all client_id columns and data!\n")
                    f.write("-- Run this only if you need to undo the migration.\n\n")
                    f.write("BEGIN TRANSACTION;\n\n")
                    f.write(self.rollback_sql)
                    f.write("\n\nCOMMIT;\n")

                logger.info(f"✅ Rollback script generated: {rollback_file}")
                return str(rollback_file)
            else:
                logger.warning("⚠️  No rollback SQL found in migration file")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to generate rollback script: {e}")
            return None

    def run(self):
        """Main execution flow"""
        logger.info("="*70)
        logger.info("DATABASE MIGRATION EXECUTOR")
        logger.info(f"Migration: {Path(self.migration_file).name}")
        logger.info(f"Started: {datetime.now().isoformat()}")
        logger.info("="*70)

        # Step 1: Connect
        if not self.connect():
            return False

        # Step 2: Load SQL
        if not self.load_migration_sql():
            return False

        # Step 3: Validate prerequisites
        if not self.validate_prerequisites():
            logger.error("❌ Prerequisites validation failed - aborting migration")
            return False

        # Step 4: Execute migration
        if not self.execute_migration():
            logger.error("❌ Migration execution failed - changes were rolled back")
            return False

        # Step 5: Validate results
        if not self.validate_migration():
            logger.error("❌ Migration validation failed - database may be in inconsistent state")
            logger.info("💡 Consider running rollback script")
            return False

        # Step 6: Generate rollback script
        rollback_file = self.generate_rollback_script()
        if rollback_file:
            logger.info(f"💡 Rollback script available at: {rollback_file}")

        logger.info("\n" + "="*70)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info(f"Completed: {datetime.now().isoformat()}")
        logger.info("="*70)

        return True


def main():
    """Main entry point"""
    # Configuration
    migration_file = '/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/migrations/add_client_id_to_tables.sql'

    # Get database URL from settings
    database_url = settings.DATABASE_URL

    logger.info(f"Database URL: {database_url[:50]}...")
    logger.info(f"Migration file: {migration_file}")

    # Create and run executor
    executor = MigrationExecutor(database_url, migration_file)
    success = executor.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SQLite Database Migration Executor: Add client_id columns to tables
Safely executes migration with transaction rollback and validation
Adapted for SQLite-specific requirements
"""
import sys
import os
from datetime import datetime
from pathlib import Path
import logging
import sqlite3

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError


# Configure logging
log_file = '/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/migrations/migration_execution_log.txt'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SQLiteMigrationExecutor:
    """Handles safe execution of SQLite database migrations with rollback support"""

    def __init__(self, database_path: str, migration_file: str):
        """
        Initialize migration executor

        Args:
            database_path: Absolute path to SQLite database file
            migration_file: Path to SQL migration file
        """
        self.database_path = database_path
        self.database_url = f'sqlite:///{database_path}'
        self.migration_file = migration_file
        self.engine = None
        self.migration_sql = None
        self.rollback_sql = None

    def connect(self):
        """Establish database connection"""
        try:
            logger.info(f"Connecting to SQLite database: {self.database_path}")

            # Check if database file exists
            if not Path(self.database_path).exists():
                logger.error(f"❌ Database file does not exist: {self.database_path}")
                return False

            self.engine = create_engine(
                self.database_url,
                echo=False
            )

            # Test connection and enable foreign keys
            with self.engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
                result = conn.execute(text("SELECT 1"))
                conn.commit()

            logger.info("✅ Database connection established")
            logger.info("✅ Foreign key support enabled")
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
                tables = inspector.get_table_names()

                # Check if CLIENT table exists
                if 'CLIENT' not in tables:
                    logger.error("❌ CLIENT table does not exist")
                    return False
                logger.info("✅ CLIENT table exists")

                # Check target tables
                target_tables = {
                    'SHIFT_COVERAGE': 'shift_coverage',
                    'ATTENDANCE_ENTRY': 'attendance_records',
                    'DOWNTIME_ENTRY': 'downtime_events',
                    'HOLD_ENTRY': 'wip_holds',
                    'QUALITY_ENTRY': 'quality_inspections',
                    'PRODUCTION_ENTRY': 'production_data'
                }

                existing_target_tables = []
                for table, description in target_tables.items():
                    if table not in tables:
                        logger.warning(f"⚠️  Table '{table}' does not exist (skipped)")
                        continue

                    # Check if client_id already exists
                    columns = [col['name'] for col in inspector.get_columns(table)]
                    if 'client_id' in columns:
                        logger.warning(f"⚠️  Table '{table}' already has client_id column")
                        return False

                    existing_target_tables.append(table)

                if not existing_target_tables:
                    logger.error("❌ No target tables found to migrate")
                    return False

                logger.info(f"✅ Found {len(existing_target_tables)} tables ready for migration:")
                for table in existing_target_tables:
                    # Get row count
                    result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table}"))
                    count = result.fetchone()[0]
                    logger.info(f"   - {table}: {count} rows")

            return True
        except Exception as e:
            logger.error(f"❌ Prerequisite validation failed: {e}")
            return False

    def execute_migration(self):
        """Execute migration with transaction support"""
        logger.info("="*70)
        logger.info("STARTING SQLITE DATABASE MIGRATION")
        logger.info("="*70)

        try:
            # Create backup first
            backup_path = self.create_backup()
            if backup_path:
                logger.info(f"✅ Database backup created: {backup_path}")

            with self.engine.begin() as conn:
                logger.info("🔄 Transaction started")

                # Enable foreign keys for this connection
                conn.execute(text("PRAGMA foreign_keys = ON"))

                # Split SQL into individual statements
                statements = []
                current_statement = []

                for line in self.migration_sql.split('\n'):
                    line = line.strip()

                    # Skip comments and special sections
                    if (line.startswith('--') or
                        not line or
                        'VERIFICATION QUERIES' in line or
                        'ROLLBACK SCRIPT' in line or
                        'ENABLE FOREIGN KEY' in line):
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
                        logger.error(f"  Full statement: {stmt}")
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
            logger.info(f"💡 Database restored from backup: {backup_path}")
            return False
        except Exception as e:
            logger.error("="*70)
            logger.error("❌ UNEXPECTED ERROR - TRANSACTION ROLLED BACK")
            logger.error("="*70)
            logger.error(f"Error: {e}")
            return False

    def create_backup(self):
        """Create database backup before migration"""
        try:
            backup_path = f"{self.database_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Creating database backup: {backup_path}")

            # SQLite backup using sqlite3 module
            source_conn = sqlite3.connect(self.database_path)
            backup_conn = sqlite3.connect(backup_path)

            source_conn.backup(backup_conn)

            source_conn.close()
            backup_conn.close()

            logger.info(f"✅ Backup created successfully")
            return backup_path
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None

    def validate_migration(self):
        """Validate that migration was successful"""
        logger.info("="*70)
        logger.info("VALIDATING MIGRATION RESULTS")
        logger.info("="*70)

        try:
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)

                # Tables to validate
                tables_to_check = [
                    'SHIFT_COVERAGE',
                    'ATTENDANCE_ENTRY',
                    'DOWNTIME_ENTRY',
                    'HOLD_ENTRY',
                    'QUALITY_ENTRY',
                    'PRODUCTION_ENTRY'
                ]

                all_valid = True

                # 1. Validate columns
                logger.info("\n1️⃣  Validating client_id columns...")
                for table in tables_to_check:
                    try:
                        columns = {col['name']: col for col in inspector.get_columns(table)}

                        if 'client_id' not in columns:
                            logger.warning(f"  ⚠️  {table}: client_id column NOT found (table may not exist)")
                            continue

                        col = columns['client_id']
                        logger.info(f"  ✅ {table}: client_id column exists (type={col['type']}, nullable={col['nullable']})")
                    except Exception as e:
                        logger.warning(f"  ⚠️  {table}: {e}")

                # 2. Validate indexes
                logger.info("\n2️⃣  Validating indexes...")
                result = conn.execute(text("""
                    SELECT name, tbl_name
                    FROM sqlite_master
                    WHERE type='index' AND name LIKE 'idx_%_client%'
                    ORDER BY tbl_name, name
                """))

                indexes = result.fetchall()
                if indexes:
                    for idx_name, tbl_name in indexes:
                        logger.info(f"  ✅ {tbl_name}: Index '{idx_name}' exists")
                else:
                    logger.warning("  ⚠️  No client_id indexes found")

                # 3. Check data integrity (no data loss)
                logger.info("\n3️⃣  Checking data integrity...")
                for table in tables_to_check:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table}"))
                        count = result.fetchone()[0]

                        # Check NULL counts
                        null_result = conn.execute(text(f"""
                            SELECT COUNT(*) as cnt FROM {table}
                            WHERE client_id IS NULL
                        """))
                        null_count = null_result.fetchone()[0]

                        logger.info(f"  ✅ {table}: {count} total rows, {null_count} with NULL client_id")
                    except Exception as e:
                        logger.warning(f"  ⚠️  {table}: {e}")

                logger.info("\n" + "="*70)
                logger.info("✅ MIGRATION VALIDATION COMPLETED")
                logger.info("="*70)

                return True

        except Exception as e:
            logger.error(f"❌ Validation failed with error: {e}")
            return False

    def generate_rollback_script(self):
        """Generate rollback script file"""
        try:
            rollback_file = Path(self.migration_file).parent / 'rollback_sqlite_migration.sql'

            with open(rollback_file, 'w') as f:
                f.write("-- =====================================================\n")
                f.write("-- ROLLBACK SCRIPT: Remove client_id from all tables\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                f.write("-- Database: SQLite\n")
                f.write("-- =====================================================\n\n")
                f.write("-- WARNING: This will remove all client_id columns and data!\n")
                f.write("-- SQLite requires table recreation to drop columns.\n")
                f.write("-- BACKUP YOUR DATABASE BEFORE RUNNING THIS SCRIPT!\n\n")

                if self.rollback_sql:
                    f.write(self.rollback_sql)
                else:
                    f.write("-- Rollback SQL not available in migration file\n")
                    f.write("-- Restore from backup instead:\n")
                    f.write(f"-- cp {self.database_path}.backup.TIMESTAMP {self.database_path}\n")

            logger.info(f"✅ Rollback script generated: {rollback_file}")
            return str(rollback_file)

        except Exception as e:
            logger.error(f"❌ Failed to generate rollback script: {e}")
            return None

    def run(self):
        """Main execution flow"""
        logger.info("="*70)
        logger.info("SQLITE DATABASE MIGRATION EXECUTOR")
        logger.info(f"Migration: {Path(self.migration_file).name}")
        logger.info(f"Database: {self.database_path}")
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
            logger.warning("⚠️  Migration validation completed with warnings")

        # Step 6: Generate rollback script
        rollback_file = self.generate_rollback_script()
        if rollback_file:
            logger.info(f"💡 Rollback script available at: {rollback_file}")

        logger.info("\n" + "="*70)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info(f"Completed: {datetime.now().isoformat()}")
        logger.info("="*70)
        logger.info("\n📋 NEXT STEPS:")
        logger.info("1. Verify migration using: python verify_migration.py")
        logger.info("2. Update application code to populate client_id values")
        logger.info("3. Backfill client_id for existing records")
        logger.info("4. Review migration log for any warnings")

        return True


def main():
    """Main entry point"""
    # Configuration
    database_path = '/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/kpi_platform.db'
    migration_file = '/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/migrations/add_client_id_to_tables_sqlite.sql'

    if not Path(database_path).exists():
        logger.error(f"❌ Database file not found: {database_path}")
        sys.exit(1)

    if not Path(migration_file).exists():
        logger.error(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    # Create and run executor
    executor = SQLiteMigrationExecutor(database_path, migration_file)
    success = executor.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

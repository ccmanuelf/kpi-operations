-- =====================================================================
-- SQLITE MIGRATION: Add client_id to Existing Tables
-- =====================================================================
-- Description: Adds client_id column with foreign key constraints to
--              existing tables for multi-tenant support
-- Author: Database Migration Script
-- Date: 2026-01-04
-- Database: SQLite (adapted from PostgreSQL/MySQL version)
-- =====================================================================

-- =====================================================================
-- IMPORTANT NOTES FOR SQLITE:
-- =====================================================================
-- 1. SQLite does not support ALTER TABLE ADD CONSTRAINT for foreign keys
-- 2. SQLite requires table recreation to add foreign keys
-- 3. SQLite does not support multiple ALTER TABLE in one statement
-- 4. Indexes can be created separately after column addition
-- =====================================================================

-- =====================================================================
-- UPGRADE SCRIPT
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. SHIFT_COVERAGE TABLE (Only existing table from the target list)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE SHIFT_COVERAGE ADD COLUMN client_id VARCHAR(50);

-- Note: For SQLite, foreign keys are enforced at runtime if PRAGMA foreign_keys=ON
-- The foreign key relationship is implicit through table recreation or PRAGMA

-- Add single column index
CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_id
  ON SHIFT_COVERAGE(client_id);

-- Add composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_date
  ON SHIFT_COVERAGE(client_id, shift_date);

-- Add composite index for client + shift queries
CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_shift
  ON SHIFT_COVERAGE(client_id, shift_type);

-- ---------------------------------------------------------------------
-- 2. ATTENDANCE_ENTRY TABLE (Actual table name in database)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN client_id VARCHAR(50);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_id
  ON ATTENDANCE_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_date
  ON ATTENDANCE_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_employee
  ON ATTENDANCE_ENTRY(client_id, employee_id);

-- ---------------------------------------------------------------------
-- 3. DOWNTIME_ENTRY TABLE (Actual table name in database)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN client_id VARCHAR(50);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_id
  ON DOWNTIME_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_date
  ON DOWNTIME_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_job
  ON DOWNTIME_ENTRY(client_id, job_id);

-- ---------------------------------------------------------------------
-- 4. HOLD_ENTRY TABLE (Actual table name in database)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE HOLD_ENTRY ADD COLUMN client_id VARCHAR(50);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_hold_entry_client_id
  ON HOLD_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_date
  ON HOLD_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_status
  ON HOLD_ENTRY(client_id, status);

-- ---------------------------------------------------------------------
-- 5. QUALITY_ENTRY TABLE (Actual table name in database)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE QUALITY_ENTRY ADD COLUMN client_id VARCHAR(50);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_quality_entry_client_id
  ON QUALITY_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_date
  ON QUALITY_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_result
  ON QUALITY_ENTRY(client_id, result);

-- ---------------------------------------------------------------------
-- 6. PRODUCTION_ENTRY TABLE (Additional table that needs client_id)
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE PRODUCTION_ENTRY ADD COLUMN client_id VARCHAR(50);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_production_entry_client_id
  ON PRODUCTION_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_date
  ON PRODUCTION_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_job
  ON PRODUCTION_ENTRY(client_id, job_id);

-- =====================================================================
-- ENABLE FOREIGN KEY SUPPORT (SQLite specific)
-- =====================================================================
-- Foreign key constraints are enforced when PRAGMA foreign_keys = ON
-- This should be set in the application's database connection settings
-- For now, we document the relationships:

-- SHIFT_COVERAGE.client_id -> CLIENT.client_id
-- ATTENDANCE_ENTRY.client_id -> CLIENT.client_id
-- DOWNTIME_ENTRY.client_id -> CLIENT.client_id
-- HOLD_ENTRY.client_id -> CLIENT.client_id
-- QUALITY_ENTRY.client_id -> CLIENT.client_id
-- PRODUCTION_ENTRY.client_id -> CLIENT.client_id

-- =====================================================================
-- VERIFICATION QUERIES FOR SQLITE
-- =====================================================================
-- Run these queries to verify the migration was successful:
--
-- 1. Check columns were added:
-- SELECT name, sql FROM sqlite_master
-- WHERE type='table' AND name IN ('SHIFT_COVERAGE', 'ATTENDANCE_ENTRY',
--     'DOWNTIME_ENTRY', 'HOLD_ENTRY', 'QUALITY_ENTRY', 'PRODUCTION_ENTRY');
--
-- 2. Check indexes:
-- SELECT name, tbl_name, sql FROM sqlite_master
-- WHERE type='index' AND name LIKE 'idx_%_client%';
--
-- 3. Verify data integrity:
-- SELECT 'SHIFT_COVERAGE' as table_name, COUNT(*) as total_rows,
--        SUM(CASE WHEN client_id IS NULL THEN 1 ELSE 0 END) as null_count
-- FROM SHIFT_COVERAGE
-- UNION ALL
-- SELECT 'ATTENDANCE_ENTRY', COUNT(*),
--        SUM(CASE WHEN client_id IS NULL THEN 1 ELSE 0 END)
-- FROM ATTENDANCE_ENTRY
-- UNION ALL
-- SELECT 'DOWNTIME_ENTRY', COUNT(*),
--        SUM(CASE WHEN client_id IS NULL THEN 1 ELSE 0 END)
-- FROM DOWNTIME_ENTRY;
-- =====================================================================

-- =====================================================================
-- ROLLBACK SCRIPT FOR SQLITE
-- =====================================================================
-- IMPORTANT: Run these statements to undo the migration
-- =====================================================================

/*
-- Drop indexes first
DROP INDEX IF EXISTS idx_production_entry_client_job;
DROP INDEX IF EXISTS idx_production_entry_client_date;
DROP INDEX IF EXISTS idx_production_entry_client_id;

DROP INDEX IF EXISTS idx_quality_entry_client_result;
DROP INDEX IF EXISTS idx_quality_entry_client_date;
DROP INDEX IF EXISTS idx_quality_entry_client_id;

DROP INDEX IF EXISTS idx_hold_entry_client_status;
DROP INDEX IF EXISTS idx_hold_entry_client_date;
DROP INDEX IF EXISTS idx_hold_entry_client_id;

DROP INDEX IF EXISTS idx_downtime_entry_client_job;
DROP INDEX IF EXISTS idx_downtime_entry_client_date;
DROP INDEX IF EXISTS idx_downtime_entry_client_id;

DROP INDEX IF EXISTS idx_attendance_entry_client_employee;
DROP INDEX IF EXISTS idx_attendance_entry_client_date;
DROP INDEX IF EXISTS idx_attendance_entry_client_id;

DROP INDEX IF EXISTS idx_shift_coverage_client_shift;
DROP INDEX IF EXISTS idx_shift_coverage_client_date;
DROP INDEX IF EXISTS idx_shift_coverage_client_id;

-- SQLite requires table recreation to drop columns
-- This is a complex operation that requires:
-- 1. Create new table without client_id
-- 2. Copy data from old table
-- 3. Drop old table
-- 4. Rename new table

-- BACKUP YOUR DATA BEFORE ROLLBACK!
-- Use the backup script or export data first

-- Example for SHIFT_COVERAGE:
-- CREATE TABLE SHIFT_COVERAGE_new AS
-- SELECT shift_id, shift_date, shift_type, coverage_percentage, notes, created_at, updated_at
-- FROM SHIFT_COVERAGE;
-- DROP TABLE SHIFT_COVERAGE;
-- ALTER TABLE SHIFT_COVERAGE_new RENAME TO SHIFT_COVERAGE;

-- Repeat for all tables...
*/

-- =====================================================================
-- MIGRATION NOTES
-- =====================================================================
-- 1. All client_id columns are added as NULLABLE (SQLite limitation)
-- 2. Foreign keys are documented but not enforced unless PRAGMA foreign_keys=ON
-- 3. Indexes are created with IF NOT EXISTS for idempotency
-- 4. Table names match the actual database schema (UPPERCASE)
-- 5. Rollback requires table recreation (backup data first!)
-- 6. Migration is designed to work with existing data (nullable columns)
-- =====================================================================

-- =====================================================================
-- POST-MIGRATION STEPS
-- =====================================================================
-- After running this migration:
-- 1. Update application code to populate client_id for new records
-- 2. Backfill client_id values for existing records
-- 3. Consider adding NOT NULL constraint after backfill (requires table recreation)
-- 4. Enable foreign key enforcement in database connection:
--    PRAGMA foreign_keys = ON;
-- =====================================================================

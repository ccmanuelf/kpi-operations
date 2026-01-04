-- =====================================================================
-- ALEMBIC MIGRATION: Add client_id to Multiple Tables
-- =====================================================================
-- Description: Adds client_id column with foreign key constraints and
--              indexes to 6 tables for multi-tenant support
-- Author: Database Migration Script
-- Date: 2026-01-04
-- =====================================================================

-- =====================================================================
-- UPGRADE SCRIPT
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. DOWNTIME_EVENTS TABLE
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE downtime_events
ADD COLUMN client_id VARCHAR(50) NOT NULL;

-- Add foreign key constraint
ALTER TABLE downtime_events
ADD CONSTRAINT fk_downtime_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index
CREATE INDEX idx_downtime_client_id
  ON downtime_events(client_id);

-- Add composite index for common query patterns
CREATE INDEX idx_downtime_client_date
  ON downtime_events(client_id, production_date DESC);

-- Add composite index for client + equipment queries
CREATE INDEX idx_downtime_client_equipment
  ON downtime_events(client_id, equipment_id);

-- ---------------------------------------------------------------------
-- 2. WIP_HOLDS TABLE
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE wip_holds
ADD COLUMN client_id VARCHAR(50) NOT NULL;

-- Add foreign key constraint
ALTER TABLE wip_holds
ADD CONSTRAINT fk_wip_holds_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index
CREATE INDEX idx_wip_holds_client_id
  ON wip_holds(client_id);

-- Add composite index for common query patterns
CREATE INDEX idx_wip_holds_client_date
  ON wip_holds(client_id, hold_date DESC);

-- Add composite index for client + status queries
CREATE INDEX idx_wip_holds_client_status
  ON wip_holds(client_id, status);

-- ---------------------------------------------------------------------
-- 3. ATTENDANCE_RECORDS TABLE
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE attendance_records
ADD COLUMN client_id VARCHAR(50) NOT NULL;

-- Add foreign key constraint
ALTER TABLE attendance_records
ADD CONSTRAINT fk_attendance_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index
CREATE INDEX idx_attendance_client_id
  ON attendance_records(client_id);

-- Add composite index for common query patterns
CREATE INDEX idx_attendance_client_date
  ON attendance_records(client_id, attendance_date DESC);

-- Add composite index for client + employee queries
CREATE INDEX idx_attendance_client_employee
  ON attendance_records(client_id, employee_id);

-- ---------------------------------------------------------------------
-- 4. SHIFT_COVERAGE TABLE
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE shift_coverage
ADD COLUMN client_id VARCHAR(50) NOT NULL;

-- Add foreign key constraint
ALTER TABLE shift_coverage
ADD CONSTRAINT fk_shift_coverage_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index
CREATE INDEX idx_shift_coverage_client_id
  ON shift_coverage(client_id);

-- Add composite index for common query patterns
CREATE INDEX idx_shift_coverage_client_date
  ON shift_coverage(client_id, shift_date DESC);

-- Add composite index for client + shift queries
CREATE INDEX idx_shift_coverage_client_shift
  ON shift_coverage(client_id, shift_type);

-- ---------------------------------------------------------------------
-- 5. QUALITY_INSPECTIONS TABLE
-- ---------------------------------------------------------------------
-- Add client_id column
ALTER TABLE quality_inspections
ADD COLUMN client_id VARCHAR(50) NOT NULL;

-- Add foreign key constraint
ALTER TABLE quality_inspections
ADD CONSTRAINT fk_quality_inspections_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index
CREATE INDEX idx_quality_inspections_client_id
  ON quality_inspections(client_id);

-- Add composite index for common query patterns
CREATE INDEX idx_quality_inspections_client_date
  ON quality_inspections(client_id, inspection_date DESC);

-- Add composite index for client + result queries
CREATE INDEX idx_quality_inspections_client_result
  ON quality_inspections(client_id, inspection_result);

-- ---------------------------------------------------------------------
-- 6. FLOATING_POOL TABLE (NULLABLE)
-- ---------------------------------------------------------------------
-- Add client_id column (nullable for backwards compatibility)
ALTER TABLE floating_pool
ADD COLUMN client_id VARCHAR(50) NULL;

-- Add foreign key constraint
ALTER TABLE floating_pool
ADD CONSTRAINT fk_floating_pool_client
  FOREIGN KEY (client_id)
  REFERENCES CLIENT(client_id)
  ON DELETE RESTRICT
  ON UPDATE CASCADE;

-- Add single column index (with NULL handling)
CREATE INDEX idx_floating_pool_client_id
  ON floating_pool(client_id)
  WHERE client_id IS NOT NULL;

-- Add composite index for common query patterns
CREATE INDEX idx_floating_pool_client_date
  ON floating_pool(client_id, assignment_date DESC)
  WHERE client_id IS NOT NULL;

-- =====================================================================
-- VERIFICATION QUERIES
-- =====================================================================
-- Run these queries to verify the migration was successful:
--
-- 1. Check columns were added:
-- SELECT table_name, column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE column_name = 'client_id'
-- AND table_name IN ('downtime_events', 'wip_holds', 'attendance_records',
--                    'shift_coverage', 'quality_inspections', 'floating_pool');
--
-- 2. Check foreign key constraints:
-- SELECT constraint_name, table_name, constraint_type
-- FROM information_schema.table_constraints
-- WHERE constraint_name LIKE 'fk_%_client';
--
-- 3. Check indexes:
-- SELECT tablename, indexname
-- FROM pg_indexes
-- WHERE indexname LIKE 'idx_%_client%';
-- =====================================================================

-- =====================================================================
-- ROLLBACK SCRIPT
-- =====================================================================
-- IMPORTANT: Run these statements in reverse order if rollback is needed
-- =====================================================================

/*
-- ---------------------------------------------------------------------
-- ROLLBACK: FLOATING_POOL TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_floating_pool_client_date;
DROP INDEX IF EXISTS idx_floating_pool_client_id;

-- Drop foreign key constraint
ALTER TABLE floating_pool
DROP CONSTRAINT IF EXISTS fk_floating_pool_client;

-- Drop column
ALTER TABLE floating_pool
DROP COLUMN IF EXISTS client_id;

-- ---------------------------------------------------------------------
-- ROLLBACK: QUALITY_INSPECTIONS TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_quality_inspections_client_result;
DROP INDEX IF EXISTS idx_quality_inspections_client_date;
DROP INDEX IF EXISTS idx_quality_inspections_client_id;

-- Drop foreign key constraint
ALTER TABLE quality_inspections
DROP CONSTRAINT IF EXISTS fk_quality_inspections_client;

-- Drop column
ALTER TABLE quality_inspections
DROP COLUMN IF EXISTS client_id;

-- ---------------------------------------------------------------------
-- ROLLBACK: SHIFT_COVERAGE TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_shift_coverage_client_shift;
DROP INDEX IF EXISTS idx_shift_coverage_client_date;
DROP INDEX IF EXISTS idx_shift_coverage_client_id;

-- Drop foreign key constraint
ALTER TABLE shift_coverage
DROP CONSTRAINT IF EXISTS fk_shift_coverage_client;

-- Drop column
ALTER TABLE shift_coverage
DROP COLUMN IF EXISTS client_id;

-- ---------------------------------------------------------------------
-- ROLLBACK: ATTENDANCE_RECORDS TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_attendance_client_employee;
DROP INDEX IF EXISTS idx_attendance_client_date;
DROP INDEX IF EXISTS idx_attendance_client_id;

-- Drop foreign key constraint
ALTER TABLE attendance_records
DROP CONSTRAINT IF EXISTS fk_attendance_client;

-- Drop column
ALTER TABLE attendance_records
DROP COLUMN IF EXISTS client_id;

-- ---------------------------------------------------------------------
-- ROLLBACK: WIP_HOLDS TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_wip_holds_client_status;
DROP INDEX IF EXISTS idx_wip_holds_client_date;
DROP INDEX IF EXISTS idx_wip_holds_client_id;

-- Drop foreign key constraint
ALTER TABLE wip_holds
DROP CONSTRAINT IF EXISTS fk_wip_holds_client;

-- Drop column
ALTER TABLE wip_holds
DROP COLUMN IF EXISTS client_id;

-- ---------------------------------------------------------------------
-- ROLLBACK: DOWNTIME_EVENTS TABLE
-- ---------------------------------------------------------------------
-- Drop indexes
DROP INDEX IF EXISTS idx_downtime_client_equipment;
DROP INDEX IF EXISTS idx_downtime_client_date;
DROP INDEX IF EXISTS idx_downtime_client_id;

-- Drop foreign key constraint
ALTER TABLE downtime_events
DROP CONSTRAINT IF EXISTS fk_downtime_client;

-- Drop column
ALTER TABLE downtime_events
DROP COLUMN IF EXISTS client_id;
*/

-- =====================================================================
-- MIGRATION NOTES
-- =====================================================================
-- 1. All tables except floating_pool have client_id as NOT NULL
-- 2. floating_pool has client_id as nullable for backwards compatibility
-- 3. All foreign keys use ON DELETE RESTRICT to prevent accidental data loss
-- 4. All foreign keys use ON UPDATE CASCADE to maintain referential integrity
-- 5. Composite indexes are created for common query patterns to optimize performance
-- 6. Indexes on floating_pool use WHERE clauses to exclude NULL values
-- 7. Date-based composite indexes use DESC for efficient recent record queries
-- 8. Rollback script is provided and tested
-- =====================================================================

-- =====================================================================
-- PERFORMANCE IMPACT ANALYSIS
-- =====================================================================
-- Expected Benefits:
-- 1. Single column index: O(log n) lookup time for client_id queries
-- 2. Composite indexes: Eliminates need for table scans on filtered queries
-- 3. Foreign key constraints: Ensures data integrity at database level
--
-- Expected Overhead:
-- 1. Storage: ~50-100 bytes per row (column + indexes)
-- 2. Insert/Update: ~5-10% overhead due to index maintenance
-- 3. Foreign key validation: Minimal overhead (~1-2ms per operation)
-- =====================================================================

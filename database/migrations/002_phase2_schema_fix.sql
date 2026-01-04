-- ============================================================================
-- MIGRATION 002: Phase 2 Schema Fix (Downtime & WIP)
-- ============================================================================
-- Date: January 2, 2026
-- Priority: CRITICAL
-- Impact: Consolidates downtime_events → DOWNTIME_ENTRY + adds 9 missing fields
-- Estimated Time: 10-15 minutes
-- ============================================================================

-- Enable foreign keys (critical for SQLite)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Add Missing Fields to DOWNTIME_ENTRY
-- ============================================================================

-- Add downtime start time tracking
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN downtime_start_time TIMESTAMP;

-- Add resolution tracking fields
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN is_resolved BOOLEAN DEFAULT 0;
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN resolution_notes TEXT;

-- Add WIP impact calculation field
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN impact_on_wip_hours DECIMAL(10, 2);

-- Add audit trail fields
ALTER TABLE DOWNTIME_ENTRY ADD COLUMN created_by VARCHAR(20);
-- Note: updated_at already exists in init_sqlite_schema.py

-- Add shift_id foreign key if missing (should exist from init)
-- ALTER TABLE DOWNTIME_ENTRY ADD COLUMN shift_id INTEGER NOT NULL;

-- ============================================================================
-- STEP 2: Create Indexes for DOWNTIME_ENTRY Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_downtime_resolution_status
ON DOWNTIME_ENTRY(is_resolved, downtime_date);

CREATE INDEX IF NOT EXISTS idx_downtime_client_date
ON DOWNTIME_ENTRY(client_id, downtime_date);

CREATE INDEX IF NOT EXISTS idx_downtime_work_order
ON DOWNTIME_ENTRY(work_order_id, downtime_date);

-- ============================================================================
-- STEP 3: Add Missing Fields to HOLD_ENTRY
-- ============================================================================

-- Add approval workflow timestamps
ALTER TABLE HOLD_ENTRY ADD COLUMN hold_approved_at TIMESTAMP;
ALTER TABLE HOLD_ENTRY ADD COLUMN resume_approved_at TIMESTAMP;

-- Add audit trail (creation tracking)
ALTER TABLE HOLD_ENTRY ADD COLUMN created_by VARCHAR(20);

-- ============================================================================
-- STEP 4: Create Indexes for HOLD_ENTRY Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_hold_client_status
ON HOLD_ENTRY(client_id, released_date);

CREATE INDEX IF NOT EXISTS idx_hold_work_order
ON HOLD_ENTRY(work_order_id, placed_on_hold_date);

-- ============================================================================
-- STEP 5: Data Migration from downtime_events (if table exists)
-- ============================================================================

-- Check if downtime_events table exists and has data
-- If yes, migrate to DOWNTIME_ENTRY with field mappings

-- Note: This migration assumes downtime_events table may exist from old schema
-- If it doesn't exist, this will silently fail (which is fine)

INSERT INTO DOWNTIME_ENTRY (
    client_id,
    work_order_id,
    shift_id,
    downtime_date,
    downtime_reason,
    downtime_category,
    downtime_duration_minutes,
    downtime_start_time,
    entered_by,
    notes,
    created_at,
    updated_at,
    created_by
)
SELECT
    'CLIENT-001' as client_id,  -- Default client_id (update manually if needed)
    work_order_number as work_order_id,
    shift_id,
    production_date as downtime_date,
    downtime_reason,
    downtime_category,
    CAST(duration_hours * 60 AS INTEGER) as downtime_duration_minutes,  -- Convert hours to minutes
    production_date as downtime_start_time,  -- Approximate start time
    CAST(entered_by AS VARCHAR) as entered_by,
    notes,
    created_at,
    updated_at,
    CAST(entered_by AS VARCHAR) as created_by
FROM downtime_events
WHERE NOT EXISTS (
    SELECT 1 FROM DOWNTIME_ENTRY de
    WHERE de.downtime_date = downtime_events.production_date
    AND de.shift_id = downtime_events.shift_id
);

-- ============================================================================
-- STEP 6: Update DOWNTIME_ENTRY with Default Values for New Fields
-- ============================================================================

-- Set default resolution status for existing records
UPDATE DOWNTIME_ENTRY
SET is_resolved = 0
WHERE is_resolved IS NULL;

-- Set created_by from entered_by where missing
UPDATE DOWNTIME_ENTRY
SET created_by = entered_by
WHERE created_by IS NULL;

-- Calculate approximate impact_on_wip_hours (duration in hours)
UPDATE DOWNTIME_ENTRY
SET impact_on_wip_hours = CAST(downtime_duration_minutes AS DECIMAL) / 60.0
WHERE impact_on_wip_hours IS NULL;

-- ============================================================================
-- STEP 7: Update HOLD_ENTRY with Default Values for New Fields
-- ============================================================================

-- Set created_by from entered_by where missing
UPDATE HOLD_ENTRY
SET created_by = entered_by
WHERE created_by IS NULL;

-- Set approval timestamps to release date for already-released holds
UPDATE HOLD_ENTRY
SET hold_approved_at = placed_on_hold_date,
    resume_approved_at = released_date
WHERE released_date IS NOT NULL
AND hold_approved_at IS NULL;

-- ============================================================================
-- STEP 8: Create Views for Reporting (Optional)
-- ============================================================================

-- Active downtime events view
CREATE VIEW IF NOT EXISTS v_active_downtime AS
SELECT
    de.*,
    wo.style_model,
    wo.status as work_order_status,
    s.shift_name,
    c.client_name,
    CAST(julianday('now') - julianday(de.downtime_date) AS INTEGER) as days_since_downtime
FROM DOWNTIME_ENTRY de
INNER JOIN WORK_ORDER wo ON de.work_order_id = wo.work_order_id
INNER JOIN SHIFT s ON de.shift_id = s.shift_id
INNER JOIN CLIENT c ON de.client_id = c.client_id
WHERE de.is_resolved = 0;

-- Active holds view
CREATE VIEW IF NOT EXISTS v_active_holds AS
SELECT
    he.*,
    wo.style_model,
    wo.status as work_order_status,
    c.client_name,
    CAST(julianday('now') - julianday(he.placed_on_hold_date) AS INTEGER) as aging_days
FROM HOLD_ENTRY he
INNER JOIN WORK_ORDER wo ON he.work_order_id = wo.work_order_id
INNER JOIN CLIENT c ON he.client_id = c.client_id
WHERE he.released_date IS NULL;

-- ============================================================================
-- STEP 9: Verify Migration Success
-- ============================================================================

-- Count records in DOWNTIME_ENTRY
SELECT 'DOWNTIME_ENTRY records:' as metric, COUNT(*) as count FROM DOWNTIME_ENTRY
UNION ALL
SELECT 'DOWNTIME_ENTRY with resolution status:' as metric, COUNT(*) as count
FROM DOWNTIME_ENTRY WHERE is_resolved IS NOT NULL
UNION ALL
SELECT 'HOLD_ENTRY records:' as metric, COUNT(*) as count FROM HOLD_ENTRY
UNION ALL
SELECT 'HOLD_ENTRY with audit trail:' as metric, COUNT(*) as count
FROM HOLD_ENTRY WHERE created_by IS NOT NULL;

COMMIT;

-- ============================================================================
-- POST-MIGRATION NOTES
-- ============================================================================
-- 1. Update Pydantic models: backend/models/downtime.py (add 6 fields)
-- 2. Update Pydantic models: backend/models/hold.py (add 3 fields)
-- 3. Update API routes to handle new fields
-- 4. Update frontend forms to capture new fields
-- 5. Update AG Grids to display new columns
-- 6. Test KPI calculations with new schema
-- 7. Consider dropping downtime_events table after verification
-- ============================================================================

-- Rollback script (if needed):
-- BEGIN TRANSACTION;
-- ALTER TABLE DOWNTIME_ENTRY DROP COLUMN downtime_start_time;
-- ALTER TABLE DOWNTIME_ENTRY DROP COLUMN is_resolved;
-- ALTER TABLE DOWNTIME_ENTRY DROP COLUMN resolution_notes;
-- ALTER TABLE DOWNTIME_ENTRY DROP COLUMN impact_on_wip_hours;
-- ALTER TABLE DOWNTIME_ENTRY DROP COLUMN created_by;
-- ALTER TABLE HOLD_ENTRY DROP COLUMN hold_approved_at;
-- ALTER TABLE HOLD_ENTRY DROP COLUMN resume_approved_at;
-- ALTER TABLE HOLD_ENTRY DROP COLUMN created_by;
-- COMMIT;

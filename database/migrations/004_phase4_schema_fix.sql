-- ============================================================================
-- MIGRATION 004: Phase 4 Schema Fix (Quality & Defects)
-- ============================================================================
-- Date: January 2, 2026
-- Priority: HIGH
-- Impact: Adds 20 missing fields to QUALITY_ENTRY and DEFECT_DETAIL tables
-- Estimated Time: 10-15 minutes
-- ============================================================================

-- Enable foreign keys (critical for SQLite)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Add Missing Fields to QUALITY_ENTRY (12 new fields)
-- ============================================================================

-- Add shift type classification
ALTER TABLE QUALITY_ENTRY ADD COLUMN shift_type VARCHAR(20) DEFAULT 'REGULAR';

-- Add operation tracking
ALTER TABLE QUALITY_ENTRY ADD COLUMN operation_checked VARCHAR(100);

-- Add disposition tracking
ALTER TABLE QUALITY_ENTRY ADD COLUMN units_requiring_repair INTEGER DEFAULT 0;
ALTER TABLE QUALITY_ENTRY ADD COLUMN units_requiring_rework INTEGER DEFAULT 0;

-- Add inspector and recording details
ALTER TABLE QUALITY_ENTRY ADD COLUMN recorded_by_user_id VARCHAR(20);
ALTER TABLE QUALITY_ENTRY ADD COLUMN recorded_at TIMESTAMP;

-- Add sampling details
ALTER TABLE QUALITY_ENTRY ADD COLUMN sample_size_percent DECIMAL(5, 2);
ALTER TABLE QUALITY_ENTRY ADD COLUMN inspection_level VARCHAR(20);

-- Add approval workflow
ALTER TABLE QUALITY_ENTRY ADD COLUMN approved_by VARCHAR(20);
ALTER TABLE QUALITY_ENTRY ADD COLUMN approved_at TIMESTAMP;

-- Add audit trail fields
ALTER TABLE QUALITY_ENTRY ADD COLUMN created_by VARCHAR(20);
ALTER TABLE QUALITY_ENTRY ADD COLUMN updated_by VARCHAR(20);

-- Note: notes, created_at, updated_at already exist

-- ============================================================================
-- STEP 2: Add CHECK Constraints for QUALITY_ENTRY
-- ============================================================================

CREATE TABLE QUALITY_ENTRY_NEW (
    quality_entry_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    inspection_date DATE NOT NULL,
    units_inspected INTEGER NOT NULL,
    units_passed INTEGER NOT NULL,
    units_failed INTEGER NOT NULL,
    total_defects_count INTEGER DEFAULT 0,
    shift_type VARCHAR(20) DEFAULT 'REGULAR' CHECK(shift_type IN ('REGULAR', 'OVERTIME', 'WEEKEND')),
    operation_checked VARCHAR(100),
    units_requiring_repair INTEGER DEFAULT 0,
    units_requiring_rework INTEGER DEFAULT 0,
    recorded_by_user_id VARCHAR(20),
    recorded_at TIMESTAMP,
    sample_size_percent DECIMAL(5, 2),
    inspection_level VARCHAR(20) CHECK(inspection_level IN ('I', 'II', 'III', 'SPECIAL') OR inspection_level IS NULL),
    approved_by VARCHAR(20),
    approved_at TIMESTAMP,
    entered_by VARCHAR(50),
    notes TEXT,
    created_by VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(20),
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id),
    FOREIGN KEY (recorded_by_user_id) REFERENCES USER(user_id),
    FOREIGN KEY (approved_by) REFERENCES USER(user_id)
);

-- Copy existing data
INSERT INTO QUALITY_ENTRY_NEW (
    quality_entry_id,
    client_id,
    work_order_id,
    inspection_date,
    units_inspected,
    units_passed,
    units_failed,
    total_defects_count,
    shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    created_by
)
SELECT
    quality_entry_id,
    client_id,
    work_order_id,
    inspection_date,
    units_inspected,
    units_passed,
    units_failed,
    total_defects_count,
    'REGULAR' as shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    entered_by as created_by
FROM QUALITY_ENTRY;

-- Drop old table and rename new one
DROP TABLE QUALITY_ENTRY;
ALTER TABLE QUALITY_ENTRY_NEW RENAME TO QUALITY_ENTRY;

-- ============================================================================
-- STEP 3: Create Indexes for QUALITY_ENTRY Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_quality_client_date
ON QUALITY_ENTRY(client_id, inspection_date);

CREATE INDEX IF NOT EXISTS idx_quality_work_order
ON QUALITY_ENTRY(work_order_id, inspection_date);

CREATE INDEX IF NOT EXISTS idx_quality_recorded_by
ON QUALITY_ENTRY(recorded_by_user_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_quality_approved_by
ON QUALITY_ENTRY(approved_by, approved_at);

CREATE INDEX IF NOT EXISTS idx_quality_shift_type
ON QUALITY_ENTRY(shift_type, inspection_date);

-- ============================================================================
-- STEP 4: Add Missing Fields to DEFECT_DETAIL (5 new fields)
-- ============================================================================

-- Add disposition flags
ALTER TABLE DEFECT_DETAIL ADD COLUMN is_rework_required BOOLEAN DEFAULT 0;
ALTER TABLE DEFECT_DETAIL ADD COLUMN is_repair_in_current_op BOOLEAN DEFAULT 0;
ALTER TABLE DEFECT_DETAIL ADD COLUMN is_scrapped BOOLEAN DEFAULT 0;

-- Add root cause analysis
ALTER TABLE DEFECT_DETAIL ADD COLUMN root_cause TEXT;

-- Add traceability
ALTER TABLE DEFECT_DETAIL ADD COLUMN unit_serial_or_id VARCHAR(100);

-- ============================================================================
-- STEP 5: Create Indexes for DEFECT_DETAIL Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_defect_quality_entry
ON DEFECT_DETAIL(quality_entry_id);

CREATE INDEX IF NOT EXISTS idx_defect_client
ON DEFECT_DETAIL(client_id);

CREATE INDEX IF NOT EXISTS idx_defect_type
ON DEFECT_DETAIL(defect_type);

CREATE INDEX IF NOT EXISTS idx_defect_disposition
ON DEFECT_DETAIL(is_rework_required, is_repair_in_current_op, is_scrapped);

CREATE INDEX IF NOT EXISTS idx_defect_unit_serial
ON DEFECT_DETAIL(unit_serial_or_id);

-- ============================================================================
-- STEP 6: Update QUALITY_ENTRY with Calculated Values
-- ============================================================================

-- Set shift_type based on inspection date (heuristic)
UPDATE QUALITY_ENTRY
SET shift_type = CASE
    WHEN strftime('%w', inspection_date) IN ('0', '6') THEN 'WEEKEND'
    ELSE 'REGULAR'
END
WHERE shift_type = 'REGULAR';

-- Set recorded_at to created_at for existing records
UPDATE QUALITY_ENTRY
SET recorded_at = created_at
WHERE recorded_at IS NULL;

-- Set recorded_by_user_id from entered_by
UPDATE QUALITY_ENTRY
SET recorded_by_user_id = entered_by
WHERE recorded_by_user_id IS NULL;

-- Set created_by from entered_by where missing
UPDATE QUALITY_ENTRY
SET created_by = entered_by
WHERE created_by IS NULL;

-- Calculate sample size percentage (assume 100% if not specified)
UPDATE QUALITY_ENTRY
SET sample_size_percent = 100.0
WHERE sample_size_percent IS NULL;

-- Set default inspection level to 'II' (AQL standard)
UPDATE QUALITY_ENTRY
SET inspection_level = 'II'
WHERE inspection_level IS NULL;

-- Calculate disposition counts based on units_failed
UPDATE QUALITY_ENTRY
SET units_requiring_rework = units_failed
WHERE units_requiring_rework = 0 AND units_failed > 0;

-- ============================================================================
-- STEP 7: Update DEFECT_DETAIL with Disposition Flags
-- ============================================================================

-- Set disposition flags based on severity (heuristic)
UPDATE DEFECT_DETAIL
SET is_scrapped = 1
WHERE severity = 'CRITICAL'
AND is_scrapped = 0;

UPDATE DEFECT_DETAIL
SET is_rework_required = 1
WHERE severity = 'MAJOR'
AND is_rework_required = 0
AND is_scrapped = 0;

UPDATE DEFECT_DETAIL
SET is_repair_in_current_op = 1
WHERE severity = 'MINOR'
AND is_repair_in_current_op = 0
AND is_scrapped = 0;

-- ============================================================================
-- STEP 8: Create Views for Quality Reporting
-- ============================================================================

-- PPM (Parts Per Million) summary view
CREATE VIEW IF NOT EXISTS v_ppm_summary AS
SELECT
    qe.client_id,
    qe.work_order_id,
    qe.inspection_date,
    qe.shift_type,
    SUM(qe.units_inspected) as total_inspected,
    SUM(qe.units_failed) as total_failed,
    SUM(qe.total_defects_count) as total_defects,
    CASE
        WHEN SUM(qe.units_inspected) > 0 THEN
            CAST(SUM(qe.units_failed) AS DECIMAL) / CAST(SUM(qe.units_inspected) AS DECIMAL) * 1000000.0
        ELSE 0
    END as ppm
FROM QUALITY_ENTRY qe
GROUP BY qe.client_id, qe.work_order_id, qe.inspection_date, qe.shift_type;

-- DPMO (Defects Per Million Opportunities) view
CREATE VIEW IF NOT EXISTS v_dpmo_summary AS
SELECT
    qe.client_id,
    qe.work_order_id,
    qe.inspection_date,
    SUM(qe.units_inspected) as total_inspected,
    SUM(qe.total_defects_count) as total_defects,
    po.opportunities_per_unit,
    CASE
        WHEN SUM(qe.units_inspected) > 0 AND po.opportunities_per_unit > 0 THEN
            CAST(SUM(qe.total_defects_count) AS DECIMAL) /
            (CAST(SUM(qe.units_inspected) AS DECIMAL) * CAST(po.opportunities_per_unit AS DECIMAL)) * 1000000.0
        ELSE 0
    END as dpmo,
    CASE
        WHEN SUM(qe.units_inspected) > 0 AND po.opportunities_per_unit > 0 THEN
            -- Approximate sigma level (simplified formula)
            0.8406 + SQRT(29.37 - 2.221 * LOG(
                CAST(SUM(qe.total_defects_count) AS DECIMAL) /
                (CAST(SUM(qe.units_inspected) AS DECIMAL) * CAST(po.opportunities_per_unit AS DECIMAL)) * 1000000.0
            ))
        ELSE 0
    END as sigma_level
FROM QUALITY_ENTRY qe
INNER JOIN WORK_ORDER wo ON qe.work_order_id = wo.work_order_id
LEFT JOIN PART_OPPORTUNITIES po ON wo.style_model = po.part_number
GROUP BY qe.client_id, qe.work_order_id, qe.inspection_date, po.opportunities_per_unit;

-- FPY (First Pass Yield) view
CREATE VIEW IF NOT EXISTS v_fpy_summary AS
SELECT
    qe.client_id,
    qe.work_order_id,
    qe.inspection_date,
    SUM(qe.units_inspected) as total_inspected,
    SUM(qe.units_passed) as total_passed,
    CASE
        WHEN SUM(qe.units_inspected) > 0 THEN
            CAST(SUM(qe.units_passed) AS DECIMAL) / CAST(SUM(qe.units_inspected) AS DECIMAL) * 100.0
        ELSE 0
    END as fpy_percentage
FROM QUALITY_ENTRY qe
GROUP BY qe.client_id, qe.work_order_id, qe.inspection_date;

-- Defect disposition summary
CREATE VIEW IF NOT EXISTS v_defect_disposition AS
SELECT
    dd.client_id,
    qe.work_order_id,
    qe.inspection_date,
    dd.defect_type,
    SUM(dd.defect_count) as total_defects,
    SUM(CASE WHEN dd.is_scrapped = 1 THEN dd.defect_count ELSE 0 END) as scrapped_count,
    SUM(CASE WHEN dd.is_rework_required = 1 THEN dd.defect_count ELSE 0 END) as rework_count,
    SUM(CASE WHEN dd.is_repair_in_current_op = 1 THEN dd.defect_count ELSE 0 END) as repair_count
FROM DEFECT_DETAIL dd
INNER JOIN QUALITY_ENTRY qe ON dd.quality_entry_id = qe.quality_entry_id
GROUP BY dd.client_id, qe.work_order_id, qe.inspection_date, dd.defect_type;

-- ============================================================================
-- STEP 9: Create Trigger for Automatic FPY Calculation
-- ============================================================================

-- Trigger to update units_passed when units_failed changes
CREATE TRIGGER IF NOT EXISTS trg_quality_entry_calculate_passed
AFTER UPDATE OF units_failed, units_inspected ON QUALITY_ENTRY
BEGIN
    UPDATE QUALITY_ENTRY
    SET units_passed = NEW.units_inspected - NEW.units_failed
    WHERE quality_entry_id = NEW.quality_entry_id;
END;

-- ============================================================================
-- STEP 10: Verify Migration Success
-- ============================================================================

SELECT 'QUALITY_ENTRY records:' as metric, COUNT(*) as count FROM QUALITY_ENTRY
UNION ALL
SELECT 'QUALITY_ENTRY with shift_type:' as metric, COUNT(*) as count
FROM QUALITY_ENTRY WHERE shift_type IS NOT NULL
UNION ALL
SELECT 'QUALITY_ENTRY with approval:' as metric, COUNT(*) as count
FROM QUALITY_ENTRY WHERE approved_by IS NOT NULL
UNION ALL
SELECT 'QUALITY_ENTRY with operation:' as metric, COUNT(*) as count
FROM QUALITY_ENTRY WHERE operation_checked IS NOT NULL
UNION ALL
SELECT 'DEFECT_DETAIL records:' as metric, COUNT(*) as count FROM DEFECT_DETAIL
UNION ALL
SELECT 'DEFECT_DETAIL with disposition:' as metric, COUNT(*) as count
FROM DEFECT_DETAIL WHERE is_scrapped = 1 OR is_rework_required = 1 OR is_repair_in_current_op = 1
UNION ALL
SELECT 'DEFECT_DETAIL with root cause:' as metric, COUNT(*) as count
FROM DEFECT_DETAIL WHERE root_cause IS NOT NULL;

COMMIT;

-- ============================================================================
-- POST-MIGRATION NOTES
-- ============================================================================
-- 1. Update Pydantic models: backend/models/quality.py (add 12 fields)
-- 2. Update Pydantic models: backend/models/defect_detail.py (add 5 fields)
-- 3. Update API routes to handle new fields
-- 4. Update frontend QualityEntryGrid.vue with new columns
-- 5. Update defect disposition workflow
-- 6. Test PPM, DPMO, FPY calculations with new schema
-- 7. Test quality approval workflow
-- 8. Create API endpoint for defect root cause analysis
-- ============================================================================

-- Rollback script (if needed):
-- DROP TABLE QUALITY_ENTRY;
-- DROP TABLE DEFECT_DETAIL;
-- Restore from backup

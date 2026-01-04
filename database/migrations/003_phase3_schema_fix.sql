-- ============================================================================
-- MIGRATION 003: Phase 3 Schema Fix (Attendance & Coverage)
-- ============================================================================
-- Date: January 2, 2026
-- Priority: HIGH
-- Impact: Adds 20 missing fields to ATTENDANCE_ENTRY and SHIFT_COVERAGE tables
-- Estimated Time: 8-12 minutes
-- ============================================================================

-- Enable foreign keys (critical for SQLite)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Add Missing Fields to ATTENDANCE_ENTRY (9 new fields)
-- ============================================================================

-- Add shift type classification
-- Note: SQLite doesn't support ENUM, use CHECK constraint instead
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN shift_type VARCHAR(20) DEFAULT 'REGULAR';

-- Add floating pool coverage tracking
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN covered_by_floating_employee_id VARCHAR(20);

-- Add coverage confirmation
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN coverage_confirmed BOOLEAN DEFAULT 0;

-- Add supervisor verification
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN verified_by_user_id VARCHAR(20);
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN verified_at TIMESTAMP;

-- Add detailed absence tracking (absence_reason may already exist, adding if not)
-- ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN absence_reason TEXT;

-- Add excused absence flag
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN is_excused_absence BOOLEAN DEFAULT 0;

-- Add audit trail fields
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN created_by VARCHAR(20);
ALTER TABLE ATTENDANCE_ENTRY ADD COLUMN updated_by VARCHAR(20);

-- Note: notes, created_at, updated_at already exist in init_sqlite_schema.py

-- ============================================================================
-- STEP 2: Add CHECK Constraints for ATTENDANCE_ENTRY
-- ============================================================================

-- Create new table with constraints, copy data, drop old, rename
-- This is the SQLite way to add CHECK constraints to existing tables

CREATE TABLE ATTENDANCE_ENTRY_NEW (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    is_absent INTEGER DEFAULT 0,
    is_late INTEGER DEFAULT 0,
    scheduled_hours DECIMAL(5, 2),
    actual_hours DECIMAL(5, 2),
    shift_type VARCHAR(20) DEFAULT 'REGULAR' CHECK(shift_type IN ('REGULAR', 'OVERTIME', 'WEEKEND')),
    covered_by_floating_employee_id VARCHAR(20),
    coverage_confirmed BOOLEAN DEFAULT 0,
    verified_by_user_id VARCHAR(20),
    verified_at TIMESTAMP,
    absence_reason TEXT,
    is_excused_absence BOOLEAN DEFAULT 0,
    entered_by VARCHAR(50),
    notes TEXT,
    created_by VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(20),
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (employee_id) REFERENCES EMPLOYEE(employee_id),
    FOREIGN KEY (covered_by_floating_employee_id) REFERENCES EMPLOYEE(employee_id),
    FOREIGN KEY (verified_by_user_id) REFERENCES USER(user_id)
);

-- Copy existing data
INSERT INTO ATTENDANCE_ENTRY_NEW (
    attendance_id,
    client_id,
    employee_id,
    shift_id,
    attendance_date,
    is_absent,
    is_late,
    scheduled_hours,
    actual_hours,
    shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    created_by
)
SELECT
    attendance_id,
    client_id,
    employee_id,
    shift_id,
    attendance_date,
    is_absent,
    is_late,
    scheduled_hours,
    actual_hours,
    'REGULAR' as shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    entered_by as created_by
FROM ATTENDANCE_ENTRY;

-- Drop old table and rename new one
DROP TABLE ATTENDANCE_ENTRY;
ALTER TABLE ATTENDANCE_ENTRY_NEW RENAME TO ATTENDANCE_ENTRY;

-- ============================================================================
-- STEP 3: Create Indexes for ATTENDANCE_ENTRY Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_attendance_client_date
ON ATTENDANCE_ENTRY(client_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_employee_date
ON ATTENDANCE_ENTRY(employee_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_shift_date
ON ATTENDANCE_ENTRY(shift_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_absence_status
ON ATTENDANCE_ENTRY(is_absent, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_floating_coverage
ON ATTENDANCE_ENTRY(covered_by_floating_employee_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_verification
ON ATTENDANCE_ENTRY(verified_by_user_id, verified_at);

-- ============================================================================
-- STEP 4: Add Missing Fields to SHIFT_COVERAGE (5 new fields)
-- ============================================================================

-- Rename table to COVERAGE_ENTRY for consistency (optional, commented out)
-- ALTER TABLE SHIFT_COVERAGE RENAME TO COVERAGE_ENTRY;

-- Add shift type classification
ALTER TABLE SHIFT_COVERAGE ADD COLUMN shift_type VARCHAR(20) DEFAULT 'REGULAR';

-- Add coverage duration tracking
ALTER TABLE SHIFT_COVERAGE ADD COLUMN coverage_duration_hours DECIMAL(5, 2);

-- Add recorder tracking
ALTER TABLE SHIFT_COVERAGE ADD COLUMN recorded_by_user_id VARCHAR(20);

-- Add verification status
ALTER TABLE SHIFT_COVERAGE ADD COLUMN verified BOOLEAN DEFAULT 0;

-- Add audit trail fields
ALTER TABLE SHIFT_COVERAGE ADD COLUMN created_by VARCHAR(20);
ALTER TABLE SHIFT_COVERAGE ADD COLUMN updated_by VARCHAR(20);

-- Note: notes, created_at, updated_at already exist

-- ============================================================================
-- STEP 5: Add CHECK Constraints for SHIFT_COVERAGE
-- ============================================================================

CREATE TABLE SHIFT_COVERAGE_NEW (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    coverage_date DATE NOT NULL,
    employees_scheduled INTEGER,
    employees_present INTEGER,
    coverage_percentage DECIMAL(5, 2),
    shift_type VARCHAR(20) DEFAULT 'REGULAR' CHECK(shift_type IN ('REGULAR', 'OVERTIME', 'WEEKEND')),
    coverage_duration_hours DECIMAL(5, 2),
    recorded_by_user_id VARCHAR(20),
    verified BOOLEAN DEFAULT 0,
    entered_by VARCHAR(50),
    notes TEXT,
    created_by VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(20),
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (shift_id) REFERENCES SHIFT(shift_id),
    FOREIGN KEY (recorded_by_user_id) REFERENCES USER(user_id)
);

-- Copy existing data
INSERT INTO SHIFT_COVERAGE_NEW (
    coverage_id,
    client_id,
    shift_id,
    coverage_date,
    employees_scheduled,
    employees_present,
    coverage_percentage,
    shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    created_by
)
SELECT
    coverage_id,
    client_id,
    shift_id,
    coverage_date,
    employees_scheduled,
    employees_present,
    coverage_percentage,
    'REGULAR' as shift_type,
    entered_by,
    notes,
    created_at,
    updated_at,
    entered_by as created_by
FROM SHIFT_COVERAGE;

-- Drop old table and rename new one
DROP TABLE SHIFT_COVERAGE;
ALTER TABLE SHIFT_COVERAGE_NEW RENAME TO SHIFT_COVERAGE;

-- ============================================================================
-- STEP 6: Create Indexes for SHIFT_COVERAGE Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_coverage_client_date
ON SHIFT_COVERAGE(client_id, coverage_date);

CREATE INDEX IF NOT EXISTS idx_coverage_shift_date
ON SHIFT_COVERAGE(shift_id, coverage_date);

CREATE INDEX IF NOT EXISTS idx_coverage_verification
ON SHIFT_COVERAGE(verified, coverage_date);

CREATE INDEX IF NOT EXISTS idx_coverage_recorder
ON SHIFT_COVERAGE(recorded_by_user_id, coverage_date);

-- ============================================================================
-- STEP 7: Update ATTENDANCE_ENTRY with Calculated Values
-- ============================================================================

-- Set shift_type based on scheduled hours (heuristic)
UPDATE ATTENDANCE_ENTRY
SET shift_type = CASE
    WHEN scheduled_hours > 8 THEN 'OVERTIME'
    WHEN strftime('%w', attendance_date) IN ('0', '6') THEN 'WEEKEND'
    ELSE 'REGULAR'
END
WHERE shift_type = 'REGULAR';

-- Set created_by from entered_by where missing
UPDATE ATTENDANCE_ENTRY
SET created_by = entered_by
WHERE created_by IS NULL;

-- Mark absences as unexcused by default (supervisor can update)
UPDATE ATTENDANCE_ENTRY
SET is_excused_absence = 0
WHERE is_absent = 1 AND is_excused_absence IS NULL;

-- ============================================================================
-- STEP 8: Update SHIFT_COVERAGE with Calculated Values
-- ============================================================================

-- Calculate coverage duration based on shift type
UPDATE SHIFT_COVERAGE
SET coverage_duration_hours = CASE
    WHEN shift_type = 'OVERTIME' THEN 12.0
    WHEN shift_type = 'WEEKEND' THEN 10.0
    ELSE 8.0
END
WHERE coverage_duration_hours IS NULL;

-- Set created_by from entered_by where missing
UPDATE SHIFT_COVERAGE
SET created_by = entered_by
WHERE created_by IS NULL;

-- Calculate coverage percentage if missing
UPDATE SHIFT_COVERAGE
SET coverage_percentage = CASE
    WHEN employees_scheduled > 0 THEN
        CAST(employees_present AS DECIMAL) / CAST(employees_scheduled AS DECIMAL) * 100.0
    ELSE 0
END
WHERE coverage_percentage IS NULL
AND employees_scheduled IS NOT NULL
AND employees_present IS NOT NULL;

-- ============================================================================
-- STEP 9: Create Views for Attendance Reporting
-- ============================================================================

-- Absenteeism summary view
CREATE VIEW IF NOT EXISTS v_absenteeism_summary AS
SELECT
    ae.client_id,
    ae.shift_id,
    ae.attendance_date,
    s.shift_name,
    COUNT(*) as total_employees,
    SUM(ae.is_absent) as absent_count,
    SUM(ae.is_late) as late_count,
    SUM(CASE WHEN ae.is_absent = 1 AND ae.is_excused_absence = 0 THEN 1 ELSE 0 END) as unexcused_absences,
    SUM(ae.scheduled_hours) as total_scheduled_hours,
    SUM(ae.actual_hours) as total_actual_hours,
    CASE
        WHEN SUM(ae.scheduled_hours) > 0 THEN
            (1 - SUM(ae.actual_hours) / SUM(ae.scheduled_hours)) * 100.0
        ELSE 0
    END as absenteeism_rate
FROM ATTENDANCE_ENTRY ae
INNER JOIN SHIFT s ON ae.shift_id = s.shift_id
GROUP BY ae.client_id, ae.shift_id, ae.attendance_date, s.shift_name;

-- Floating pool coverage view
CREATE VIEW IF NOT EXISTS v_floating_pool_coverage AS
SELECT
    ae.attendance_date,
    ae.shift_id,
    ae.employee_id as absent_employee,
    e1.employee_name as absent_employee_name,
    ae.covered_by_floating_employee_id,
    e2.employee_name as covering_employee_name,
    ae.coverage_confirmed,
    ae.verified_by_user_id,
    ae.verified_at,
    ae.shift_type
FROM ATTENDANCE_ENTRY ae
INNER JOIN EMPLOYEE e1 ON ae.employee_id = e1.employee_id
LEFT JOIN EMPLOYEE e2 ON ae.covered_by_floating_employee_id = e2.employee_id
WHERE ae.is_absent = 1
AND ae.covered_by_floating_employee_id IS NOT NULL;

-- ============================================================================
-- STEP 10: Verify Migration Success
-- ============================================================================

SELECT 'ATTENDANCE_ENTRY records:' as metric, COUNT(*) as count FROM ATTENDANCE_ENTRY
UNION ALL
SELECT 'ATTENDANCE_ENTRY with shift_type:' as metric, COUNT(*) as count
FROM ATTENDANCE_ENTRY WHERE shift_type IS NOT NULL
UNION ALL
SELECT 'ATTENDANCE_ENTRY with floating coverage:' as metric, COUNT(*) as count
FROM ATTENDANCE_ENTRY WHERE covered_by_floating_employee_id IS NOT NULL
UNION ALL
SELECT 'SHIFT_COVERAGE records:' as metric, COUNT(*) as count FROM SHIFT_COVERAGE
UNION ALL
SELECT 'SHIFT_COVERAGE with duration:' as metric, COUNT(*) as count
FROM SHIFT_COVERAGE WHERE coverage_duration_hours IS NOT NULL;

COMMIT;

-- ============================================================================
-- POST-MIGRATION NOTES
-- ============================================================================
-- 1. Update Pydantic models: backend/models/attendance.py (add 9 fields)
-- 2. Update Pydantic models: backend/models/coverage.py (add 5 fields)
-- 3. Update API routes to handle new fields
-- 4. Update frontend AttendanceEntryGrid.vue with new columns
-- 5. Update floating pool assignment logic
-- 6. Test Bradford Factor calculation with new schema
-- 7. Test supervisor verification workflow
-- ============================================================================

-- Rollback script (if needed):
-- DROP TABLE ATTENDANCE_ENTRY;
-- DROP TABLE SHIFT_COVERAGE;
-- Restore from backup

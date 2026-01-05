-- =====================================================================
-- SQLITE MIGRATION: Add Indexes for client_id columns
-- =====================================================================
-- Description: Adds indexes for existing client_id columns
-- Date: 2026-01-04
-- =====================================================================

-- SHIFT_COVERAGE indexes
CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_id
  ON SHIFT_COVERAGE(client_id);

CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_date
  ON SHIFT_COVERAGE(client_id, shift_date);

CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_shift
  ON SHIFT_COVERAGE(client_id, shift_type);

-- ATTENDANCE_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_id
  ON ATTENDANCE_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_date
  ON ATTENDANCE_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_employee
  ON ATTENDANCE_ENTRY(client_id, employee_id);

-- DOWNTIME_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_id
  ON DOWNTIME_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_date
  ON DOWNTIME_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_job
  ON DOWNTIME_ENTRY(client_id, job_id);

-- HOLD_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_hold_entry_client_id
  ON HOLD_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_date
  ON HOLD_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_status
  ON HOLD_ENTRY(client_id, status);

-- QUALITY_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_quality_entry_client_id
  ON QUALITY_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_date
  ON QUALITY_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_result
  ON QUALITY_ENTRY(client_id, result);

-- PRODUCTION_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_production_entry_client_id
  ON PRODUCTION_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_date
  ON PRODUCTION_ENTRY(client_id, date);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_job
  ON PRODUCTION_ENTRY(client_id, job_id);

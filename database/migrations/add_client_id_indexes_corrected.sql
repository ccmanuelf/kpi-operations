-- =====================================================================
-- SQLITE MIGRATION: Add Indexes for client_id columns (CORRECTED)
-- =====================================================================
-- Description: Adds performance indexes for existing client_id columns
--              Using actual column names from database schema
-- Date: 2026-01-04
-- =====================================================================

-- SHIFT_COVERAGE indexes
CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_id
  ON SHIFT_COVERAGE(client_id);

CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_date
  ON SHIFT_COVERAGE(client_id, coverage_date DESC);

CREATE INDEX IF NOT EXISTS idx_shift_coverage_client_shift
  ON SHIFT_COVERAGE(client_id, shift_id);

-- ATTENDANCE_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_id
  ON ATTENDANCE_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_date
  ON ATTENDANCE_ENTRY(client_id, attendance_date DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_employee
  ON ATTENDANCE_ENTRY(client_id, employee_id);

CREATE INDEX IF NOT EXISTS idx_attendance_entry_client_shift
  ON ATTENDANCE_ENTRY(client_id, shift_id);

-- DOWNTIME_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_id
  ON DOWNTIME_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_date
  ON DOWNTIME_ENTRY(client_id, downtime_date DESC);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_wo
  ON DOWNTIME_ENTRY(client_id, work_order_id);

CREATE INDEX IF NOT EXISTS idx_downtime_entry_client_shift
  ON DOWNTIME_ENTRY(client_id, shift_id);

-- HOLD_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_hold_entry_client_id
  ON HOLD_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_date
  ON HOLD_ENTRY(client_id, placed_on_hold_date DESC);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_wo
  ON HOLD_ENTRY(client_id, work_order_id);

CREATE INDEX IF NOT EXISTS idx_hold_entry_client_released
  ON HOLD_ENTRY(client_id, released_date);

-- QUALITY_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_quality_entry_client_id
  ON QUALITY_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_date
  ON QUALITY_ENTRY(client_id, inspection_date DESC);

CREATE INDEX IF NOT EXISTS idx_quality_entry_client_wo
  ON QUALITY_ENTRY(client_id, work_order_id);

-- PRODUCTION_ENTRY indexes
CREATE INDEX IF NOT EXISTS idx_production_entry_client_id
  ON PRODUCTION_ENTRY(client_id);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_date
  ON PRODUCTION_ENTRY(client_id, production_date DESC);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_shift
  ON PRODUCTION_ENTRY(client_id, shift_id);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_wo
  ON PRODUCTION_ENTRY(client_id, work_order_id);

CREATE INDEX IF NOT EXISTS idx_production_entry_client_product
  ON PRODUCTION_ENTRY(client_id, product_id);

-- SQLite-compatible schema for Manufacturing KPI Platform
-- Phase 1: Core tables (already created)
-- Phase 2-4: Extension tables for all 10 KPIs

-- Note: SQLite differences from MariaDB:
-- 1. No AUTO_INCREMENT (use AUTOINCREMENT)
-- 2. No UNSIGNED (just use INTEGER)
-- 3. No ENUM (use CHECK constraints or TEXT)
-- 4. No COMMENT (use -- comments instead)

-- ============================================================
-- PHASE 2: WIP AGING, OTD, AVAILABILITY
-- ============================================================

-- Work Order table (core for Phase 2-4)
CREATE TABLE IF NOT EXISTS work_order (
    work_order_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    style_model TEXT NOT NULL,
    planned_quantity INTEGER NOT NULL,
    actual_quantity INTEGER DEFAULT 0,
    actual_start_date TEXT,  -- ISO 8601: YYYY-MM-DD
    planned_ship_date TEXT,  -- For OTD calculation
    actual_delivery_date TEXT,  -- For OTD calculation
    ideal_cycle_time REAL,  -- Decimal hours (0.25 = 15 min)
    status TEXT CHECK(status IN ('ACTIVE','ON_HOLD','COMPLETED','REJECTED','CANCELLED')) DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_work_order_client ON work_order(client_id);
CREATE INDEX IF NOT EXISTS idx_work_order_status ON work_order(status);
CREATE INDEX IF NOT EXISTS idx_work_order_dates ON work_order(actual_start_date, planned_ship_date);

-- Job table (line items within work orders)
CREATE TABLE IF NOT EXISTS job (
    job_id TEXT PRIMARY KEY,
    work_order_id TEXT NOT NULL,
    operation_name TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (work_order_id) REFERENCES work_order(work_order_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_work_order ON job(work_order_id);

-- Downtime Entry table (for Availability KPI #8)
CREATE TABLE IF NOT EXISTS downtime_entry (
    downtime_entry_id TEXT PRIMARY KEY,
    work_order_id TEXT NOT NULL,
    shift_date TEXT NOT NULL,
    downtime_reason TEXT CHECK(downtime_reason IN ('EQUIPMENT_FAILURE','MATERIAL_SHORTAGE','SETUP_CHANGEOVER','QUALITY_HOLD','MAINTENANCE','OTHER')),
    downtime_duration_minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (work_order_id) REFERENCES work_order(work_order_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_downtime_work_order ON downtime_entry(work_order_id);
CREATE INDEX IF NOT EXISTS idx_downtime_date ON downtime_entry(shift_date);

-- Hold Entry table (for WIP Aging KPI #1)
CREATE TABLE IF NOT EXISTS hold_entry (
    hold_entry_id TEXT PRIMARY KEY,
    work_order_id TEXT NOT NULL,
    hold_status TEXT CHECK(hold_status IN ('ON_HOLD','RESUMED','CANCELLED')) DEFAULT 'ON_HOLD',
    hold_date TEXT,
    resume_date TEXT,
    total_hold_duration_hours REAL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (work_order_id) REFERENCES work_order(work_order_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hold_work_order ON hold_entry(work_order_id);
CREATE INDEX IF NOT EXISTS idx_hold_status ON hold_entry(hold_status);

-- ============================================================
-- PHASE 3: ATTENDANCE & ABSENTEEISM
-- ============================================================

-- Employee table
CREATE TABLE IF NOT EXISTS employee (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    employee_name TEXT NOT NULL,
    is_floating_pool INTEGER DEFAULT 0,  -- Boolean: 0=regular, 1=floating pool
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_employee_floating ON employee(is_floating_pool);

-- Attendance Entry table (for Absenteeism KPI #10)
CREATE TABLE IF NOT EXISTS attendance_entry (
    attendance_entry_id TEXT PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    shift_date TEXT NOT NULL,
    scheduled_hours REAL NOT NULL,
    actual_hours REAL DEFAULT 0,
    is_absent INTEGER NOT NULL DEFAULT 0,  -- Boolean
    absence_type TEXT CHECK(absence_type IN ('UNSCHEDULED_ABSENCE','VACATION','MEDICAL_LEAVE','PERSONAL_LEAVE') OR absence_type IS NULL),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employee(employee_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance_entry(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_entry(shift_date);
CREATE INDEX IF NOT EXISTS idx_attendance_absent ON attendance_entry(is_absent);

-- Coverage Entry table (floating pool assignments)
CREATE TABLE IF NOT EXISTS coverage_entry (
    coverage_entry_id TEXT PRIMARY KEY,
    floating_employee_id INTEGER NOT NULL,
    covered_employee_id INTEGER NOT NULL,
    shift_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (floating_employee_id) REFERENCES employee(employee_id),
    FOREIGN KEY (covered_employee_id) REFERENCES employee(employee_id)
);

CREATE INDEX IF NOT EXISTS idx_coverage_floating ON coverage_entry(floating_employee_id);
CREATE INDEX IF NOT EXISTS idx_coverage_covered ON coverage_entry(covered_employee_id);

-- ============================================================
-- PHASE 4: QUALITY METRICS
-- ============================================================

-- Quality Entry table (for PPM, DPMO, FPY, RTY KPIs #4-7)
CREATE TABLE IF NOT EXISTS quality_entry (
    quality_entry_id TEXT PRIMARY KEY,
    work_order_id TEXT NOT NULL,
    shift_date TEXT NOT NULL,
    units_inspected INTEGER NOT NULL,
    units_passed INTEGER NOT NULL,
    units_defective INTEGER NOT NULL,
    total_defects_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (work_order_id) REFERENCES work_order(work_order_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_work_order ON quality_entry(work_order_id);
CREATE INDEX IF NOT EXISTS idx_quality_date ON quality_entry(shift_date);

-- Defect Detail table (drill-down for quality issues)
CREATE TABLE IF NOT EXISTS defect_detail (
    defect_detail_id TEXT PRIMARY KEY,
    quality_entry_id TEXT NOT NULL,
    defect_category TEXT,
    defect_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (quality_entry_id) REFERENCES quality_entry(quality_entry_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_defect_quality_entry ON defect_detail(quality_entry_id);

-- Part Opportunities table (for DPMO calculation)
CREATE TABLE IF NOT EXISTS part_opportunities (
    part_number TEXT PRIMARY KEY,
    opportunities_per_unit INTEGER NOT NULL
);

-- ============================================================
-- VIEWS FOR KPI CALCULATIONS
-- ============================================================

-- View: WIP Aging (KPI #1)
CREATE VIEW IF NOT EXISTS v_wip_aging AS
SELECT
    wo.work_order_id,
    wo.client_id,
    wo.style_model,
    wo.actual_start_date,
    COALESCE(h.total_hold_duration_hours, 0) AS total_hold_hours,
    CAST(
        (julianday('now') - julianday(wo.actual_start_date)) -
        (COALESCE(h.total_hold_duration_hours, 0) / 24.0)
    AS INTEGER) AS net_aging_days
FROM work_order wo
LEFT JOIN (
    SELECT
        work_order_id,
        SUM(total_hold_duration_hours) AS total_hold_duration_hours
    FROM hold_entry
    WHERE hold_status IN ('ON_HOLD', 'RESUMED')
    GROUP BY work_order_id
) h ON wo.work_order_id = h.work_order_id
WHERE wo.status IN ('ACTIVE', 'ON_HOLD')
AND wo.actual_start_date IS NOT NULL;

-- View: On-Time Delivery (KPI #2)
CREATE VIEW IF NOT EXISTS v_on_time_delivery AS
SELECT
    client_id,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN actual_delivery_date <= planned_ship_date THEN 1 ELSE 0 END) AS on_time_orders,
    CAST(SUM(CASE WHEN actual_delivery_date <= planned_ship_date THEN 1 ELSE 0 END) AS REAL) /
        COUNT(*) * 100 AS otd_percentage
FROM work_order
WHERE status = 'COMPLETED'
AND planned_ship_date IS NOT NULL
AND actual_delivery_date IS NOT NULL
GROUP BY client_id;

-- View: Availability Summary (KPI #8)
CREATE VIEW IF NOT EXISTS v_availability_summary AS
SELECT
    d.shift_date,
    d.work_order_id,
    SUM(d.downtime_duration_minutes) AS total_downtime_minutes,
    (480 - SUM(d.downtime_duration_minutes)) / 480.0 * 100 AS availability_percentage
FROM downtime_entry d
GROUP BY d.shift_date, d.work_order_id;

-- View: Absenteeism Summary (KPI #10)
CREATE VIEW IF NOT EXISTS v_absenteeism_summary AS
SELECT
    shift_date,
    SUM(scheduled_hours) AS total_scheduled_hours,
    SUM(CASE WHEN is_absent = 1 THEN scheduled_hours ELSE 0 END) AS total_absent_hours,
    CAST(SUM(CASE WHEN is_absent = 1 THEN scheduled_hours ELSE 0 END) AS REAL) /
        SUM(scheduled_hours) * 100 AS absenteeism_rate
FROM attendance_entry
GROUP BY shift_date;

-- View: Quality Summary (for PPM, FPY calculations)
CREATE VIEW IF NOT EXISTS v_quality_summary AS
SELECT
    q.shift_date,
    q.work_order_id,
    wo.client_id,
    wo.style_model,
    q.units_inspected,
    q.units_passed,
    q.units_defective,
    q.total_defects_count,
    CAST(q.units_passed AS REAL) / q.units_inspected * 100 AS fpy_percentage,
    CAST(q.units_defective AS REAL) / q.units_inspected * 1000000 AS ppm
FROM quality_entry q
JOIN work_order wo ON q.work_order_id = wo.work_order_id;

-- ============================================================
-- INITIALIZATION COMPLETE
-- ============================================================

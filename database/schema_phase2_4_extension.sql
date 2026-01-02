-- Manufacturing KPI Platform - Phase 2-4 Schema Extensions
-- Based on CSV Data Inventories
-- Phase 2: Downtime & WIP Tracking
-- Phase 3: Attendance Tracking
-- Phase 4: Quality Metrics

-- ============================================================================
-- PHASE 2: WORK ORDER & JOB TRACKING (For WIP Aging & OTD)
-- ============================================================================

-- From 01-Core_DataEntities_Inventory.csv
CREATE TABLE IF NOT EXISTS `work_order` (
  `work_order_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `style_model` VARCHAR(100) NOT NULL,
  `planned_quantity` INT UNSIGNED NOT NULL CHECK (planned_quantity > 0),
  `planned_start_date` DATE DEFAULT NULL,
  `actual_start_date` DATE DEFAULT NULL,
  `planned_ship_date` DATE DEFAULT NULL COMMENT 'For OTD calculation',
  `required_date` DATE DEFAULT NULL COMMENT 'Fallback for OTD',
  `actual_delivery_date` DATE DEFAULT NULL,
  `ideal_cycle_time` DECIMAL(10,4) DEFAULT NULL COMMENT 'Hours per unit',
  `status` ENUM('ACTIVE','ON_HOLD','COMPLETED','REJECTED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
  `receipt_date` DATE DEFAULT NULL,
  `acknowledged_date` DATE DEFAULT NULL,
  `priority_level` ENUM('RUSH','STANDARD','LOW') DEFAULT 'STANDARD',
  `po_number` VARCHAR(50) DEFAULT NULL,
  `notes` TEXT,
  `created_by` INT UNSIGNED DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX `idx_client_id` (`client_id`),
  INDEX `idx_status` (`status`),
  INDEX `idx_actual_start_date` (`actual_start_date`),
  INDEX `idx_planned_ship_date` (`planned_ship_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `job` (
  `job_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `work_order_id` VARCHAR(50) NOT NULL,
  `job_number` VARCHAR(50) DEFAULT NULL,
  `part_number` VARCHAR(50) NOT NULL,
  `quantity_ordered` INT UNSIGNED NOT NULL CHECK (quantity_ordered > 0),
  `quantity_completed` INT UNSIGNED DEFAULT 0,
  `quantity_scrapped` INT UNSIGNED DEFAULT 0,
  `priority_level` ENUM('RUSH','STANDARD','LOW') DEFAULT 'STANDARD',
  `notes` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`work_order_id`) REFERENCES `work_order`(`work_order_id`) ON DELETE CASCADE,
  INDEX `idx_work_order_id` (`work_order_id`),
  INDEX `idx_part_number` (`part_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PHASE 2: DOWNTIME TRACKING (For Availability KPI #8)
-- ============================================================================

-- From 03-Phase2_Downtime_WIP_Inventory.csv
CREATE TABLE IF NOT EXISTS `downtime_entry` (
  `downtime_entry_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `work_order_id` VARCHAR(50) NOT NULL,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `shift_date` DATE NOT NULL,
  `shift_type` ENUM('SHIFT_1ST','SHIFT_2ND','SAT_OT','SUN_OT','OTHER') NOT NULL,
  `downtime_reason` ENUM(
    'EQUIPMENT_FAILURE',
    'MATERIAL_SHORTAGE',
    'CHANGEOVER_SETUP',
    'LACK_OF_ORDERS',
    'MAINTENANCE_SCHEDULED',
    'QC_HOLD',
    'MISSING_SPECIFICATION',
    'OTHER'
  ) NOT NULL,
  `downtime_reason_detail` TEXT,
  `downtime_duration_minutes` INT UNSIGNED NOT NULL CHECK (downtime_duration_minutes > 0),
  `downtime_start_time` TIME DEFAULT NULL,
  `responsible_person_id` INT UNSIGNED DEFAULT NULL,
  `reported_by_user_id` INT UNSIGNED NOT NULL,
  `reported_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_resolved` TINYINT(1) NOT NULL DEFAULT 1,
  `resolution_notes` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`work_order_id`) REFERENCES `work_order`(`work_order_id`) ON DELETE CASCADE,
  FOREIGN KEY (`reported_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_shift_date` (`shift_date`),
  INDEX `idx_downtime_reason` (`downtime_reason`),
  INDEX `idx_client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PHASE 2: HOLD/RESUME TRACKING (For WIP Aging KPI #1)
-- ============================================================================

-- From 03-Phase2_Downtime_WIP_Inventory.csv
CREATE TABLE IF NOT EXISTS `hold_entry` (
  `hold_entry_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `work_order_id` VARCHAR(50) NOT NULL,
  `job_id` VARCHAR(50) DEFAULT NULL,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `hold_status` ENUM('ON_HOLD','RESUMED','CANCELLED') NOT NULL,
  `hold_date` DATE DEFAULT NULL,
  `hold_time` TIME DEFAULT NULL,
  `hold_reason` ENUM(
    'MATERIAL_INSPECTION',
    'QUALITY_ISSUE',
    'ENGINEERING_REVIEW',
    'CUSTOMER_REQUEST',
    'MISSING_SPECIFICATION',
    'EQUIPMENT_UNAVAILABLE',
    'CAPACITY_CONSTRAINT',
    'OTHER'
  ) NOT NULL,
  `hold_reason_detail` TEXT NOT NULL,
  `hold_approved_by_user_id` INT UNSIGNED NOT NULL,
  `hold_approved_at` TIMESTAMP NOT NULL,
  `resume_date` DATE DEFAULT NULL,
  `resume_time` TIME DEFAULT NULL,
  `resume_approved_by_user_id` INT UNSIGNED DEFAULT NULL,
  `resume_approved_at` TIMESTAMP NULL DEFAULT NULL,
  `total_hold_duration_hours` DECIMAL(10,2) DEFAULT NULL,
  `hold_notes` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`work_order_id`) REFERENCES `work_order`(`work_order_id`) ON DELETE CASCADE,
  FOREIGN KEY (`job_id`) REFERENCES `job`(`job_id`) ON DELETE CASCADE,
  FOREIGN KEY (`hold_approved_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_hold_status` (`hold_status`),
  INDEX `idx_hold_date` (`hold_date`),
  INDEX `idx_client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PHASE 3: ATTENDANCE TRACKING (For Absenteeism KPI #10)
-- ============================================================================

-- Employee table (minimal - expand later if needed)
CREATE TABLE IF NOT EXISTS `employee` (
  `employee_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `employee_code` VARCHAR(20) NOT NULL UNIQUE,
  `employee_name` VARCHAR(100) NOT NULL,
  `department` VARCHAR(50) DEFAULT NULL,
  `is_floating_pool` TINYINT(1) NOT NULL DEFAULT 0,
  `client_id_assigned` VARCHAR(20) DEFAULT NULL,
  `hourly_rate` DECIMAL(10,2) DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX `idx_employee_code` (`employee_code`),
  INDEX `idx_department` (`department`),
  INDEX `idx_is_floating_pool` (`is_floating_pool`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- From 04-Phase3_Attendance_Inventory.csv
CREATE TABLE IF NOT EXISTS `attendance_entry` (
  `attendance_entry_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `employee_id` INT UNSIGNED NOT NULL,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `shift_date` DATE NOT NULL,
  `shift_type` ENUM('SHIFT_1ST','SHIFT_2ND','SAT_OT','SUN_OT','OTHER') NOT NULL,
  `scheduled_hours` DECIMAL(10,2) NOT NULL,
  `actual_hours` DECIMAL(10,2) DEFAULT NULL,
  `is_absent` TINYINT(1) NOT NULL,
  `absence_type` ENUM(
    'UNSCHEDULED_ABSENCE',
    'VACATION',
    'MEDICAL_LEAVE',
    'PERSONAL_DAY',
    'SUSPENDED',
    'OTHER'
  ) DEFAULT NULL,
  `absence_hours` DECIMAL(10,2) DEFAULT NULL,
  `covered_by_floating_employee_id` INT UNSIGNED DEFAULT NULL,
  `coverage_confirmed` TINYINT(1) NOT NULL DEFAULT 0,
  `recorded_by_user_id` INT UNSIGNED NOT NULL,
  `recorded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `verified_by_user_id` INT UNSIGNED DEFAULT NULL,
  `verified_at` TIMESTAMP NULL DEFAULT NULL,
  `notes` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`employee_id`) REFERENCES `employee`(`employee_id`) ON DELETE CASCADE,
  FOREIGN KEY (`recorded_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_shift_date` (`shift_date`),
  INDEX `idx_employee_id` (`employee_id`),
  INDEX `idx_client_id` (`client_id`),
  INDEX `idx_is_absent` (`is_absent`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Floating pool coverage tracking
CREATE TABLE IF NOT EXISTS `coverage_entry` (
  `coverage_entry_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `absent_employee_id` INT UNSIGNED NOT NULL,
  `floating_employee_id` INT UNSIGNED NOT NULL,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `shift_date` DATE NOT NULL,
  `shift_type` ENUM('SHIFT_1ST','SHIFT_2ND','SAT_OT','SUN_OT','OTHER') NOT NULL,
  `coverage_duration_hours` DECIMAL(10,2) NOT NULL,
  `recorded_by_user_id` INT UNSIGNED NOT NULL,
  `recorded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `verified` TINYINT(1) NOT NULL DEFAULT 0,
  `notes` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`absent_employee_id`) REFERENCES `employee`(`employee_id`) ON DELETE CASCADE,
  FOREIGN KEY (`floating_employee_id`) REFERENCES `employee`(`employee_id`) ON DELETE CASCADE,
  FOREIGN KEY (`recorded_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_shift_date` (`shift_date`),
  INDEX `idx_floating_employee_id` (`floating_employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PHASE 4: QUALITY INSPECTION TRACKING (For PPM, DPMO, FPY, RTY)
-- ============================================================================

-- From 05-Phase4_Quality_Inventory.csv
CREATE TABLE IF NOT EXISTS `quality_entry` (
  `quality_entry_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `work_order_id` VARCHAR(50) NOT NULL,
  `job_id` VARCHAR(50) DEFAULT NULL,
  `client_id` VARCHAR(20) NOT NULL DEFAULT 'CLIENT-DEFAULT',
  `shift_date` DATE NOT NULL,
  `shift_type` ENUM('SHIFT_1ST','SHIFT_2ND','SAT_OT','SUN_OT','OTHER') NOT NULL,
  `operation_checked` VARCHAR(50) NOT NULL,
  `units_inspected` INT UNSIGNED NOT NULL CHECK (units_inspected > 0),
  `units_passed` INT UNSIGNED NOT NULL,
  `units_defective` INT UNSIGNED NOT NULL,
  `units_requiring_rework` INT UNSIGNED DEFAULT NULL,
  `units_requiring_repair` INT UNSIGNED DEFAULT NULL,
  `total_defects_count` INT UNSIGNED NOT NULL COMMENT 'For DPMO calculation',
  `qc_inspector_id` INT UNSIGNED NOT NULL,
  `recorded_by_user_id` INT UNSIGNED NOT NULL,
  `recorded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `inspection_method` ENUM(
    'VISUAL',
    'MEASUREMENT',
    'FUNCTIONAL_TEST',
    'SAMPLE_CHECK',
    '100_PERCENT_INSPECTION',
    'OTHER'
  ) DEFAULT NULL,
  `sample_size_percent` DECIMAL(5,2) DEFAULT NULL,
  `notes` TEXT,
  `verified_by_user_id` INT UNSIGNED DEFAULT NULL,
  `verified_at` TIMESTAMP NULL DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`work_order_id`) REFERENCES `work_order`(`work_order_id`) ON DELETE CASCADE,
  FOREIGN KEY (`job_id`) REFERENCES `job`(`job_id`) ON DELETE CASCADE,
  FOREIGN KEY (`qc_inspector_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  FOREIGN KEY (`recorded_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_shift_date` (`shift_date`),
  INDEX `idx_operation_checked` (`operation_checked`),
  INDEX `idx_client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Defect detail tracking
CREATE TABLE IF NOT EXISTS `defect_detail` (
  `defect_detail_id` VARCHAR(50) NOT NULL PRIMARY KEY,
  `quality_entry_id` VARCHAR(50) NOT NULL,
  `defect_type` ENUM(
    'STITCHING',
    'COLOR_MISMATCH',
    'SIZING',
    'MATERIAL_DEFECT',
    'ASSEMBLY',
    'FINISHING',
    'PACKAGING',
    'OTHER'
  ) NOT NULL,
  `defect_description` TEXT NOT NULL,
  `unit_serial_or_id` VARCHAR(50) DEFAULT NULL,
  `is_rework_required` TINYINT(1) NOT NULL,
  `is_repair_in_current_op` TINYINT(1) NOT NULL,
  `is_scrapped` TINYINT(1) DEFAULT 0,
  `root_cause` ENUM(
    'OPERATOR_ERROR',
    'MATERIAL_ISSUE',
    'EQUIPMENT_ISSUE',
    'PROCESS_ISSUE',
    'DESIGN_ISSUE',
    'UNKNOWN'
  ) DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (`quality_entry_id`) REFERENCES `quality_entry`(`quality_entry_id`) ON DELETE CASCADE,
  INDEX `idx_defect_type` (`defect_type`),
  INDEX `idx_root_cause` (`root_cause`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Part opportunities master data (for DPMO)
CREATE TABLE IF NOT EXISTS `part_opportunities` (
  `part_number` VARCHAR(50) NOT NULL PRIMARY KEY,
  `opportunities_per_unit` INT UNSIGNED NOT NULL CHECK (opportunities_per_unit > 0),
  `description` VARCHAR(500) DEFAULT NULL,
  `updated_by_user_id` INT UNSIGNED DEFAULT NULL,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `notes` TEXT,

  FOREIGN KEY (`updated_by_user_id`) REFERENCES `user`(`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VIEWS FOR KPI CALCULATIONS
-- ============================================================================

-- WIP Aging View (KPI #1)
CREATE OR REPLACE VIEW `v_wip_aging` AS
SELECT
  wo.work_order_id,
  wo.client_id,
  wo.style_model,
  wo.status,
  wo.actual_start_date,
  DATEDIFF(CURDATE(), wo.actual_start_date) AS days_since_start,
  COALESCE(SUM(he.total_hold_duration_hours) / 24, 0) AS total_hold_days,
  DATEDIFF(CURDATE(), wo.actual_start_date) - COALESCE(SUM(he.total_hold_duration_hours) / 24, 0) AS net_wip_aging_days,
  CASE
    WHEN DATEDIFF(CURDATE(), wo.actual_start_date) - COALESCE(SUM(he.total_hold_duration_hours) / 24, 0) <= 7 THEN '0-7 days'
    WHEN DATEDIFF(CURDATE(), wo.actual_start_date) - COALESCE(SUM(he.total_hold_duration_hours) / 24, 0) <= 14 THEN '8-14 days'
    WHEN DATEDIFF(CURDATE(), wo.actual_start_date) - COALESCE(SUM(he.total_hold_duration_hours) / 24, 0) <= 30 THEN '15-30 days'
    ELSE '30+ days'
  END AS aging_bucket
FROM work_order wo
LEFT JOIN hold_entry he ON wo.work_order_id = he.work_order_id AND he.hold_status = 'RESUMED'
WHERE wo.status = 'ACTIVE'
GROUP BY wo.work_order_id, wo.client_id, wo.style_model, wo.status, wo.actual_start_date;

-- On-Time Delivery View (KPI #2)
CREATE OR REPLACE VIEW `v_on_time_delivery` AS
SELECT
  wo.work_order_id,
  wo.client_id,
  wo.planned_ship_date,
  wo.required_date,
  wo.actual_delivery_date,
  CASE
    WHEN wo.actual_delivery_date IS NOT NULL THEN
      CASE
        WHEN wo.actual_delivery_date <= COALESCE(wo.planned_ship_date, wo.required_date) THEN 1
        ELSE 0
      END
    ELSE NULL
  END AS is_on_time,
  CASE
    WHEN wo.status = 'COMPLETED' THEN 1
    ELSE 0
  END AS is_complete
FROM work_order wo
WHERE wo.actual_delivery_date IS NOT NULL OR wo.status = 'COMPLETED';

-- Availability Summary (KPI #8)
CREATE OR REPLACE VIEW `v_availability_summary` AS
SELECT
  de.shift_date,
  de.shift_type,
  de.client_id,
  SUM(de.downtime_duration_minutes) AS total_downtime_minutes,
  SUM(de.downtime_duration_minutes) / 60 AS total_downtime_hours,
  CASE
    WHEN de.shift_type = 'SHIFT_1ST' THEN 10
    WHEN de.shift_type = 'SHIFT_2ND' THEN 9
    WHEN de.shift_type IN ('SAT_OT', 'SUN_OT') THEN 8
    ELSE 9
  END AS planned_hours,
  ROUND((1 - (SUM(de.downtime_duration_minutes) / 60) /
    CASE
      WHEN de.shift_type = 'SHIFT_1ST' THEN 10
      WHEN de.shift_type = 'SHIFT_2ND' THEN 9
      WHEN de.shift_type IN ('SAT_OT', 'SUN_OT') THEN 8
      ELSE 9
    END) * 100, 2) AS availability_percentage
FROM downtime_entry de
GROUP BY de.shift_date, de.shift_type, de.client_id;

-- Absenteeism Summary (KPI #10)
CREATE OR REPLACE VIEW `v_absenteeism_summary` AS
SELECT
  ae.shift_date,
  ae.client_id,
  SUM(ae.scheduled_hours) AS total_scheduled_hours,
  SUM(CASE WHEN ae.is_absent = 1 THEN ae.absence_hours ELSE 0 END) AS total_absence_hours,
  ROUND((SUM(CASE WHEN ae.is_absent = 1 THEN ae.absence_hours ELSE 0 END) /
         SUM(ae.scheduled_hours)) * 100, 2) AS absenteeism_percentage,
  COUNT(CASE WHEN ae.is_absent = 1 THEN 1 END) AS absent_count,
  COUNT(*) AS total_employees
FROM attendance_entry ae
GROUP BY ae.shift_date, ae.client_id;

-- Quality PPM/DPMO Summary (KPIs #4, #5)
CREATE OR REPLACE VIEW `v_quality_summary` AS
SELECT
  qe.shift_date,
  qe.client_id,
  qe.operation_checked,
  SUM(qe.units_inspected) AS total_units_inspected,
  SUM(qe.units_defective) AS total_defects,
  SUM(qe.total_defects_count) AS total_defect_count,
  ROUND((SUM(qe.units_defective) / SUM(qe.units_inspected)) * 1000000, 2) AS ppm,
  ROUND((SUM(qe.units_passed) / SUM(qe.units_inspected)) * 100, 2) AS fpy_percentage
FROM quality_entry qe
GROUP BY qe.shift_date, qe.client_id, qe.operation_checked;

-- ============================================================================
-- SAMPLE DATA INSERTION
-- ============================================================================
-- Note: See seed_data_phase2_4.sql for comprehensive sample data

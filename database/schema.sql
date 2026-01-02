-- Manufacturing KPI Platform - Database Schema
-- MariaDB 10.11+ with InnoDB Engine
-- Phase 1: Production Entry Focus

-- Drop tables if exist (for clean setup)
DROP TABLE IF EXISTS `audit_log`;
DROP TABLE IF EXISTS `report_generation`;
DROP TABLE IF EXISTS `kpi_targets`;
DROP TABLE IF EXISTS `production_entry`;
DROP TABLE IF EXISTS `product`;
DROP TABLE IF EXISTS `shift`;
DROP TABLE IF EXISTS `user`;

-- ============================================================================
-- USER MANAGEMENT
-- ============================================================================
CREATE TABLE `user` (
  `user_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL UNIQUE,
  `email` VARCHAR(100) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(100) NOT NULL,
  `role` ENUM('admin', 'supervisor', 'operator', 'viewer') NOT NULL DEFAULT 'operator',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  INDEX `idx_username` (`username`),
  INDEX `idx_email` (`email`),
  INDEX `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SHIFT DEFINITION
-- ============================================================================
CREATE TABLE `shift` (
  `shift_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `shift_name` VARCHAR(50) NOT NULL UNIQUE,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`shift_id`),
  INDEX `idx_shift_name` (`shift_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PRODUCT CATALOG
-- ============================================================================
CREATE TABLE `product` (
  `product_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `product_code` VARCHAR(50) NOT NULL UNIQUE,
  `product_name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `ideal_cycle_time` DECIMAL(8,4) DEFAULT NULL COMMENT 'Hours per unit - NULL triggers inference',
  `unit_of_measure` VARCHAR(20) NOT NULL DEFAULT 'units',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`product_id`),
  INDEX `idx_product_code` (`product_code`),
  INDEX `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PRODUCTION ENTRY (Core Phase 1 Table)
-- ============================================================================
CREATE TABLE `production_entry` (
  `entry_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `product_id` INT UNSIGNED NOT NULL,
  `shift_id` INT UNSIGNED NOT NULL,
  `production_date` DATE NOT NULL,
  `work_order_number` VARCHAR(50) DEFAULT NULL,

  -- Production Metrics
  `units_produced` INT UNSIGNED NOT NULL,
  `run_time_hours` DECIMAL(8,2) NOT NULL COMMENT 'Actual production runtime in hours',
  `employees_assigned` INT UNSIGNED NOT NULL,

  -- Quality Metrics (Optional for Phase 1)
  `defect_count` INT UNSIGNED DEFAULT 0,
  `scrap_count` INT UNSIGNED DEFAULT 0,

  -- Calculated KPIs (stored for performance, recalculated on demand)
  `efficiency_percentage` DECIMAL(8,4) DEFAULT NULL COMMENT 'KPI #3: Efficiency',
  `performance_percentage` DECIMAL(8,4) DEFAULT NULL COMMENT 'KPI #9: Performance',

  -- Metadata
  `notes` TEXT,
  `entered_by` INT UNSIGNED NOT NULL,
  `confirmed_by` INT UNSIGNED DEFAULT NULL COMMENT 'Supervisor confirmation',
  `confirmation_timestamp` TIMESTAMP NULL DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`entry_id`),
  FOREIGN KEY (`product_id`) REFERENCES `product`(`product_id`) ON DELETE RESTRICT,
  FOREIGN KEY (`shift_id`) REFERENCES `shift`(`shift_id`) ON DELETE RESTRICT,
  FOREIGN KEY (`entered_by`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  FOREIGN KEY (`confirmed_by`) REFERENCES `user`(`user_id`) ON DELETE SET NULL,

  INDEX `idx_production_date` (`production_date`),
  INDEX `idx_work_order` (`work_order_number`),
  INDEX `idx_entered_by` (`entered_by`),
  INDEX `idx_composite` (`production_date`, `shift_id`, `product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- KPI TARGETS (For Dashboard Comparison)
-- ============================================================================
CREATE TABLE `kpi_targets` (
  `target_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `kpi_name` VARCHAR(100) NOT NULL,
  `target_value` DECIMAL(10,4) NOT NULL,
  `unit` VARCHAR(20) NOT NULL,
  `effective_from` DATE NOT NULL,
  `effective_to` DATE DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`target_id`),
  INDEX `idx_kpi_name` (`kpi_name`),
  INDEX `idx_effective_dates` (`effective_from`, `effective_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- REPORT GENERATION TRACKING
-- ============================================================================
CREATE TABLE `report_generation` (
  `report_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `report_type` ENUM('daily', 'weekly', 'monthly', 'custom') NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `generated_by` INT UNSIGNED NOT NULL,
  `file_path` VARCHAR(255) DEFAULT NULL,
  `status` ENUM('pending', 'completed', 'failed') NOT NULL DEFAULT 'pending',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_id`),
  FOREIGN KEY (`generated_by`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  INDEX `idx_report_type` (`report_type`),
  INDEX `idx_status` (`status`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- AUDIT LOG (For Compliance & Tracking)
-- ============================================================================
CREATE TABLE `audit_log` (
  `log_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED DEFAULT NULL,
  `action` VARCHAR(100) NOT NULL,
  `table_name` VARCHAR(50) NOT NULL,
  `record_id` INT UNSIGNED DEFAULT NULL,
  `old_value` TEXT,
  `new_value` TEXT,
  `ip_address` VARCHAR(45) DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`),
  FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE SET NULL,
  INDEX `idx_table_record` (`table_name`, `record_id`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================
-- Additional composite indexes for common queries
ALTER TABLE `production_entry`
  ADD INDEX `idx_date_shift` (`production_date`, `shift_id`),
  ADD INDEX `idx_product_date` (`product_id`, `production_date`);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Daily Production Summary
CREATE OR REPLACE VIEW `v_daily_production_summary` AS
SELECT
  pe.production_date,
  s.shift_name,
  p.product_code,
  p.product_name,
  SUM(pe.units_produced) AS total_units,
  SUM(pe.run_time_hours) AS total_runtime,
  AVG(pe.efficiency_percentage) AS avg_efficiency,
  AVG(pe.performance_percentage) AS avg_performance,
  COUNT(*) AS entry_count
FROM production_entry pe
JOIN product p ON pe.product_id = p.product_id
JOIN shift s ON pe.shift_id = s.shift_id
GROUP BY pe.production_date, s.shift_name, p.product_code, p.product_name;

-- KPI Dashboard View
CREATE OR REPLACE VIEW `v_kpi_dashboard` AS
SELECT
  DATE_FORMAT(pe.production_date, '%Y-%m') AS month,
  AVG(pe.efficiency_percentage) AS avg_efficiency,
  AVG(pe.performance_percentage) AS avg_performance,
  SUM(pe.units_produced) AS total_units,
  SUM(pe.defect_count) AS total_defects,
  SUM(pe.scrap_count) AS total_scrap,
  ROUND((SUM(pe.defect_count) + SUM(pe.scrap_count)) / SUM(pe.units_produced) * 100, 2) AS reject_rate_percentage
FROM production_entry pe
WHERE pe.production_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY DATE_FORMAT(pe.production_date, '%Y-%m')
ORDER BY month DESC;

-- ============================================================================
-- STORED PROCEDURES FOR KPI CALCULATIONS
-- ============================================================================

DELIMITER $$

-- Calculate Efficiency (KPI #3)
-- FORMULA PER CSV REQUIREMENT:
-- Efficiency = (Units × Cycle Time) / (Employees × SCHEDULED Hours) × 100
-- CRITICAL: Uses SCHEDULED shift hours, NOT actual runtime hours
-- Runtime is used for Performance KPI, not Efficiency KPI
CREATE PROCEDURE `sp_calculate_efficiency`(IN p_entry_id INT UNSIGNED)
BEGIN
  DECLARE v_ideal_cycle_time DECIMAL(8,4);
  DECLARE v_units_produced INT UNSIGNED;
  DECLARE v_employees INT UNSIGNED;
  DECLARE v_shift_start TIME;
  DECLARE v_shift_end TIME;
  DECLARE v_shift_hours DECIMAL(8,2);
  DECLARE v_efficiency DECIMAL(8,4);

  -- Get entry data with shift times (NOT runtime!)
  SELECT
    p.ideal_cycle_time,
    pe.units_produced,
    pe.employees_assigned,
    s.start_time,
    s.end_time
  INTO v_ideal_cycle_time, v_units_produced, v_employees, v_shift_start, v_shift_end
  FROM production_entry pe
  JOIN product p ON pe.product_id = p.product_id
  JOIN shift s ON pe.shift_id = s.shift_id
  WHERE pe.entry_id = p_entry_id;

  -- Inference: Use default if ideal_cycle_time is NULL
  IF v_ideal_cycle_time IS NULL THEN
    SET v_ideal_cycle_time = 0.25; -- Default: 15 minutes per unit
  END IF;

  -- Calculate SCHEDULED shift hours from start/end times
  -- Handle overnight shifts (end < start)
  IF v_shift_end >= v_shift_start THEN
    SET v_shift_hours = TIME_TO_SEC(TIMEDIFF(v_shift_end, v_shift_start)) / 3600;
  ELSE
    -- Overnight shift: add 24 hours to end time
    SET v_shift_hours = (TIME_TO_SEC(TIMEDIFF(v_shift_end, v_shift_start)) + 86400) / 3600;
  END IF;

  -- Calculate: (units_produced × ideal_cycle_time) / (employees_assigned × SCHEDULED_hours)
  -- NOT (employees × runtime) - that would be productivity, not efficiency
  IF v_employees > 0 AND v_shift_hours > 0 THEN
    SET v_efficiency = (v_units_produced * v_ideal_cycle_time) / (v_employees * v_shift_hours);
  ELSE
    SET v_efficiency = 0;
  END IF;

  -- Update entry
  UPDATE production_entry
  SET efficiency_percentage = v_efficiency * 100
  WHERE entry_id = p_entry_id;
END$$

-- Calculate Performance (KPI #9)
CREATE PROCEDURE `sp_calculate_performance`(IN p_entry_id INT UNSIGNED)
BEGIN
  DECLARE v_ideal_cycle_time DECIMAL(8,4);
  DECLARE v_units_produced INT UNSIGNED;
  DECLARE v_runtime DECIMAL(8,2);
  DECLARE v_performance DECIMAL(8,4);

  -- Get entry data
  SELECT
    p.ideal_cycle_time,
    pe.units_produced,
    pe.run_time_hours
  INTO v_ideal_cycle_time, v_units_produced, v_runtime
  FROM production_entry pe
  JOIN product p ON pe.product_id = p.product_id
  WHERE pe.entry_id = p_entry_id;

  -- Inference: Use default if ideal_cycle_time is NULL
  IF v_ideal_cycle_time IS NULL THEN
    SET v_ideal_cycle_time = 0.25;
  END IF;

  -- Calculate: (ideal_cycle_time × units_produced) / run_time_hours × 100
  IF v_runtime > 0 THEN
    SET v_performance = (v_ideal_cycle_time * v_units_produced) / v_runtime * 100;
  ELSE
    SET v_performance = 0;
  END IF;

  -- Update entry
  UPDATE production_entry
  SET performance_percentage = v_performance
  WHERE entry_id = p_entry_id;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC KPI CALCULATION
-- ============================================================================

DELIMITER $$

CREATE TRIGGER `tr_production_entry_after_insert`
AFTER INSERT ON `production_entry`
FOR EACH ROW
BEGIN
  CALL sp_calculate_efficiency(NEW.entry_id);
  CALL sp_calculate_performance(NEW.entry_id);
END$$

CREATE TRIGGER `tr_production_entry_after_update`
AFTER UPDATE ON `production_entry`
FOR EACH ROW
BEGIN
  IF NEW.units_produced <> OLD.units_produced
     OR NEW.run_time_hours <> OLD.run_time_hours
     OR NEW.employees_assigned <> OLD.employees_assigned THEN
    CALL sp_calculate_efficiency(NEW.entry_id);
    CALL sp_calculate_performance(NEW.entry_id);
  END IF;
END$$

DELIMITER ;

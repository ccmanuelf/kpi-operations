-- Manufacturing KPI Platform - Seed Data
-- Sample data for testing Phase 1 MVP

-- ============================================================================
-- USERS
-- ============================================================================
INSERT INTO `user` (`username`, `email`, `password_hash`, `full_name`, `role`) VALUES
('admin', 'admin@company.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIx.N9C/zu', 'System Administrator', 'admin'),
('supervisor1', 'supervisor@company.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIx.N9C/zu', 'Jane Supervisor', 'supervisor'),
('operator1', 'operator1@company.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIx.N9C/zu', 'John Operator', 'operator'),
('operator2', 'operator2@company.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIx.N9C/zu', 'Maria Worker', 'operator');
-- Password for all users: "password123"

-- ============================================================================
-- SHIFTS
-- ============================================================================
INSERT INTO `shift` (`shift_name`, `start_time`, `end_time`) VALUES
('Morning', '06:00:00', '14:00:00'),
('Afternoon', '14:00:00', '22:00:00'),
('Night', '22:00:00', '06:00:00');

-- ============================================================================
-- PRODUCTS
-- ============================================================================
INSERT INTO `product` (`product_code`, `product_name`, `description`, `ideal_cycle_time`, `unit_of_measure`) VALUES
('WDG-001', 'Widget Standard', 'Standard widget component', 0.25, 'units'),
('WDG-002', 'Widget Premium', 'Premium widget with advanced features', 0.35, 'units'),
('ASM-100', 'Assembly A100', 'Complete assembly unit A100', 0.50, 'units'),
('ASM-200', 'Assembly A200', 'Advanced assembly A200', 0.75, 'units'),
('PART-500', 'Generic Part 500', 'Generic replacement part', NULL, 'units'); -- NULL triggers inference

-- ============================================================================
-- KPI TARGETS
-- ============================================================================
INSERT INTO `kpi_targets` (`kpi_name`, `target_value`, `unit`, `effective_from`) VALUES
('Efficiency', 85.00, '%', '2025-01-01'),
('Performance', 90.00, '%', '2025-01-01'),
('Quality Rate', 95.00, '%', '2025-01-01'),
('OEE', 75.00, '%', '2025-01-01');

-- ============================================================================
-- PRODUCTION ENTRIES (Sample Data)
-- ============================================================================
-- Week 1: Dec 23-27, 2025
INSERT INTO `production_entry` (
  `product_id`, `shift_id`, `production_date`, `work_order_number`,
  `units_produced`, `run_time_hours`, `employees_assigned`,
  `defect_count`, `scrap_count`, `entered_by`, `confirmed_by`, `notes`
) VALUES
-- Monday Morning
(1, 1, '2025-12-23', 'WO-2025-001', 250, 7.5, 3, 5, 2, 3, 2, 'Normal production'),
(2, 1, '2025-12-23', 'WO-2025-002', 180, 7.0, 2, 3, 1, 3, 2, 'Started new batch'),

-- Monday Afternoon
(1, 2, '2025-12-23', 'WO-2025-001', 240, 7.8, 3, 8, 3, 3, 2, 'Machine calibration done'),
(3, 2, '2025-12-23', 'WO-2025-003', 120, 7.5, 4, 2, 0, 3, 2, 'Good quality run'),

-- Tuesday Morning
(1, 1, '2025-12-24', 'WO-2025-004', 260, 7.3, 3, 4, 1, 3, 2, 'Excellent performance'),
(2, 1, '2025-12-24', 'WO-2025-005', 190, 7.2, 2, 2, 0, 3, 2, 'No issues'),

-- Tuesday Afternoon
(3, 2, '2025-12-24', 'WO-2025-006', 130, 7.6, 4, 3, 1, 3, 2, 'Material delay 30min'),
(4, 2, '2025-12-24', 'WO-2025-007', 85, 7.5, 5, 1, 0, 3, 2, 'Complex assembly'),

-- Wednesday Morning
(1, 1, '2025-12-25', 'WO-2025-008', 255, 7.4, 3, 6, 2, 3, 2, 'Regular production'),
(5, 1, '2025-12-25', 'WO-2025-009', 300, 7.0, 2, 10, 5, 3, NULL, 'Needs confirmation'),

-- Wednesday Afternoon (Peak performance)
(1, 2, '2025-12-25', 'WO-2025-010', 275, 7.2, 3, 3, 1, 3, 2, 'Record efficiency'),
(2, 2, '2025-12-25', 'WO-2025-011', 200, 6.8, 2, 1, 0, 3, 2, 'Best batch this week'),

-- Thursday Morning
(3, 1, '2025-12-26', 'WO-2025-012', 125, 7.5, 4, 4, 2, 3, 2, 'Standard run'),
(4, 1, '2025-12-26', 'WO-2025-013', 90, 7.8, 5, 2, 1, 3, 2, 'Training new operator'),

-- Thursday Afternoon
(1, 2, '2025-12-26', 'WO-2025-014', 245, 7.7, 3, 7, 3, 3, 2, 'Minor quality issues'),
(5, 2, '2025-12-26', 'WO-2025-015', 280, 7.1, 2, 12, 6, 3, 2, 'High defect rate'),

-- Friday Morning
(1, 1, '2025-12-27', 'WO-2025-016', 265, 7.3, 3, 5, 2, 3, 2, 'End of week strong'),
(2, 1, '2025-12-27', 'WO-2025-017', 195, 7.1, 2, 3, 1, 3, 2, 'Good quality'),

-- Friday Afternoon
(3, 2, '2025-12-27', 'WO-2025-018', 135, 7.4, 4, 3, 1, 3, 2, 'Week completed'),
(4, 2, '2025-12-27', 'WO-2025-019', 88, 7.6, 5, 1, 0, 3, 2, 'Cleanup and maintenance');

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check KPI calculations (should be populated by triggers)
-- SELECT
--   entry_id,
--   production_date,
--   units_produced,
--   efficiency_percentage,
--   performance_percentage
-- FROM production_entry
-- ORDER BY production_date DESC, entry_id DESC
-- LIMIT 10;

-- View daily summary
-- SELECT * FROM v_daily_production_summary
-- WHERE production_date >= '2025-12-23'
-- ORDER BY production_date DESC;

-- Check KPI dashboard
-- SELECT * FROM v_kpi_dashboard;

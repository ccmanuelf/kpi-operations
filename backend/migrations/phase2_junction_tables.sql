-- Phase 2.1: Data Layer Normalization - Junction Tables
-- Creates USER_CLIENT_ASSIGNMENT and EMPLOYEE_CLIENT_ASSIGNMENT tables
--
-- NOTE: All existing data is SAMPLE DATA and can be regenerated.
-- This migration creates new tables without modifying existing schema.

-- ============================================================================
-- USER_CLIENT_ASSIGNMENT Junction Table
-- Replaces comma-separated client_id_assigned in USER table
-- ============================================================================
CREATE TABLE IF NOT EXISTS USER_CLIENT_ASSIGNMENT (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign keys
    user_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50) NOT NULL,

    -- Assignment metadata
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by VARCHAR(50),

    -- Is this the user's primary/default client?
    is_primary INTEGER DEFAULT 0,

    -- Soft delete / deactivation
    is_active INTEGER DEFAULT 1,
    deactivated_at TIMESTAMP,
    deactivated_by VARCHAR(50),

    -- Audit timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (user_id) REFERENCES USER(user_id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id) ON DELETE RESTRICT,
    UNIQUE(user_id, client_id)
);

-- Indexes for USER_CLIENT_ASSIGNMENT
CREATE INDEX IF NOT EXISTS idx_user_client_user ON USER_CLIENT_ASSIGNMENT(user_id);
CREATE INDEX IF NOT EXISTS idx_user_client_client ON USER_CLIENT_ASSIGNMENT(client_id);
CREATE INDEX IF NOT EXISTS idx_user_client_active ON USER_CLIENT_ASSIGNMENT(is_active);


-- ============================================================================
-- EMPLOYEE_CLIENT_ASSIGNMENT Junction Table
-- Replaces comma-separated client_id_assigned in EMPLOYEE table
-- ============================================================================
CREATE TABLE IF NOT EXISTS EMPLOYEE_CLIENT_ASSIGNMENT (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign keys
    employee_id INTEGER NOT NULL,
    client_id VARCHAR(50) NOT NULL,

    -- Assignment type: 'DEDICATED' or 'FLOATING'
    assignment_type VARCHAR(20) NOT NULL DEFAULT 'DEDICATED',

    -- Assignment validity period
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,

    -- Assignment metadata
    assigned_by VARCHAR(50),
    notes VARCHAR(500),

    -- Soft delete / deactivation
    is_active INTEGER DEFAULT 1,
    deactivated_at TIMESTAMP,
    deactivated_by VARCHAR(50),

    -- Audit timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (employee_id) REFERENCES EMPLOYEE(employee_id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id) ON DELETE RESTRICT,
    UNIQUE(employee_id, client_id)
);

-- Indexes for EMPLOYEE_CLIENT_ASSIGNMENT
CREATE INDEX IF NOT EXISTS idx_employee_client_employee ON EMPLOYEE_CLIENT_ASSIGNMENT(employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_client_client ON EMPLOYEE_CLIENT_ASSIGNMENT(client_id);
CREATE INDEX IF NOT EXISTS idx_employee_client_type ON EMPLOYEE_CLIENT_ASSIGNMENT(assignment_type);
CREATE INDEX IF NOT EXISTS idx_employee_client_active ON EMPLOYEE_CLIENT_ASSIGNMENT(is_active);


-- ============================================================================
-- SHARED_DEFECT_TYPE Table (Phase 3.4)
-- System-default defect types shared across all clients
-- ============================================================================
CREATE TABLE IF NOT EXISTS SHARED_DEFECT_TYPE (
    defect_type_id VARCHAR(50) PRIMARY KEY,
    defect_code VARCHAR(20) NOT NULL,
    defect_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    description TEXT,
    is_system_default INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed common industry defects
INSERT OR IGNORE INTO SHARED_DEFECT_TYPE (defect_type_id, defect_code, defect_name, category, description) VALUES
('STITCH-001', 'ST001', 'Broken Stitch', 'Stitching', 'Thread breakage in seam'),
('STITCH-002', 'ST002', 'Skip Stitch', 'Stitching', 'Missing stitches in seam'),
('STITCH-003', 'ST003', 'Uneven Stitch', 'Stitching', 'Irregular stitch spacing'),
('FABRIC-001', 'FB001', 'Fabric Hole', 'Fabric', 'Hole or tear in fabric'),
('FABRIC-002', 'FB002', 'Fabric Stain', 'Fabric', 'Visible stain on fabric'),
('FABRIC-003', 'FB003', 'Color Variation', 'Fabric', 'Color inconsistency'),
('MEAS-001', 'MS001', 'Out of Spec', 'Measurement', 'Measurement outside tolerance'),
('MEAS-002', 'MS002', 'Asymmetric', 'Measurement', 'Left/right asymmetry'),
('TRIM-001', 'TR001', 'Missing Trim', 'Trim', 'Required trim not attached'),
('TRIM-002', 'TR002', 'Wrong Trim', 'Trim', 'Incorrect trim type or color'),
('LABEL-001', 'LB001', 'Missing Label', 'Label', 'Required label not attached'),
('LABEL-002', 'LB002', 'Wrong Label', 'Label', 'Incorrect label information');


-- ============================================================================
-- Migration Notes
-- ============================================================================
--
-- Phase 2.2 requires updating client_auth.py to use junction tables.
-- The middleware should check:
-- 1. First, try junction table (new system)
-- 2. Fall back to comma-separated field (legacy support)
--
-- Phase 2.4 requires regenerating sample data with junction table entries.
--
-- To run this migration:
--   sqlite3 backend/kpi_operations.db < backend/migrations/phase2_junction_tables.sql

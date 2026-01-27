-- ============================================================================
-- MIGRATION 005: Phase 10 Workflow Foundation
-- ============================================================================
-- Date: January 26, 2026
-- Priority: HIGH
-- Impact: Adds workflow lifecycle tracking to WORK_ORDER and CLIENT_CONFIG
-- Creates WORKFLOW_TRANSITION_LOG table for audit trail
-- Estimated Time: 15-20 minutes
-- ============================================================================

-- Enable foreign keys (critical for SQLite)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ============================================================================
-- STEP 1: Add Workflow Date Fields to WORK_ORDER
-- ============================================================================

-- Workflow lifecycle dates
ALTER TABLE WORK_ORDER ADD COLUMN received_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN planned_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN expected_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN dispatch_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN shipped_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN closure_date DATETIME;
ALTER TABLE WORK_ORDER ADD COLUMN closed_by INTEGER;

-- Workflow state tracking
ALTER TABLE WORK_ORDER ADD COLUMN previous_status VARCHAR(20);

-- ============================================================================
-- STEP 2: Create Indexes for WORK_ORDER Workflow Fields
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_work_order_received_date
ON WORK_ORDER(received_date);

CREATE INDEX IF NOT EXISTS idx_work_order_dispatch_date
ON WORK_ORDER(dispatch_date);

CREATE INDEX IF NOT EXISTS idx_work_order_shipped_date
ON WORK_ORDER(shipped_date);

CREATE INDEX IF NOT EXISTS idx_work_order_closure_date
ON WORK_ORDER(closure_date);

CREATE INDEX IF NOT EXISTS idx_work_order_status_client
ON WORK_ORDER(status, client_id);

-- ============================================================================
-- STEP 3: Add Workflow Configuration to CLIENT_CONFIG
-- ============================================================================

-- Workflow configuration (stored as JSON text)
ALTER TABLE CLIENT_CONFIG ADD COLUMN workflow_statuses TEXT
DEFAULT '["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]';

ALTER TABLE CLIENT_CONFIG ADD COLUMN workflow_transitions TEXT
DEFAULT '{
    "RELEASED": ["RECEIVED"],
    "IN_PROGRESS": ["RELEASED"],
    "COMPLETED": ["IN_PROGRESS"],
    "SHIPPED": ["COMPLETED"],
    "CLOSED": ["SHIPPED", "COMPLETED"],
    "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
    "DEMOTED": ["RELEASED"],
    "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
    "REJECTED": ["IN_PROGRESS", "COMPLETED"]
}';

ALTER TABLE CLIENT_CONFIG ADD COLUMN workflow_optional_statuses TEXT
DEFAULT '["SHIPPED", "DEMOTED"]';

ALTER TABLE CLIENT_CONFIG ADD COLUMN workflow_closure_trigger VARCHAR(30)
DEFAULT 'at_shipment';

ALTER TABLE CLIENT_CONFIG ADD COLUMN workflow_version INTEGER
DEFAULT 1;

-- ============================================================================
-- STEP 4: Create WORKFLOW_TRANSITION_LOG Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS WORKFLOW_TRANSITION_LOG (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    from_status VARCHAR(20),  -- NULL for initial creation
    to_status VARCHAR(20) NOT NULL,
    transitioned_by INTEGER,
    transitioned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    trigger_source VARCHAR(50) CHECK(trigger_source IN ('manual', 'automatic', 'bulk', 'api', 'import')),
    elapsed_from_received_hours INTEGER,
    elapsed_from_previous_hours INTEGER,

    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (transitioned_by) REFERENCES USER(user_id)
);

-- ============================================================================
-- STEP 5: Create Indexes for WORKFLOW_TRANSITION_LOG
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_workflow_log_work_order
ON WORKFLOW_TRANSITION_LOG(work_order_id, transitioned_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_log_client
ON WORKFLOW_TRANSITION_LOG(client_id, transitioned_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_log_from_to
ON WORKFLOW_TRANSITION_LOG(from_status, to_status);

CREATE INDEX IF NOT EXISTS idx_workflow_log_trigger
ON WORKFLOW_TRANSITION_LOG(trigger_source, transitioned_at);

CREATE INDEX IF NOT EXISTS idx_workflow_log_user
ON WORKFLOW_TRANSITION_LOG(transitioned_by, transitioned_at);

-- ============================================================================
-- STEP 6: Populate Workflow Dates from Existing Data
-- ============================================================================

-- Set received_date from created_at for existing work orders
UPDATE WORK_ORDER
SET received_date = created_at
WHERE received_date IS NULL AND created_at IS NOT NULL;

-- Set dispatch_date from actual_start_date for started orders
UPDATE WORK_ORDER
SET dispatch_date = actual_start_date
WHERE dispatch_date IS NULL AND actual_start_date IS NOT NULL;

-- Set shipped_date from actual_delivery_date for delivered orders
UPDATE WORK_ORDER
SET shipped_date = actual_delivery_date
WHERE shipped_date IS NULL AND actual_delivery_date IS NOT NULL;

-- Set expected_date from planned_ship_date
UPDATE WORK_ORDER
SET expected_date = planned_ship_date
WHERE expected_date IS NULL AND planned_ship_date IS NOT NULL;

-- Set closure_date for COMPLETED/CLOSED status orders without one
UPDATE WORK_ORDER
SET closure_date = COALESCE(shipped_date, updated_at, created_at)
WHERE closure_date IS NULL
AND status IN ('COMPLETED', 'CLOSED', 'SHIPPED');

-- ============================================================================
-- STEP 7: Create Initial Transition Log Entries for Existing Orders
-- ============================================================================

-- Insert initial RECEIVED transition for all existing work orders
INSERT INTO WORKFLOW_TRANSITION_LOG (
    work_order_id,
    client_id,
    from_status,
    to_status,
    transitioned_at,
    trigger_source,
    notes
)
SELECT
    wo.work_order_id,
    wo.client_id,
    NULL,  -- from_status is NULL for initial creation
    'RECEIVED',
    COALESCE(wo.received_date, wo.created_at, CURRENT_TIMESTAMP),
    'import',
    'Migration: Initial status from existing data'
FROM WORK_ORDER wo
WHERE NOT EXISTS (
    SELECT 1 FROM WORKFLOW_TRANSITION_LOG wtl
    WHERE wtl.work_order_id = wo.work_order_id
);

-- Insert current status transition for non-RECEIVED orders
INSERT INTO WORKFLOW_TRANSITION_LOG (
    work_order_id,
    client_id,
    from_status,
    to_status,
    transitioned_at,
    trigger_source,
    notes
)
SELECT
    wo.work_order_id,
    wo.client_id,
    'RECEIVED',
    wo.status,
    COALESCE(wo.updated_at, wo.created_at, CURRENT_TIMESTAMP),
    'import',
    'Migration: Current status from existing data'
FROM WORK_ORDER wo
WHERE wo.status != 'RECEIVED'
AND NOT EXISTS (
    SELECT 1 FROM WORKFLOW_TRANSITION_LOG wtl
    WHERE wtl.work_order_id = wo.work_order_id
    AND wtl.to_status = wo.status
);

-- ============================================================================
-- STEP 8: Create Views for Workflow Analytics
-- ============================================================================

-- Work Order Lifecycle Summary
CREATE VIEW IF NOT EXISTS v_work_order_lifecycle AS
SELECT
    wo.work_order_id,
    wo.client_id,
    wo.style_model,
    wo.status,
    wo.received_date,
    wo.dispatch_date,
    wo.shipped_date,
    wo.closure_date,
    -- Elapsed time calculations (in hours)
    CASE
        WHEN wo.closure_date IS NOT NULL AND wo.received_date IS NOT NULL THEN
            CAST((julianday(wo.closure_date) - julianday(wo.received_date)) * 24 AS INTEGER)
        ELSE NULL
    END as total_lifecycle_hours,
    CASE
        WHEN wo.dispatch_date IS NOT NULL AND wo.received_date IS NOT NULL THEN
            CAST((julianday(wo.dispatch_date) - julianday(wo.received_date)) * 24 AS INTEGER)
        ELSE NULL
    END as received_to_dispatch_hours,
    CASE
        WHEN wo.closure_date IS NOT NULL AND wo.dispatch_date IS NOT NULL THEN
            CAST((julianday(wo.closure_date) - julianday(wo.dispatch_date)) * 24 AS INTEGER)
        ELSE NULL
    END as dispatch_to_closure_hours,
    -- Status counts from transition log
    (SELECT COUNT(*) FROM WORKFLOW_TRANSITION_LOG wtl
     WHERE wtl.work_order_id = wo.work_order_id) as transition_count
FROM WORK_ORDER wo;

-- Workflow Transition Statistics
CREATE VIEW IF NOT EXISTS v_workflow_transition_stats AS
SELECT
    client_id,
    from_status,
    to_status,
    COUNT(*) as transition_count,
    AVG(elapsed_from_previous_hours) as avg_elapsed_hours,
    MIN(transitioned_at) as first_occurrence,
    MAX(transitioned_at) as last_occurrence
FROM WORKFLOW_TRANSITION_LOG
GROUP BY client_id, from_status, to_status;

-- Current Status Distribution by Client
CREATE VIEW IF NOT EXISTS v_status_distribution AS
SELECT
    client_id,
    status,
    COUNT(*) as order_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY client_id), 2) as percentage
FROM WORK_ORDER
GROUP BY client_id, status;

-- ============================================================================
-- STEP 9: Verify Migration Success
-- ============================================================================

SELECT 'WORK_ORDER with received_date:' as metric, COUNT(*) as count
FROM WORK_ORDER WHERE received_date IS NOT NULL
UNION ALL
SELECT 'WORK_ORDER with dispatch_date:' as metric, COUNT(*) as count
FROM WORK_ORDER WHERE dispatch_date IS NOT NULL
UNION ALL
SELECT 'WORK_ORDER with closure_date:' as metric, COUNT(*) as count
FROM WORK_ORDER WHERE closure_date IS NOT NULL
UNION ALL
SELECT 'CLIENT_CONFIG with workflow_statuses:' as metric, COUNT(*) as count
FROM CLIENT_CONFIG WHERE workflow_statuses IS NOT NULL
UNION ALL
SELECT 'WORKFLOW_TRANSITION_LOG entries:' as metric, COUNT(*) as count
FROM WORKFLOW_TRANSITION_LOG
UNION ALL
SELECT 'Unique work orders in log:' as metric, COUNT(DISTINCT work_order_id) as count
FROM WORKFLOW_TRANSITION_LOG;

COMMIT;

-- ============================================================================
-- POST-MIGRATION NOTES
-- ============================================================================
-- 1. SQLAlchemy schemas updated: backend/schemas/work_order.py
-- 2. SQLAlchemy schemas created: backend/schemas/workflow.py
-- 3. SQLAlchemy schemas updated: backend/schemas/client_config.py
-- 4. Pydantic models updated: backend/models/work_order.py
-- 5. Pydantic models created: backend/models/workflow.py
-- 6. Pydantic models updated: backend/models/client_config.py
-- 7. Next steps:
--    - Implement state machine validation (Task #9)
--    - Implement elapsed time calculations (Task #13)
--    - Create workflow API routes (Task #14)
--    - Create frontend components (Task #15)
--    - Create admin configuration UI (Task #16)
-- ============================================================================

-- Rollback script (if needed):
-- DROP VIEW IF EXISTS v_status_distribution;
-- DROP VIEW IF EXISTS v_workflow_transition_stats;
-- DROP VIEW IF EXISTS v_work_order_lifecycle;
-- DROP TABLE IF EXISTS WORKFLOW_TRANSITION_LOG;
-- Then restore WORK_ORDER and CLIENT_CONFIG from backup

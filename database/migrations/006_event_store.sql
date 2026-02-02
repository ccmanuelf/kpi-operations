-- Migration 006: EVENT_STORE Table
-- Phase 3: Domain Events Infrastructure
-- Creates persistent storage for domain events

-- ============================================================================
-- EVENT_STORE Table
-- Stores all domain events for audit, replay, and analytics
-- ============================================================================

CREATE TABLE IF NOT EXISTS EVENT_STORE (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50),
    triggered_by INTEGER,
    occurred_at DATETIME NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for efficient queries
-- ============================================================================

-- Event ID lookup (unique)
CREATE UNIQUE INDEX IF NOT EXISTS ix_event_store_event_id
    ON EVENT_STORE (event_id);

-- Event type filtering (e.g., all WorkOrderStatusChanged events)
CREATE INDEX IF NOT EXISTS ix_event_store_event_type
    ON EVENT_STORE (event_type);

-- Occurred at for time-based queries
CREATE INDEX IF NOT EXISTS ix_event_store_occurred_at
    ON EVENT_STORE (occurred_at);

-- Aggregate lookup (e.g., all events for a specific work order)
CREATE INDEX IF NOT EXISTS ix_event_store_aggregate
    ON EVENT_STORE (aggregate_type, aggregate_id);

-- Client-scoped time queries (multi-tenant)
CREATE INDEX IF NOT EXISTS ix_event_store_client_time
    ON EVENT_STORE (client_id, occurred_at);

-- Event type + time for analytics
CREATE INDEX IF NOT EXISTS ix_event_store_type_time
    ON EVENT_STORE (event_type, occurred_at);

-- ============================================================================
-- Migration verification
-- ============================================================================

-- Verify table exists
SELECT name FROM sqlite_master WHERE type='table' AND name='EVENT_STORE';

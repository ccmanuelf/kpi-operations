-- Migration: Add User Preferences, Saved Filters, and Filter History tables
-- Date: 2026-01-16
-- Features: Custom Dashboards, Advanced Filtering, QR Code Integration

-- 1. User Preferences (dashboard customization)
CREATE TABLE IF NOT EXISTS USER_PREFERENCES (
    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    preference_type VARCHAR(50) NOT NULL,  -- 'dashboard', 'widget', 'theme'
    preference_key VARCHAR(100) NOT NULL,
    preference_value TEXT NOT NULL,  -- JSON structure
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, preference_type, preference_key)
);

-- Index for fast user preference lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON USER_PREFERENCES(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_type ON USER_PREFERENCES(user_id, preference_type);

-- 2. Saved Filters (Personal only - no sharing)
CREATE TABLE IF NOT EXISTS SAVED_FILTER (
    filter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    filter_name VARCHAR(100) NOT NULL,
    filter_type VARCHAR(50) NOT NULL,  -- 'production', 'quality', 'dashboard', 'downtime', 'attendance'
    filter_config TEXT NOT NULL,  -- JSON: {client_id, date_range, shifts, products, thresholds}
    is_default BOOLEAN DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    last_used_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for saved filters
CREATE INDEX IF NOT EXISTS idx_saved_filter_user ON SAVED_FILTER(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_filter_type ON SAVED_FILTER(user_id, filter_type);
CREATE INDEX IF NOT EXISTS idx_saved_filter_default ON SAVED_FILTER(user_id, is_default);

-- 3. Filter History (recent filter applications for quick access)
CREATE TABLE IF NOT EXISTS FILTER_HISTORY (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(50) NOT NULL,
    filter_config TEXT NOT NULL,  -- JSON of applied filter
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index for filter history lookups
CREATE INDEX IF NOT EXISTS idx_filter_history_user ON FILTER_HISTORY(user_id);
CREATE INDEX IF NOT EXISTS idx_filter_history_applied ON FILTER_HISTORY(user_id, applied_at DESC);

-- 4. Default Role-Based Widget Configurations (seed data)
-- This provides the default dashboard layouts for each role
CREATE TABLE IF NOT EXISTS DASHBOARD_WIDGET_DEFAULTS (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role VARCHAR(20) NOT NULL,  -- 'admin', 'poweruser', 'leader', 'operator'
    widget_key VARCHAR(50) NOT NULL,
    widget_name VARCHAR(100) NOT NULL,
    widget_order INTEGER NOT NULL DEFAULT 0,
    is_visible BOOLEAN DEFAULT 1,
    default_config TEXT,  -- JSON for widget-specific settings
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role, widget_key)
);

-- Seed default widget configurations for each role
INSERT OR IGNORE INTO DASHBOARD_WIDGET_DEFAULTS (role, widget_key, widget_name, widget_order, is_visible, default_config) VALUES
-- OPERATOR: Focus on data entry and their assigned client
('operator', 'qr_scanner', 'QR Scanner', 1, 1, '{"position": "top-left"}'),
('operator', 'my_kpis', 'My KPIs', 2, 1, '{"kpis": ["efficiency", "quality"]}'),
('operator', 'data_entry_shortcuts', 'Data Entry Shortcuts', 3, 1, '{}'),
('operator', 'recent_entries', 'Recent Entries', 4, 1, '{"limit": 10}'),

-- LEADER: Multi-client overview with team metrics
('leader', 'client_overview', 'Client Overview', 1, 1, '{}'),
('leader', 'team_kpis', 'Team KPIs', 2, 1, '{"kpis": ["efficiency", "quality", "otd"]}'),
('leader', 'efficiency_trends', 'Efficiency Trends', 3, 1, '{"days": 30}'),
('leader', 'attendance_summary', 'Attendance Summary', 4, 1, '{}'),
('leader', 'qr_scanner', 'QR Scanner', 5, 1, '{}'),

-- POWERUSER: Full analytics and predictions
('poweruser', 'all_kpis_grid', 'All KPIs Grid', 1, 1, '{}'),
('poweruser', 'predictions', 'Predictions', 2, 1, '{"forecast_days": 14}'),
('poweruser', 'analytics_deep_dive', 'Analytics Deep Dive', 3, 1, '{}'),
('poweruser', 'reports', 'Reports', 4, 1, '{}'),
('poweruser', 'efficiency_trends', 'Efficiency Trends', 5, 1, '{"days": 90}'),
('poweruser', 'qr_scanner', 'QR Scanner', 6, 1, '{}'),

-- ADMIN: System health plus all features
('admin', 'system_health', 'System Health', 1, 1, '{}'),
('admin', 'user_stats', 'User Statistics', 2, 1, '{}'),
('admin', 'all_kpis_grid', 'All KPIs Grid', 3, 1, '{}'),
('admin', 'audit_log', 'Audit Log', 4, 1, '{"limit": 20}'),
('admin', 'predictions', 'Predictions', 5, 1, '{}'),
('admin', 'qr_scanner', 'QR Scanner', 6, 1, '{}');

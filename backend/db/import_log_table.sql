-- Import Log Table
-- Tracks all CSV uploads and batch imports for auditing and troubleshooting

CREATE TABLE IF NOT EXISTS import_log (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    import_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_name VARCHAR(255),
    rows_attempted INTEGER NOT NULL,
    rows_succeeded INTEGER NOT NULL,
    rows_failed INTEGER NOT NULL,
    error_details TEXT,
    import_type VARCHAR(50) NOT NULL CHECK (import_type IN ('csv_upload', 'batch_import')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for querying by user
CREATE INDEX IF NOT EXISTS idx_import_log_user_id ON import_log(user_id);

-- Index for querying by timestamp
CREATE INDEX IF NOT EXISTS idx_import_log_timestamp ON import_log(import_timestamp DESC);

-- Comments
COMMENT ON TABLE import_log IS 'Audit log for all CSV and batch imports';
COMMENT ON COLUMN import_log.log_id IS 'Primary key';
COMMENT ON COLUMN import_log.user_id IS 'User who performed the import';
COMMENT ON COLUMN import_log.import_timestamp IS 'When the import occurred';
COMMENT ON COLUMN import_log.file_name IS 'Original filename (for CSV uploads)';
COMMENT ON COLUMN import_log.rows_attempted IS 'Total rows in import';
COMMENT ON COLUMN import_log.rows_succeeded IS 'Successfully imported rows';
COMMENT ON COLUMN import_log.rows_failed IS 'Failed rows';
COMMENT ON COLUMN import_log.error_details IS 'JSON string of error details';
COMMENT ON COLUMN import_log.import_type IS 'Type of import: csv_upload or batch_import';

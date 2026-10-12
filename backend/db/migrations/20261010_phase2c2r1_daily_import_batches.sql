CREATE TABLE IF NOT EXISTS daily_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    client_batch_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    service_dates_json TEXT NOT NULL DEFAULT '[]',
    result_json TEXT,
    error_code TEXT,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, client_batch_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_import_batches_status
ON daily_import_batches (tenant_id, status, updated_at);

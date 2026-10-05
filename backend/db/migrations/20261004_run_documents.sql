CREATE TABLE IF NOT EXISTS driver_run_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'generated',
    source_hash TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_url TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    created_by_user_id INTEGER,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT,
    published_by_user_id INTEGER,
    published_by TEXT,
    stale_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, business_date, driver_id, vehicle_id, version)
);

CREATE INDEX IF NOT EXISTS idx_driver_run_documents_group
ON driver_run_documents (tenant_id, business_date, driver_id, vehicle_id, version DESC);

CREATE INDEX IF NOT EXISTS idx_driver_run_documents_driver_published
ON driver_run_documents (tenant_id, driver_id, status, published_at DESC);

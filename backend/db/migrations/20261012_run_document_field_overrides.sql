CREATE TABLE IF NOT EXISTS dispatch_document_field_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    run_group_id TEXT NOT NULL,
    field_id TEXT NOT NULL,
    value_text TEXT,
    updated_by_user_id INTEGER,
    updated_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, run_group_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_document_field_overrides_group
ON dispatch_document_field_overrides(tenant_id, run_group_id, field_id);

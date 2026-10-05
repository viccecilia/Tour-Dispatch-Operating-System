ALTER TABLE driver_run_documents ADD COLUMN reviewed_at TEXT;
ALTER TABLE driver_run_documents ADD COLUMN reviewed_by_user_id INTEGER;
ALTER TABLE driver_run_documents ADD COLUMN reviewed_by TEXT;

CREATE INDEX IF NOT EXISTS idx_driver_run_documents_review
ON driver_run_documents (tenant_id, status, reviewed_at DESC);

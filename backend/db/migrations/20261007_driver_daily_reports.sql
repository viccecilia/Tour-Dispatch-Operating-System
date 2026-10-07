-- Driver daily reports are a driver-owned operational record. They keep a
-- frozen summary of the driver's own published jobs for the business date.
CREATE TABLE IF NOT EXISTS driver_daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    assignment_snapshot_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    rest_hours REAL,
    submitted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, driver_id, business_date),
    FOREIGN KEY(driver_id) REFERENCES drivers(id)
);

CREATE INDEX IF NOT EXISTS idx_driver_daily_reports_tenant_driver_date
    ON driver_daily_reports(tenant_id, driver_id, business_date DESC);

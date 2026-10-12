-- V0.14 Phase 2A: additive document snapshots and future driver records.
-- Existing orders, PDFs and published rows remain untouched and readable.

ALTER TABLE orders ADD COLUMN document_kind TEXT;
ALTER TABLE orders ADD COLUMN applicant_slot INTEGER;
ALTER TABLE orders ADD COLUMN applicant_slot_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN applicant_slot_confirmed_by_user_id INTEGER;
ALTER TABLE orders ADD COLUMN applicant_slot_confirmed_at TEXT;
ALTER TABLE orders ADD COLUMN pickup_source_text TEXT;
ALTER TABLE orders ADD COLUMN dropoff_source_text TEXT;
ALTER TABLE orders ADD COLUMN pickup_parsed_location TEXT;
ALTER TABLE orders ADD COLUMN dropoff_parsed_location TEXT;
ALTER TABLE orders ADD COLUMN pickup_suggested_location TEXT;
ALTER TABLE orders ADD COLUMN dropoff_suggested_location TEXT;
ALTER TABLE orders ADD COLUMN pickup_location_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN dropoff_location_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN fare_jpy REAL;
ALTER TABLE orders ADD COLUMN service_fee_jpy REAL;
ALTER TABLE orders ADD COLUMN document_advance_jpy REAL;
ALTER TABLE orders ADD COLUMN toll_fee_jpy REAL;
ALTER TABLE orders ADD COLUMN price_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN tax_included_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN price_confirmed_by_user_id INTEGER;
ALTER TABLE orders ADD COLUMN price_confirmed_by TEXT;
ALTER TABLE orders ADD COLUMN price_confirmed_at TEXT;
ALTER TABLE orders ADD COLUMN price_snapshot_json TEXT;
ALTER TABLE orders ADD COLUMN area_validation_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE orders ADD COLUMN area_confirmed_by_user_id INTEGER;
ALTER TABLE orders ADD COLUMN area_confirmed_at TEXT;

ALTER TABLE driver_run_documents ADD COLUMN document_id TEXT;
ALTER TABLE driver_run_documents ADD COLUMN document_version_id TEXT;
ALTER TABLE driver_run_documents ADD COLUMN run_group_id TEXT;
ALTER TABLE driver_run_documents ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'generated';
ALTER TABLE driver_run_documents ADD COLUMN document_kind TEXT NOT NULL DEFAULT 'run_packet';
ALTER TABLE driver_run_documents ADD COLUMN snapshot_json TEXT;
ALTER TABLE driver_run_documents ADD COLUMN source_sha256 TEXT;
ALTER TABLE driver_run_documents ADD COLUMN pdf_sha256 TEXT;
ALTER TABLE driver_run_documents ADD COLUMN supersedes_document_version_id TEXT;
ALTER TABLE driver_run_documents ADD COLUMN revoked_at TEXT;
ALTER TABLE driver_run_documents ADD COLUMN revoked_by_user_id INTEGER;
ALTER TABLE driver_run_documents ADD COLUMN revoked_by TEXT;
ALTER TABLE driver_run_documents ADD COLUMN revoke_reason TEXT;

UPDATE driver_run_documents
SET document_id = COALESCE(document_id, 'legacy-document-' || tenant_id || '-' || business_date || '-' || driver_id || '-' || vehicle_id),
    document_version_id = COALESCE(document_version_id, 'legacy-version-' || id),
    run_group_id = COALESCE(run_group_id, 'legacy-run-group-' || tenant_id || '-' || business_date || '-' || driver_id || '-' || vehicle_id),
    lifecycle_status = CASE WHEN status = 'stale' THEN 'superseded' ELSE status END,
    source_sha256 = COALESCE(source_sha256, source_hash);

CREATE UNIQUE INDEX IF NOT EXISTS idx_driver_run_documents_version_id
ON driver_run_documents(document_version_id);

CREATE INDEX IF NOT EXISTS idx_driver_run_documents_run_group
ON driver_run_documents(tenant_id, run_group_id, version DESC);

CREATE TABLE IF NOT EXISTS dispatch_document_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    run_group_id TEXT NOT NULL,
    business_date TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    current_document_version_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, document_id),
    UNIQUE(tenant_id, run_group_id)
);

CREATE TABLE IF NOT EXISTS dispatch_route_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_node_id TEXT NOT NULL,
    run_group_id TEXT NOT NULL,
    document_version_id TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    order_id INTEGER,
    node_type TEXT NOT NULL CHECK(node_type IN ('garage_out', 'pickup', 'via', 'dropoff', 'wait', 'rest', 'garage_in')),
    planned_location TEXT,
    planned_arrival_at TEXT,
    planned_departure_at TEXT,
    load_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, document_version_id, route_node_id)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_route_nodes_group
ON dispatch_route_nodes(tenant_id, run_group_id, document_version_id, sequence_number);

CREATE TABLE IF NOT EXISTS dispatch_route_node_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_node_id TEXT NOT NULL,
    run_group_id TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    actual_arrival_at TEXT,
    actual_departure_at TEXT,
    odometer_km REAL,
    actual_location TEXT,
    actual_node_status TEXT,
    change_reason TEXT,
    entered_by_user_id INTEGER,
    entered_by TEXT,
    entered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, run_group_id, route_node_id)
);

CREATE TABLE IF NOT EXISTS driver_daily_inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    inspection_id TEXT NOT NULL,
    vehicle_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    run_group_id TEXT NOT NULL,
    inspection_items_json TEXT NOT NULL DEFAULT '{}',
    inspection_result TEXT,
    defects TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    inspected_at TEXT,
    submitted_by_user_id INTEGER,
    submitted_by TEXT,
    reviewed_by_user_id INTEGER,
    reviewed_by TEXT,
    reviewed_at TEXT,
    linked_daily_record_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, inspection_id),
    UNIQUE(tenant_id, vehicle_id, business_date, driver_id, run_group_id)
);

CREATE TABLE IF NOT EXISTS dispatch_document_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    document_version_id TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    first_viewed_at TEXT,
    last_viewed_at TEXT,
    first_downloaded_at TEXT,
    last_downloaded_at TEXT,
    confirmed_received_at TEXT,
    confirmed_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, document_version_id, driver_id)
);

CREATE TABLE IF NOT EXISTS dispatch_document_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    document_version_id TEXT,
    event_type TEXT NOT NULL,
    actor_user_id INTEGER,
    actor_role TEXT,
    actor_name TEXT,
    event_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispatch_document_events_version
ON dispatch_document_events(tenant_id, document_version_id, created_at);


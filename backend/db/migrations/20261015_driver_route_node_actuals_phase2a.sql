-- Driver Phase 2A: durable actual-node revisions, source binding and idempotency audit.
-- This is additive. Planned route nodes, orders, assignments and published documents are unchanged.

ALTER TABLE dispatch_route_node_actuals ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE dispatch_route_node_actuals ADD COLUMN source_document_version_id TEXT;
ALTER TABLE dispatch_route_node_actuals ADD COLUMN source_sha256 TEXT;

CREATE TABLE IF NOT EXISTS driver_route_node_actual_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    actor_user_id INTEGER,
    actor_role TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    client_request_id TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    run_group_id TEXT NOT NULL,
    route_node_id TEXT NOT NULL,
    source_document_version_id TEXT NOT NULL,
    source_sha256 TEXT,
    expected_revision INTEGER NOT NULL,
    resulting_revision INTEGER NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    client_recorded_at TEXT,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, driver_id, client_request_id)
);

CREATE INDEX IF NOT EXISTS idx_driver_route_node_actual_requests_node
ON driver_route_node_actual_requests(tenant_id, run_group_id, route_node_id, created_at);

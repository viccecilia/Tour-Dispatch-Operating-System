-- V0.14 Phase 2B: persisted suggestion provenance and editable route-node overrides.
-- Additive only. Published PDF snapshots and historical route nodes remain immutable.

ALTER TABLE orders ADD COLUMN end_time_source TEXT;
ALTER TABLE orders ADD COLUMN end_time_confirmed INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS dispatch_route_node_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    run_group_id TEXT NOT NULL,
    route_node_id TEXT NOT NULL,
    planned_location TEXT,
    planned_arrival_at TEXT,
    planned_departure_at TEXT,
    location_confirmed INTEGER NOT NULL DEFAULT 0,
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    updated_by_user_id INTEGER,
    updated_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, run_group_id, route_node_id)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_route_node_overrides_group
ON dispatch_route_node_overrides(tenant_id, run_group_id, route_node_id);

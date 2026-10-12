-- V0.14 Phase 2C-1: mobile route presets and isolated charter drafts.
-- Additive only. Existing fixed-tour runs, orders and document snapshots remain unchanged.

ALTER TABLE fixed_tour_routes ADD COLUMN description TEXT;
ALTER TABLE fixed_tour_routes ADD COLUMN trip_type TEXT NOT NULL DEFAULT 'day';
ALTER TABLE fixed_tour_routes ADD COLUMN duration_days INTEGER NOT NULL DEFAULT 1;
ALTER TABLE fixed_tour_routes ADD COLUMN created_by_user_id INTEGER;
ALTER TABLE fixed_tour_routes ADD COLUMN updated_by_user_id INTEGER;

ALTER TABLE fixed_tour_route_stops ADD COLUMN preset_node_id TEXT;
ALTER TABLE fixed_tour_route_stops ADD COLUMN day_index INTEGER NOT NULL DEFAULT 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fixed_tour_route_stops_preset_node
ON fixed_tour_route_stops(tenant_id, route_id, preset_node_id);

CREATE TABLE IF NOT EXISTS fixed_tour_charter_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    charter_id TEXT NOT NULL,
    source_preset_id INTEGER,
    source_preset_version INTEGER,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    trip_type TEXT NOT NULL DEFAULT 'day',
    duration_days INTEGER NOT NULL DEFAULT 1,
    business_start_date TEXT NOT NULL,
    business_end_date TEXT NOT NULL,
    route_name TEXT NOT NULL,
    route_snapshot_json TEXT NOT NULL,
    client_request_id TEXT NOT NULL,
    created_by_user_id INTEGER,
    updated_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, charter_id),
    UNIQUE(tenant_id, client_request_id),
    FOREIGN KEY(source_preset_id) REFERENCES fixed_tour_routes(id),
    FOREIGN KEY(order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_fixed_tour_charter_drafts_order
ON fixed_tour_charter_drafts(tenant_id, order_id);


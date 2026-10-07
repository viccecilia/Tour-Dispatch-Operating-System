-- Fixed-tour templates are tenant-local source data.  A materialized run keeps
-- its own snapshot, so later template edits cannot rewrite historical PDFs.
CREATE TABLE IF NOT EXISTS fixed_tour_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_code TEXT NOT NULL,
    route_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    default_start_time TEXT,
    default_end_time TEXT,
    standard_duration_minutes INTEGER,
    operations_business_area TEXT,
    default_order_type TEXT NOT NULL DEFAULT '包车',
    route_summary TEXT,
    document_remark TEXT,
    application_method TEXT NOT NULL DEFAULT 'ウェブサイト',
    applicant_name TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, route_code)
);
CREATE TABLE IF NOT EXISTS fixed_tour_route_stops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL,
    stop_type TEXT NOT NULL,
    location_name TEXT NOT NULL,
    default_arrival_time TEXT,
    default_departure_time TEXT,
    stay_minutes INTEGER,
    note TEXT,
    UNIQUE(route_id, sequence_no),
    FOREIGN KEY(route_id) REFERENCES fixed_tour_routes(id)
);
CREATE TABLE IF NOT EXISTS fixed_tour_route_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    vehicle_type TEXT NOT NULL,
    price_jpy REAL NOT NULL,
    UNIQUE(route_id, vehicle_type),
    FOREIGN KEY(route_id) REFERENCES fixed_tour_routes(id)
);
CREATE TABLE IF NOT EXISTS fixed_tour_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    route_snapshot_json TEXT NOT NULL,
    business_date TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    assignment_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, business_date, driver_id, vehicle_id, route_id),
    FOREIGN KEY(route_id) REFERENCES fixed_tour_routes(id),
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(assignment_id) REFERENCES assignments(id)
);
CREATE TABLE IF NOT EXISTS fixed_tour_run_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL,
    segment_position TEXT NOT NULL,
    pickup_location TEXT NOT NULL,
    dropoff_location TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    same_passenger INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    order_id INTEGER,
    snapshot_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, sequence_no),
    FOREIGN KEY(run_id) REFERENCES fixed_tour_runs(id),
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE INDEX IF NOT EXISTS idx_fixed_tour_routes_tenant_status ON fixed_tour_routes(tenant_id, status, route_name);
CREATE INDEX IF NOT EXISTS idx_fixed_tour_runs_tenant_date ON fixed_tour_runs(tenant_id, business_date);

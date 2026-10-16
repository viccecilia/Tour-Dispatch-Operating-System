-- Driver Phase 2B-0A: durable provisional-task facts and carrier-admin approval history.
-- Additive only.  No existing order, assignment, actual-node, document or finance row is rewritten.

ALTER TABLE orders ADD COLUMN origin_kind TEXT;
ALTER TABLE orders ADD COLUMN origin_provisional_task_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_origin_provisional_unique
ON orders (tenant_id, origin_provisional_task_id)
WHERE origin_kind = 'driver_provisional'
  AND origin_provisional_task_id IS NOT NULL
  AND origin_provisional_task_id <> ''
  AND COALESCE(is_deleted, 0) = 0;

CREATE TABLE IF NOT EXISTS driver_provisional_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    provisional_task_id TEXT NOT NULL,
    display_number TEXT NOT NULL,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    source_assignment_id INTEGER,
    business_date TEXT NOT NULL,
    service_kind TEXT NOT NULL DEFAULT 'other',
    service_source TEXT,
    authorization_source TEXT,
    authorization_evidence TEXT,
    actual_pickup_location TEXT,
    actual_pickup_at TEXT,
    actual_dropoff_location TEXT,
    actual_dropoff_at TEXT,
    odometer_km REAL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN (
            'draft', 'pending_company_confirmation', 'needs_information',
            'approved_new_order', 'approved_linked_order', 'rejected'
        )),
    revision INTEGER NOT NULL DEFAULT 1,
    original_snapshot_json TEXT NOT NULL,
    linked_order_id INTEGER,
    linked_assignment_id INTEGER,
    review_action TEXT,
    review_reason TEXT,
    reviewed_by_user_id INTEGER,
    reviewed_by_name TEXT,
    submitted_at TEXT,
    reviewed_at TEXT,
    created_by_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provisional_task_id),
    UNIQUE(tenant_id, provisional_task_id),
    UNIQUE(tenant_id, display_number),
    FOREIGN KEY(driver_id) REFERENCES drivers(id),
    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY(source_assignment_id) REFERENCES assignments(id),
    FOREIGN KEY(linked_order_id) REFERENCES orders(id),
    FOREIGN KEY(linked_assignment_id) REFERENCES assignments(id),
    FOREIGN KEY(reviewed_by_user_id) REFERENCES users(id),
    FOREIGN KEY(created_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_driver_provisional_tasks_driver
ON driver_provisional_tasks (tenant_id, driver_id, business_date, status, id);

CREATE INDEX IF NOT EXISTS idx_driver_provisional_tasks_admin_queue
ON driver_provisional_tasks (tenant_id, status, business_date, id);

CREATE TABLE IF NOT EXISTS driver_provisional_task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    provisional_task_id TEXT NOT NULL,
    actor_user_id INTEGER NOT NULL,
    actor_role TEXT NOT NULL,
    actor_scope TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    client_request_id TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    expected_revision INTEGER,
    resulting_revision INTEGER NOT NULL,
    before_json TEXT,
    after_json TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    reason TEXT,
    client_recorded_at TEXT,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, actor_user_id, client_request_id),
    FOREIGN KEY(provisional_task_id) REFERENCES driver_provisional_tasks(provisional_task_id),
    FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_driver_provisional_task_events_history
ON driver_provisional_task_events (tenant_id, provisional_task_id, id);

CREATE TRIGGER IF NOT EXISTS trg_driver_provisional_original_snapshot_immutable
BEFORE UPDATE OF original_snapshot_json ON driver_provisional_tasks
WHEN NEW.original_snapshot_json <> OLD.original_snapshot_json
BEGIN
    SELECT RAISE(ABORT, 'provisional_original_snapshot_immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_driver_provisional_no_delete
BEFORE DELETE ON driver_provisional_tasks
BEGIN
    SELECT RAISE(ABORT, 'provisional_task_history_permanent');
END;

CREATE TRIGGER IF NOT EXISTS trg_driver_provisional_event_no_update
BEFORE UPDATE ON driver_provisional_task_events
BEGIN
    SELECT RAISE(ABORT, 'provisional_event_append_only');
END;

CREATE TRIGGER IF NOT EXISTS trg_driver_provisional_event_no_delete
BEFORE DELETE ON driver_provisional_task_events
BEGIN
    SELECT RAISE(ABORT, 'provisional_event_append_only');
END;

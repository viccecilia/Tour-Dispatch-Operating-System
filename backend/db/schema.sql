CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    monthly_price INTEGER NOT NULL DEFAULT 0,
    features_json TEXT NOT NULL DEFAULT '{}',
    limits_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL UNIQUE,
    plan_code TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (plan_code) REFERENCES plans(code)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    feature TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    usage_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'dispatcher', 'operations_manager', 'driver')),
    display_name TEXT NOT NULL,
    phone TEXT,
    profile_type TEXT,
    profile_id INTEGER,
    wx_openid TEXT,
    wx_unionid TEXT,
    wx_bound_at TEXT,
    wx_bind_status TEXT NOT NULL DEFAULT 'unbound',
    last_login_at TEXT,
    password_changed_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    department_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS operator_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER NOT NULL,
    department_id INTEGER,
    team_id INTEGER,
    title TEXT,
    phone TEXT,
    invite_status TEXT NOT NULL DEFAULT 'active',
    invited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disabled_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS dispatch_mobile_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    dispatcher_id INTEGER,
    dispatcher_code TEXT,
    dispatcher_name TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    summary TEXT,
    source_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    agency_code TEXT,
    company_name TEXT,
    name TEXT NOT NULL,
    address TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    responsible_person TEXT,
    contact_email TEXT,
    fax TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    remark TEXT,
    portal_code TEXT,
    is_portal_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    std_name TEXT NOT NULL UNIQUE,
    loc_type TEXT,
    aliases TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER,
    name TEXT NOT NULL,
    driver_code TEXT,
    driver_language TEXT,
    office TEXT,
    driver_external_id TEXT,
    license_number TEXT,
    residence_status TEXT,
    residence_due_date TEXT,
    health_check_remaining_days INTEGER,
    wechat TEXT,
    line TEXT,
    whatsapp TEXT,
    kakao TEXT,
    email TEXT,
    license_expires_at TEXT,
    license_due_date TEXT,
    license_file_url TEXT,
    medical_check_expires_at TEXT,
    health_check_due_date TEXT,
    health_check_file_url TEXT,
    driver_status TEXT,
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    plate_no TEXT UNIQUE,
    plate_number TEXT UNIQUE,
    vehicle_type TEXT,
    vehicle_type_code TEXT,
    plate_short_code TEXT,
    vehicle_color TEXT,
    snow_tire TEXT,
    vehicle_group TEXT,
    first_registration_date TEXT,
    company_registration_date TEXT,
    last_inspection_date TEXT,
    next_inspection_due_date TEXT,
    shaken_due_date TEXT,
    insurance_due_date TEXT,
    inspection_expires_at TEXT,
    insurance_expires_at TEXT,
    maintenance_status TEXT,
    seats INTEGER,
    seat_count INTEGER,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicle_inspection_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    vehicle_id INTEGER NOT NULL,
    inspection_type TEXT NOT NULL DEFAULT 'inspection',
    inspection_date TEXT NOT NULL,
    source TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    oid TEXT UNIQUE,
    order_date TEXT NOT NULL,
    end_date TEXT,
    start_time TEXT,
    end_time TEXT,
    pickup_location TEXT,
    dropoff_location TEXT,
    pickup_latitude REAL,
    pickup_longitude REAL,
    dropoff_latitude REAL,
    dropoff_longitude REAL,
    order_type TEXT,
    vehicle_type TEXT,
    order_note_code TEXT,
    order_source TEXT,
    vehicle_class TEXT,
    vehicle_type_code TEXT,
    plate_short_code TEXT,
    driver_code TEXT,
    driver_language TEXT,
    vehicle_color TEXT,
    snow_tire TEXT,
    passenger_count INTEGER NOT NULL DEFAULT 0,
    luggage_count INTEGER NOT NULL DEFAULT 0,
    guest_name TEXT,
    guest_contact TEXT,
    agency_id INTEGER,
    agency_name TEXT,
    price REAL,
    price_rmb REAL,
    price_jpy REAL,
    fee_remark TEXT,
    collection_amount_jpy REAL,
    driver_advance_amount REAL NOT NULL DEFAULT 0,
    driver_collect_amount REAL NOT NULL DEFAULT 0,
    driver_settlement_amount REAL NOT NULL DEFAULT 0,
    driver_settlement_status TEXT NOT NULL DEFAULT 'pending',
    driver_settlement_note TEXT,
    agency_settlement_status TEXT NOT NULL DEFAULT 'pending',
    parking_fee_jpy REAL,
    other_fee_jpy REAL,
    driver_salary_jpy REAL,
    remark TEXT,
    dispatch_status TEXT NOT NULL DEFAULT 'unassigned',
    execution_status TEXT NOT NULL DEFAULT 'assigned',
    settlement_status TEXT NOT NULL DEFAULT 'pending',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agency_id) REFERENCES agencies(id)
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    order_id INTEGER NOT NULL,
    driver_id INTEGER,
    vehicle_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    execution_status TEXT NOT NULL DEFAULT 'assigned',
    assigned_at TEXT,
    cancelled_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE IF NOT EXISTS driver_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    assignment_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    report_type TEXT NOT NULL,
    report_status TEXT NOT NULL DEFAULT 'submitted',
    report_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latitude REAL,
    longitude REAL,
    location_text TEXT,
    note TEXT,
    photo_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id)
);

CREATE TABLE IF NOT EXISTS driver_evidence_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    assignment_id INTEGER NOT NULL,
    order_id INTEGER,
    driver_id INTEGER NOT NULL,
    evidence_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    note TEXT,
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id)
);

CREATE TABLE IF NOT EXISTS driver_workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    driver_id INTEGER NOT NULL,
    assignment_id INTEGER,
    order_id INTEGER,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL DEFAULT 'submitted',
    latitude REAL,
    longitude REAL,
    location_text TEXT,
    note TEXT,
    event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS driver_expense_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    driver_id INTEGER NOT NULL,
    assignment_id INTEGER,
    order_id INTEGER,
    expense_kind TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'JPY',
    submit_status TEXT NOT NULL DEFAULT 'unsubmitted',
    receipt_photo_url TEXT,
    note TEXT,
    submitted_at TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    actor TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    summary TEXT,
    before_json TEXT,
    after_json TEXT,
    diff_json TEXT,
    source_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_anomaly_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    scan_type TEXT NOT NULL DEFAULT 'governance',
    issue_count INTEGER NOT NULL DEFAULT 0,
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS location_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    driver_id INTEGER NOT NULL,
    vehicle_id INTEGER,
    assignment_id INTEGER,
    order_id INTEGER,
    latitude REAL,
    longitude REAL,
    location_text TEXT,
    source TEXT NOT NULL DEFAULT 'driver',
    reported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    order_id INTEGER,
    assignment_id INTEGER,
    incident_type TEXT NOT NULL DEFAULT 'exception',
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    title TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    delay_minutes INTEGER,
    complaint_contact TEXT,
    accident_location TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'unread',
    target_role TEXT,
    link TEXT,
    source_type TEXT,
    source_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS order_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL DEFAULT 1,
    oid TEXT,
    raw_text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'text',
    parse_status TEXT NOT NULL DEFAULT 'pending',
    order_date TEXT,
    end_date TEXT,
    start_time TEXT,
    end_time TEXT,
    pickup_location TEXT,
    dropoff_location TEXT,
    order_type TEXT,
    vehicle_type TEXT,
    order_note_code TEXT,
    order_source TEXT,
    vehicle_class TEXT,
    vehicle_type_code TEXT,
    plate_short_code TEXT,
    driver_code TEXT,
    driver_language TEXT,
    vehicle_color TEXT,
    snow_tire TEXT,
    passenger_count INTEGER,
    luggage_count INTEGER,
    guest_name TEXT,
    guest_contact TEXT,
    agency_name TEXT,
    price REAL,
    price_rmb REAL,
    price_jpy REAL,
    fee_remark TEXT,
    collection_amount_jpy REAL,
    parking_fee_jpy REAL,
    other_fee_jpy REAL,
    driver_salary_jpy REAL,
    remark TEXT,
    parse_result_json TEXT,
    confirmed_order_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (confirmed_order_id) REFERENCES orders(id)
);

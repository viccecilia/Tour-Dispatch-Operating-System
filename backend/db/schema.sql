CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'dispatcher', 'driver')),
    display_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    contact_phone TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_no TEXT UNIQUE,
    plate_number TEXT UNIQUE,
    vehicle_type TEXT,
    seats INTEGER,
    seat_count INTEGER,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oid TEXT UNIQUE,
    order_date TEXT NOT NULL,
    end_date TEXT,
    start_time TEXT,
    end_time TEXT,
    pickup_location TEXT,
    dropoff_location TEXT,
    order_type TEXT,
    vehicle_type TEXT,
    passenger_count INTEGER NOT NULL DEFAULT 0,
    luggage_count INTEGER NOT NULL DEFAULT 0,
    guest_name TEXT,
    guest_contact TEXT,
    agency_id INTEGER,
    agency_name TEXT,
    price REAL,
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

CREATE TABLE IF NOT EXISTS order_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    passenger_count INTEGER,
    luggage_count INTEGER,
    guest_name TEXT,
    guest_contact TEXT,
    agency_name TEXT,
    price REAL,
    remark TEXT,
    parse_result_json TEXT,
    confirmed_order_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (confirmed_order_id) REFERENCES orders(id)
);

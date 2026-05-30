import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from backend.app.config import DB_PATH, DEFAULT_ADMIN


SCHEMA_PATH = Path(__file__).with_name("schema.sql")

ORDER_COLUMNS: dict[str, str] = {
    "oid": "TEXT",
    "end_date": "TEXT",
    "start_time": "TEXT",
    "end_time": "TEXT",
    "pickup_location": "TEXT",
    "dropoff_location": "TEXT",
    "pickup_latitude": "REAL",
    "pickup_longitude": "REAL",
    "dropoff_latitude": "REAL",
    "dropoff_longitude": "REAL",
    "order_type": "TEXT",
    "vehicle_type": "TEXT",
    "order_note_code": "TEXT",
    "order_source": "TEXT",
    "vehicle_class": "TEXT",
    "vehicle_type_code": "TEXT",
    "plate_short_code": "TEXT",
    "driver_code": "TEXT",
    "driver_language": "TEXT",
    "vehicle_color": "TEXT",
    "snow_tire": "TEXT",
    "passenger_count": "INTEGER NOT NULL DEFAULT 0",
    "luggage_count": "INTEGER NOT NULL DEFAULT 0",
    "guest_name": "TEXT",
    "guest_contact": "TEXT",
    "agency_name": "TEXT",
    "price": "REAL",
    "price_rmb": "REAL",
    "price_jpy": "REAL",
    "fee_remark": "TEXT",
    "collection_amount_jpy": "REAL",
    "driver_advance_amount": "REAL NOT NULL DEFAULT 0",
    "driver_collect_amount": "REAL NOT NULL DEFAULT 0",
    "driver_settlement_amount": "REAL NOT NULL DEFAULT 0",
    "driver_settlement_status": "TEXT NOT NULL DEFAULT 'pending'",
    "driver_settlement_note": "TEXT",
    "agency_settlement_status": "TEXT NOT NULL DEFAULT 'pending'",
    "parking_fee_jpy": "REAL",
    "other_fee_jpy": "REAL",
    "driver_salary_jpy": "REAL",
    "remark": "TEXT",
    "dispatch_status": "TEXT NOT NULL DEFAULT 'unassigned'",
    "execution_status": "TEXT NOT NULL DEFAULT 'assigned'",
    "settlement_status": "TEXT NOT NULL DEFAULT 'pending'",
    "source_channel": "TEXT",
    "created_by_dispatcher": "TEXT",
    "created_by_dispatcher_id": "INTEGER",
    "created_by_dispatcher_code": "TEXT",
    "updated_by_dispatcher": "TEXT",
    "updated_by_dispatcher_id": "INTEGER",
    "updated_by_dispatcher_code": "TEXT",
    "is_deleted": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TEXT",
}

DRIVER_COLUMNS: dict[str, str] = {
    "driver_code": "TEXT",
    "driver_language": "TEXT",
    "office": "TEXT",
    "driver_status": "TEXT",
    "driver_external_id": "TEXT",
    "license_number": "TEXT",
    "residence_status": "TEXT",
    "residence_due_date": "TEXT",
    "health_check_remaining_days": "INTEGER",
    "wechat": "TEXT",
    "line": "TEXT",
    "whatsapp": "TEXT",
    "kakao": "TEXT",
    "email": "TEXT",
    "license_due_date": "TEXT",
    "health_check_due_date": "TEXT",
    "license_file_url": "TEXT",
    "health_check_file_url": "TEXT",
    "license_expires_at": "TEXT",
    "medical_check_expires_at": "TEXT",
    "updated_at": "TEXT",
}

VEHICLE_COLUMNS: dict[str, str] = {
    "plate_number": "TEXT",
    "seat_count": "INTEGER",
    "plate_short_code": "TEXT",
    "vehicle_type_code": "TEXT",
    "vehicle_color": "TEXT",
    "snow_tire": "TEXT",
    "vehicle_group": "TEXT",
    "first_registration_date": "TEXT",
    "company_registration_date": "TEXT",
    "last_inspection_date": "TEXT",
    "next_inspection_due_date": "TEXT",
    "shaken_due_date": "TEXT",
    "insurance_due_date": "TEXT",
    "inspection_expires_at": "TEXT",
    "insurance_expires_at": "TEXT",
    "maintenance_status": "TEXT",
    "updated_at": "TEXT",
}

ASSIGNMENT_COLUMNS: dict[str, str] = {
    "execution_status": "TEXT NOT NULL DEFAULT 'assigned'",
    "assigned_at": "TEXT",
    "cancelled_at": "TEXT",
    "updated_at": "TEXT",
}

DRIVER_REPORT_COLUMNS: dict[str, str] = {
    "assignment_id": "INTEGER",
    "order_id": "INTEGER",
    "driver_id": "INTEGER",
    "report_type": "TEXT",
    "report_status": "TEXT NOT NULL DEFAULT 'submitted'",
    "report_time": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "location_text": "TEXT",
    "note": "TEXT",
    "photo_url": "TEXT",
    "updated_at": "TEXT",
}

LOCATION_LOG_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "driver_id": "INTEGER",
    "vehicle_id": "INTEGER",
    "assignment_id": "INTEGER",
    "order_id": "INTEGER",
    "latitude": "REAL",
    "longitude": "REAL",
    "location_text": "TEXT",
    "source": "TEXT NOT NULL DEFAULT 'driver'",
    "reported_at": "TEXT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}

DRIVER_WORKFLOW_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "driver_id": "INTEGER",
    "assignment_id": "INTEGER",
    "order_id": "INTEGER",
    "event_type": "TEXT",
    "event_status": "TEXT NOT NULL DEFAULT 'submitted'",
    "latitude": "REAL",
    "longitude": "REAL",
    "location_text": "TEXT",
    "note": "TEXT",
    "event_time": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

DRIVER_EXPENSE_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "driver_id": "INTEGER",
    "assignment_id": "INTEGER",
    "order_id": "INTEGER",
    "expense_kind": "TEXT",
    "category": "TEXT",
    "amount": "REAL NOT NULL DEFAULT 0",
    "currency": "TEXT NOT NULL DEFAULT 'JPY'",
    "submit_status": "TEXT NOT NULL DEFAULT 'unsubmitted'",
    "receipt_photo_url": "TEXT",
    "note": "TEXT",
    "submitted_at": "TEXT",
    "confirmed_at": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

INCIDENT_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "order_id": "INTEGER",
    "assignment_id": "INTEGER",
    "incident_type": "TEXT NOT NULL DEFAULT 'exception'",
    "severity": "TEXT NOT NULL DEFAULT 'medium'",
    "status": "TEXT NOT NULL DEFAULT 'open'",
    "title": "TEXT",
    "description": "TEXT",
    "owner": "TEXT",
    "delay_minutes": "INTEGER",
    "complaint_contact": "TEXT",
    "accident_location": "TEXT",
    "resolution": "TEXT",
    "created_at": "TEXT",
    "closed_at": "TEXT",
    "updated_at": "TEXT",
}

NOTIFICATION_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "notification_type": "TEXT",
    "title": "TEXT",
    "body": "TEXT",
    "priority": "TEXT NOT NULL DEFAULT 'normal'",
    "status": "TEXT NOT NULL DEFAULT 'unread'",
    "target_role": "TEXT",
    "link": "TEXT",
    "source_type": "TEXT",
    "source_id": "TEXT",
    "created_at": "TEXT",
    "read_at": "TEXT",
    "updated_at": "TEXT",
}

ORDER_DRAFT_COLUMNS: dict[str, str] = {
    "oid": "TEXT",
    "raw_text": "TEXT",
    "source_type": "TEXT NOT NULL DEFAULT 'text'",
    "parse_status": "TEXT NOT NULL DEFAULT 'pending'",
    "order_date": "TEXT",
    "end_date": "TEXT",
    "start_time": "TEXT",
    "end_time": "TEXT",
    "pickup_location": "TEXT",
    "dropoff_location": "TEXT",
    "order_type": "TEXT",
    "vehicle_type": "TEXT",
    "order_note_code": "TEXT",
    "order_source": "TEXT",
    "vehicle_class": "TEXT",
    "vehicle_type_code": "TEXT",
    "plate_short_code": "TEXT",
    "driver_code": "TEXT",
    "driver_language": "TEXT",
    "vehicle_color": "TEXT",
    "snow_tire": "TEXT",
    "passenger_count": "INTEGER",
    "luggage_count": "INTEGER",
    "guest_name": "TEXT",
    "guest_contact": "TEXT",
    "agency_name": "TEXT",
    "price": "REAL",
    "price_rmb": "REAL",
    "price_jpy": "REAL",
    "fee_remark": "TEXT",
    "collection_amount_jpy": "REAL",
    "parking_fee_jpy": "REAL",
    "other_fee_jpy": "REAL",
    "driver_salary_jpy": "REAL",
    "remark": "TEXT",
    "parse_result_json": "TEXT",
    "confirmed_order_id": "INTEGER",
    "source_channel": "TEXT",
    "created_by_dispatcher": "TEXT",
    "created_by_dispatcher_id": "INTEGER",
    "created_by_dispatcher_code": "TEXT",
    "updated_by_dispatcher": "TEXT",
    "updated_by_dispatcher_id": "INTEGER",
    "updated_by_dispatcher_code": "TEXT",
    "updated_at": "TEXT",
}

LOCATION_COLUMNS: dict[str, str] = {
    "std_name": "TEXT",
    "loc_type": "TEXT",
    "aliases": "TEXT",
    "updated_at": "TEXT",
}

AGENCY_COLUMNS: dict[str, str] = {
    "agency_code": "TEXT",
    "company_name": "TEXT",
    "address": "TEXT",
    "responsible_person": "TEXT",
    "contact_email": "TEXT",
    "fax": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'active'",
    "remark": "TEXT",
    "portal_code": "TEXT",
    "is_portal_enabled": "INTEGER NOT NULL DEFAULT 1",
    "updated_at": "TEXT",
}

BILLING_TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "plans": {
        "code": "TEXT",
        "name": "TEXT",
        "monthly_price": "INTEGER NOT NULL DEFAULT 0",
        "features_json": "TEXT NOT NULL DEFAULT '{}'",
        "limits_json": "TEXT NOT NULL DEFAULT '{}'",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    },
    "tenant_subscriptions": {
        "tenant_id": "INTEGER",
        "plan_code": "TEXT NOT NULL DEFAULT 'free'",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "started_at": "TEXT",
        "expires_at": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    },
    "usage_events": {
        "tenant_id": "INTEGER NOT NULL DEFAULT 1",
        "feature": "TEXT",
        "quantity": "INTEGER NOT NULL DEFAULT 1",
        "usage_date": "TEXT",
        "created_at": "TEXT",
    },
}

USER_COLUMNS: dict[str, str] = {
    "phone": "TEXT",
    "profile_type": "TEXT",
    "profile_id": "INTEGER",
    "wx_openid": "TEXT",
    "wx_unionid": "TEXT",
    "wx_bound_at": "TEXT",
    "wx_bind_status": "TEXT NOT NULL DEFAULT 'unbound'",
    "last_login_at": "TEXT",
    "password_changed_at": "TEXT",
    "updated_at": "TEXT",
}

ORG_TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "departments": {
        "tenant_id": "INTEGER NOT NULL DEFAULT 1",
        "name": "TEXT",
        "description": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    },
    "teams": {
        "tenant_id": "INTEGER NOT NULL DEFAULT 1",
        "department_id": "INTEGER",
        "name": "TEXT",
        "description": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    },
    "operator_profiles": {
        "tenant_id": "INTEGER NOT NULL DEFAULT 1",
        "user_id": "INTEGER",
        "department_id": "INTEGER",
        "team_id": "INTEGER",
        "operator_code": "TEXT",
        "title": "TEXT",
        "phone": "TEXT",
        "invite_status": "TEXT NOT NULL DEFAULT 'active'",
        "invited_at": "TEXT",
        "disabled_at": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    },
}

DISPATCH_MOBILE_AUDIT_COLUMNS: dict[str, str] = {
    "tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "dispatcher_id": "INTEGER",
    "dispatcher_code": "TEXT",
    "dispatcher_name": "TEXT",
    "action": "TEXT",
    "entity_type": "TEXT",
    "entity_id": "TEXT",
    "before_json": "TEXT",
    "after_json": "TEXT",
    "summary": "TEXT",
    "source_path": "TEXT",
    "created_at": "TEXT",
}

TENANT_TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "departments": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "teams": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "operator_profiles": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "agencies": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "locations": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "drivers": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "vehicles": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "orders": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "assignments": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "driver_reports": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "location_logs": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "incidents": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "notifications": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "order_drafts": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "tenant_subscriptions": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
    "usage_events": {"tenant_id": "INTEGER NOT NULL DEFAULT 1"},
}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=TRUNCATE")
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db(seed: bool = True) -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        ensure_user_schema(conn)
        ensure_order_schema(conn)
        ensure_driver_vehicle_schema(conn)
        ensure_assignment_schema(conn)
        ensure_order_draft_schema(conn)
        ensure_driver_report_schema(conn)
        ensure_driver_evidence_schema(conn)
        ensure_location_log_schema(conn)
        ensure_driver_workflow_schema(conn)
        ensure_driver_expense_schema(conn)
        ensure_incident_schema(conn)
        ensure_notification_schema(conn)
        ensure_billing_schema(conn)
        ensure_org_schema(conn)
        ensure_dispatch_mobile_audit_schema(conn)
        ensure_agency_schema(conn)
        ensure_location_schema(conn)
        ensure_tenant_schema(conn)
        if seed:
            seed_tenants(conn)
            seed_admin(conn)
            seed_plans(conn)
            seed_subscriptions(conn)
            seed_organization(conn)
            seed_agency_portals(conn)
            seed_dispatch_resources(conn)
            seed_locations(conn)
        conn.commit()


def ensure_user_schema(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    create_sql = row["sql"] if row else ""
    if create_sql and "operations_manager" not in create_sql:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE TABLE users_new (
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
            )
            """
        )
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        optional = [
            "phone",
            "profile_type",
            "profile_id",
            "wx_openid",
            "wx_unionid",
            "wx_bound_at",
            "wx_bind_status",
            "last_login_at",
            "password_changed_at",
        ]
        select_optional = [
            name if name in existing else ("'unbound'" if name == "wx_bind_status" else "NULL")
            for name in optional
        ]
        conn.execute(
            f"""
            INSERT INTO users_new (
                id, tenant_id, username, password_hash, role, display_name,
                phone, profile_type, profile_id, wx_openid, wx_unionid, wx_bound_at,
                wx_bind_status, last_login_at, password_changed_at,
                is_active, created_at, updated_at
            )
            SELECT
                id, COALESCE(tenant_id, 1), username, password_hash, role, display_name,
                {", ".join(select_optional)},
                COALESCE(is_active, 1), COALESCE(created_at, CURRENT_TIMESTAMP), COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            FROM users
            """
        )
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.execute("PRAGMA foreign_keys=ON")
    _ensure_columns(conn, "users", USER_COLUMNS)
    conn.execute("UPDATE users SET wx_bind_status = COALESCE(NULLIF(wx_bind_status, ''), 'unbound')")


def ensure_order_schema(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(orders)").fetchall()
    }
    for name, definition in ORDER_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {definition}")

    refreshed = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(orders)").fetchall()
    }
    if "pickup_place" in refreshed and "pickup_location" in refreshed:
        conn.execute(
            """
            UPDATE orders
            SET pickup_location = COALESCE(pickup_location, pickup_place)
            WHERE pickup_location IS NULL
            """
        )
    if "dropoff_place" in refreshed and "dropoff_location" in refreshed:
        conn.execute(
            """
            UPDATE orders
            SET dropoff_location = COALESCE(dropoff_location, dropoff_place)
            WHERE dropoff_location IS NULL
            """
        )
    if "status" in refreshed and "dispatch_status" in refreshed:
        conn.execute(
            """
            UPDATE orders
            SET dispatch_status = COALESCE(dispatch_status, status, 'unassigned')
            WHERE dispatch_status IS NULL OR dispatch_status = ''
            """
        )
    conn.execute(
        """
        UPDATE orders
        SET oid = printf('WXO%06d', id)
        WHERE oid IS NULL OR oid = ''
        """
    )
    conn.execute(
        """
        UPDATE orders
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    conn.execute(
        """
        UPDATE orders
        SET end_date = COALESCE(end_date, order_date)
        WHERE end_date IS NULL OR end_date = ''
        """
    )
    conn.execute(
        """
        UPDATE orders
        SET order_note_code = COALESCE(NULLIF(order_note_code, ''), 'D'),
            order_source = COALESCE(NULLIF(order_source, ''), agency_name),
            price_rmb = COALESCE(price_rmb, price)
        """
    )
    refresh_order_oids(conn)


def ensure_driver_vehicle_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "drivers", DRIVER_COLUMNS)
    _ensure_columns(conn, "vehicles", VEHICLE_COLUMNS)
    conn.execute(
        """
        UPDATE drivers
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    conn.execute(
        """
        UPDATE drivers
        SET driver_status = COALESCE(NULLIF(driver_status, ''), status),
            license_due_date = COALESCE(NULLIF(license_due_date, ''), license_expires_at),
            health_check_due_date = COALESCE(NULLIF(health_check_due_date, ''), medical_check_expires_at),
            license_expires_at = COALESCE(NULLIF(license_expires_at, ''), license_due_date),
            medical_check_expires_at = COALESCE(NULLIF(medical_check_expires_at, ''), health_check_due_date)
        """
    )
    conn.execute(
        """
        UPDATE vehicles
        SET plate_number = COALESCE(plate_number, plate_no)
        WHERE plate_number IS NULL OR plate_number = ''
        """
    )
    conn.execute(
        """
        UPDATE vehicles
        SET seat_count = COALESCE(seat_count, seats)
        WHERE seat_count IS NULL
        """
    )
    conn.execute(
        """
        UPDATE vehicles
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    conn.execute(
        """
        UPDATE vehicles
        SET next_inspection_due_date = COALESCE(NULLIF(next_inspection_due_date, ''), inspection_expires_at),
            inspection_expires_at = COALESCE(NULLIF(inspection_expires_at, ''), next_inspection_due_date),
            insurance_due_date = COALESCE(NULLIF(insurance_due_date, ''), insurance_expires_at),
            insurance_expires_at = COALESCE(NULLIF(insurance_expires_at, ''), insurance_due_date)
        """
    )


def ensure_assignment_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "assignments", ASSIGNMENT_COLUMNS)
    conn.execute(
        """
        UPDATE assignments
        SET status = 'active'
        WHERE status = 'planned'
        """
    )
    conn.execute(
        """
        UPDATE assignments
        SET execution_status = COALESCE(execution_status, 'assigned')
        WHERE execution_status IS NULL OR execution_status = ''
        """
    )
    conn.execute(
        """
        UPDATE assignments
        SET assigned_at = COALESCE(assigned_at, created_at, CURRENT_TIMESTAMP)
        WHERE status = 'active' AND (assigned_at IS NULL OR assigned_at = '')
        """
    )


def ensure_order_draft_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "order_drafts", ORDER_DRAFT_COLUMNS)
    conn.execute(
        """
        UPDATE order_drafts
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    conn.execute(
        """
        UPDATE order_drafts
        SET oid = REPLACE(COALESCE(order_date, DATE('now')), '-', '') || '-' || printf('%03d', id)
        WHERE oid IS NULL OR oid = ''
        """
    )
    conn.execute(
        """
        UPDATE order_drafts
        SET end_date = COALESCE(end_date, order_date)
        WHERE end_date IS NULL OR end_date = ''
        """
    )
    conn.execute(
        """
        UPDATE order_drafts
        SET order_note_code = COALESCE(NULLIF(order_note_code, ''), 'D'),
            order_source = COALESCE(NULLIF(order_source, ''), agency_name),
            price_rmb = COALESCE(price_rmb, price)
        """
    )


def ensure_driver_report_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "driver_reports", DRIVER_REPORT_COLUMNS)
    conn.execute(
        """
        UPDATE driver_reports
        SET report_time = COALESCE(report_time, created_at, CURRENT_TIMESTAMP)
        WHERE report_time IS NULL OR report_time = ''
        """
    )
    conn.execute(
        """
        UPDATE driver_reports
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
      )


def ensure_driver_evidence_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(
        conn,
        "driver_evidence_uploads",
        {
            "tenant_id": "INTEGER NOT NULL DEFAULT 1",
            "assignment_id": "INTEGER",
            "order_id": "INTEGER",
            "driver_id": "INTEGER",
            "evidence_type": "TEXT",
            "file_name": "TEXT",
            "file_url": "TEXT",
            "note": "TEXT",
            "uploaded_at": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
    )
    conn.execute(
        """
        UPDATE driver_evidence_uploads
        SET uploaded_at = COALESCE(uploaded_at, created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE uploaded_at IS NULL OR uploaded_at = '' OR updated_at IS NULL OR updated_at = ''
        """
    )


def ensure_location_log_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS location_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            driver_id INTEGER,
            vehicle_id INTEGER,
            assignment_id INTEGER,
            order_id INTEGER,
            latitude REAL,
            longitude REAL,
            location_text TEXT,
            source TEXT NOT NULL DEFAULT 'driver',
            reported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "location_logs", LOCATION_LOG_COLUMNS)
    conn.execute(
        """
        UPDATE location_logs
        SET reported_at = COALESCE(reported_at, created_at, CURRENT_TIMESTAMP)
        WHERE reported_at IS NULL OR reported_at = ''
        """
    )
    conn.execute(
        """
        UPDATE location_logs
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )


def ensure_driver_workflow_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_workflow_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            driver_id INTEGER,
            assignment_id INTEGER,
            order_id INTEGER,
            event_type TEXT,
            event_status TEXT NOT NULL DEFAULT 'submitted',
            latitude REAL,
            longitude REAL,
            location_text TEXT,
            note TEXT,
            event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "driver_workflow_events", DRIVER_WORKFLOW_COLUMNS)
    conn.execute(
        """
        UPDATE driver_workflow_events
        SET event_time = COALESCE(event_time, created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE event_time IS NULL OR event_time = '' OR updated_at IS NULL OR updated_at = ''
        """
    )


def ensure_driver_expense_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_expense_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            driver_id INTEGER,
            assignment_id INTEGER,
            order_id INTEGER,
            expense_kind TEXT,
            category TEXT,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'JPY',
            submit_status TEXT NOT NULL DEFAULT 'unsubmitted',
            receipt_photo_url TEXT,
            note TEXT,
            submitted_at TEXT,
            confirmed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "driver_expense_reports", DRIVER_EXPENSE_COLUMNS)


def ensure_incident_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            order_id INTEGER,
            assignment_id INTEGER,
            incident_type TEXT NOT NULL DEFAULT 'exception',
            severity TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            title TEXT,
            description TEXT,
            owner TEXT,
            delay_minutes INTEGER,
            complaint_contact TEXT,
            accident_location TEXT,
            resolution TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "incidents", INCIDENT_COLUMNS)
    conn.execute(
        """
        UPDATE incidents
        SET status = COALESCE(NULLIF(status, ''), 'open'),
            incident_type = COALESCE(NULLIF(incident_type, ''), 'exception'),
            severity = COALESCE(NULLIF(severity, ''), 'medium'),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        """
    )


def ensure_notification_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "notifications", NOTIFICATION_COLUMNS)
    conn.execute(
        """
        UPDATE notifications
        SET priority = COALESCE(NULLIF(priority, ''), 'normal'),
            status = COALESCE(NULLIF(status, ''), 'unread'),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        """
    )


def ensure_location_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "locations", LOCATION_COLUMNS)
    conn.execute(
        """
        UPDATE locations
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )


def ensure_agency_schema(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn, "agencies", AGENCY_COLUMNS)
    conn.execute(
        """
        UPDATE agencies
        SET is_portal_enabled = COALESCE(is_portal_enabled, 1),
            status = COALESCE(NULLIF(status, ''), 'active'),
            company_name = COALESCE(NULLIF(company_name, ''), name),
            updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE is_portal_enabled IS NULL
           OR status IS NULL OR status = ''
           OR company_name IS NULL OR company_name = ''
           OR updated_at IS NULL OR updated_at = ''
        """
    )


def ensure_billing_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL UNIQUE,
            plan_code TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            feature TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            usage_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for table, columns in BILLING_TABLE_COLUMNS.items():
        _ensure_columns(conn, table, columns)
        if "updated_at" in columns:
            conn.execute(
                f"""
                UPDATE {table}
                SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                WHERE updated_at IS NULL OR updated_at = ''
                """
            )
    conn.execute(
        """
        UPDATE usage_events
        SET usage_date = COALESCE(usage_date, date(created_at), CURRENT_DATE)
        WHERE usage_date IS NULL OR usage_date = ''
        """
    )


def ensure_org_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            department_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL,
            department_id INTEGER,
            team_id INTEGER,
            operator_code TEXT,
            title TEXT,
            phone TEXT,
            invite_status TEXT NOT NULL DEFAULT 'active',
            invited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            disabled_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "users", USER_COLUMNS)
    for table, columns in ORG_TABLE_COLUMNS.items():
        _ensure_columns(conn, table, columns)
        conn.execute(
            f"""
            UPDATE {table}
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL OR updated_at = ''
            """
        )
    conn.execute(
        """
        UPDATE users
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    conn.execute(
        """
        UPDATE operator_profiles
        SET invite_status = CASE
                WHEN user_id IN (SELECT id FROM users WHERE is_active = 0) THEN 'disabled'
                ELSE COALESCE(NULLIF(invite_status, ''), 'active')
            END,
            invited_at = COALESCE(invited_at, created_at, CURRENT_TIMESTAMP)
        """
    )


def ensure_dispatch_mobile_audit_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_mobile_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            dispatcher_id INTEGER,
            dispatcher_code TEXT,
            dispatcher_name TEXT,
            action TEXT,
            entity_type TEXT,
            entity_id TEXT,
            before_json TEXT,
            after_json TEXT,
            summary TEXT,
            source_path TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_columns(conn, "dispatch_mobile_audit_logs", DISPATCH_MOBILE_AUDIT_COLUMNS)


def ensure_tenant_schema(conn: sqlite3.Connection) -> None:
    for table, columns in TENANT_TABLE_COLUMNS.items():
        _ensure_columns(conn, table, columns)
        conn.execute(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL OR tenant_id = 0")


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def refresh_order_oids(conn: sqlite3.Connection) -> None:
    from backend.services.order_number_service import build_order_oid, normalize_vehicle_type_code, plate_short_code

    rows = conn.execute(
        """
        SELECT id, order_date, order_note_code, order_source, vehicle_type, vehicle_type_code
        FROM orders
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY order_date ASC, id ASC
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE orders SET oid = ? WHERE id = ?",
            (f"__OID_REFRESH_{row['id']}__", row["id"]),
        )
    serials: dict[str, int] = {}
    assignments = {
        row["order_id"]: dict(row)
        for row in conn.execute(
            """
            SELECT a.order_id, d.name AS driver_name, v.plate_number, o.driver_code, o.vehicle_type_code, o.vehicle_type
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            LEFT JOIN drivers d ON d.id = a.driver_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            WHERE a.status = 'active'
            """
        ).fetchall()
    }
    for row in rows:
        order_date = row["order_date"] or ""
        date_key = str(order_date).replace("-", "")
        serials[date_key] = serials.get(date_key, 0) + 1
        assignment = assignments.get(row["id"])
        if assignment:
            vehicle_code = assignment.get("vehicle_type_code") or normalize_vehicle_type_code(assignment.get("vehicle_type"))
            oid = build_order_oid(
                order_note_code=row["order_note_code"],
                order_source=row["order_source"],
                order_date=order_date,
                serial=serials[date_key],
                plate_code=plate_short_code(assignment.get("plate_number")),
                driver_code=assignment.get("driver_code"),
                driver_name=assignment.get("driver_name"),
                vehicle_type_code=vehicle_code,
                temporary=False,
            )
            conn.execute(
                """
                UPDATE orders
                SET plate_short_code = COALESCE(NULLIF(plate_short_code, ''), ?),
                    driver_code = COALESCE(NULLIF(driver_code, ''), ?),
                    vehicle_type_code = COALESCE(NULLIF(vehicle_type_code, ''), ?)
                WHERE id = ?
                """,
                (
                    plate_short_code(assignment.get("plate_number")),
                    _driver_code(assignment.get("driver_name")),
                    vehicle_code,
                    row["id"],
                ),
            )
        else:
            oid = build_order_oid(
                order_note_code=row["order_note_code"],
                order_source=row["order_source"],
                order_date=order_date,
                serial=serials[date_key],
                vehicle_type_code=row["vehicle_type_code"],
                vehicle_type=row["vehicle_type"],
                temporary=True,
            )
        conn.execute("UPDATE orders SET oid = ? WHERE id = ?", (oid, row["id"]))


def _plate_code(value: object) -> str:
    chars = re.sub(r"[^0-9A-Za-z]", "", str(value or ""))
    return (chars[-4:] or "CAR0").upper()


def _driver_code(value: object) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    ascii_chars = "".join(ch for ch in text.upper() if "A" <= ch <= "Z")
    if ascii_chars:
        return ascii_chars[:3]
    return text[:2] or "DR"


def seed_admin(conn: sqlite3.Connection) -> None:
    seed_tenants(conn)
    conn.execute(
        """
        INSERT OR IGNORE INTO users (tenant_id, username, password_hash, role, display_name)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            DEFAULT_ADMIN["username"],
            hash_password(DEFAULT_ADMIN["password"]),
            DEFAULT_ADMIN["role"],
            DEFAULT_ADMIN["display_name"],
        ),
    )
    for username, password, role, display_name in [
        ("dispatcher", "dispatcher123", "dispatcher", "调度员"),
        ("operations_manager", "ops123", "operations_manager", "运行管理"),
        ("driver_demo", "driver123", "driver", "司机演示账号"),
        ("tenant2_admin", "admin123", "admin", "第二租户管理员"),
    ]:
        tenant_id = 2 if username == "tenant2_admin" else 1
        conn.execute(
            """
            INSERT OR IGNORE INTO users (tenant_id, username, password_hash, role, display_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tenant_id, username, hash_password(password), role, display_name),
        )


def seed_tenants(conn: sqlite3.Connection) -> None:
    for name, slug in [("Demo Travel Company", "demo"), ("Second Demo Company", "tenant2")]:
        conn.execute(
            """
            INSERT OR IGNORE INTO tenants (name, slug, status)
            VALUES (?, ?, 'active')
            """,
            (name, slug),
        )


def seed_plans(conn: sqlite3.Connection) -> None:
    plans = [
        (
            "free",
            "Free",
            0,
            {
                "dashboard": True,
                "orders": True,
                "parser": True,
                "dispatch": False,
                "calendar": False,
                "driver_monitor": False,
                "vehicles": False,
                "finance": False,
                "incidents": False,
                "ai_parser_v2": False,
            },
            {"orders_per_month": 100, "parser_runs_per_month": 50, "drivers": 3, "vehicles": 3},
        ),
        (
            "plus",
            "Plus",
            9900,
            {
                "dashboard": True,
                "orders": True,
                "parser": True,
                "dispatch": True,
                "calendar": True,
                "driver_monitor": True,
                "vehicles": True,
                "finance": False,
                "incidents": True,
                "ai_parser_v2": True,
            },
            {"orders_per_month": 1500, "parser_runs_per_month": 1000, "drivers": 30, "vehicles": 30},
        ),
        (
            "pro",
            "Pro",
            29900,
            {
                "dashboard": True,
                "orders": True,
                "parser": True,
                "dispatch": True,
                "calendar": True,
                "driver_monitor": True,
                "vehicles": True,
                "finance": True,
                "incidents": True,
                "ai_parser_v2": True,
                "fleet_tracking": True,
            },
            {"orders_per_month": 10000, "parser_runs_per_month": 5000, "drivers": 200, "vehicles": 200},
        ),
    ]
    for code, name, price, features, limits in plans:
        conn.execute(
            """
            INSERT INTO plans (code, name, monthly_price, features_json, limits_json, status, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                monthly_price = excluded.monthly_price,
                features_json = excluded.features_json,
                limits_json = excluded.limits_json,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            """,
            (code, name, price, json.dumps(features, ensure_ascii=False), json.dumps(limits, ensure_ascii=False)),
        )


def seed_subscriptions(conn: sqlite3.Connection) -> None:
    for tenant_id, plan_code in [(1, "pro"), (2, "free")]:
        conn.execute(
            """
            INSERT INTO tenant_subscriptions (tenant_id, plan_code, status, started_at, updated_at)
            VALUES (?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id) DO UPDATE SET
                plan_code = COALESCE(NULLIF(tenant_subscriptions.plan_code, ''), excluded.plan_code),
                status = COALESCE(NULLIF(tenant_subscriptions.status, ''), 'active'),
                updated_at = CURRENT_TIMESTAMP
            """,
            (tenant_id, plan_code),
        )


def seed_organization(conn: sqlite3.Connection) -> None:
    department_specs = [
        (1, "Operations", "Dispatch and daily control room"),
        (1, "Driver Operations", "Driver execution and reporting"),
        (1, "Back Office", "Finance and administration"),
        (2, "Operations", "Tenant 2 operations"),
    ]
    for tenant_id, name, description in department_specs:
        conn.execute(
            """
            INSERT INTO departments (tenant_id, name, description, status, updated_at)
            SELECT ?, ?, ?, 'active', CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM departments WHERE tenant_id = ? AND name = ?
            )
            """,
            (tenant_id, name, description, tenant_id, name),
        )

    def department_id(tenant_id: int, name: str) -> int | None:
        row = conn.execute(
            "SELECT id FROM departments WHERE tenant_id = ? AND name = ?",
            (tenant_id, name),
        ).fetchone()
        return row["id"] if row else None

    team_specs = [
        (1, department_id(1, "Operations"), "Dispatch Team", "Order intake and dispatch"),
        (1, department_id(1, "Driver Operations"), "Driver Team", "Driver execution"),
        (1, department_id(1, "Back Office"), "Admin Team", "Billing and system admin"),
        (2, department_id(2, "Operations"), "Dispatch Team", "Tenant 2 dispatch"),
    ]
    for tenant_id, dept_id, name, description in team_specs:
        conn.execute(
            """
            INSERT INTO teams (tenant_id, department_id, name, description, status, updated_at)
            SELECT ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM teams WHERE tenant_id = ? AND name = ?
            )
            """,
            (tenant_id, dept_id, name, description, tenant_id, name),
        )

    role_defaults = {
        "admin": ("Back Office", "Admin Team", "Admin"),
        "dispatcher": ("Operations", "Dispatch Team", "Dispatcher"),
        "operations_manager": ("Driver Operations", "Driver Team", "Operations Manager"),
        "driver": ("Driver Operations", "Driver Team", "Driver"),
    }
    users = conn.execute(
        """
        SELECT id, tenant_id, role, is_active
        FROM users
        """
    ).fetchall()
    for user in users:
        dept_name, team_name, title = role_defaults.get(user["role"], role_defaults["dispatcher"])
        dept = conn.execute(
            "SELECT id FROM departments WHERE tenant_id = ? AND name = ?",
            (user["tenant_id"], dept_name),
        ).fetchone()
        team = conn.execute(
            "SELECT id FROM teams WHERE tenant_id = ? AND name = ?",
            (user["tenant_id"], team_name),
        ).fetchone()
        existing = conn.execute(
            "SELECT id FROM operator_profiles WHERE tenant_id = ? AND user_id = ? LIMIT 1",
            (user["tenant_id"], user["id"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE operator_profiles
                SET invite_status = CASE WHEN ? = 0 THEN 'disabled' ELSE COALESCE(NULLIF(invite_status, ''), 'active') END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user["is_active"], existing["id"]),
            )
            continue
        conn.execute(
            """
            INSERT INTO operator_profiles (
                tenant_id, user_id, department_id, team_id, title, invite_status, invited_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                user["tenant_id"],
                user["id"],
                dept["id"] if dept else None,
                team["id"] if team else None,
                title,
                "active" if user["is_active"] else "disabled",
            ),
        )


def seed_agency_portals(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, tenant_id, name, agency_code
        FROM agencies
        WHERE portal_code IS NULL OR portal_code = ''
        """
    ).fetchall()
    for row in rows:
        prefix = (row["agency_code"] or "AG").upper()
        code = f"{prefix}{row['tenant_id']}{row['id']:04d}"
        conn.execute(
            """
            UPDATE agencies
            SET portal_code = ?,
                is_portal_enabled = COALESCE(is_portal_enabled, 1)
            WHERE id = ? AND tenant_id = ?
            """,
            (code, row["id"], row["tenant_id"]),
        )


def seed_dispatch_resources(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE drivers
        SET status = 'inactive',
            driver_status = 'inactive',
            updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = 1
          AND phone IN ('090-1000-0001', '090-1000-0002', '090-1000-0003')
        """
    )
    drivers = [
        ("姚博", "YB", "英语可", "本社", "090-6058-7891", "available"),
        ("李力", "LL", "", "本社", "080-4238-1388", "available"),
        ("万強", "WQ", "英语可", "本社", "070-2303-6669", "available"),
        ("夏天忻", "XTX", "", "本社", "080-4034-1775", "available"),
        ("周伝波", "ZCB", "", "本社", "090-9613-8613", "available"),
        ("姜小涛", "JXT", "", "本社", "070-8508-9919", "available"),
        ("高弘强", "GHQ", "", "京都営業所", "080-4867-0502", "available"),
        ("李成志", "LCZ", "韩语可", "本社", "080-4647-9188", "available"),
        ("王啓超", "WQC", "英语可", "本社", "090-4273-9895", "available"),
        ("胡東鍇", "HDK", "英语可", "本社", "090-3660-0829", "available"),
        ("呂雲龍", "LYL", "", "本社", "080-2952-0888", "available"),
        ("先山武志", "SKYM", "英语可", "本社", "090-7486-8828", "available"),
        ("白石賢志", "SRIS", "", "京都営業所", "070-2015-1485", "available"),
        ("富塚紀子", "TOYO", "", "京都営業所", "080-3142-8725", "available"),
        ("山下洋子／李洋", "LY", "", "京都営業所", "080-5328-6390", "available"),
    ]
    for name, driver_code, driver_language, office, phone, status in drivers:
        exists = conn.execute(
            "SELECT 1 FROM drivers WHERE tenant_id = 1 AND phone = ? LIMIT 1",
            (phone,),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO drivers (
                    tenant_id, name, driver_code, driver_language, office, phone, status, driver_status
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, driver_code, driver_language, office, phone, status, status),
            )
        else:
            conn.execute(
                """
                UPDATE drivers
                SET name = ?,
                    driver_code = ?,
                    driver_language = ?,
                    office = ?,
                    status = ?,
                    driver_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = 1 AND phone = ?
                """,
                (name, driver_code, driver_language, office, status, status, phone),
            )
        conn.execute(
            """
            UPDATE drivers
            SET status = 'deleted',
                driver_status = 'deleted',
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = 1
              AND phone = ?
              AND id NOT IN (SELECT MIN(id) FROM drivers WHERE tenant_id = 1 AND phone = ?)
            """,
            (phone, phone),
        )

    vehicles = [
        ("品川500あ1001", "商务车", 6, "available"),
        ("品川500あ1002", "中巴", 18, "available"),
        ("品川500あ1003", "商务车", 6, "maintenance"),
    ]
    vehicles = []
    for plate_number, vehicle_type, seat_count, status in vehicles:
        exists = conn.execute(
            """
            SELECT 1
            FROM vehicles
            WHERE tenant_id = 1 AND (plate_number = ? OR plate_no = ?)
            LIMIT 1
            """,
            (plate_number, plate_number),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO vehicles (tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                """,
                (plate_number, plate_number, vehicle_type, seat_count, seat_count, status),
            )


def seed_locations(conn: sqlite3.Connection) -> None:
    from backend.services.location_service import seed_default_locations

    seed_default_locations(conn)


def table_counts(tables: Iterable[str]) -> dict[str, int]:
    with get_connection() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]
            for table in tables
        }

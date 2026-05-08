import hashlib
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
    "order_type": "TEXT",
    "vehicle_type": "TEXT",
    "passenger_count": "INTEGER NOT NULL DEFAULT 0",
    "luggage_count": "INTEGER NOT NULL DEFAULT 0",
    "guest_name": "TEXT",
    "guest_contact": "TEXT",
    "agency_name": "TEXT",
    "price": "REAL",
    "remark": "TEXT",
    "dispatch_status": "TEXT NOT NULL DEFAULT 'unassigned'",
    "execution_status": "TEXT NOT NULL DEFAULT 'assigned'",
    "settlement_status": "TEXT NOT NULL DEFAULT 'pending'",
    "is_deleted": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TEXT",
}

DRIVER_COLUMNS: dict[str, str] = {
    "updated_at": "TEXT",
}

VEHICLE_COLUMNS: dict[str, str] = {
    "plate_number": "TEXT",
    "seat_count": "INTEGER",
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
    "passenger_count": "INTEGER",
    "luggage_count": "INTEGER",
    "guest_name": "TEXT",
    "guest_contact": "TEXT",
    "agency_name": "TEXT",
    "price": "REAL",
    "remark": "TEXT",
    "parse_result_json": "TEXT",
    "confirmed_order_id": "INTEGER",
    "updated_at": "TEXT",
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
        ensure_order_schema(conn)
        ensure_driver_vehicle_schema(conn)
        ensure_assignment_schema(conn)
        ensure_order_draft_schema(conn)
        ensure_driver_report_schema(conn)
        if seed:
            seed_admin(conn)
            seed_dispatch_resources(conn)
        conn.commit()


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


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def refresh_order_oids(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, order_date
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
            SELECT a.order_id, d.name AS driver_name, v.plate_number
            FROM assignments a
            LEFT JOIN drivers d ON d.id = a.driver_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            WHERE a.status = 'active'
            """
        ).fetchall()
    }
    for row in rows:
        order_date = row["order_date"] or ""
        date_text = str(order_date).replace("-", "")
        if len(date_text) != 8 or not date_text.isdigit():
            date_text = "ORDER"
        serials[date_text] = serials.get(date_text, 0) + 1
        oid = f"{date_text}-{serials[date_text]:03d}"
        assignment = assignments.get(row["id"])
        if assignment:
            oid = f"{oid}-{_plate_code(assignment.get('plate_number'))}-{_driver_code(assignment.get('driver_name'))}"
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
    conn.execute(
        """
        INSERT OR IGNORE INTO users (username, password_hash, role, display_name)
        VALUES (?, ?, ?, ?)
        """,
        (
            DEFAULT_ADMIN["username"],
            hash_password(DEFAULT_ADMIN["password"]),
            DEFAULT_ADMIN["role"],
            DEFAULT_ADMIN["display_name"],
        ),
    )


def seed_dispatch_resources(conn: sqlite3.Connection) -> None:
    drivers = [
        ("田中司机", "090-1000-0001", "available"),
        ("佐藤司机", "090-1000-0002", "available"),
        ("高桥司机", "090-1000-0003", "inactive"),
    ]
    for name, phone, status in drivers:
        exists = conn.execute(
            "SELECT 1 FROM drivers WHERE phone = ? LIMIT 1",
            (phone,),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO drivers (name, phone, status)
                VALUES (?, ?, ?)
                """,
                (name, phone, status),
            )
        conn.execute(
            """
            UPDATE drivers
            SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
            WHERE phone = ?
              AND id NOT IN (SELECT MIN(id) FROM drivers WHERE phone = ?)
            """,
            (phone, phone),
        )

    vehicles = [
        ("品川500あ1001", "商务车", 6, "available"),
        ("品川500あ1002", "中巴", 18, "available"),
        ("品川500あ1003", "商务车", 6, "maintenance"),
    ]
    for plate_number, vehicle_type, seat_count, status in vehicles:
        exists = conn.execute(
            """
            SELECT 1
            FROM vehicles
            WHERE plate_number = ? OR plate_no = ?
            LIMIT 1
            """,
            (plate_number, plate_number),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO vehicles (plate_no, plate_number, vehicle_type, seats, seat_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plate_number, plate_number, vehicle_type, seat_count, seat_count, status),
            )


def table_counts(tables: Iterable[str]) -> dict[str, int]:
    with get_connection() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]
            for table in tables
        }

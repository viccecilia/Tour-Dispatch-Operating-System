import argparse
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


TRIAL_DB = ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"
SOURCE_DB = ROOT_DIR / "runtime" / "wx_dispatch.sqlite3"

TRANSACTION_TABLES = [
    "audit_logs",
    "dispatch_mobile_audit_logs",
    "data_anomaly_scans",
    "notifications",
    "workflow_runs",
    "usage_events",
    "location_logs",
    "driver_reports",
    "driver_evidence_uploads",
    "driver_workflow_events",
    "driver_expense_reports",
    "assignments",
    "order_drafts",
    "incidents",
    "orders",
]

MASTER_TABLES = [
    "drivers",
    "vehicles",
    "agencies",
    "locations",
    "vehicle_inspection_records",
]

COUNT_TABLES = [
    "users",
    "drivers",
    "vehicles",
    "agencies",
    "locations",
    "orders",
    "assignments",
    "order_drafts",
    "driver_reports",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the internal-test trial database.")
    parser.add_argument("--db", default=str(TRIAL_DB), help="Trial SQLite database path.")
    parser.add_argument("--source", default=str(SOURCE_DB), help="Optional local source DB for real resource tables.")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the trial database.")
    parser.add_argument("--keep-transactions", action="store_true", help="Keep runtime transaction tables.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    source_path = Path(args.source).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if args.reset and db_path.exists():
        db_path.unlink()

    os.environ["WX_DISPATCH_DB"] = str(db_path)
    os.environ["WX_DISPATCH_DEMO_MODE"] = "false"
    os.environ["WX_DISPATCH_TRIAL_MODE"] = "true"
    os.environ["WX_DISPATCH_RESET_DEMO_ON_START"] = "false"

    from backend.db.database import get_connection, hash_password, init_db, table_counts

    init_db(seed=True)
    if source_path.exists() and source_path.resolve() != db_path.resolve():
        _copy_master_tables(source_path, db_path)

    with get_connection() as conn:
        if not args.keep_transactions:
            for table in TRANSACTION_TABLES:
                if _table_exists(conn, table):
                    conn.execute(f"DELETE FROM {table}")
        _keep_only_real_drivers(conn)
        _keep_only_real_vehicles(conn)
        _ensure_trial_accounts(conn, hash_password)
        conn.commit()

    print(f"trial_database={db_path}")
    print(f"source_database={source_path if source_path.exists() else 'none'}")
    print(table_counts([table for table in COUNT_TABLES if _table_exists_runtime(table)]))
    print("trial_database_ready=true")
    print("trial_credentials=admin/admin123, dispatcher 090-72-0001/0001, operations 090-73-0001/0001, driver phone/last4")
    print("super_wechat_id=zongzou")


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone() is not None


def _table_exists_runtime(table: str) -> bool:
    from backend.db.database import get_connection

    with get_connection() as conn:
        return _table_exists(conn, table)


def _copy_master_tables(source_path: Path, trial_path: Path) -> None:
    with _connect(source_path) as source, _connect(trial_path) as trial:
        for table in MASTER_TABLES:
            if not _table_exists(source, table) or not _table_exists(trial, table):
                continue
            source_cols = [row["name"] for row in source.execute(f"PRAGMA table_info({table})").fetchall()]
            trial_cols = [row["name"] for row in trial.execute(f"PRAGMA table_info({table})").fetchall()]
            cols = [col for col in source_cols if col in trial_cols]
            if not cols:
                continue
            trial.execute(f"DELETE FROM {table}")
            placeholders = ", ".join(["?"] * len(cols))
            col_sql = ", ".join(cols)
            rows = source.execute(f"SELECT {col_sql} FROM {table}").fetchall()
            for row in rows:
                trial.execute(
                    f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})",
                    [row[col] for col in cols],
                )
        trial.commit()


def _normalize_phone(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _username_from_phone(phone: str) -> str:
    return _normalize_phone(phone)


def _password_tail(phone: str) -> str:
    digits = _normalize_phone(phone)
    return digits[-4:] if len(digits) >= 4 else "1234"


def _keep_only_real_drivers(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "drivers"):
        return
    rows = conn.execute("SELECT id, name, phone, driver_code FROM drivers WHERE tenant_id = 1").fetchall()
    for row in rows:
        phone = str(row["phone"] or "")
        code = str(row["driver_code"] or "").strip()
        name = str(row["name"] or "")
        keep = phone.startswith("0") and bool(code) and not re.match(r"^R\d+", name)
        if not keep:
            conn.execute("DELETE FROM drivers WHERE id = ?", (row["id"],))


def _keep_only_real_vehicles(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "vehicles"):
        return
    rows = conn.execute("SELECT id, plate_number, plate_no FROM vehicles WHERE tenant_id = 1").fetchall()
    for row in rows:
        plate = str(row["plate_number"] or row["plate_no"] or "")
        if not plate.startswith("なにわ"):
            conn.execute("DELETE FROM vehicles WHERE id = ?", (row["id"],))
    conn.execute(
        """
        UPDATE vehicles
        SET status = CASE WHEN status IN ('inactive', 'deleted') THEN 'available' ELSE COALESCE(status, 'available') END,
            updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = 1
        """
    )


def _ensure_trial_accounts(conn: sqlite3.Connection, hash_password) -> None:
    _upsert_user(conn, hash_password, "admin", "admin123", "admin", "系统管理员", "090-00-000001")
    _upsert_operator(conn, hash_password, "090-72-0001", "调度测试", "dispatcher")
    _upsert_operator(conn, hash_password, "090-73-0001", "运行管理测试", "operations_manager")
    for driver in conn.execute(
        """
        SELECT id, name, phone
        FROM drivers
        WHERE tenant_id = 1 AND COALESCE(TRIM(phone), '') != ''
        ORDER BY id
        """
    ).fetchall():
        username = _username_from_phone(driver["phone"])
        password = _password_tail(driver["phone"])
        user_id = _upsert_user(conn, hash_password, username, password, "driver", driver["name"], driver["phone"], "driver", driver["id"])
        conn.execute("UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, driver["id"]))


def _upsert_operator(conn: sqlite3.Connection, hash_password, phone: str, name: str, role: str) -> int:
    username = _username_from_phone(phone)
    user_id = _upsert_user(conn, hash_password, username, _password_tail(phone), role, name, phone, "operator", None)
    row = conn.execute("SELECT id FROM operator_profiles WHERE tenant_id = 1 AND phone = ? LIMIT 1", (phone,)).fetchone()
    if row:
        profile_id = row["id"]
        conn.execute(
            """
            UPDATE operator_profiles
            SET user_id = ?, title = ?, invite_status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id, role, profile_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO operator_profiles (tenant_id, user_id, title, phone, invite_status, updated_at)
            VALUES (1, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            """,
            (user_id, role, phone),
        )
        profile_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute("UPDATE users SET profile_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (profile_id, user_id))
    return user_id


def _upsert_user(
    conn: sqlite3.Connection,
    hash_password,
    username: str,
    password: str,
    role: str,
    display_name: str,
    phone: str,
    profile_type: str | None = None,
    profile_id: int | None = None,
) -> int:
    row = conn.execute("SELECT id FROM users WHERE tenant_id = 1 AND username = ? LIMIT 1", (username,)).fetchone()
    if row:
        user_id = row["id"]
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?,
                role = ?,
                display_name = ?,
                phone = ?,
                profile_type = ?,
                profile_id = COALESCE(?, profile_id),
                is_active = 1,
                wx_bind_status = COALESCE(NULLIF(wx_bind_status, ''), 'unbound'),
                password_changed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (hash_password(password), role, display_name, phone, profile_type, profile_id, user_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO users (
                tenant_id, username, password_hash, role, display_name, phone,
                profile_type, profile_id, wx_bind_status, is_active,
                password_changed_at, updated_at
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 'unbound', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (username, hash_password(password), role, display_name, phone, profile_type, profile_id),
        )
        user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return int(user_id)


if __name__ == "__main__":
    main()

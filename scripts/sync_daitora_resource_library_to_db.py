from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.resource_library_service import list_resource_library


DEFAULT_DB = ROOT / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"
TENANT_ID = 8204
TENANT_NAME = "Daitora"
TENANT_SLUG = "DTR"
ADMIN_USERNAME = "08046447554"
OPS_USERNAME = "08046447555"
ADMIN_PASSWORD = "447554"
HIDDEN_VEHICLE_CODES = {"7721", "3724"}


def sha256_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def digits(value: Any) -> str:
    return "".join(re.findall(r"\d+", str(value or "")))


def plate_suffix(value: Any) -> str:
    raw = digits(value)
    if not raw:
        return ""
    suffix = raw[-4:]
    return str(int(suffix)) if suffix else ""


def first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def parse_date_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    iso = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if iso:
        return f"{int(iso.group(1)):04d}-{int(iso.group(2)):02d}-{int(iso.group(3)):02d}"
    jp = re.search(r"令和\s*(\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})", text)
    if jp:
        return f"{2018 + int(jp.group(1)):04d}-{int(jp.group(2)):02d}-{int(jp.group(3)):02d}"
    compact = re.search(r"\bR\s*(\d{1,2})(\d{2})(\d{2})\b", text, re.IGNORECASE)
    if compact:
        return f"{2018 + int(compact.group(1)):04d}-{int(compact.group(2)):02d}-{int(compact.group(3)):02d}"
    slash = re.search(r"\bR\s*(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{1,2})", text, re.IGNORECASE)
    if slash:
        return f"{2018 + int(slash.group(1)):04d}-{int(slash.group(2)):02d}-{int(slash.group(3)):02d}"
    return ""


def parse_latest_date(value: Any) -> str:
    text = str(value or "")
    dates: list[str] = []
    for part in re.split(r"[/,、\s]+", text):
        parsed = parse_date_token(part)
        if parsed:
            dates.append(parsed)
    parsed_whole = parse_date_token(text)
    if parsed_whole:
        dates.append(parsed_whole)
    return max(dates) if dates else ""


def add_one_year(iso: str) -> str:
    if not iso:
        return ""
    base = datetime.strptime(iso, "%Y-%m-%d").date()
    try:
        return base.replace(year=base.year + 1).isoformat()
    except ValueError:
        return base.replace(year=base.year + 1, day=28).isoformat()


def normalize_office(value: str) -> str:
    text = str(value or "").strip()
    if "京都" in text:
        return "京都営業所"
    return "本社"


def normalize_driver_status(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"retired", "deleted", "resigned", "離職", "离职"}:
        return "retired"
    if text in {"resting", "leave", "vacation", "休假"}:
        return "resting"
    return "available"


def normalize_vehicle_status(value: str, suffix: str) -> str:
    if suffix in HIDDEN_VEHICLE_CODES:
        return "retired"
    text = str(value or "").strip().lower()
    if text in {"retired", "deleted", "removed", "廃車", "废车"}:
        return "retired"
    if text in {"maintenance", "repair", "修理中", "维修"}:
        return "maintenance"
    return "available"


def normalize_vehicle_type_code(vehicle_type: str) -> str:
    text = str(vehicle_type or "").lower()
    if "alphard" in text or "アルファ" in text:
        return "alphard"
    if "hiace" in text or "nissan" in text or "mercedes" in text:
        return "hiace"
    return "hiace"


def normalize_seat_count(vehicle_type: str) -> int:
    return 5 if normalize_vehicle_type_code(vehicle_type) == "alphard" else 10


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def insert_or_update(conn: sqlite3.Connection, table: str, keys: dict[str, Any], values: dict[str, Any]) -> int:
    cols = table_columns(conn, table)
    payload = {k: v for k, v in values.items() if k in cols}
    row = None
    clauses = []
    params = []
    for key, value in keys.items():
        if key in cols and value not in (None, ""):
            clauses.append(f"{key} = ?")
            params.append(value)
    if clauses:
        row = conn.execute(f"SELECT id FROM {table} WHERE {' AND '.join(clauses)} LIMIT 1", params).fetchone()
    if not row and table == "vehicles":
        fallback_clauses = []
        fallback_params = []
        for key in ("plate_no", "plate_number", "plate_short_code"):
            value = values.get(key) or keys.get(key)
            if key in cols and value not in (None, ""):
                fallback_clauses.append(f"{key} = ?")
                fallback_params.append(value)
        if fallback_clauses:
            row = conn.execute(f"SELECT id FROM {table} WHERE {' OR '.join(fallback_clauses)} LIMIT 1", fallback_params).fetchone()
    if not row and table == "drivers":
        fallback_clauses = []
        fallback_params = []
        for key in ("driver_external_id", "phone"):
            value = values.get(key) or keys.get(key)
            if key in cols and value not in (None, ""):
                fallback_clauses.append(f"{key} = ?")
                fallback_params.append(value)
        if fallback_clauses:
            row = conn.execute(f"SELECT id FROM {table} WHERE {' OR '.join(fallback_clauses)} LIMIT 1", fallback_params).fetchone()
    if row:
        item_id = int(row["id"])
        if payload:
            assignments = ", ".join(f"{key} = ?" for key in payload)
            conn.execute(f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [*payload.values(), item_id])
        return item_id
    if "created_at" in cols:
        payload.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    if "updated_at" in cols:
        payload.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))
    columns = ", ".join(payload)
    marks = ", ".join("?" for _ in payload)
    cur = conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(payload.values()))
    return int(cur.lastrowid)


def ensure_tenant(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM tenants WHERE id = ?", (TENANT_ID,)).fetchone()
    if not row:
        row = conn.execute("SELECT id FROM tenants WHERE slug = ? OR name = ?", (TENANT_SLUG, TENANT_NAME)).fetchone()
    if row:
        tenant_id = int(row["id"])
        conn.execute(
            "UPDATE tenants SET name = ?, slug = ?, status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (TENANT_NAME, TENANT_SLUG, tenant_id),
        )
        return tenant_id
    conn.execute(
        "INSERT INTO tenants (id, name, slug, status, created_at, updated_at) VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (TENANT_ID, TENANT_NAME, TENANT_SLUG),
    )
    return TENANT_ID


def ensure_user(
    conn: sqlite3.Connection,
    username: str,
    role: str,
    display_name: str,
    phone: str = "",
    profile_type: str | None = None,
    profile_id: int | None = None,
    password: str | None = None,
) -> int:
    password_hash = sha256_password(password or digits(username)[-6:] or "123456")
    values = {
        "tenant_id": TENANT_ID,
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "display_name": display_name,
        "phone": phone or username,
        "profile_type": profile_type,
        "profile_id": profile_id,
        "is_active": 1,
    }
    return insert_or_update(conn, "users", {"username": username}, values)


def sync_drivers(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    active_keys: set[str] = set()
    for row in rows:
        name = first(row, "運転手名", "司机姓名", "name", "driver_name")
        if not name:
            continue
        driver_code = first(row, "運転手ID", "司机代码", "driver_code", "code")
        phone = first(row, "携帯電話番号", "电话", "phone")
        username = digits(phone) or driver_code
        office = normalize_office(first(row, "所属営業所", "office"))
        health_date = parse_date_token(first(row, "健康诊断日期", "健康診断日"))
        license_due = parse_date_token(first(row, "免许有効期限", "免許有効期限"))
        residence_due = parse_date_token(first(row, "再留期限有效日期", "在留期限"))
        health_due = add_one_year(health_date)
        status = normalize_driver_status(first(row, "状態", "status", "driver_status"))
        active_keys.add(driver_code or phone or name)
        values = {
            "tenant_id": TENANT_ID,
            "name": name,
            "driver_code": driver_code or name,
            "driver_language": first(row, "语言", "language"),
            "office": office,
            "driver_external_id": driver_code,
            "license_number": first(row, "免許番号", "驾照号"),
            "residence_status": first(row, "在留資格"),
            "residence_due_date": residence_due,
            "health_check_remaining_days": int(first(row, "健康诊断剩余有效天数") or "0") if first(row, "健康诊断剩余有效天数") else None,
            "phone": phone,
            "email": first(row, "メールアドレス", "mail", "email"),
            "license_due_date": license_due,
            "license_expires_at": license_due,
            "health_check_due_date": health_due,
            "medical_check_expires_at": health_date,
            "driver_status": status,
            "status": status,
        }
        driver_id = insert_or_update(
            conn,
            "drivers",
            {"tenant_id": TENANT_ID, "driver_external_id": driver_code} if driver_code else {"tenant_id": TENANT_ID, "name": name},
            values,
        )
        if username:
            user_id = ensure_user(conn, username, "driver", f"{name} YuzuDriver", phone, "driver", driver_id)
            conn.execute("UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, driver_id))
    if active_keys:
        current = conn.execute("SELECT id, driver_external_id, phone, name FROM drivers WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
        for row in current:
            key = row["driver_external_id"] or row["phone"] or row["name"]
            if key not in active_keys:
                conn.execute("UPDATE drivers SET status = 'retired', driver_status = 'retired', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return len(rows)


def sync_vehicles(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    active_suffixes: set[str] = set()
    for row in rows:
        suffix = plate_suffix(row.get("suffix") or row.get("plate_number") or row.get("id"))
        if not suffix:
            continue
        active_suffixes.add(suffix)
        vehicle_type = str(row.get("vehicle_type") or "")
        type_code = normalize_vehicle_type_code(vehicle_type)
        status = normalize_vehicle_status(str(row.get("status") or ""), suffix)
        plate_number = str(row.get("plate_number") or suffix)
        shaken_due = parse_latest_date(row.get("vehicle_inspection_due_date"))
        latest_shaken = parse_latest_date(row.get("shaken_date") or row.get("annual_inspection_date"))
        latest_three = parse_latest_date(row.get("three_month_inspection_date"))
        values = {
            "tenant_id": TENANT_ID,
            "plate_no": suffix,
            "plate_number": plate_number,
            "plate_short_code": suffix,
            "vehicle_type": vehicle_type or type_code,
            "vehicle_type_code": type_code,
            "vehicle_group": "10座" if type_code == "hiace" else "3代",
            "seat_count": normalize_seat_count(vehicle_type),
            "seats": normalize_seat_count(vehicle_type),
            "status": status,
            "last_inspection_date": latest_three or latest_shaken,
            "next_inspection_due_date": latest_three,
            "shaken_due_date": shaken_due,
            "inspection_expires_at": shaken_due,
            "maintenance_status": "" if status == "available" else status,
        }
        insert_or_update(conn, "vehicles", {"plate_number": plate_number}, values)
    if active_suffixes:
        current = conn.execute("SELECT id, plate_no, plate_short_code FROM vehicles WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
        for row in current:
            suffix = plate_suffix(row["plate_short_code"] or row["plate_no"])
            if suffix and suffix not in active_suffixes:
                conn.execute("UPDATE vehicles SET status = 'retired', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return len(rows)


def sync(db_path: Path) -> dict[str, Any]:
    global TENANT_ID
    library = list_resource_library()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        TENANT_ID = ensure_tenant(conn)
        ensure_user(conn, ADMIN_USERNAME, "admin", f"Daitora Admin {ADMIN_USERNAME}", ADMIN_USERNAME, "operator", None, ADMIN_PASSWORD)
        ensure_user(conn, OPS_USERNAME, "operations_manager", f"Daitora Operations {OPS_USERNAME}", OPS_USERNAME, "operator", None, ADMIN_PASSWORD)
        drivers = sync_drivers(conn, library.get("drivers") or [])
        vehicles = sync_vehicles(conn, library.get("vehicles") or [])
        conn.commit()
        active_drivers = conn.execute("SELECT count(*) FROM drivers WHERE tenant_id = ? AND status = 'available'", (TENANT_ID,)).fetchone()[0]
        active_vehicles = conn.execute("SELECT count(*) FROM vehicles WHERE tenant_id = ? AND status = 'available'", (TENANT_ID,)).fetchone()[0]
        return {
            "db": str(db_path),
            "resource_summary": library.get("summary"),
            "synced_drivers": drivers,
            "synced_vehicles": vehicles,
            "active_drivers": active_drivers,
            "active_vehicles": active_vehicles,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    print(sync(Path(args.db)))


if __name__ == "__main__":
    main()

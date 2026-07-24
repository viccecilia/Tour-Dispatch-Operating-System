from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

# These names reflect the current online page (2026-07-20).  The source CSV
# saved on 2026-07-17 still marks 王爽 and 胡東鍇 as active, so the current
# online state intentionally overrides those two old rows.
FORCE_RETIRED_NAMES = {"王爽", "胡東鍇"}
CURRENT_DRIVER_CODES = {
    "周政": "12361",
    "叢枝佳": "kyoto-1",
    "林澤群": "kyoto-2",
    "矢口萱": "kyoto-3",
    "董星": "kyoto-4",
    "刘晓丽": "12363",
    "权永住": "12365",
    "菜卫平": "12360",
}
CURRENT_CAN_DRIVE_NAMES = {
    "姚博", "李力", "周伝波", "姜小涛", "高弘强", "李成志", "王啓超",
    "先山武志", "白石賢志", "山下洋子", "朱英心", "许海龙", "王敏",
    "岸田博光", "楊正元", "郝宗竹", "韓朝新", "其堯", "楊健波", "張永",
    "趙梓瑶", "杜依軒", "王偉兵", "李沢浩", "栾冲", "周政", "叢枝佳",
    "林澤群", "矢口萱", "董星", "刘晓丽", "权永住", "菜卫平",
}
CURRENT_DRIVER_OVERRIDES = {
    "刘晓丽": {
        "driver_code": "12363", "phone": "080-4647-1999",
        "license_due_date": "2028-03-25", "license_number": "621606948020",
        "residence_status": "永住者", "residence_due_date": "2027-02-17",
    },
    "权永住": {
        "driver_code": "12365", "phone": "080-3106-9666",
        "license_due_date": "2029-01-27", "license_number": "621104983445",
        "residence_status": "永住者", "residence_due_date": "2031-12-09",
    },
    "菜卫平": {
        "driver_code": "12360", "phone": "060-6971-8890",
        "license_due_date": "2027-06-27", "license_number": "621103645000",
        "residence_status": "日本の国籍", "residence_due_date": "",
    },
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def digits(value: Any) -> str:
    return "".join(re.findall(r"\d+", clean(value)))


def normalized_plate(value: Any) -> str:
    return re.sub(r"[\s・･]", "", clean(value)).lower()


def plate_suffix(value: Any) -> str:
    found = digits(value)
    return str(int(found[-4:])) if found else ""


def iso_date(value: Any) -> str:
    text = clean(value)
    if not text or text == "-":
        return ""
    match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if match:
        return f"{2018 + int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"\bR\s*(\d{1,2})\s*[/.-]?(\d{2})\s*[/.-]?(\d{2})\b", text, re.IGNORECASE)
    if match:
        return f"{2018 + int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return ""


def add_one_year(value: str) -> str:
    if not value:
        return ""
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    try:
        return parsed.replace(year=parsed.year + 1).isoformat()
    except ValueError:
        return parsed.replace(year=parsed.year + 1, day=28).isoformat()


def add_three_months(value: str) -> str:
    if not value:
        return ""
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    month = parsed.month + 3
    year = parsed.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    for day in range(parsed.day, 27, -1):
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    return date(year, month, 28).isoformat()


def dates_in(value: Any) -> list[str]:
    text = clean(value)
    candidates = re.findall(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|令和\s*\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|R\s*\d{1,2}[/. -]?\d{2}[/. -]?\d{2}", text, re.IGNORECASE)
    return sorted({parsed for item in candidates if (parsed := iso_date(item))})


def read_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise ValueError(f"empty_csv:{path}")
    return rows[1:]


def driver_sources(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in read_rows(path):
        if len(row) < 15 or not clean(row[3]):
            continue
        name = clean(row[3])
        source_status = clean(row[13])
        is_retired = source_status in {"离职", "離職", "退职", "退職"} or name in FORCE_RETIRED_NAMES
        driver_code = CURRENT_DRIVER_CODES.get(name, clean(row[1]))
        health_check_date = iso_date(row[8])
        item = {
            "name": name,
            "driver_code": driver_code,
            "driver_external_id": driver_code,
            "office": clean(row[2]),
            "phone": clean(row[10]),
            "license_due_date": iso_date(row[4]),
            "license_expires_at": iso_date(row[4]),
            "license_number": clean(row[5]),
            "residence_status": clean(row[6]),
            "residence_due_date": iso_date(row[7]),
            "health_check_due_date": health_check_date,
            "medical_check_expires_at": add_one_year(health_check_date),
            "health_check_remaining_days": (
                (datetime.strptime(add_one_year(health_check_date), "%Y-%m-%d").date() - date.today()).days
                if health_check_date else None
            ),
            "email": clean(row[12]),
            "status": "retired" if is_retired else "available",
            "driver_status": "retired" if is_retired else ("available" if name in CURRENT_CAN_DRIVE_NAMES else "inactive"),
            "source_status": source_status,
        }
        item.update(CURRENT_DRIVER_OVERRIDES.get(name, {}))
        result.append(item)
    return result


def vehicle_sources(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in read_rows(path):
        if len(row) < 15 or not clean(row[0]):
            continue
        three_month_dates = dates_in(row[7])
        annual_dates = dates_in(row[8])
        shaken_dates = dates_in(row[6])
        records = [
            *[("inspection", item, "线上3个月点检") for item in three_month_dates],
            *[("annual_inspection", item, "线上12个月点检") for item in annual_dates],
            *[("shaken", item, "线上车检") for item in shaken_dates],
        ]
        latest_three = max(three_month_dates, default="")
        latest_any = max([*three_month_dates, *annual_dates, *shaken_dates], default="")
        result.append({
            "plate_number": clean(row[0]),
            "plate_no": clean(row[0]),
            "plate_short_code": clean(row[1]) or plate_suffix(row[0]),
            "vehicle_group": clean(row[2]),
            "vehicle_type_code": clean(row[3]),
            "vehicle_type": clean(row[4]) or clean(row[3]),
            "last_inspection_date": latest_any,
            "next_inspection_due_date": add_three_months(latest_three),
            "shaken_due_date": iso_date(row[5]),
            "inspection_expires_at": iso_date(row[5]),
            "status": "available",
            "maintenance_status": "",
            "inspection_records": records,
        })
    return result


def assignment_count(conn: sqlite3.Connection, column: str, item_id: int) -> int:
    return int(conn.execute(
        f"SELECT COUNT(*) FROM assignments WHERE tenant_id = ? AND {column} = ?",
        (TENANT_ID, item_id),
    ).fetchone()[0])


def pick_driver(conn: sqlite3.Connection, source: dict[str, Any], used: set[int]) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    rows = conn.execute("SELECT * FROM drivers WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
    phone = digits(source["phone"])
    same_identity = [
        row for row in rows
        if (phone and digits(row["phone"]) == phone) or clean(row["name"]) == source["name"]
    ]
    available = [row for row in same_identity if int(row["id"]) not in used]
    if not available:
        return None, same_identity
    available.sort(key=lambda row: (
        -assignment_count(conn, "driver_id", int(row["id"])),
        0 if clean(row["status"]) not in {"retired", "deleted"} else 1,
        int(row["id"]),
    ))
    return available[0], same_identity


def pick_vehicle(conn: sqlite3.Connection, source: dict[str, Any], used: set[int]) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    rows = conn.execute("SELECT * FROM vehicles WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
    plate = normalized_plate(source["plate_number"])
    suffix = plate_suffix(source["plate_short_code"])
    same_identity = [
        row for row in rows
        if normalized_plate(row["plate_number"] or row["plate_no"]) == plate
        or (suffix and plate_suffix(row["plate_short_code"] or row["plate_number"] or row["plate_no"]) == suffix)
    ]
    available = [row for row in same_identity if int(row["id"]) not in used]
    if not available:
        return None, same_identity
    available.sort(key=lambda row: (
        0 if clean(row["plate_number"] or row["plate_no"]) == source["plate_number"] else 1,
        -assignment_count(conn, "vehicle_id", int(row["id"])),
        0 if clean(row["status"]) not in {"retired", "deleted"} else 1,
        int(row["id"]),
    ))
    return available[0], same_identity


def update_row(conn: sqlite3.Connection, table: str, item_id: int, values: dict[str, Any]) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    data = {key: value for key, value in values.items() if key in columns}
    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?",
        [*data.values(), item_id, TENANT_ID],
    )


def insert_row(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    data = {"tenant_id": TENANT_ID, **{key: value for key, value in values.items() if key in columns}}
    names = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    cursor = conn.execute(
        f"INSERT INTO {table} ({names}, created_at, updated_at) VALUES ({marks}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        list(data.values()),
    )
    return int(cursor.lastrowid)


def sync_drivers(conn: sqlite3.Connection, sources: list[dict[str, Any]], apply: bool) -> dict[str, Any]:
    used: set[int] = set()
    changes: list[dict[str, Any]] = []
    for source in sources:
        if source["name"] == "胡東鍇":
            continue
        selected, identity_rows = pick_driver(conn, source, used)
        action = "insert" if selected is None else "update"
        item_id = int(selected["id"]) if selected else -(len(changes) + 1)
        if apply:
            item_id = insert_row(conn, "drivers", source) if selected is None else int(selected["id"])
            if selected is not None:
                update_row(conn, "drivers", item_id, source)
        used.add(item_id)
        duplicate_ids = [int(row["id"]) for row in identity_rows if int(row["id"]) != item_id]
        if apply:
            for duplicate_id in duplicate_ids:
                conn.execute(
                    "UPDATE assignments SET driver_id = ? WHERE tenant_id = ? AND driver_id = ? AND status = 'active'",
                    (item_id, TENANT_ID, duplicate_id),
                )
                update_row(conn, "drivers", duplicate_id, {"status": "retired", "driver_status": "retired"})
            bound_users = conn.execute(
                f"SELECT * FROM users WHERE tenant_id = ? AND role = 'driver' AND profile_id IN ({','.join('?' for _ in [item_id, *duplicate_ids])})",
                (TENANT_ID, item_id, *duplicate_ids),
            ).fetchall()
            if source["status"] == "retired":
                for user in bound_users:
                    conn.execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            elif bound_users:
                chosen_user = sorted(bound_users, key=lambda row: (0 if int(row["profile_id"] or 0) == item_id else 1, int(row["id"])))[0]
                conn.execute(
                    "UPDATE users SET profile_id = ?, profile_type = 'driver', phone = COALESCE(NULLIF(?, ''), phone), is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (item_id, source["phone"], chosen_user["id"]),
                )
                conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (chosen_user["id"], item_id))
                for user in bound_users:
                    if int(user["id"]) != int(chosen_user["id"]):
                        conn.execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        changes.append({"action": action, "id": item_id, "name": source["name"], "status": source["status"], "driver_status": source["driver_status"], "duplicates": duplicate_ids})

    rows = conn.execute("SELECT id, name, status FROM drivers WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
    retired_absent: list[dict[str, Any]] = []
    for row in rows:
        if int(row["id"]) in used or clean(row["status"]) in {"retired", "deleted"}:
            continue
        retired_absent.append({"id": int(row["id"]), "name": row["name"], "active_assignments": conn.execute("SELECT COUNT(*) FROM assignments WHERE tenant_id = ? AND driver_id = ? AND status = 'active'", (TENANT_ID, row["id"])).fetchone()[0]})
        if apply:
            update_row(conn, "drivers", int(row["id"]), {"status": "retired", "driver_status": "retired"})
            conn.execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND role = 'driver' AND profile_id = ?", (TENANT_ID, row["id"]))
    return {"sources": len(sources) - 1, "changes": changes, "retired_absent": retired_absent}


def sync_vehicles(conn: sqlite3.Connection, sources: list[dict[str, Any]], apply: bool) -> dict[str, Any]:
    used: set[int] = set()
    changes: list[dict[str, Any]] = []
    for source in sources:
        selected, identity_rows = pick_vehicle(conn, source, used)
        action = "insert" if selected is None else "update"
        item_id = int(selected["id"]) if selected else -(len(changes) + 1)
        if apply:
            item_id = insert_row(conn, "vehicles", source) if selected is None else int(selected["id"])
            if selected is not None:
                update_row(conn, "vehicles", item_id, source)
            conn.execute("DELETE FROM vehicle_inspection_records WHERE tenant_id = ? AND vehicle_id = ? AND source = 'online-vehicle-docs'", (TENANT_ID, item_id))
            for inspection_type, inspection_date, note in source["inspection_records"]:
                conn.execute(
                    "INSERT INTO vehicle_inspection_records (tenant_id, vehicle_id, inspection_type, inspection_date, source, note, created_at, updated_at) VALUES (?, ?, ?, ?, 'online-vehicle-docs', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (TENANT_ID, item_id, inspection_type, inspection_date, note),
                )
        used.add(item_id)
        duplicate_ids = [int(row["id"]) for row in identity_rows if int(row["id"]) != item_id]
        if apply:
            for duplicate_id in duplicate_ids:
                conn.execute(
                    "UPDATE assignments SET vehicle_id = ? WHERE tenant_id = ? AND vehicle_id = ? AND status = 'active'",
                    (item_id, TENANT_ID, duplicate_id),
                )
                update_row(conn, "vehicles", duplicate_id, {"status": "retired", "maintenance_status": "retired"})
        changes.append({"action": action, "id": item_id, "plate": source["plate_number"], "duplicates": duplicate_ids})

    rows = conn.execute("SELECT id, plate_number, status FROM vehicles WHERE tenant_id = ?", (TENANT_ID,)).fetchall()
    retired_absent: list[dict[str, Any]] = []
    for row in rows:
        if int(row["id"]) in used or clean(row["status"]) in {"retired", "deleted"}:
            continue
        retired_absent.append({"id": int(row["id"]), "plate": row["plate_number"], "active_assignments": conn.execute("SELECT COUNT(*) FROM assignments WHERE tenant_id = ? AND vehicle_id = ? AND status = 'active'", (TENANT_ID, row["id"])).fetchone()[0]})
        if apply:
            update_row(conn, "vehicles", int(row["id"]), {"status": "retired", "maintenance_status": "retired"})
    return {"sources": len(sources), "changes": changes, "retired_absent": retired_absent}


def validate(conn: sqlite3.Connection) -> dict[str, Any]:
    driver_counts = Counter(row[0] for row in conn.execute("SELECT status FROM drivers WHERE tenant_id = ?", (TENANT_ID,)))
    vehicle_counts = Counter(row[0] for row in conn.execute("SELECT status FROM vehicles WHERE tenant_id = ?", (TENANT_ID,)))
    return {
        "drivers": dict(driver_counts),
        "vehicles": dict(vehicle_counts),
        "dispatchable_drivers": conn.execute("SELECT COUNT(*) FROM drivers WHERE tenant_id = ? AND status = 'available' AND driver_status = 'available'", (TENANT_ID,)).fetchone()[0],
        "active_driver_accounts": conn.execute("SELECT COUNT(*) FROM users WHERE tenant_id = ? AND role = 'driver' AND is_active = 1", (TENANT_ID,)).fetchone()[0],
        "active_assignments": conn.execute("SELECT COUNT(*) FROM assignments WHERE tenant_id = ? AND status = 'active'", (TENANT_ID,)).fetchone()[0],
        "broken_assignment_drivers": conn.execute("SELECT COUNT(*) FROM assignments a LEFT JOIN drivers d ON d.id=a.driver_id AND d.tenant_id=a.tenant_id WHERE a.tenant_id=? AND d.id IS NULL", (TENANT_ID,)).fetchone()[0],
        "broken_assignment_vehicles": conn.execute("SELECT COUNT(*) FROM assignments a LEFT JOIN vehicles v ON v.id=a.vehicle_id AND v.tenant_id=a.tenant_id WHERE a.tenant_id=? AND v.id IS NULL", (TENANT_ID,)).fetchone()[0],
        "broken_driver_profiles": conn.execute("SELECT COUNT(*) FROM users u LEFT JOIN drivers d ON d.id=u.profile_id AND d.tenant_id=u.tenant_id WHERE u.tenant_id=? AND u.role='driver' AND u.is_active=1 AND d.id IS NULL", (TENANT_ID,)).fetchone()[0],
    }


def main() -> None:
    global TENANT_ID
    parser = argparse.ArgumentParser(description="Synchronize Daitora local resources from the online source tables without replacing database IDs.")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--drivers", required=True, type=Path)
    parser.add_argument("--vehicles", required=True, type=Path)
    parser.add_argument("--tenant", type=int, default=529)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    TENANT_ID = args.tenant
    if not args.db.exists():
        raise SystemExit(f"database_not_found:{args.db}")
    if not args.drivers.exists() or not args.vehicles.exists():
        raise SystemExit("source_csv_not_found")

    backup = None
    if args.apply:
        backup = args.db.with_name(f"{args.db.stem}.before_online_resource_sync_{datetime.now():%Y%m%d_%H%M%S}{args.db.suffix}")
        shutil.copy2(args.db, backup)

    drivers = driver_sources(args.drivers)
    vehicles = vehicle_sources(args.vehicles)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE" if args.apply else "BEGIN")
        result = {
            "mode": "apply" if args.apply else "dry-run",
            "tenant_id": TENANT_ID,
            "backup": str(backup) if backup else None,
            "driver_sync": sync_drivers(conn, drivers, args.apply),
            "vehicle_sync": sync_vehicles(conn, vehicles, args.apply),
        }
        if args.apply:
            conn.commit()
            conn.execute("BEGIN")
        result["validation"] = validate(conn)
        conn.rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

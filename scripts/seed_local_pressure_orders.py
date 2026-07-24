from __future__ import annotations

import argparse
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "runtime" / "wx_dispatch.sqlite3"
TEST_PREFIX = "P100-"
TEST_MARK = "[P100]"


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def insert_dynamic(conn: sqlite3.Connection, table: str, values: dict) -> int:
    cols = columns(conn, table)
    filtered = {key: value for key, value in values.items() if key in cols}
    names = list(filtered)
    placeholders = ", ".join("?" for _ in names)
    sql = f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [filtered[name] for name in names])
    return int(cur.lastrowid)


def pick_tenant(conn: sqlite3.Connection, tenant_id: int | None) -> int:
    if tenant_id:
        return tenant_id
    row = conn.execute(
        """
        SELECT id
          FROM tenants
         WHERE lower(name) = 'daitora'
            OR lower(slug) IN ('dtr', 'daitora')
         ORDER BY CASE WHEN id = 529 THEN 0 ELSE 1 END, id DESC
         LIMIT 1
        """
    ).fetchone()
    if row:
        return int(row["id"])
    row = conn.execute(
        "SELECT tenant_id, COUNT(*) c FROM drivers GROUP BY tenant_id ORDER BY c DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise RuntimeError("No tenant with drivers found.")
    return int(row["tenant_id"])


def available_drivers(conn: sqlite3.Connection, tenant_id: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
          FROM drivers
         WHERE tenant_id = ?
           AND COALESCE(status, 'available') NOT IN ('deleted', 'archived', 'disabled')
           AND COALESCE(driver_status, 'available') NOT IN ('deleted', 'archived', 'disabled')
         ORDER BY id
        """,
        (tenant_id,),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"No available drivers for tenant {tenant_id}.")
    return rows


def available_vehicles(conn: sqlite3.Connection, tenant_id: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
          FROM vehicles
         WHERE tenant_id = ?
           AND COALESCE(status, 'available') NOT IN ('deleted', 'archived', 'disabled', 'reduced', 'out_of_service')
           AND COALESCE(maintenance_status, 'available') NOT IN ('deleted', 'archived', 'disabled', 'reduced', 'out_of_service')
         ORDER BY id
        """,
        (tenant_id,),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"No available vehicles for tenant {tenant_id}.")
    return rows


def backup_db(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak_pressure100_{stamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def clear_previous(conn: sqlite3.Connection) -> tuple[int, int]:
    rows = conn.execute(
        "SELECT id FROM orders WHERE oid LIKE ? OR COALESCE(remark, '') LIKE ?",
        (f"{TEST_PREFIX}%", f"%{TEST_MARK}%"),
    ).fetchall()
    order_ids = [int(row["id"]) for row in rows]
    if not order_ids:
        return 0, 0
    placeholders = ", ".join("?" for _ in order_ids)
    assignment_count = conn.execute(
        f"SELECT COUNT(*) FROM assignments WHERE order_id IN ({placeholders})", order_ids
    ).fetchone()[0]
    conn.execute(f"DELETE FROM assignments WHERE order_id IN ({placeholders})", order_ids)
    conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
    return int(len(order_ids)), int(assignment_count)


def time_pair(index: int, driver_count: int, start_date: datetime) -> tuple[str, str, str, str]:
    driver_cycle = index // max(driver_count, 1)
    slot_in_cycle = index % max(driver_count, 1)
    day_offset = driver_cycle // 6
    within_day_cycle = driver_cycle % 6
    # Stagger by driver to avoid a solid wall at the same minute.
    start_minutes = 6 * 60 + within_day_cycle * 150 + (slot_in_cycle % 5) * 6
    start_dt = start_date + timedelta(days=day_offset, minutes=start_minutes)
    end_dt = start_dt + timedelta(minutes=105)
    return (
        start_dt.strftime("%Y-%m-%d"),
        end_dt.strftime("%Y-%m-%d"),
        start_dt.strftime("%H:%M"),
        end_dt.strftime("%H:%M"),
    )


def seed(conn: sqlite3.Connection, tenant_id: int, count: int, start_date: str) -> Counter:
    drivers = available_drivers(conn, tenant_id)
    vehicles = available_vehicles(conn, tenant_id)
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_driver: Counter = Counter()

    route_pairs = [
        ("KIX-T1", "大阪市内"),
        ("大阪市内", "京都包车"),
        ("USJ", "奈良公园"),
        ("京都站", "关西机场T1"),
        ("大阪酒店", "神户港"),
    ]
    order_types = ["接机", "包车", "包车", "送机", "单送"]

    for idx in range(count):
        driver = drivers[idx % len(drivers)]
        vehicle = vehicles[idx % len(vehicles)]
        order_date, end_date, start_time, end_time = time_pair(idx, len(drivers), base_date)
        pickup, dropoff = route_pairs[idx % len(route_pairs)]
        order_type = order_types[idx % len(order_types)]
        oid = f"{TEST_PREFIX}{base_date.strftime('%y%m%d')}-{idx + 1:04d}"
        driver_name = driver["name"] or f"driver-{driver['id']}"
        plate = vehicle["plate_short_code"] or vehicle["plate_no"] or vehicle["plate_number"] or f"vehicle-{vehicle['id']}"
        vehicle_type = vehicle["vehicle_type"] or vehicle["vehicle_type_code"] or "A-3"

        order_id = insert_dynamic(
            conn,
            "orders",
            {
                "tenant_id": tenant_id,
                "oid": oid,
                "order_date": order_date,
                "end_date": end_date,
                "start_time": start_time,
                "end_time": end_time,
                "pickup_location": pickup,
                "dropoff_location": dropoff,
                "order_type": order_type,
                "vehicle_type": vehicle_type,
                "vehicle_type_code": vehicle["vehicle_type_code"],
                "plate_short_code": plate,
                "driver_code": driver["driver_code"],
                "driver_language": driver["driver_language"],
                "passenger_count": 2 + (idx % 5),
                "luggage_count": idx % 4,
                "guest_name": f"Pressure Guest {idx + 1:03d}",
                "guest_contact": f"+81 90-9900-{idx + 1:04d}",
                "price": 30000 + (idx % 8) * 2500,
                "price_jpy": 30000 + (idx % 8) * 2500,
                "remark": f"{TEST_MARK} local saturation test. Driver={driver_name}; Vehicle={plate}",
                "dispatch_status": "assigned",
                "execution_status": "assigned",
                "settlement_status": "unsettled",
                "is_deleted": 0,
                "created_at": now,
                "updated_at": now,
                "source_channel": "local_pressure_seed",
                "created_by_dispatcher": "Codex pressure seed",
                "created_by_dispatcher_id": None,
                "created_by_dispatcher_code": "P100",
            },
        )
        insert_dynamic(
            conn,
            "assignments",
            {
                "tenant_id": tenant_id,
                "order_id": order_id,
                "driver_id": driver["id"],
                "vehicle_id": vehicle["id"],
                "status": "active",
                "execution_status": "assigned",
                "assigned_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        by_driver[f"{driver_name} / {plate}"] += 1

    return by_driver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--start-date", default="2026-06-27")
    parser.add_argument("--clear-only", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    backup_path = None if args.no_backup else backup_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        tenant_id = pick_tenant(conn, args.tenant_id)
        removed_orders, removed_assignments = clear_previous(conn)
        by_driver = Counter() if args.clear_only else seed(conn, tenant_id, args.count, args.start_date)

    print(f"db={db_path}")
    if backup_path:
        print(f"backup={backup_path}")
    print(f"tenant_id={tenant_id}")
    print(f"removed_orders={removed_orders} removed_assignments={removed_assignments}")
    inserted = 0 if args.clear_only else args.count
    print(f"inserted_orders={inserted} inserted_assignments={inserted}")
    if by_driver:
        print("top_driver_loads=")
        for name, load in by_driver.most_common(12):
            print(f"  {name}: {load}")


if __name__ == "__main__":
    main()

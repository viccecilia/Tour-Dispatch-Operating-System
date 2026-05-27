from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import get_connection, init_db, refresh_order_oids
from backend.services.order_number_service import build_order_oid, normalize_vehicle_type_code
from backend.services.parser_service import parse_chinese_order


# Real operator samples supplied by the user. Dates are shifted to recent dates
# when inserted, but raw_text keeps the original operator wording for parser demos.
REAL_ORDER_TEXTS = [
    "3.29 10:00 大阪单送名古屋 10座 1700",
    "3.29 14:10 关西接机大阪 10座600",
    "3.29 08:05 关西接机大阪 10座600",
    "3.29 08:00/20:00 环球往返接送 3代600",
    "3.29 07:30 大阪单送新大阪 3代 300",
    "3.29 08:20 京都送机关西 3代 绿800",
    "3.29 19:30 京都单送关西酒店 3代绿 600+4000",
    "3.29 14:00 关西接机京都 3代 绿800",
    "3.29 11:00 大阪送机神户机场 3代 绿450",
    "3.29 07:30 大阪送机关西 3代 绿450",
    "3.29 11:30 大阪送机关西 3代 儿童座椅 绿450",
    "3.29 13:00 大阪单送关西酒店 3代 绿450",
    "3.29 11:25 关西接机大阪 3代 儿童座椅 绿450",
    "3.29 13:05 关西接机大阪 3代 绿450",
    "3.29 15:00 关西接机大阪 3代 绿450",
    "3.29 16:10 关西接机大阪 3代 绿450",
    "3.29 19:30 关西接机大阪 3代 绿450",
    "3.29 21:15 关西接机大阪 3代 绿450",
    "3.29 06:30 大阪送机关西 10座 绿600",
    "12.11 11:00 大阪送机关西 3代 500-",
    "12.11 12:30 大阪单送神户 儿童座椅*2 3代 550",
    "12.11 17:30 大阪单送京都 3代 绿600",
    "12.11 10:40 京都送机关西 3代 绿900",
    "12.11 12:45 京都送机关西 3代 绿900",
    "12.11 06:20 大阪送机关西 3代 绿530",
    "12.11 06:30 大阪送机关西 3代 绿530",
    "12.11 07:00 大阪送机关西 3代×2 绿 530*2",
    "12.11 09:30 大阪送机关西 3代 绿530",
    "12.11 10:00 大阪送机关西 3代 绿530",
    "12.11 12:30 大阪送机关西 3代 绿530",
    "12.11 13:00 大阪送机关西 3代 绿530",
    "12.11 12:45 关西接机大阪 3代绿 儿童座椅2 530+2000",
    "12.11 15:30 关西接机大阪 3代 绿530",
    "12.11 16:55 关西接机大阪 3代绿530 +举牌2000",
    "12.11 21:25 关西接机大阪 3代 绿530",
    "12.11 15:30 新大阪站单送大阪 10座 绿 450",
    "12.11 10:00 京都单送大阪 10座 绿 750",
    "12.11 18:55 伊丹接机京都 10座 绿 750",
    "12.11 12:30 神户机场接机大阪 10座 绿 700",
    "12.11 06:00 大阪送机关西 10座 儿童座椅 绿 650",
    "12.11 15:30 大阪送机关西 10座 绿 650",
    "12.11 17:00 大阪送机关西 10座 绿 650",
    "12.11 11:35 关西接机大阪 10座 儿童座椅 绿 650",
    "12.11 15:30 新大阪接站市内 10座450-",
    "12.11 11:30 大阪送机关西 10座 650-",
    "12.11 21:30 关西接机大阪 10座 650-",
    "12.10 05:00 大阪送机关西 3代500",
    "12.10 16:45 新大阪接站市内 2代300",
    "12.10 11:00 京都送机关西 3代 绿900",
    "12.10 12:30 京都送机关西 3代 儿童座椅 绿900",
]

TRANSACTION_TABLES = [
    "driver_evidence_uploads",
    "driver_expense_reports",
    "driver_workflow_events",
    "driver_reports",
    "location_logs",
    "incidents",
    "notifications",
    "assignments",
    "order_drafts",
    "audit_logs",
    "operation_logs",
    "orders",
]


def main() -> None:
    init_db(seed=True)
    base_date = date.today()
    with get_connection() as conn:
        deleted = _clear_runtime_data(conn)
        agency = _first_agency(conn)
        drivers = _current_drivers(conn)
        vehicles = _current_vehicles(conn)
        order_ids = _seed_recent_real_orders(conn, base_date, agency)
        assignment_ids = _seed_assignments_from_current_resources(conn, order_ids, drivers, vehicles)
        _seed_recent_real_drafts(conn, base_date, agency)
        refresh_order_oids(conn)
        conn.commit()

    result = {
        "date": base_date.isoformat(),
        "orders": len(order_ids),
        "assignments": len(assignment_ids),
        "drivers_used_from_current_db": len(drivers),
        "vehicles_used_from_current_db": len(vehicles),
        "deleted_runtime_rows": deleted,
        "source": "recent real Osaka/KIX/Kyoto operator samples",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _clear_runtime_data(conn) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for table in TRANSACTION_TABLES:
        if not _table_exists(conn, table):
            continue
        count = conn.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]
        conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
        deleted[table] = count
    return deleted


def _table_exists(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone() is not None


def _first_agency(conn) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT id, COALESCE(company_name, name, agency_code, '大寅') AS agency_name
        FROM agencies
        WHERE tenant_id = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if row:
        return dict(row)
    cursor = conn.execute(
        """
        INSERT INTO agencies (tenant_id, agency_code, company_name, name, status, updated_at)
        VALUES (1, 'D', '大寅', '大寅', 'active', CURRENT_TIMESTAMP)
        """
    )
    return {"id": cursor.lastrowid, "agency_name": "大寅"}


def _current_drivers(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, driver_code
        FROM drivers
        WHERE tenant_id = 1
          AND COALESCE(status, driver_status, 'available') NOT IN ('inactive', 'disabled')
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _current_vehicles(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, plate_number, plate_no, vehicle_type, vehicle_type_code
        FROM vehicles
        WHERE tenant_id = 1
          AND COALESCE(status, 'available') NOT IN ('inactive', 'disabled', 'scrapped')
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _seed_recent_real_orders(conn, base_date: date, agency: dict[str, Any]) -> list[int]:
    order_ids: list[int] = []
    for index, raw_text in enumerate(REAL_ORDER_TEXTS, start=1):
        parsed = parse_chinese_order(raw_text)
        order_date = _recent_order_date(base_date, index)
        vehicle_type = parsed.get("vehicle_type") or "待确认"
        vehicle_type_code = parsed.get("vehicle_type_code") or normalize_vehicle_type_code(vehicle_type)
        oid = build_order_oid(
            order_note_code="D",
            order_source="D",
            order_date=order_date.isoformat(),
            serial=index,
            vehicle_type_code=vehicle_type_code,
            temporary=True,
        )
        dispatch_status = "unassigned" if index <= 16 else "assigned"
        execution_status = "assigned" if dispatch_status == "assigned" else "pending"
        cursor = conn.execute(
            """
            INSERT INTO orders (
                tenant_id, oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, vehicle_type,
                order_note_code, order_source, vehicle_type_code, vehicle_color, snow_tire,
                passenger_count, luggage_count, guest_name, guest_contact,
                agency_id, agency_name, price, price_rmb, price_jpy,
                fee_remark, other_fee_jpy, remark,
                dispatch_status, execution_status, settlement_status,
                driver_settlement_status, agency_settlement_status, is_deleted,
                created_at, updated_at
            )
            VALUES (
                1, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                'D', 'D', ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, 'pending',
                'pending', 'pending', 0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                oid,
                order_date.isoformat(),
                (order_date + _end_date_delta(parsed)).isoformat(),
                parsed.get("start_time"),
                parsed.get("end_time"),
                parsed.get("pickup_location") or "待确认",
                parsed.get("dropoff_location") or "待确认",
                parsed.get("order_type") or "待确认",
                vehicle_type,
                vehicle_type_code,
                parsed.get("vehicle_color"),
                parsed.get("snow_tire"),
                parsed.get("passenger_count") or 0,
                parsed.get("luggage_count") or 0,
                parsed.get("guest_name") or "演示客人",
                parsed.get("guest_contact") or "138****8825",
                agency["id"],
                agency["agency_name"],
                parsed.get("price"),
                parsed.get("price"),
                parsed.get("price_jpy"),
                parsed.get("fee_remark"),
                parsed.get("other_fee_jpy"),
                f"真实订单样本平移到最近日期；原文：{raw_text}",
                dispatch_status,
                execution_status,
            ),
        )
        order_ids.append(cursor.lastrowid)
    return order_ids


def _seed_assignments_from_current_resources(
    conn,
    order_ids: list[int],
    drivers: list[dict[str, Any]],
    vehicles: list[dict[str, Any]],
) -> list[int]:
    if not drivers or not vehicles:
        return []
    assignment_ids: list[int] = []
    # Keep the first block unassigned for dispatch demos; assign the remainder
    # with current database drivers/vehicles, never synthetic demo resources.
    for index, order_id in enumerate(order_ids[16:], start=0):
        driver = drivers[index % len(drivers)]
        vehicle = vehicles[index % len(vehicles)]
        status = "completed" if index % 9 == 8 else "confirmed" if index % 5 == 4 else "assigned"
        cursor = conn.execute(
            """
            INSERT INTO assignments (
                tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
                assigned_at, created_at, updated_at
            )
            VALUES (1, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (order_id, driver["id"], vehicle["id"], status),
        )
        assignment_ids.append(cursor.lastrowid)
        conn.execute(
            """
            UPDATE orders
            SET dispatch_status = 'assigned',
                execution_status = ?,
                driver_code = COALESCE(NULLIF(?, ''), driver_code),
                plate_short_code = COALESCE(NULLIF(?, ''), plate_short_code),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                driver.get("driver_code") or _short_name(driver.get("name")),
                _plate_short(vehicle.get("plate_number") or vehicle.get("plate_no")),
                order_id,
            ),
        )
    return assignment_ids


def _seed_recent_real_drafts(conn, base_date: date, agency: dict[str, Any]) -> None:
    draft_texts = [
        "12.10 08:35 关西举牌接机伊丹 3代 绿630",
        "12.09 09:00 京都送机关西 10座 儿童坐垫 绿 1000",
        "12.07 16:55 关西举牌接机大阪儿童座椅 3代绿530",
        "客户只说下午机场到市内，车型和时间待确认",
        "明天大阪附近用车，价格未定",
    ]
    for index, raw_text in enumerate(draft_texts, start=1):
        parsed = parse_chinese_order(raw_text)
        order_date = _recent_order_date(base_date, index + 50).isoformat() if parsed.get("start_time") else None
        status = "parsed" if parsed.get("start_time") else "failed"
        conn.execute(
            """
            INSERT INTO order_drafts (
                tenant_id, oid, raw_text, source_type, parse_status,
                order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, vehicle_type,
                agency_name, price, fee_remark, remark,
                parse_result_json, created_at, updated_at
            )
            VALUES (
                1, ?, ?, 'text', ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                f"{base_date:%y%m%d}-DRAFT-{index:03d}",
                raw_text,
                status,
                order_date,
                order_date,
                parsed.get("start_time"),
                parsed.get("end_time"),
                parsed.get("pickup_location"),
                parsed.get("dropoff_location"),
                parsed.get("order_type"),
                parsed.get("vehicle_type"),
                agency["agency_name"] if status == "parsed" else None,
                parsed.get("price"),
                parsed.get("fee_remark"),
                parsed.get("remark") or raw_text,
                json.dumps({"status": status, "raw_text": raw_text, "parsed": parsed}, ensure_ascii=False),
            ),
        )


def _recent_order_date(base_date: date, index: int) -> date:
    # Spread 50 samples across today and the next four days, keeping daily lists realistic.
    return base_date + timedelta(days=(index - 1) // 12)


def _end_date_delta(parsed: dict[str, Any]) -> timedelta:
    start = str(parsed.get("start_time") or "")
    end = str(parsed.get("end_time") or "")
    if start and end and end < start:
        return timedelta(days=1)
    return timedelta(0)


def _plate_short(value: Any) -> str:
    chars = "".join(ch for ch in str(value or "") if ch.isalnum())
    return chars[-4:] or ""


def _short_name(value: Any) -> str:
    text = str(value or "").strip()
    return text[:2] if text else ""


if __name__ == "__main__":
    main()

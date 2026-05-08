import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import get_connection, init_db


AGENCIES = [
    ("东京旅运", "张经理", "090-2000-0001"),
    ("樱花旅行", "李经理", "090-2000-0002"),
    ("富士观光", "王经理", "090-2000-0003"),
    ("关西地接", "赵经理", "090-2000-0004"),
    ("日和假期", "陈经理", "090-2000-0005"),
]

DRIVERS = [
    ("张师傅", "139-0000-1111", "available"),
    ("李师傅", "138-0000-2222", "available"),
    ("王师傅", "137-0000-3333", "available"),
    ("赵师傅", "136-0000-4444", "available"),
    ("刘师傅", "135-0000-5555", "available"),
    ("田中司机", "090-1000-0001", "available"),
    ("佐藤司机", "090-1000-0002", "available"),
    ("高桥司机", "090-1000-0003", "available"),
    ("演示司机A", "090-1000-0004", "available"),
    ("演示司机B", "090-1000-0005", "available"),
]

VEHICLES = [
    ("京A12345", "丰田埃尔法", 7, "available"),
    ("京A23456", "别克GL8", 7, "available"),
    ("京A34567", "大众威然", 7, "available"),
    ("京A45678", "考斯特", 23, "available"),
    ("京A56789", "奔驰V级", 7, "available"),
    ("京B1001", "海狮", 10, "available"),
    ("京B1002", "中巴", 18, "available"),
    ("京C9001", "商务车", 6, "available"),
]

ROUTES = [
    ("首都机场", "酒店（国贸）", "接机", "丰田埃尔法"),
    ("酒店（国贸）", "景点（故宫）", "市内包车", "别克GL8"),
    ("故宫", "颐和园", "市内包车", "丰田埃尔法"),
    ("颐和园", "酒店（国贸）", "市内包车", "别克GL8"),
    ("酒店", "八达岭长城", "包车", "丰田埃尔法"),
    ("酒店", "首都机场", "送机", "别克GL8"),
    ("羽田机场", "东京酒店", "接机", "商务车"),
    ("东京站", "成田机场", "送机", "商务车"),
]

EXECUTION_PLAN = (
    ["assigned"] * 20
    + ["in_service"] * 5
    + ["completed"] * 5
)


def main() -> None:
    init_db(seed=True)
    today = date.today()
    with get_connection() as conn:
        _clear_demo_data(conn)
        agency_ids = _seed_agencies(conn)
        driver_ids = _seed_drivers(conn)
        vehicle_ids = _seed_vehicles(conn)
        order_ids = _seed_orders(conn, today, agency_ids)
        assignment_ids = _seed_assignments(conn, order_ids, driver_ids, vehicle_ids)
        _seed_reports(conn, assignment_ids, driver_ids)
        _seed_drafts(conn, today)
        conn.commit()

    result = {
        "date": today.isoformat(),
        "orders_today": 40,
        "unassigned_orders": 10,
        "active_assignments": len(assignment_ids),
        "drivers": 10,
        "vehicles": 8,
        "agencies": 5,
        "pending_drafts": 3,
        "failed_drafts": 2,
        "returned_reports": 3,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _clear_demo_data(conn) -> None:
    for table in ("driver_reports", "assignments", "order_drafts", "orders", "drivers", "vehicles", "agencies"):
        conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))


def _seed_agencies(conn) -> list[int]:
    ids = []
    for name, contact_name, contact_phone in AGENCIES:
        cursor = conn.execute(
            """
            INSERT INTO agencies (name, contact_name, contact_phone)
            VALUES (?, ?, ?)
            """,
            (name, contact_name, contact_phone),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_drivers(conn) -> list[int]:
    ids = []
    for name, phone, status in DRIVERS:
        cursor = conn.execute(
            """
            INSERT INTO drivers (name, phone, status, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (name, phone, status),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_vehicles(conn) -> list[int]:
    ids = []
    for plate_number, vehicle_type, seat_count, status in VEHICLES:
        cursor = conn.execute(
            """
            INSERT INTO vehicles (plate_no, plate_number, vehicle_type, seats, seat_count, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (plate_number, plate_number, vehicle_type, seat_count, seat_count, status),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_orders(conn, today: date, agency_ids: list[int]) -> list[int]:
    ids = []
    for index in range(40):
        pickup, dropoff, order_type, vehicle_type = ROUTES[index % len(ROUTES)]
        day = today
        start_hour = 7 + (index % 12)
        start_minute = 0 if index % 2 == 0 else 30
        end_hour = start_hour + 1 + (1 if order_type == "包车" else 0)
        end_minute = start_minute
        dispatch_status = "unassigned" if index < 10 else "assigned"
        execution_status = "assigned" if index < 10 else EXECUTION_PLAN[index - 10]
        settlement_status = "settled" if index in (34, 35, 36, 37, 38) else "pending"
        agency_id = agency_ids[index % len(agency_ids)]
        agency_name = AGENCIES[index % len(AGENCIES)][0]
        price = 600 + (index % 8) * 100
        oid = f"{today:%Y%m%d}-{index + 1:03d}"
        cursor = conn.execute(
            """
            INSERT INTO orders (
                oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, vehicle_type,
                passenger_count, luggage_count, guest_name, guest_contact,
                agency_id, agency_name, price, remark, dispatch_status,
                execution_status, settlement_status, is_deleted, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            """,
            (
                oid,
                day.isoformat(),
                day.isoformat(),
                f"{start_hour:02d}:{start_minute:02d}",
                f"{end_hour:02d}:{end_minute:02d}",
                pickup,
                dropoff,
                order_type,
                vehicle_type,
                2 + index % 6,
                index % 4,
                f"演示客人{index + 1:02d}",
                f"138****{8800 + index:04d}",
                agency_id,
                agency_name,
                price,
                f"客户备注：演示订单 {index + 1:02d}，行李 {index % 4} 件。",
                dispatch_status,
                execution_status,
                settlement_status,
            ),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_assignments(conn, order_ids: list[int], driver_ids: list[int], vehicle_ids: list[int]) -> list[int]:
    assignment_ids = []
    for index, order_id in enumerate(order_ids[10:]):
        driver_id = driver_ids[index % len(driver_ids)]
        vehicle_id = vehicle_ids[index % len(vehicle_ids)]
        execution_status = EXECUTION_PLAN[index]
        cursor = conn.execute(
            """
            INSERT INTO assignments (order_id, driver_id, vehicle_id, status, execution_status, assigned_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (order_id, driver_id, vehicle_id, execution_status),
        )
        assignment_id = cursor.lastrowid
        assignment_ids.append(assignment_id)
        row = conn.execute(
            """
            SELECT o.oid, d.name AS driver_name, v.plate_number
            FROM orders o
            JOIN drivers d ON d.id = ?
            JOIN vehicles v ON v.id = ?
            WHERE o.id = ?
            """,
            (driver_id, vehicle_id, order_id),
        ).fetchone()
        plate_code = "".join(ch for ch in row["plate_number"] if ch.isalnum())[-4:]
        driver_code = row["driver_name"][:2]
        conn.execute(
            "UPDATE orders SET oid = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (f"{row['oid']}-{plate_code}-{driver_code}", order_id),
        )
    return assignment_ids


def _seed_reports(conn, assignment_ids: list[int], driver_ids: list[int]) -> None:
    flows = {
        "assigned": [],
        "in_service": ["confirm_order", "depart_yard", "arrive_pickup", "start_service"],
        "completed": ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order"],
        "returned": ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"],
    }
    for index, assignment_id in enumerate(assignment_ids):
        status = "assigned"
        if 20 <= index < 25:
            status = "in_service"
        elif 25 <= index < 30:
            status = "completed"
        if index in (27, 28, 29):
            status = "returned"
            conn.execute("UPDATE assignments SET execution_status = 'returned' WHERE id = ?", (assignment_id,))
            conn.execute(
                """
                UPDATE orders
                SET execution_status = 'returned'
                WHERE id = (SELECT order_id FROM assignments WHERE id = ?)
                """,
                (assignment_id,),
            )
        for step_no, report_type in enumerate(flows[status]):
            row = conn.execute("SELECT order_id, driver_id FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            report_time = datetime.now() - timedelta(minutes=(30 - step_no) * 3)
            conn.execute(
                """
                INSERT INTO driver_reports (
                    assignment_id, order_id, driver_id, report_type, report_status,
                    report_time, latitude, longitude, location_text, note, updated_at
                )
                VALUES (?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    assignment_id,
                    row["order_id"],
                    row["driver_id"] or driver_ids[index % len(driver_ids)],
                    report_type,
                    report_time.strftime("%Y-%m-%d %H:%M:%S"),
                    35.68,
                    139.76,
                    "演示位置",
                    f"演示报备 {report_type}",
                ),
            )


def _seed_drafts(conn, today: date) -> None:
    created_at = f"{today.isoformat()} 09:00:00"
    rows = [
        ("5/20 08:00 首都机场->酒店 4人 2箱 丰田埃尔法 张先生 600", "parsed", today, "08:00", "10:30", "首都机场", "酒店", "接机", "丰田埃尔法", 600, None),
        ("5/20 11:00 酒店->故宫 4人 市内包车 别克GL8 800", "parsed", today, "11:00", "14:00", "酒店", "故宫", "市内包车", "别克GL8", 800, None),
        ("5/20 15:00 故宫->颐和园 4人 丰田埃尔法 700", "parsed", today, "15:00", "17:30", "故宫", "颐和园", "市内包车", "丰田埃尔法", 700, None),
        ("完全无法识别但必须保留的自由文本 A", "failed", None, None, None, None, None, None, None, None, None),
        ("客户只发了图片，文字无法解析，待人工补录", "failed", None, None, None, None, None, None, None, None, None),
    ]
    for index, row in enumerate(rows, start=1):
        raw_text, status, day, start_time, end_time, pickup, dropoff, order_type, vehicle_type, price, _ = row
        oid = f"{today:%Y%m%d}-{index:03d}"
        order_date = day.isoformat() if day else None
        conn.execute(
            """
            INSERT INTO order_drafts (
                oid, raw_text, source_type, parse_status, order_date, end_date,
                start_time, end_time, pickup_location, dropoff_location,
                order_type, vehicle_type, passenger_count, luggage_count,
                agency_name, price, remark, parse_result_json, created_at, updated_at
            )
            VALUES (?, ?, 'text', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                oid,
                raw_text,
                status,
                order_date,
                order_date,
                start_time,
                end_time,
                pickup,
                dropoff,
                order_type,
                vehicle_type,
                4 if status == "parsed" else None,
                2 if status == "parsed" else None,
                "东京旅运" if status == "parsed" else None,
                price,
                raw_text,
                json.dumps({"status": status, "raw_text": raw_text}, ensure_ascii=False),
                created_at,
                created_at,
            ),
        )


if __name__ == "__main__":
    main()

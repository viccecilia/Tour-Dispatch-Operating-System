import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import get_connection, init_db, refresh_order_oids


AGENCIES = [
    ("东京旅运", "张经理", "090-2000-0001"),
    ("樱花旅行", "李经理", "090-2000-0002"),
    ("富士观光", "王经理", "090-2000-0003"),
    ("关西地接", "赵经理", "090-2000-0004"),
    ("日和假期", "陈经理", "090-2000-0005"),
]

DRIVERS = [
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

VEHICLES = [
    ("なにわ330を1001", "1001", "H", "ハイエース", 10, "白", "雪", "available"),
    ("なにわ330う1021", "1021", "H", "ハイエース", 10, "白", "", "available"),
    ("なにわ330い1027", "1027", "H", "ハイエース", 10, "黒", "雪", "available"),
    ("なにわ300あ7886", "7886", "H", "ハイエース", 10, "白", "雪", "available"),
    ("なにわ330う710", "710", "A", "ヴェルファHV", 7, "黒", "", "available"),
    ("なにわ300あ6637", "6637", "A", "30系アルファード", 7, "黒", "雪", "available"),
    ("なにわ300あ6644", "6644", "A", "30系アルファード", 7, "黒", "雪", "available"),
    ("なにわ300あ6781", "6781", "A", "ヴェルファHV", 7, "黒", "", "available"),
    ("なにわ300あ7007", "7007", "A", "30系アルファード", 7, "黒", "雪", "available"),
    ("なにわ300あ7011", "7011", "A", "ヴェルファHV", 7, "黒", "", "available"),
    ("なにわ300あ7012", "7012", "A", "30系アルファード", 7, "黒", "", "available"),
    ("なにわ300あ7025", "7025", "A", "30系アルファード", 7, "白", "", "available"),
    ("なにわ300あ7026", "7026", "A", "30系アルファード", 7, "黒", "", "available"),
    ("なにわ300あ6832", "6832", "A", "30系アルファードHV", 7, "黒", "", "available"),
    ("なにわ300あ7495", "7495", "A", "30系アルファード", 7, "黒", "", "available"),
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
        _normalize_business_fields(conn)
        refresh_order_oids(conn)
        conn.commit()

    result = {
        "date": today.isoformat(),
        "orders_today": 40,
        "unassigned_orders": 10,
        "active_assignments": len(assignment_ids),
        "drivers": 15,
        "vehicles": 15,
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
    codes = ["D", "X", "K", "S", "N"]
    for index, (name, contact_name, contact_phone) in enumerate(AGENCIES):
        cursor = conn.execute(
            """
            INSERT INTO agencies (
                agency_code, company_name, name, address, contact_name, contact_phone,
                responsible_person, contact_email, fax, status, remark, portal_code,
                is_portal_enabled, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 1, CURRENT_TIMESTAMP)
            """,
            (
                codes[index % len(codes)],
                name,
                name,
                f"大阪市中央区演示町 {index + 1}-1",
                contact_name,
                contact_phone,
                f"担当{index + 1}",
                f"agency{index + 1}@demo.local",
                f"06-0000-00{index + 1:02d}",
                "演示旅行社资料，可在旅行社维护页编辑。",
                f"{codes[index % len(codes)]}100{index + 1}",
            ),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_drivers(conn) -> list[int]:
    ids = []
    today = date.today()
    for index, (name, driver_code, driver_language, office, phone, status) in enumerate(DRIVERS):
        license_due = today + timedelta(days=15 + index * 7)
        health_due = today + timedelta(days=20 + index * 6)
        cursor = conn.execute(
            """
            INSERT INTO drivers (
                name, driver_code, driver_language, office, phone, status, driver_status,
                license_due_date, health_check_due_date, license_expires_at, medical_check_expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                name,
                driver_code,
                driver_language,
                office,
                phone,
                status,
                status,
                license_due.isoformat(),
                health_due.isoformat(),
                license_due.isoformat(),
                health_due.isoformat(),
            ),
        )
        ids.append(cursor.lastrowid)
    return ids


def _seed_vehicles(conn) -> list[int]:
    ids = []
    today = date.today()
    for index, (plate_number, plate_short_code, vehicle_type_code, vehicle_type, seat_count, color, snow_tire, status) in enumerate(VEHICLES):
        last_inspection = today - timedelta(days=65 - (index % 6))
        next_inspection = today + timedelta(days=10 + index * 4)
        shaken_due = today + timedelta(days=12 + index * 9)
        insurance_due = today + timedelta(days=45 + index * 11)
        cursor = conn.execute(
            """
            INSERT INTO vehicles (
                plate_no, plate_number, plate_short_code, vehicle_type_code,
                vehicle_type, seats, seat_count, vehicle_color, snow_tire, status,
                last_inspection_date, next_inspection_due_date, shaken_due_date, insurance_due_date,
                inspection_expires_at, insurance_expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                plate_number,
                plate_number,
                plate_short_code,
                vehicle_type_code,
                vehicle_type,
                seat_count,
                seat_count,
                color,
                snow_tire,
                status,
                last_inspection.isoformat(),
                next_inspection.isoformat(),
                shaken_due.isoformat(),
                insurance_due.isoformat(),
                next_inspection.isoformat(),
                insurance_due.isoformat(),
            ),
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


def _normalize_business_fields(conn) -> None:
    conn.execute(
        """
        UPDATE orders
        SET order_note_code = COALESCE(NULLIF(order_note_code, ''), 'D'),
            order_source = COALESCE(NULLIF(order_source, ''), agency_name),
            price_rmb = COALESCE(price_rmb, price),
            vehicle_type_code = COALESCE(
                NULLIF(vehicle_type_code, ''),
                CASE
                    WHEN vehicle_type LIKE '%10%' OR vehicle_type LIKE '%海%' THEN 'H'
                    WHEN vehicle_type LIKE '%18%' OR vehicle_type LIKE '%中%' THEN 'C'
                    ELSE 'A'
                END
            )
        """
    )
    conn.execute(
        """
        UPDATE order_drafts
        SET order_note_code = COALESCE(NULLIF(order_note_code, ''), 'D'),
            order_source = COALESCE(NULLIF(order_source, ''), agency_name),
            price_rmb = COALESCE(price_rmb, price),
            vehicle_type_code = COALESCE(
                NULLIF(vehicle_type_code, ''),
                CASE
                    WHEN vehicle_type LIKE '%10%' OR vehicle_type LIKE '%海%' THEN 'H'
                    WHEN vehicle_type LIKE '%18%' OR vehicle_type LIKE '%中%' THEN 'C'
                    ELSE 'A'
                END
            )
        """
    )


if __name__ == "__main__":
    main()

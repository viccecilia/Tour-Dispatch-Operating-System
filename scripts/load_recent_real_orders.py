from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import DB_PATH
from backend.db.database import init_db
from backend.services.order_number_service import build_order_oid


@dataclass(frozen=True)
class RealOrderSeed:
    raw_text: str
    start_time: str
    end_time: str
    pickup_location: str
    dropoff_location: str
    order_type: str
    vehicle_type: str
    price: float
    vehicle_color: str = ""
    snow_tire: str = "no"
    fee_remark: str = ""
    other_fee_jpy: float | None = None
    remark: str = ""


REAL_ORDERS: list[RealOrderSeed] = [
    RealOrderSeed("3.29 10:00 大阪单送名古屋 10座 1700", "10:00", "13:00", "大阪", "名古屋", "单送", "10座", 1700),
    RealOrderSeed("3.29 14:10 关西接机大阪 10座600", "14:10", "15:40", "关西机场", "大阪", "接机", "10座", 600),
    RealOrderSeed("3.29 08:05 关西接机大阪 10座600", "08:05", "09:35", "关西机场", "大阪", "接机", "10座", 600),
    RealOrderSeed("3.29 08:00/20:00 环球往返接送 3代600", "08:00", "20:00", "酒店", "环球影城往返", "往返接送", "3代", 600),
    RealOrderSeed("3.29 07:30 大阪单送新大阪 3代 300", "07:30", "08:15", "大阪", "新大阪", "单送", "3代", 300),
    RealOrderSeed("3.29 08:20 京都送机关西 3代 绿800", "08:20", "10:00", "京都", "关西机场", "送机", "3代", 800, vehicle_color="绿"),
    RealOrderSeed("3.29 19:30 京都单送关西酒店 3代绿 600+4000", "19:30", "21:00", "京都", "关西酒店", "单送", "3代", 600, vehicle_color="绿", fee_remark="另收 4000", other_fee_jpy=4000),
    RealOrderSeed("3.29 14:00 关西接机京都 3代 绿800", "14:00", "15:40", "关西机场", "京都", "接机", "3代", 800, vehicle_color="绿"),
    RealOrderSeed("3.29 11:00 大阪送机神户机场 3代 绿450", "11:00", "12:20", "大阪", "神户机场", "送机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 07:30 大阪送机关西 3代 绿450", "07:30", "08:40", "大阪", "关西机场", "送机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 11:30 大阪送机关西 3代 儿童座椅 绿450", "11:30", "12:40", "大阪", "关西机场", "送机", "3代", 450, vehicle_color="绿", remark="儿童座椅"),
    RealOrderSeed("3.29 13:00 大阪单送关西酒店 3代 绿450", "13:00", "14:10", "大阪", "关西酒店", "单送", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 11:25 关西接机大阪 3代 儿童座椅 绿450", "11:25", "12:40", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿", remark="儿童座椅"),
    RealOrderSeed("3.29 13:05 关西接机大阪 3代 绿450", "13:05", "14:20", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 15:00 关西接机大阪 3代 绿450", "15:00", "16:15", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 16:10 关西接机大阪 3代 绿450", "16:10", "17:25", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 19:30 关西接机大阪 3代 绿450", "19:30", "20:45", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 21:15 关西接机大阪 3代 绿450", "21:15", "22:30", "关西机场", "大阪", "接机", "3代", 450, vehicle_color="绿"),
    RealOrderSeed("3.29 06:30 大阪送机关西 10座 绿600", "06:30", "07:45", "大阪", "关西机场", "送机", "10座", 600, vehicle_color="绿"),
]


TRANSACTION_TABLES = [
    "driver_evidence_uploads",
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


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return row is not None


def clear_transaction_tables(conn: sqlite3.Connection) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for table_name in TRANSACTION_TABLES:
        if not table_exists(conn, table_name):
            continue
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        conn.execute(f"DELETE FROM {table_name}")
        deleted[table_name] = count
    for table_name in TRANSACTION_TABLES:
        if table_exists(conn, table_name):
            conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
    return deleted


def vehicle_type_code(vehicle_type: str) -> str:
    return "H" if "10" in vehicle_type else "A"


def insert_orders(conn: sqlite3.Connection, order_date: str) -> list[str]:
    oids: list[str] = []
    for index, order in enumerate(sorted(REAL_ORDERS, key=lambda item: item.start_time), start=1):
        code = vehicle_type_code(order.vehicle_type)
        oid = build_order_oid(
            order_note_code="D",
            order_date=order_date,
            serial=index,
            vehicle_type_code=code,
            temporary=True,
        )
        remark_parts = [f"真实样本平移自 3.29：{order.raw_text}"]
        if order.remark:
            remark_parts.append(order.remark)
        conn.execute(
            """
            INSERT INTO orders (
                tenant_id, oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, vehicle_type,
                order_note_code, order_source, vehicle_type_code, vehicle_color, snow_tire,
                price, price_jpy, fee_remark, other_fee_jpy, remark,
                dispatch_status, execution_status, settlement_status,
                driver_settlement_status, agency_settlement_status, is_deleted
            )
            VALUES (
                1, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                'D', '真实订单样本', ?, ?, ?,
                ?, ?, ?, ?, ?,
                'unassigned', 'assigned', 'pending',
                'pending', 'pending', 0
            )
            """,
            (
                oid,
                order_date,
                order_date,
                order.start_time,
                order.end_time,
                order.pickup_location,
                order.dropoff_location,
                order.order_type,
                order.vehicle_type,
                code,
                order.vehicle_color,
                order.snow_tire,
                order.price,
                order.price,
                order.fee_remark,
                order.other_fee_jpy,
                "；".join(remark_parts),
            ),
        )
        oids.append(oid)
    return oids


def main() -> None:
    init_db(seed=True)
    order_date = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        deleted = clear_transaction_tables(conn)
        oids = insert_orders(conn, order_date)
        conn.commit()
    print(f"database={DB_PATH}")
    print(f"order_date={order_date}")
    print(f"deleted={deleted}")
    print(f"inserted_orders={len(oids)}")
    print("first_oid=" + (oids[0] if oids else "-"))
    print("last_oid=" + (oids[-1] if oids else "-"))


if __name__ == "__main__":
    main()

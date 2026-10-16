"""Start a localhost-only M1 acceptance demo against an explicitly isolated SQLite file."""

from __future__ import annotations

import os
import sys
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api.routes import ApiHandler
from backend.db import database
from backend.services.driver_provisional_service import (
    create_driver_provisional_task,
    price_company_provisional_task,
    review_company_provisional_task,
    submit_driver_provisional_task,
)


def seed() -> None:
    database.init_db(seed=True)
    with closing(database.get_connection()) as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = 'm1_admin'").fetchone():
            return
        driver_id = int(conn.execute(
            "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, 'M1 验收司机', 'available', 'available')"
        ).lastrowid)
        driver_user_id = int(conn.execute(
            """INSERT INTO users (tenant_id, username, password_hash, role, account_scope, display_name, is_active,
                                  profile_type, profile_id)
               VALUES (1, 'm1_driver', ?, 'driver', 'driver', 'M1 验收司机', 1, 'driver', ?)""",
            (database.hash_password("test123"), driver_id),
        ).lastrowid)
        conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (driver_user_id, driver_id))
        admin_user_id = int(conn.execute(
            """INSERT INTO users (tenant_id, username, password_hash, role, account_scope, display_name, is_active)
               VALUES (1, 'm1_admin', ?, 'admin', 'carrier', 'M1 车公司管理员', 1)""",
            (database.hash_password("test123"),),
        ).lastrowid)
        vehicle_id = int(conn.execute(
            "INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (1, '大阪500あM115', 'available')"
        ).lastrowid)
        order_id = int(conn.execute(
            """INSERT INTO orders (tenant_id, oid, order_date, end_date, start_time, end_time,
                                   pickup_location, dropoff_location, order_type, dispatch_status, execution_status)
               VALUES (1, 'M1-DEMO-SHIFT', '2026-10-15', '2026-10-15', '08:00', '20:00',
                       '大阪車庫', '大阪車庫', 'charter', 'assigned', 'assigned')"""
        ).lastrowid)
        conn.execute(
            """INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
                                         assigned_at, published_at)
               VALUES (1, ?, ?, ?, 'active', 'assigned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (order_id, driver_id, vehicle_id),
        )
        conn.commit()

    driver = {
        "id": driver_user_id, "tenant_id": 1, "role": "driver", "account_scope": "driver",
        "profile_id": driver_id, "display_name": "M1 验收司机",
    }
    admin = {
        "id": admin_user_id, "tenant_id": 1, "role": "admin", "account_scope": "carrier",
        "display_name": "M1 车公司管理员",
    }
    common = {
        "business_date": "2026-10-15", "service_kind": "airport_transfer",
        "service_source": "company_admin_phone", "authorization_source": "carrier_admin_phone",
        "authorization_evidence": "M1 本地隔离验收联络记录", "actual_pickup_location": "関西空港 T1",
        "actual_pickup_at": "2026-10-15T13:20:00+09:00", "actual_dropoff_location": "大阪市内ホテル",
        "actual_dropoff_at": "2026-10-15T14:20:00+09:00", "pickup_odometer_km": 120.1,
        "dropoff_odometer_km": 128.4, "note": "仅用于本地 M1 人工验收",
    }
    pending = create_driver_provisional_task(driver, {**common, "client_request_id": "m1-demo-pending-create"})["task"]
    submit_driver_provisional_task(driver, pending["provisional_task_id"], {
        "client_request_id": "m1-demo-pending-submit", "expected_revision": pending["revision"]
    })
    approved = create_driver_provisional_task(driver, {
        **common, "client_request_id": "m1-demo-approved-create", "actual_pickup_location": "伊丹空港",
        "actual_dropoff_location": "梅田ホテル", "pickup_odometer_km": 210.0, "dropoff_odometer_km": 226.5,
    })["task"]
    approved = submit_driver_provisional_task(driver, approved["provisional_task_id"], {
        "client_request_id": "m1-demo-approved-submit", "expected_revision": approved["revision"]
    })["task"]
    approved_result = review_company_provisional_task(admin, approved["provisional_task_id"], "approve-create", {
        "client_request_id": "m1-demo-approved-review", "expected_revision": approved["revision"],
        "reason": "本地验收确认",
    })
    price_company_provisional_task(admin, approved["provisional_task_id"], {
        "client_request_id": "m1-demo-approved-price", "expected_revision": approved_result["task"]["revision"],
        "price_jpy": 19500, "driver_salary_jpy": 7500, "driver_settlement_amount": 7500,
        "driver_settlement_status": "pending", "reason": "本地验收定价",
    })


def main() -> None:
    db_path = str(database.DB_PATH)
    if "m1" not in db_path.lower() or "artifacts" not in db_path.lower():
        raise RuntimeError(f"isolated_m1_database_required:{db_path}")
    seed()
    host = "127.0.0.1"
    port = int(os.environ.get("WX_DISPATCH_PORT", "18766"))
    print(f"M1 local demo API: http://{host}:{port}", flush=True)
    print("Carrier admin: m1_admin / test123", flush=True)
    ThreadingHTTPServer((host, port), ApiHandler).serve_forever()


if __name__ == "__main__":
    main()

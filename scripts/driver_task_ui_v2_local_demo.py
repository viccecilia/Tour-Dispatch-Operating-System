"""Run a localhost-only Driver Task UI V2 acceptance fixture.

The database path must explicitly live under an artifacts/driver-task-ui-v2
directory.  This fixture never connects to Trial or Production.
"""

from __future__ import annotations

import json
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
from backend.services.document_model_service import make_run_group_id, stable_id


FIXTURE_DATES = {
    "2026-10-13": "assigned",
    "2026-10-14": "in_service",
    "2026-10-15": "returned",
    "2026-10-16": "completed",
    "2026-10-17": "assigned",
}
FIXTURE_TASK_COUNTS = {"2026-10-17": 10}
ZERO_TASK_DATE = "2026-10-12"
HOME_SCENARIO = os.environ.get("DRIVER_HOME_UI_V2_SCENARIO", "").strip().lower()


def insert_node(conn, *, tenant_id, run_group_id, version_id, driver_id, vehicle_id,
                business_date, sequence, order_id, node_type, location, arrival, departure):
    route_node_id = stable_id("node", run_group_id, order_id or 0, node_type, sequence)
    conn.execute(
        """INSERT INTO dispatch_route_nodes
           (tenant_id, route_node_id, run_group_id, document_version_id, driver_id,
            vehicle_id, business_date, sequence_number, order_id, node_type,
            planned_location, planned_arrival_at, planned_departure_at, load_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned')""",
        (tenant_id, route_node_id, run_group_id, version_id, driver_id, vehicle_id,
         business_date, sequence, order_id, node_type, location, arrival, departure),
    )


def create_plan(conn, driver_id: int, vehicle_id: int, business_date: str, status: str,
                task_count: int = 3) -> int:
    tenant_id = 1
    run_group_id = make_run_group_id(tenant_id, business_date, driver_id, vehicle_id)
    version_id = f"ui-v2-{business_date}"
    source_sha = stable_id("source", run_group_id, task_count)
    conn.execute(
        """INSERT INTO driver_run_documents
           (tenant_id, business_date, driver_id, vehicle_id, version, status, source_hash,
            file_name, file_path, file_url, page_count, published_at, document_id,
            document_version_id, run_group_id, lifecycle_status, snapshot_json, source_sha256)
           VALUES (?, ?, ?, ?, 1, 'published', ?, ?, ?, ?, 2, CURRENT_TIMESTAMP,
                   ?, ?, ?, 'published', '{}', ?)""",
        (tenant_id, business_date, driver_id, vehicle_id, source_sha,
         f"{version_id}.pdf", f"C:/isolated/{version_id}.pdf", f"/isolated/{version_id}.pdf",
         stable_id("doc", run_group_id), version_id, run_group_id, source_sha),
    )
    sequence = 1
    insert_node(
        conn, tenant_id=tenant_id, run_group_id=run_group_id, version_id=version_id,
        driver_id=driver_id, vehicle_id=vehicle_id, business_date=business_date,
        sequence=sequence, order_id=None, node_type="garage_out", location="大阪営業所車庫",
        arrival=None, departure=f"{business_date}T07:30:00",
    )
    first_assignment_id = 0
    routes = (
        ("関西空港 T1", "梅田ホテル"),
        ("新大阪駅", "京都駅八条口"),
        ("大阪城公園", "なんばホテル"),
    )
    for index in range(1, task_count + 1):
        pickup, dropoff = routes[(index - 1) % len(routes)]
        start_hour = 7 + index
        conn.execute(
            """INSERT INTO orders
               (tenant_id, oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, dispatch_status, execution_status)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, 'airport', 'assigned', ?)""",
            (f"UIV2-{business_date.replace('-', '')}-{index}", business_date, business_date,
             f"{start_hour:02d}:00", f"{start_hour + 1:02d}:00", pickup, dropoff, status),
        )
        order_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """INSERT INTO assignments
               (tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
                assigned_at, published_at)
               VALUES (1, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (order_id, driver_id, vehicle_id, status),
        )
        assignment_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        first_assignment_id = first_assignment_id or assignment_id
        sequence += 1
        insert_node(
            conn, tenant_id=tenant_id, run_group_id=run_group_id, version_id=version_id,
            driver_id=driver_id, vehicle_id=vehicle_id, business_date=business_date,
            sequence=sequence, order_id=order_id, node_type="pickup", location=pickup,
            arrival=f"{business_date}T{start_hour - 1:02d}:50:00",
            departure=f"{business_date}T{start_hour:02d}:00:00",
        )
        sequence += 1
        insert_node(
            conn, tenant_id=tenant_id, run_group_id=run_group_id, version_id=version_id,
            driver_id=driver_id, vehicle_id=vehicle_id, business_date=business_date,
            sequence=sequence, order_id=order_id, node_type="dropoff", location=dropoff,
            arrival=f"{business_date}T{start_hour + 1:02d}:00:00",
            departure=f"{business_date}T{start_hour + 1:02d}:10:00",
        )
    sequence += 1
    insert_node(
        conn, tenant_id=tenant_id, run_group_id=run_group_id, version_id=version_id,
        driver_id=driver_id, vehicle_id=vehicle_id, business_date=business_date,
        sequence=sequence, order_id=None, node_type="garage_in", location="大阪営業所車庫",
        arrival=f"{business_date}T20:00:00", departure=None,
    )
    return first_assignment_id


def insert_workflow(conn, driver_id: int, assignment_id: int, business_date: str,
                    event_type: str, time_text: str, note: dict):
    order_id = conn.execute("SELECT order_id FROM assignments WHERE id = ?", (assignment_id,)).fetchone()[0]
    conn.execute(
        """INSERT INTO driver_workflow_events
           (tenant_id, driver_id, assignment_id, order_id, event_type, event_status,
            location_text, note, event_time)
           VALUES (1, ?, ?, ?, ?, 'submitted', '大阪営業所車庫', ?, ?)""",
        (driver_id, assignment_id, order_id, event_type,
         json.dumps(note, ensure_ascii=False), f"{business_date} {time_text}:00"),
    )


def seed() -> None:
    db_path = Path(database.DB_PATH).resolve()
    normalized = str(db_path).replace("\\", "/").lower()
    if "/artifacts/driver-task-ui-v2/" not in normalized:
        raise RuntimeError(f"isolated_driver_task_ui_v2_database_required:{db_path}")
    database.init_db(seed=True)
    with closing(database.get_connection()) as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = 'ui_v2_driver'").fetchone()
        if existing:
            return
        conn.execute(
            "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, 'UI V2 验收司机', 'available', 'available')"
        )
        driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """INSERT INTO users
               (tenant_id, username, password_hash, role, display_name, is_active,
                profile_type, profile_id, account_scope)
               VALUES (1, 'ui_v2_driver', ?, 'driver', 'UI V2 验收司机', 1, 'driver', ?, 'driver')""",
            (database.hash_password("test123"), driver_id),
        )
        user_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (user_id, driver_id))
        conn.execute("INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (1, '大阪500あ2016', 'available')")
        vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        if HOME_SCENARIO:
            if HOME_SCENARIO not in {"no_tasks", "not_departed", "running", "returned"}:
                raise RuntimeError(f"invalid_driver_home_ui_v2_scenario:{HOME_SCENARIO}")
            if HOME_SCENARIO != "no_tasks":
                execution_status = {
                    "not_departed": "assigned",
                    "running": "in_service",
                    "returned": "returned",
                }[HOME_SCENARIO]
                assignment_id = create_plan(
                    conn, driver_id, vehicle_id, "2026-10-16", execution_status, task_count=3
                )
                if HOME_SCENARIO in {"running", "returned"}:
                    insert_workflow(conn, driver_id, assignment_id, "2026-10-16", "depart_yard", "07:40", {
                        "sleep_hours": 7.5,
                        "checks": ["light", "brake", "body", "license", "certificate", "alcohol", "sleep"],
                    })
                    insert_workflow(conn, driver_id, assignment_id, "2026-10-16", "alcohol_test_out", "07:38", {
                        "attachments": [{"kind": "alcohol_test_out", "name": "出库酒测.jpg"}],
                    })
                if HOME_SCENARIO == "returned":
                    insert_workflow(conn, driver_id, assignment_id, "2026-10-16", "return_yard", "20:10", {
                        "rest_hours": 1.5,
                        "checks": ["clean", "inspection", "alcohol", "roll_call"],
                    })
                    insert_workflow(conn, driver_id, assignment_id, "2026-10-16", "alcohol_test_in", "20:08", {
                        "attachments": [{"kind": "alcohol_test_in", "name": "入库酒测.jpg"}],
                    })
        else:
            first_assignments = {
                day: create_plan(
                    conn,
                    driver_id,
                    vehicle_id,
                    day,
                    status,
                    task_count=FIXTURE_TASK_COUNTS.get(day, 3),
                )
                for day, status in FIXTURE_DATES.items()
            }
            for day in ("2026-10-14", "2026-10-15", "2026-10-16"):
                assignment_id = first_assignments[day]
                insert_workflow(conn, driver_id, assignment_id, day, "depart_yard", "07:40", {
                    "sleep_hours": 7.5,
                    "checks": ["light", "brake", "body", "license", "certificate", "alcohol", "sleep"],
                })
                insert_workflow(conn, driver_id, assignment_id, day, "alcohol_test_out", "07:38", {
                    "attachments": [{"kind": "alcohol_test_out", "name": "出库酒测.jpg"}],
                })
            for day in ("2026-10-15", "2026-10-16"):
                assignment_id = first_assignments[day]
                insert_workflow(conn, driver_id, assignment_id, day, "return_yard", "20:10", {
                    "rest_hours": 1.5,
                    "checks": ["clean", "inspection", "alcohol", "roll_call"],
                })
                insert_workflow(conn, driver_id, assignment_id, day, "alcohol_test_in", "20:08", {
                    "attachments": [{"kind": "alcohol_test_in", "name": "入库酒测.jpg"}],
                })
            conn.execute(
                """INSERT INTO driver_daily_reports
                   (tenant_id, driver_id, business_date, status, assignment_snapshot_json,
                    summary, rest_hours, submitted_at)
                   VALUES (1, ?, '2026-10-15', 'draft', '[]', '日报尚待正式提交', 1.5, NULL)""",
                (driver_id,),
            )
            conn.execute(
                """INSERT INTO driver_daily_reports
                   (tenant_id, driver_id, business_date, status, assignment_snapshot_json,
                    summary, rest_hours, submitted_at)
                   VALUES (1, ?, '2026-10-16', 'submitted', '[]', '当日运行正常', 1.5, CURRENT_TIMESTAMP)""",
                (driver_id,),
            )
        conn.commit()


def main() -> None:
    seed()
    host = "127.0.0.1"
    port = int(os.environ.get("WX_DISPATCH_PORT", "18765"))
    print(f"Driver Task UI V2 local API: http://{host}:{port}", flush=True)
    print("Fixture account: ui_v2_driver / test123", flush=True)
    if HOME_SCENARIO:
        print(f"Driver Home UI V2 scenario: {HOME_SCENARIO}", flush=True)
    else:
        print(f"Zero-task date: {ZERO_TASK_DATE}", flush=True)
        print("Three-task states: 2026-10-13 .. 2026-10-16", flush=True)
        print("Ten-task date: 2026-10-17", flush=True)
    ThreadingHTTPServer((host, port), ApiHandler).serve_forever()


if __name__ == "__main__":
    main()

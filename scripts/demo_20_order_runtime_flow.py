from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import DB_PATH
from backend.db.database import init_db


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
TOKEN = ""
TENANT_ID = 1

DEMO_PHOTO_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mNk+M8AAwUBAZv4YVQAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class DemoOrderSpec:
    raw_text: str
    day_offset: int
    start_time: str
    end_time: str
    pickup_location: str
    dropoff_location: str
    order_type: str
    vehicle_type: str
    price: int
    remark: str = ""


REAL_ORDER_SPECS: list[DemoOrderSpec] = [
    DemoOrderSpec("3.29 06:30 大阪送机关西 10座 绿600", 0, "06:30", "07:45", "大阪市内", "KIX", "送机", "10座", 600, "绿牌"),
    DemoOrderSpec("3.29 07:30 大阪单送新大阪 3代 300", 0, "07:30", "08:15", "大阪市内", "新大阪站", "单送", "3代", 300),
    DemoOrderSpec("3.29 08:05 关西接机大阪 10座600", 0, "08:05", "09:35", "KIX", "大阪市内", "接机", "10座", 600),
    DemoOrderSpec("3.29 08:20 京都送机关西 3代 绿800", 0, "08:20", "10:00", "京都市内", "KIX", "送机", "3代", 800, "绿牌"),
    DemoOrderSpec("3.29 10:00 大阪单送名古屋 10座 1700", 0, "10:00", "13:00", "大阪市内", "名古屋", "单送", "10座", 1700),
    DemoOrderSpec("3.29 11:00 大阪送机神户机场 3代 绿450", 0, "11:00", "12:20", "大阪市内", "神户机场", "送机", "3代", 450, "绿牌"),
    DemoOrderSpec("3.29 11:25 关西接机大阪 3代 儿童座椅 绿450", 0, "11:25", "12:40", "KIX", "大阪市内", "接机", "3代", 450, "儿童座椅；绿牌"),
    DemoOrderSpec("3.29 13:00 大阪单送关西酒店 3代 绿450", 0, "13:00", "14:10", "大阪市内", "关西酒店", "单送", "3代", 450, "绿牌"),
    DemoOrderSpec("3.29 14:00 关西接机京都 3代 绿800", 0, "14:00", "15:40", "KIX", "京都市内", "接机", "3代", 800, "绿牌"),
    DemoOrderSpec("3.29 15:00 关西接机大阪 3代 绿450", 0, "15:00", "16:15", "KIX", "大阪市内", "接机", "3代", 450, "绿牌"),
    DemoOrderSpec("12.10 05:00 大阪送机关西 3代500", 1, "05:00", "06:15", "大阪市内", "KIX", "送机", "3代", 500),
    DemoOrderSpec("12.10 08:35 关西举牌接机伊丹 3代 绿630", 1, "08:35", "10:00", "KIX", "伊丹机场", "接机", "3代", 630, "举牌；绿牌"),
    DemoOrderSpec("12.10 11:00 京都送机关西 3代 绿900", 1, "11:00", "12:40", "京都市内", "KIX", "送机", "3代", 900, "绿牌"),
    DemoOrderSpec("12.10 12:30 关西接机京都 10座 绿 1000", 1, "12:30", "14:20", "KIX", "京都市内", "接机", "10座", 1000, "绿牌"),
    DemoOrderSpec("12.10 13:00 大阪送机关西 10座 绿 650", 1, "13:00", "14:20", "大阪市内", "KIX", "送机", "10座", 650, "绿牌"),
    DemoOrderSpec("12.10 16:45 新大阪接站市内 2代300", 1, "16:45", "17:35", "新大阪站", "大阪市内", "接站", "2代", 300),
    DemoOrderSpec("12.11 06:20 大阪送机关西 3代 绿530", 2, "06:20", "07:35", "大阪市内", "KIX", "送机", "3代", 530, "绿牌"),
    DemoOrderSpec("12.11 10:00 京都单送大阪 10座 绿 750", 2, "10:00", "11:45", "京都市内", "大阪市内", "单送", "10座", 750, "绿牌"),
    DemoOrderSpec("12.11 12:45 关西接机大阪 3代绿 儿童座椅2 530+2000", 2, "12:45", "14:00", "KIX", "大阪市内", "接机", "3代", 530, "儿童座椅2；附加费用2000"),
    DemoOrderSpec("12.11 21:30 关西接机大阪 10座 650-", 2, "21:30", "22:45", "KIX", "大阪市内", "接机", "10座", 650),
]


TRANSACTION_TABLES = [
    "driver_evidence_uploads",
    "driver_expense_reports",
    "driver_reports",
    "driver_workflow_events",
    "location_logs",
    "notifications",
    "assignments",
    "order_drafts",
    "orders",
]


def request(method: str, path: str, payload: dict[str, Any] | None = None, *, token: bool = True) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if TOKEN and token:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            parsed["_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def login() -> None:
    global TOKEN
    ping = request("GET", "/api/ping", token=False)
    if ping.get("ok") is not True:
        raise RuntimeError(f"backend ping failed: {ping}")
    auth = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"}, token=False)
    TOKEN = str(auth.get("token") or "")
    if not TOKEN:
        raise RuntimeError(f"admin login failed: {auth}")


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone() is not None


def clear_runtime_tables() -> dict[str, int]:
    init_db(seed=True)
    deleted: dict[str, int] = {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table_name in TRANSACTION_TABLES:
            if not table_exists(conn, table_name):
                continue
            count = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            conn.execute(f"DELETE FROM {table_name}")
            deleted[table_name] = count
        if table_exists(conn, "sqlite_sequence"):
            for table_name in TRANSACTION_TABLES:
                conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
        if table_exists(conn, "drivers"):
            conn.execute(
                "UPDATE drivers SET status='available', driver_status=COALESCE(NULLIF(driver_status,''),'available'), updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
                (TENANT_ID,),
            )
        if table_exists(conn, "vehicles"):
            conn.execute(
                "UPDATE vehicles SET status='available', maintenance_status=COALESCE(NULLIF(maintenance_status,''),'available'), updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
                (TENANT_ID,),
            )
        conn.commit()
    return deleted


def order_date(spec: DemoOrderSpec) -> str:
    return (date.today() + timedelta(days=spec.day_offset)).isoformat()


def raw_text() -> str:
    return "\n".join(spec.raw_text for spec in REAL_ORDER_SPECS)


def vehicle_code(vehicle_type: str) -> str:
    return "H" if "10" in vehicle_type else "A"


def parse_and_correct_drafts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    response = request("POST", "/api/parser/text", {"text": raw_text(), "batch": True})
    drafts = list(response.get("drafts") or [])
    if len(drafts) < len(REAL_ORDER_SPECS):
        raise RuntimeError(f"parser returned {len(drafts)} drafts, expected {len(REAL_ORDER_SPECS)}")

    corrected: list[dict[str, Any]] = []
    correction_log: list[dict[str, Any]] = []
    for index, (draft, spec) in enumerate(zip(drafts[: len(REAL_ORDER_SPECS)], REAL_ORDER_SPECS, strict=True), start=1):
        before = {
            "order_date": draft.get("order_date"),
            "start_time": draft.get("start_time"),
            "pickup_location": draft.get("pickup_location"),
            "dropoff_location": draft.get("dropoff_location"),
            "vehicle_type": draft.get("vehicle_type"),
            "price": draft.get("price"),
        }
        payload = {
            "order_date": order_date(spec),
            "end_date": order_date(spec),
            "start_time": spec.start_time,
            "end_time": spec.end_time,
            "pickup_location": spec.pickup_location,
            "dropoff_location": spec.dropoff_location,
            "order_type": spec.order_type,
            "vehicle_type": spec.vehicle_type,
            "vehicle_class": spec.vehicle_type,
            "vehicle_type_code": vehicle_code(spec.vehicle_type),
            "passenger_count": 0,
            "luggage_count": 0,
            "guest_name": f"演示客人{index:02d}",
            "guest_contact": f"090-0000-{1200 + index}",
            "agency_name": "东京旅运",
            "price": spec.price,
            "price_jpy": spec.price,
            "remark": "；".join(part for part in [spec.remark, f"原始订单：{spec.raw_text}"] if part),
            "parse_status": "parsed",
        }
        updated = request("PUT", f"/api/parser/drafts/{draft['id']}", payload).get("draft")
        corrected.append(updated)
        if before != {key: payload.get(key) for key in before}:
            correction_log.append({"draft_id": draft["id"], "before": before, "after": {key: payload.get(key) for key in before}})
    return corrected, correction_log


def confirm_drafts(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for draft in drafts:
        confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm")
        order = request("GET", f"/api/orders/{confirmed['order_id']}").get("order")
        if not order:
            raise RuntimeError(f"failed to read confirmed order for draft {draft['id']}")
        orders.append(order)
    return orders


def minutes(value: str | None) -> int:
    if not value or ":" not in value:
        return 0
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def overlaps(a: tuple[str, int, int], b: tuple[str, int, int]) -> bool:
    return a[0] == b[0] and a[1] < b[2] and b[1] < a[2]


def load_resources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drivers = request("GET", "/api/resources/drivers").get("drivers", [])
    vehicles = request("GET", "/api/resources/vehicles").get("vehicles", [])
    drivers = [d for d in drivers if (d.get("status") or "available") not in {"inactive", "disabled"}]
    vehicles = [v for v in vehicles if (v.get("status") or "available") not in {"inactive", "disabled"}]
    vehicles.sort(key=lambda v: (0 if str(v.get("plate_number") or "").startswith("なにわ300あ") else 1, str(v.get("plate_number") or "")))
    if not drivers or not vehicles:
        raise RuntimeError("existing drivers/vehicles are required; none were found")
    return drivers, vehicles


def assign_orders_to_existing_resources(orders: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drivers, vehicles = load_resources()
    driver_busy: dict[int, list[tuple[str, int, int]]] = {int(d["id"]): [] for d in drivers}
    vehicle_busy: dict[int, list[tuple[str, int, int]]] = {int(v["id"]): [] for v in vehicles}
    assignment_log: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []

    for order in sorted(orders, key=lambda item: (item.get("order_date") or "", item.get("start_time") or "")):
        interval = (str(order.get("order_date") or ""), minutes(order.get("start_time")), minutes(order.get("end_time")) or minutes(order.get("start_time")) + 60)
        selected: tuple[dict[str, Any], dict[str, Any]] | None = None
        for driver in drivers:
            did = int(driver["id"])
            if any(overlaps(interval, busy) for busy in driver_busy[did]):
                continue
            for vehicle in vehicles:
                vid = int(vehicle["id"])
                if any(overlaps(interval, busy) for busy in vehicle_busy[vid]):
                    continue
                selected = (driver, vehicle)
                break
            if selected:
                break
        if not selected:
            raise RuntimeError(f"no free driver/vehicle pair for order {order.get('oid')}")
        driver, vehicle = selected
        result = request(
            "POST",
            "/api/dispatch/assign",
            {"order_ids": [order["id"]], "driver_id": driver["id"], "vehicle_id": vehicle["id"]},
        )
        if not result.get("success"):
            raise RuntimeError(f"dispatch failed for order {order.get('oid')}: {result}")
        assignment_id = result["assignment_ids"][0]
        driver_busy[int(driver["id"])].append(interval)
        vehicle_busy[int(vehicle["id"])].append(interval)
        assignment_log.append(
            {
                "order_id": order["id"],
                "oid": order.get("oid"),
                "assignment_id": assignment_id,
                "driver_id": driver["id"],
                "driver_name": driver.get("name"),
                "vehicle_id": vehicle["id"],
                "plate_number": vehicle.get("plate_number"),
            }
        )

    all_assignments = request("GET", "/api/dispatch/assignments").get("assignments", [])
    by_id = {item.get("id") or item.get("assignment_id"): item for item in all_assignments}
    for item in assignment_log:
        assignment = by_id.get(item["assignment_id"])
        if assignment:
            assignments.append(assignment)
    return assignments, assignment_log


def submit_report(driver_id: int, assignment_id: int, report_type: str, location_text: str) -> dict[str, Any]:
    return request(
        "POST",
        "/api/driver/report",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "report_type": report_type,
            "latitude": 34.7025,
            "longitude": 135.4959,
            "location_text": location_text,
            "note": f"20单演示：{report_type}",
        },
    )


def submit_workflow(driver_id: int, assignment_id: int, event_type: str, note: str) -> dict[str, Any]:
    return request(
        "POST",
        "/api/driver/workflow-event",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "event_type": event_type,
            "latitude": 34.7025,
            "longitude": 135.4959,
            "location_text": "大阪车库",
            "note": note,
        },
    )


def upload_evidence(driver_id: int, assignment_id: int, evidence_type: str, note: str) -> dict[str, Any]:
    return request(
        "POST",
        "/api/driver/evidence",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "evidence_type": evidence_type,
            "image_base64": DEMO_PHOTO_BASE64,
            "note": note,
        },
    )


def submit_expense(driver_id: int, assignment: dict[str, Any], kind: str, category: str, amount: int, status: str) -> dict[str, Any]:
    return request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver_id,
            "assignment_id": assignment.get("id") or assignment.get("assignment_id"),
            "order_id": assignment.get("order_id"),
            "expense_kind": kind,
            "category": category,
            "amount": amount,
            "currency": "JPY",
            "submit_status": status,
            "receipt_photo_url": "/uploads/demo_receipt.png" if kind == "advance" else "",
            "note": "20单演示费用上报",
        },
    )


def simulate_driver_runtime(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for assignment in assignments:
        grouped.setdefault(int(assignment["driver_id"]), []).append(assignment)

    report_count = 0
    evidence_count = 0
    expense_count = 0
    for driver_id, items in grouped.items():
        items.sort(key=lambda item: (item.get("order_date") or "", item.get("start_time") or ""))
        first_id = int(items[0].get("id") or items[0].get("assignment_id"))
        submit_workflow(driver_id, first_id, "vehicle_check_out", "车灯/刹车/车身确认")
        submit_workflow(driver_id, first_id, "alcohol_test_out", "出库前酒精测试")
        submit_workflow(driver_id, first_id, "roll_call_out", "点呼出库")
        for index, item in enumerate(items, start=1):
            assignment_id = int(item.get("id") or item.get("assignment_id"))
            for report_type, label in [
                ("confirm_order", "司机确认接单"),
                ("depart_yard", "出库前往上车点"),
                ("arrive_pickup", "到达上车点"),
            ]:
                result = submit_report(driver_id, assignment_id, report_type, label)
                if not result.get("success"):
                    raise RuntimeError(f"driver report failed: {result}")
                report_count += 1
            for evidence_type, note in [
                ("arrive_waiting_photo", "到达等待照片"),
                ("pickup_photo", "接到客人照片"),
            ]:
                result = upload_evidence(driver_id, assignment_id, evidence_type, note)
                if not result.get("success"):
                    raise RuntimeError(f"evidence upload failed: {result}")
                evidence_count += 1
            result = submit_report(driver_id, assignment_id, "start_service", "开始行程")
            if not result.get("success"):
                raise RuntimeError(f"start_service failed: {result}")
            report_count += 1
            result = upload_evidence(driver_id, assignment_id, "waypoint_photo", "中途地点照片")
            if not result.get("success"):
                raise RuntimeError(f"waypoint evidence failed: {result}")
            evidence_count += 1
            result = upload_evidence(driver_id, assignment_id, "dropoff_photo", "送达照片")
            if not result.get("success"):
                raise RuntimeError(f"dropoff evidence failed: {result}")
            evidence_count += 1
            result = submit_report(driver_id, assignment_id, "complete_order", "行程结束")
            if not result.get("success"):
                raise RuntimeError(f"complete_order failed: {result}")
            report_count += 1
            if index in {1, len(items)}:
                submit_expense(driver_id, item, "advance", "停车费", 1200 + index * 100, "submitted")
                submit_expense(driver_id, item, "collect", "代收车费", 3000 + index * 500, "in_hand")
                expense_count += 2
        last_id = int(items[-1].get("id") or items[-1].get("assignment_id"))
        submit_workflow(driver_id, last_id, "vehicle_cleaning", "车辆清扫")
        submit_workflow(driver_id, last_id, "vehicle_check_in", "入库点检")
        submit_workflow(driver_id, last_id, "alcohol_test_in", "入库酒精测试")
        submit_workflow(driver_id, last_id, "roll_call_in", "点呼入库")
        result = submit_report(driver_id, last_id, "return_yard", "车辆入库")
        if not result.get("success"):
            raise RuntimeError(f"return_yard failed: {result}")
        report_count += 1
    return {"driver_count": len(grouped), "report_count": report_count, "evidence_count": evidence_count, "expense_count": expense_count}


def probe_surfaces(driver_id: int) -> dict[str, Any]:
    probes: list[tuple[str, str]] = [
        ("web_dashboard", "/api/dashboard/summary"),
        ("web_orders", "/api/orders"),
        ("web_dispatch", "/api/dispatch/assignments"),
        ("web_finance", "/api/finance/ledger"),
        ("driver_workbench", f"/api/driver/workbench?driver_id={driver_id}"),
        ("driver_assignments", f"/api/driver/assignments?driver_id={driver_id}"),
        ("dispatch_mobile_dashboard", "/api/dispatch-mobile/dashboard"),
        ("dispatch_mobile_shared", "/api/dispatch-mobile/shared-state"),
    ]
    result: dict[str, Any] = {}
    for name, path in probes:
        started = time.perf_counter()
        try:
            payload = request("GET", path, token=not path.startswith("/api/driver/") and not path.startswith("/api/dispatch-mobile/"))
            result[name] = {"ok": True, "elapsed_ms": round((time.perf_counter() - started) * 1000), "keys": sorted(k for k in payload if not k.startswith("_"))[:8]}
        except Exception as exc:
            result[name] = {"ok": False, "elapsed_ms": round((time.perf_counter() - started) * 1000), "error": str(exc)}
    return result


def snapshot_counts(driver_id: int) -> dict[str, Any]:
    finance = request("GET", "/api/finance/ledger")
    expenses = request("GET", "/api/finance/driver-expenses")
    assignments = request("GET", "/api/dispatch/assignments").get("assignments", [])
    driver_workbench = request("GET", f"/api/driver/workbench?driver_id={driver_id}", token=False)
    with sqlite3.connect(DB_PATH) as conn:
        counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in [
                "orders",
                "order_drafts",
                "assignments",
                "driver_reports",
                "driver_evidence_uploads",
                "driver_expense_reports",
                "location_logs",
                "notifications",
            ]
            if table_exists(conn, table)
        }
    return {
        "db_counts": counts,
        "finance_order_count": len(finance.get("orders", [])),
        "finance_summary": finance.get("summary", {}),
        "finance_expense_count": len(expenses.get("expenses", [])),
        "assignment_status_counts": _count_by(assignments, "execution_status"),
        "sample_driver_workbench": {
            "driver_id": driver_workbench.get("driver_id"),
            "today_order_count": driver_workbench.get("today_order_count"),
            "vehicle_status": driver_workbench.get("vehicle_status"),
            "today_pending_expenses": driver_workbench.get("today_pending_expenses"),
        },
    }


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "-")
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_result(result: dict[str, Any]) -> Path:
    out_dir = ROOT_DIR / "runtime" / "demo_runs" / f"twenty_order_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "RESULT.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = out_dir / "SUMMARY.md"
    summary.write_text(
        "\n".join(
            [
                "# 20 Order Runtime Flow",
                "",
                f"- orders: {result['counts']['db_counts'].get('orders')}",
                f"- assignments: {result['counts']['db_counts'].get('assignments')}",
                f"- driver_reports: {result['counts']['db_counts'].get('driver_reports')}",
                f"- evidence: {result['counts']['db_counts'].get('driver_evidence_uploads')}",
                f"- expenses: {result['counts']['db_counts'].get('driver_expense_reports')}",
                f"- result: {path}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear runtime orders and run a 20-order parser -> dispatch -> driver -> finance flow.")
    parser.add_argument("--skip-clear", action="store_true", help="Do not clear runtime order/assignment/report data before running.")
    args = parser.parse_args()

    started = time.perf_counter()
    print("=== 20单全链路演示 ===")
    print(f"base_url={BASE_URL}")
    deleted = {} if args.skip_clear else clear_runtime_tables()
    print(f"已清空运行数据: {deleted}")
    login()
    print("1/7 解析真实订单文本，生成20条草稿")
    drafts, correction_log = parse_and_correct_drafts()
    print(f"草稿数量: {len(drafts)}；纠错数量: {len(correction_log)}")
    print("2/7 原地确认草稿，写入订单池")
    orders = confirm_drafts(drafts)
    print(f"订单数量: {len(orders)}")
    print("3/7 使用当前数据库司机和车辆自动配单")
    assignments, assignment_log = assign_orders_to_existing_resources(orders)
    print(f"派车记录: {len(assignments)}；涉及司机: {len({x['driver_id'] for x in assignments})}；涉及车辆: {len({x['vehicle_id'] for x in assignments})}")
    print("4/7 模拟司机确认接单、出库、到达、照片、完成、入库")
    driver_runtime = simulate_driver_runtime(assignments)
    print(f"司机报备: {driver_runtime}")
    first_driver_id = int(assignments[0]["driver_id"])
    print("5/7 检查 Web / 司机端 / 调度端 / 财务端 API 联动")
    surfaces = probe_surfaces(first_driver_id)
    print(json.dumps(surfaces, ensure_ascii=False, indent=2))
    print("6/7 生成财务与数据库快照")
    counts = snapshot_counts(first_driver_id)
    result = {
        "ok": True,
        "base_url": BASE_URL,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "deleted": deleted,
        "draft_count": len(drafts),
        "order_count": len(orders),
        "assignment_count": len(assignments),
        "correction_log": correction_log[:5],
        "assignment_log": assignment_log,
        "driver_runtime": driver_runtime,
        "surface_probes": surfaces,
        "counts": counts,
    }
    result_path = write_result(result)
    print("7/7 完成")
    print(f"结果文件: {result_path}")


if __name__ == "__main__":
    main()

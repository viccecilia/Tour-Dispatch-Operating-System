import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
TOKEN = ""

DEMO_PHOTO_BASE64 = {
    "arrive_waiting_photo": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP8z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
    "pickup_photo": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mNk+M8AAwUBAZv4YVQAAAAASUVORK5CYII=",
    "waypoint_photo": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP8/5+hHgAHggJ/lS37VQAAAABJRU5ErkJggg==",
    "dropoff_photo": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP8z/CfAQADAgH/ooEwSAAAAABJRU5ErkJggg==",
    "expense_receipt_photo": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP8z/D/PwAHgwJ/lTA+7QAAAABJRU5ErkJggg==",
}

ORDER_TEXT = """5.29 08:00 关西接机大阪 10座600
5.29 10:20 大阪单送京都 3代 绿450
5.29 13:30 京都-奈良-大阪 包车 10座 儿童座椅*1 1600（高速另算）
5.29 18:10 大阪送机关西 3代 绿450"""


def request(method: str, path: str, payload: dict | None = None, *, token: bool = True) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN and token:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body}
        parsed["_status"] = exc.code
        raise RuntimeError(f"{method} {path} failed: {exc.code} {json.dumps(parsed, ensure_ascii=False)}") from exc


def pause(args: argparse.Namespace, message: str) -> None:
    print(f"\n=== {message} ===")
    if args.pause:
        input("打开后台/司机端确认画面后，按回车继续...")
    elif args.step_delay:
        time.sleep(args.step_delay)


def login() -> None:
    global TOKEN
    ping = request("GET", "/api/ping", token=False)
    if ping.get("ok") is not True:
        raise RuntimeError("backend ping failed")
    auth = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"}, token=False)
    TOKEN = auth["token"]


def ensure_demo_assets() -> list[Path]:
    asset_dir = ROOT_DIR / "runtime" / "demo_assets" / "driver_flow"
    asset_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, value in DEMO_PHOTO_BASE64.items():
        path = asset_dir / f"{name}.png"
        path.write_bytes(base64.b64decode(value))
        paths.append(path)
    return paths


def time_to_minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def minutes_to_time(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def find_free_demo_times(driver_id: int) -> list[tuple[str, str]]:
    """Find four same-day slots for the fixed demo driver so repeated demos do not collide."""
    today = date.today().isoformat()
    durations = [30, 30, 30, 30]
    gap = 10
    busy: list[tuple[int, int]] = []
    assignments = request("GET", f"/api/driver/assignments?driver_id={driver_id}").get("assignments", [])
    for item in assignments:
        if item.get("order_date") != today:
            continue
        if (item.get("assignment_status") or "active") == "cancelled":
            continue
        start = time_to_minutes(item.get("start_time"))
        end = time_to_minutes(item.get("end_time"))
        if start is None or end is None:
            continue
        busy.append((start, max(end, start + 30)))

    for base in range(10, 22 * 60, 10):
        cursor = base
        candidate: list[tuple[int, int]] = []
        for duration in durations:
            start = cursor
            end = start + duration
            candidate.append((start, end))
            cursor = end + gap
        if candidate[-1][1] > 23 * 60:
            break
        if any(intervals_overlap(start, end, busy_start, busy_end) for start, end in candidate for busy_start, busy_end in busy):
            continue
        return [(minutes_to_time(start), minutes_to_time(end)) for start, end in candidate]

    raise RuntimeError(f"driver_id={driver_id} has no same-day free demo window; run reset_demo_db or choose another driver")


def pick_resource(args: argparse.Namespace) -> tuple[dict, dict]:
    suffix = datetime.now().strftime("%H%M%S")
    if args.driver_id:
        drivers = request("GET", "/api/resources/drivers").get("drivers", [])
        driver = next((item for item in drivers if int(item.get("id") or 0) == args.driver_id), None)
        if not driver:
            raise RuntimeError(f"driver_id={args.driver_id} not found")
        if args.vehicle_id:
            vehicles = request("GET", "/api/resources/vehicles").get("vehicles", [])
            vehicle = next((item for item in vehicles if int(item.get("id") or 0) == args.vehicle_id), None)
            if not vehicle:
                raise RuntimeError(f"vehicle_id={args.vehicle_id} not found")
        else:
            vehicle = request(
                "POST",
                "/api/resources/vehicles",
                {"plate_number": f"DEMO-{suffix}", "vehicle_type": "ハイエース 10座", "seat_count": 10, "status": "available"},
            )["vehicle"]
        return driver, vehicle

    driver = request(
        "POST",
        "/api/resources/drivers",
        {"name": f"演示司机{suffix}", "phone": f"090-DEMO-{suffix}", "status": "available", "driver_code": f"D{suffix[-3:]}"},
    )["driver"]
    vehicle = request(
        "POST",
        "/api/resources/vehicles",
        {"plate_number": f"DEMO-{suffix}", "vehicle_type": "ハイエース 10座", "seat_count": 10, "status": "available"},
    )["vehicle"]
    return driver, vehicle


def parse_and_fix_orders(driver_id: int = 0) -> list[dict]:
    response = request("POST", "/api/parser/text", {"text": ORDER_TEXT, "batch": True})
    drafts = response.get("drafts") or ([response["draft"]] if response.get("draft") else [])
    if len(drafts) < 4:
        raise RuntimeError(f"parser returned {len(drafts)} drafts, expected at least 4")

    today = date.today()
    if driver_id:
        times = find_free_demo_times(driver_id)
    else:
        times = [("08:00", "09:10"), ("10:20", "11:40"), ("13:30", "16:40"), ("18:10", "19:20")]
    fixed_specs = [
        (*times[0], "关西机场", "大阪市内酒店", "接机", "10座", 600),
        (*times[1], "大阪市内酒店", "京都站", "单送", "3代绿牌", 450),
        (*times[2], "京都", "奈良-大阪", "包车", "10座", 1600),
        (*times[3], "大阪市内酒店", "关西机场", "送机", "3代绿牌", 450),
    ]
    fixed_drafts = []
    run_code = datetime.now().strftime("%H%M%S")
    for idx, (draft, spec) in enumerate(zip(drafts[:4], fixed_specs, strict=False), start=1):
        start, end, pickup, dropoff, order_type, vehicle_type, price = spec
        payload = {
            "oid": f"DEMO-{date.today().strftime('%y%m%d')}-{run_code}-{idx:02d}",
            "order_date": today.isoformat(),
            "end_date": today.isoformat(),
            "start_time": start,
            "end_time": end,
            "pickup_location": pickup,
            "dropoff_location": dropoff,
            "order_type": order_type,
            "vehicle_type": vehicle_type,
            "price": price,
            "guest_name": "演示客人",
            "guest_contact": "090-0000-1234",
            "agency_name": "演示旅行社",
            "remark": f"演示脚本人工修正：{draft.get('raw_text', '')}",
            "parse_status": "parsed",
        }
        fixed_drafts.append(request("PUT", f"/api/parser/drafts/{draft['id']}", payload)["draft"])
    return fixed_drafts


def confirm_drafts(drafts: list[dict]) -> list[dict]:
    orders = []
    for draft in drafts:
        confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm")
        order = request("GET", f"/api/orders/{confirmed['order_id']}")["order"]
        orders.append(order)
    return orders


def assign_orders(orders: list[dict], driver: dict, vehicle: dict) -> list[dict]:
    assigned = request(
        "POST",
        "/api/dispatch/assign",
        {"order_ids": [order["id"] for order in orders], "driver_id": driver["id"], "vehicle_id": vehicle["id"]},
    )
    if not assigned.get("success"):
        raise RuntimeError(f"dispatch assign failed: {assigned}")
    assignments = request("GET", f"/api/driver/assignments?driver_id={driver['id']}").get("assignments", [])
    assignment_ids = set(assigned.get("assignment_ids") or [])
    selected = [item for item in assignments if item.get("assignment_id") in assignment_ids or item.get("id") in assignment_ids]
    if len(selected) != len(orders):
        order_ids = {order["id"] for order in orders}
        selected = [item for item in assignments if item.get("order_id") in order_ids]
    return selected


def submit_workflow(driver_id: int, assignment_id: int, event_type: str, note: str) -> dict:
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


def submit_report(driver_id: int, assignment_id: int, report_type: str, location_text: str) -> dict:
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
            "note": f"演示脚本：{report_type}",
        },
    )


def upload_evidence(driver_id: int, assignment_id: int, evidence_type: str, note: str) -> dict:
    return request(
        "POST",
        "/api/driver/evidence",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "evidence_type": evidence_type,
            "image_base64": DEMO_PHOTO_BASE64[evidence_type],
            "note": note,
        },
    )


def submit_driver_expenses(driver_id: int, assignment: dict) -> tuple[dict, dict]:
    advance = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver_id,
            "assignment_id": assignment["assignment_id"],
            "order_id": assignment["order_id"],
            "expense_kind": "advance",
            "category": "停车费",
            "amount": 1800,
            "submit_status": "submitted",
            "receipt_photo_url": "demo_assets/driver_flow/expense_receipt_photo.png",
            "note": "演示停车费报销",
        },
    )
    collect = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver_id,
            "assignment_id": assignment["assignment_id"],
            "order_id": assignment["order_id"],
            "expense_kind": "collect",
            "category": "代收车费",
            "amount": 4500,
            "submit_status": "in_hand",
            "note": "演示代收费用，仍在司机手中",
        },
    )
    return advance, collect


def run_driver_flow(assignments: list[dict], driver: dict, args: argparse.Namespace) -> None:
    driver_id = int(driver["id"])
    first_assignment = int(assignments[0]["assignment_id"])
    pause(args, "司机端：确认收到 4 个订单")
    for item in assignments:
        submit_report(driver_id, int(item["assignment_id"]), "confirm_order", "司机确认接单")

    pause(args, "司机端：车辆检查、酒精测试、点呼出库")
    for event_type in ["vehicle_check_out", "alcohol_test_out", "roll_call_out"]:
        submit_workflow(driver_id, first_assignment, event_type, f"演示出库流程：{event_type}")

    for index, item in enumerate(assignments, start=1):
        assignment_id = int(item["assignment_id"])
        pause(args, f"司机端：开始第 {index} 单，到达上车点")
        submit_report(driver_id, assignment_id, "depart_yard", f"第 {index} 单出库/出发")
        submit_report(driver_id, assignment_id, "arrive_pickup", f"第 {index} 单上车点")
        upload_evidence(driver_id, assignment_id, "arrive_waiting_photo", f"第 {index} 单到达等待照片")

        pause(args, f"司机端：第 {index} 单接到客人并上传照片")
        upload_evidence(driver_id, assignment_id, "pickup_photo", f"第 {index} 单接到客人照片")
        submit_report(driver_id, assignment_id, "start_service", f"第 {index} 单开始服务")
        upload_evidence(driver_id, assignment_id, "waypoint_photo", f"第 {index} 单中途地点照片")

        pause(args, f"司机端：第 {index} 单送达并完成订单")
        upload_evidence(driver_id, assignment_id, "dropoff_photo", f"第 {index} 单送达照片")
        submit_report(driver_id, assignment_id, "complete_order", f"第 {index} 单完成")

    pause(args, "司机端：全部订单完成，车辆入库点呼")
    last_assignment = int(assignments[-1]["assignment_id"])
    for event_type in ["vehicle_cleaning", "vehicle_check_in", "alcohol_test_in", "roll_call_in"]:
        submit_workflow(driver_id, last_assignment, event_type, f"演示入库流程：{event_type}")
    submit_report(driver_id, last_assignment, "return_yard", "车辆已入库")


def finance_snapshot(driver: dict, order_ids: list[int]) -> dict:
    params = urllib.parse.urlencode({"driver_id": driver["id"], "date_from": date.today().isoformat(), "date_to": date.today().isoformat()})
    ledger = request("GET", f"/api/finance/ledger?{params}")
    expenses = request("GET", f"/api/finance/driver-expenses?{urllib.parse.urlencode({'driver_id': driver['id']})}")
    return {
        "ledger_orders": [
            {
                "order_id": row.get("order_id"),
                "oid": row.get("oid"),
                "execution_status": row.get("execution_status"),
                "price": row.get("price"),
                "driver_advance_amount": row.get("driver_advance_amount"),
                "driver_collect_amount": row.get("driver_collect_amount"),
            }
            for row in ledger.get("orders", [])
            if row.get("order_id") in order_ids
        ],
        "expense_summary": expenses.get("summary", {}),
        "expense_count": len(expenses.get("expenses", [])),
    }


def write_result(result: dict) -> Path:
    result_dir = ROOT_DIR / "runtime" / "demo_runs"
    result_dir.mkdir(parents=True, exist_ok=True)
    path = result_dir / f"full_runtime_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a visible parser -> dispatch -> driver -> finance demo flow.")
    parser.add_argument("--no-pause", dest="pause", action="store_false", help="Run without waiting for Enter between demo steps.")
    parser.add_argument("--step-delay", type=float, default=0.0, help="Delay seconds between steps when --no-pause is used.")
    parser.add_argument("--driver-id", type=int, default=0, help="Use an existing driver id so the miniapp can watch a fixed driver.")
    parser.add_argument("--vehicle-id", type=int, default=0, help="Use an existing vehicle id with --driver-id.")
    parser.set_defaults(pause=True)
    args = parser.parse_args()

    login()
    asset_paths = ensure_demo_assets()

    pause(args, "后台：粘贴 4 条订单文本并自动解析")
    drafts = parse_and_fix_orders(args.driver_id)

    pause(args, "后台：模拟解析有误，已人工修正日期、路线、车型和价格")
    orders = confirm_drafts(drafts)

    pause(args, "后台：选择同一个司机和车辆，批量派 4 单")
    driver, vehicle = pick_resource(args)
    assignments = assign_orders(orders, driver, vehicle)
    assignments = sorted(assignments, key=lambda item: (item.get("order_date") or "", item.get("start_time") or ""))
    print(f"\n演示司机: {driver.get('name')} / driver_id={driver.get('id')}")
    print(f"演示车辆: {vehicle.get('plate_number')} / vehicle_id={vehicle.get('id')}")
    print("微信开发者工具司机端如果没看到订单，请在“我的 -> 切换司机”输入上面的 driver_id。")

    run_driver_flow(assignments, driver, args)

    pause(args, "司机端：提交停车费报销和代收车费")
    advance, collect = submit_driver_expenses(int(driver["id"]), assignments[-1])

    pause(args, "后台财务：查看完成订单和司机费用待确认池")
    result = {
        "base_url": BASE_URL,
        "driver": {"id": driver.get("id"), "name": driver.get("name")},
        "vehicle": {"id": vehicle.get("id"), "plate_number": vehicle.get("plate_number")},
        "draft_ids": [draft["id"] for draft in drafts],
        "order_ids": [order["id"] for order in orders],
        "assignment_ids": [item["assignment_id"] for item in assignments],
        "advance_expense": advance,
        "collect_expense": collect,
        "finance": finance_snapshot(driver, [order["id"] for order in orders]),
        "demo_assets": [str(path) for path in asset_paths],
    }
    result_path = write_result(result)
    print("\n演示流程已完成。")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n结果文件: {result_path}")


if __name__ == "__main__":
    main()

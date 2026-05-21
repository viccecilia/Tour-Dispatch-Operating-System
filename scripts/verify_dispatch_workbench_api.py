import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
WORK_DATE = "2026-06-20"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def assert_true(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)


def create_order(index: int) -> dict:
    slot = index % 10
    day_offset = index // 10
    date = f"2026-06-{20 + day_offset:02d}"
    start_hour = 6 + slot
    end_hour = start_hour + 1
    return request(
        "POST",
        "/api/orders",
        {
            "order_date": date,
            "end_date": date,
            "start_time": f"{start_hour:02d}:00",
            "end_time": f"{end_hour:02d}:00",
            "pickup_location": f"大阪酒店{index:02d}",
            "dropoff_location": f"京都景点{index:02d}",
            "order_type": "包车",
            "vehicle_type": "商务车 绿牌",
            "passenger_count": 3,
            "guest_name": f"R014客人{index:02d}",
            "agency_name": "R014测试旅行社",
            "price": 1500 + index,
            "remark": "R014 dispatch workbench smoke",
        },
    )["order"]


def main() -> None:
    ping = request("GET", "/api/ping")
    assert_true("ping", ping.get("ok") is True)
    request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})

    suffix = "R014"
    driver = request("POST", "/api/resources/drivers", {"name": f"{suffix}司机A", "phone": "R014-A", "status": "available"})["driver"]
    driver_b = request("POST", "/api/resources/drivers", {"name": f"{suffix}司机B", "phone": "R014-B", "status": "available"})["driver"]
    vehicle = request("POST", "/api/resources/vehicles", {"plate_number": "R014A20260620", "vehicle_type": "商务车 绿牌", "seat_count": 6, "status": "available"})["vehicle"]
    vehicle_b = request("POST", "/api/resources/vehicles", {"plate_number": "R014B20260620", "vehicle_type": "商务车 绿牌", "seat_count": 6, "status": "available"})["vehicle"]

    orders = [create_order(index) for index in range(30)]
    order_ids = [order["id"] for order in orders]
    unassigned = request("GET", "/api/dispatch/unassigned-orders")["orders"]
    assert_true("created_30_unassigned", all(order_id in {item["id"] for item in unassigned} for order_id in order_ids))

    route_query = urllib.parse.urlencode({"order_ids": ",".join(str(order_id) for order_id in order_ids)})
    route = request("GET", f"/api/dispatch/route-suggestion?{route_query}")
    assert_true("route_suggestion_count", len(route.get("orders", [])) == 30)

    assigned = request("POST", "/api/dispatch/assign", {"order_ids": order_ids, "driver_id": driver["id"], "vehicle_id": vehicle["id"]})
    assert_true("bulk_assign_success", assigned.get("success") is True)
    assert_true("assignment_count", len(assigned.get("assignment_ids", [])) == 30)

    first_order = request("GET", f"/api/orders/{order_ids[0]}")["order"]
    assert_true("order_status_assigned", first_order.get("dispatch_status") == "assigned")
    assignments = request("GET", "/api/dispatch/assignments")["assignments"]
    assigned_ids = set(assigned["assignment_ids"])
    assert_true("assignments_written", assigned_ids.issubset({item["id"] for item in assignments}))

    calendar = request("GET", f"/api/calendar/dispatch?view=day&date={WORK_DATE}")
    assert_true("calendar_has_assignment", any(item.get("order_id") == order_ids[0] for item in calendar.get("items", [])))

    driver_assignments = request("GET", f"/api/driver/assignments?driver_id={driver['id']}")["assignments"]
    assert_true("driver_receives_task", any(item.get("order_id") == order_ids[0] for item in driver_assignments))

    conflict_order = request(
        "POST",
        "/api/orders",
        {
            "order_date": WORK_DATE,
            "end_date": WORK_DATE,
            "start_time": "06:30",
            "end_time": "07:30",
            "pickup_location": "大阪冲突点",
            "dropoff_location": "京都冲突点",
            "order_type": "包车",
            "vehicle_type": "商务车 绿牌",
            "price": 1600,
        },
    )["order"]
    conflict = request("POST", "/api/dispatch/assign", {"order_ids": [conflict_order["id"]], "driver_id": driver["id"], "vehicle_id": vehicle["id"]})
    assert_true("conflict_blocked", conflict.get("success") is False and len(conflict.get("conflicts", [])) > 0)

    cancel = request("POST", "/api/dispatch/cancel", {"assignment_id": assigned["assignment_ids"][0]})
    assert_true("cancel_success", cancel.get("success") is True)
    cancelled_order = request("GET", f"/api/orders/{order_ids[0]}")["order"]
    assert_true("cancelled_back_to_unassigned", cancelled_order.get("dispatch_status") == "unassigned")

    reassign = request("POST", "/api/dispatch/reassign", {"order_ids": [order_ids[1]], "new_driver_id": driver_b["id"], "new_vehicle_id": vehicle_b["id"]})
    assert_true("reassign_success", reassign.get("success") is True)

    summary = request("GET", "/api/dashboard/summary")

    result = {
        "created_unassigned_orders": len(order_ids),
        "route_orders": len(route.get("orders", [])),
        "bulk_assign_success": assigned.get("success"),
        "assignment_count": len(assigned.get("assignment_ids", [])),
        "first_order_status": first_order.get("dispatch_status"),
        "calendar_has_assignment": any(item.get("order_id") == order_ids[0] for item in calendar.get("items", [])),
        "driver_receives_task": any(item.get("order_id") == order_ids[0] for item in driver_assignments),
        "conflict_success": conflict.get("success"),
        "conflict_count": len(conflict.get("conflicts", [])),
        "cancel_success": cancel.get("success"),
        "cancelled_order_status": cancelled_order.get("dispatch_status"),
        "reassign_success": reassign.get("success"),
        "dashboard_assigned_orders": summary.get("assigned_orders"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

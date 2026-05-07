import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:8000")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as parse_exc:
            raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from parse_exc
        payload["_status"] = exc.code
        return payload


def create_order(start_time: str, end_time: str, suffix: str) -> dict:
    today = date.today().isoformat()
    return request(
        "POST",
        "/api/orders",
        {
            "order_date": today,
            "start_time": start_time,
            "end_time": end_time,
            "pickup_location": f"东京站{suffix}",
            "dropoff_location": f"成田机场{suffix}",
            "order_type": "送机",
            "vehicle_type": "商务车",
            "passenger_count": 2,
            "luggage_count": 2,
            "guest_name": f"派车测试{suffix}",
            "guest_contact": "09000000000",
            "agency_name": "R003测试旅行社",
            "price": 21000,
            "remark": "R003 dispatch smoke",
        },
    )["order"]


def main() -> None:
    init_db(seed=True)

    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    base_minute = 360 + (int(datetime.now().timestamp()) % 480)
    start_a = _format_time(base_minute)
    end_a = _format_time(base_minute + 60)
    start_b = _format_time(base_minute + 30)
    end_b = _format_time(base_minute + 90)
    order_a = create_order(start_a, end_a, "A")
    order_b = create_order(start_b, end_b, "B")

    orders_before = request("GET", "/api/orders")
    unassigned = request("GET", "/api/dispatch/unassigned-orders")
    suffix = str(int(datetime.now().timestamp()))
    driver_one = request("POST", "/api/resources/drivers", {"name": f"R003司机A{suffix}", "phone": f"R003-A-{suffix}", "status": "available"})["driver"]
    driver_two = request("POST", "/api/resources/drivers", {"name": f"R003司机B{suffix}", "phone": f"R003-B-{suffix}", "status": "available"})["driver"]
    vehicle_one = request("POST", "/api/resources/vehicles", {"plate_number": f"R003A{suffix}", "vehicle_type": "商务车", "seat_count": 6, "status": "available"})["vehicle"]
    vehicle_two = request("POST", "/api/resources/vehicles", {"plate_number": f"R003B{suffix}", "vehicle_type": "商务车", "seat_count": 6, "status": "available"})["vehicle"]
    drivers = [driver_one, driver_two]
    vehicles = [vehicle_one, vehicle_two]

    assign_a = request(
        "POST",
        "/api/dispatch/assign",
        {
            "order_ids": [order_a["id"]],
            "driver_id": drivers[0]["id"],
            "vehicle_id": vehicles[0]["id"],
        },
    )
    assigned_order = request("GET", f"/api/orders/{order_a['id']}")["order"]
    active_assignments = request("GET", "/api/dispatch/assignments")["assignments"]

    conflict = request(
        "POST",
        "/api/dispatch/assign",
        {
            "order_ids": [order_b["id"]],
            "driver_id": drivers[0]["id"],
            "vehicle_id": vehicles[0]["id"],
        },
    )
    route_order_ids = f"{order_a['id']},{order_b['id']}"
    route = request(
        "GET",
        f"/api/dispatch/route-suggestion?{urllib.parse.urlencode({'order_ids': route_order_ids})}",
    )
    cancel = request("POST", "/api/dispatch/cancel", {"assignment_id": assign_a["assignment_ids"][0]})
    cancelled_order = request("GET", f"/api/orders/{order_a['id']}")["order"]

    assign_again = request(
        "POST",
        "/api/dispatch/assign",
        {
            "order_ids": [order_a["id"]],
            "driver_id": drivers[0]["id"],
            "vehicle_id": vehicles[0]["id"],
        },
    )
    reassign = request(
        "POST",
        "/api/dispatch/reassign",
        {
            "order_ids": [order_a["id"]],
            "new_driver_id": drivers[1]["id"],
            "new_vehicle_id": vehicles[1]["id"],
        },
    )
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "orders_api_count": len(orders_before.get("orders", [])),
        "created_order_ids": [order_a["id"], order_b["id"]],
        "unassigned_count": len(unassigned.get("orders", [])),
        "drivers_count": len(drivers),
        "vehicles_count": len(vehicles),
        "assign_success": assign_a.get("success") is True,
        "assigned_order_status": assigned_order.get("dispatch_status"),
        "active_assignment_exists": any(item["id"] == assign_a["assignment_ids"][0] for item in active_assignments),
        "conflict_success": conflict.get("success"),
        "conflict_count": len(conflict.get("conflicts", [])),
        "route_link_count": len(route.get("links", [])),
        "cancel_success": cancel.get("success") is True,
        "cancelled_order_status": cancelled_order.get("dispatch_status"),
        "assign_again_success": assign_again.get("success") is True,
        "reassign_success": reassign.get("success") is True,
        "new_assignment_ids": reassign.get("new_assignment_ids", []),
        "cancelled_old_assignment_ids": reassign.get("cancelled_old_assignment_ids", []),
        "dashboard_assigned_orders": summary.get("assigned_orders"),
        "dashboard_available_drivers": summary.get("available_drivers"),
        "dashboard_available_vehicles": summary.get("available_vehicles"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_time(total_minutes: int) -> str:
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


if __name__ == "__main__":
    main()

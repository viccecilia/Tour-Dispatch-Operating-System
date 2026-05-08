import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
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


def create_order() -> dict:
    today = date.today().isoformat()
    base_minute = 420 + (int(datetime.now().timestamp()) % 360)
    return request(
        "POST",
        "/api/orders",
        {
            "order_date": today,
            "start_time": _format_time(base_minute),
            "end_time": _format_time(base_minute + 60),
            "pickup_location": "羽田机场",
            "dropoff_location": "东京酒店",
            "order_type": "接机",
            "vehicle_type": "商务车",
            "passenger_count": 3,
            "luggage_count": 2,
            "guest_name": "日历测试客人",
            "guest_contact": "09000000001",
            "agency_name": "R004测试旅行社",
            "price": 23000,
            "remark": "R004 calendar smoke",
        },
    )["order"]


def main() -> None:
    init_db(seed=True)

    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    orders_before = request("GET", "/api/orders")
    order = create_order()
    suffix = str(int(datetime.now().timestamp()))
    drivers = [request("POST", "/api/resources/drivers", {"name": f"R004司机{suffix}", "phone": f"R004-{suffix}", "status": "available"})["driver"]]
    vehicles = [request("POST", "/api/resources/vehicles", {"plate_number": f"R004{suffix}", "vehicle_type": "商务车", "seat_count": 6, "status": "available"})["vehicle"]]

    assigned = request(
        "POST",
        "/api/dispatch/assign",
        {"order_ids": [order["id"]], "driver_id": drivers[0]["id"], "vehicle_id": vehicles[0]["id"]},
    )
    if not assigned.get("success"):
        raise RuntimeError(f"assign failed: {assigned}")
    assignment_id = assigned["assignment_ids"][0]
    assignments = request("GET", "/api/dispatch/assignments")["assignments"]
    today = date.today().isoformat()
    day = request("GET", f"/api/calendar/dispatch?{urllib.parse.urlencode({'view': 'day', 'date': today})}")
    week = request("GET", f"/api/calendar/dispatch?{urllib.parse.urlencode({'view': 'week', 'date': today})}")
    month = request("GET", f"/api/calendar/dispatch?{urllib.parse.urlencode({'view': 'month', 'date': today})}")
    detail = request("GET", f"/api/calendar/dispatch/detail/{assignment_id}")
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "orders_api_count": len(orders_before.get("orders", [])),
        "created_order_id": order["id"],
        "assignment_id": assignment_id,
        "assignment_list_contains": any(item["id"] == assignment_id for item in assignments),
        "day_ok": day.get("ok") is True,
        "day_contains_assignment": any(item["assignment_id"] == assignment_id for item in day.get("items", [])),
        "week_ok": week.get("ok") is True,
        "week_contains_assignment": any(item["assignment_id"] == assignment_id for item in week.get("items", [])),
        "month_ok": month.get("ok") is True,
        "month_summary_count": len(month.get("month_summary", [])),
        "detail_ok": detail.get("ok") is True,
        "detail_assignment_id": detail.get("detail", {}).get("assignment_id"),
        "dashboard_today_assigned_orders": summary.get("today_assigned_orders"),
        "dashboard_today_unassigned_orders": summary.get("today_unassigned_orders"),
        "dashboard_today_pending_settlement_orders": summary.get("today_pending_settlement_orders"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_time(total_minutes: int) -> str:
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


if __name__ == "__main__":
    main()

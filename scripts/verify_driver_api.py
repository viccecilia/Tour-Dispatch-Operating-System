import json
import os
import sys
import urllib.error
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


def main() -> None:
    init_db(seed=True)
    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    suffix = str(int(datetime.now().timestamp()))
    drivers = [
        request("POST", "/api/resources/drivers", {"name": f"R006司机A{suffix}", "phone": f"R006-A-{suffix}", "status": "available"})["driver"],
        request("POST", "/api/resources/drivers", {"name": f"R006司机B{suffix}", "phone": f"R006-B-{suffix}", "status": "available"})["driver"],
    ]
    vehicles = [
        request("POST", "/api/resources/vehicles", {"plate_number": f"R006{suffix}", "vehicle_type": "商务车", "seat_count": 6, "status": "available"})["vehicle"]
    ]
    driver_id = drivers[0]["id"]
    other_driver_id = drivers[1]["id"]
    vehicle_id = vehicles[0]["id"]

    base_minute = 480 + (int(datetime.now().timestamp()) % 360)
    order = request(
        "POST",
        "/api/orders",
        {
            "order_date": date.today().isoformat(),
            "start_time": _format_time(base_minute),
            "end_time": _format_time(base_minute + 60),
            "pickup_location": "司机端测试起点",
            "dropoff_location": "司机端测试终点",
            "order_type": "接机",
            "vehicle_type": "商务车",
            "passenger_count": 2,
            "luggage_count": 1,
            "guest_name": "司机端客人",
            "guest_contact": "09011112222",
            "agency_name": "R006测试旅行社",
            "price": 25000,
            "remark": "R006 driver smoke",
        },
    )["order"]
    assigned = request("POST", "/api/dispatch/assign", {"order_ids": [order["id"]], "driver_id": driver_id, "vehicle_id": vehicle_id})
    if not assigned.get("success"):
        raise RuntimeError(f"assign failed: {assigned}")
    assignment_id = assigned["assignment_ids"][0]

    own_assignments = request("GET", f"/api/driver/assignments?driver_id={driver_id}")["assignments"]
    detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver_id}")["assignment"]
    other_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={other_driver_id}")

    statuses = []
    for report_type in ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"]:
        report = request(
            "POST",
            "/api/driver/report",
            {
                "driver_id": driver_id,
                "assignment_id": assignment_id,
                "report_type": report_type,
                "latitude": 35.68,
                "longitude": 139.76,
                "location_text": "东京站附近",
                "note": f"{report_type} smoke",
            },
        )
        statuses.append(report.get("new_execution_status"))

    returned_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver_id}")["assignment"]
    reports = request("GET", f"/api/driver/reports?driver_id={driver_id}")["reports"]
    driver_dashboard = request("GET", f"/api/driver/dashboard?driver_id={driver_id}")
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "assignment_id": assignment_id,
        "own_assignment_visible": any(item["assignment_id"] == assignment_id for item in own_assignments),
        "detail_execution_status_initial": detail.get("execution_status"),
        "other_driver_blocked": other_detail.get("_status") == 404,
        "status_flow": statuses,
        "final_execution_status": returned_detail.get("execution_status"),
        "report_count_for_assignment": len([item for item in reports if item["assignment_id"] == assignment_id]),
        "driver_dashboard_count": driver_dashboard.get("active_assignment_count"),
        "dashboard_returned_orders": summary.get("today_returned_orders"),
        "dashboard_unreported_assignments": summary.get("unreported_assignments"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_time(total_minutes: int) -> str:
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


if __name__ == "__main__":
    main()

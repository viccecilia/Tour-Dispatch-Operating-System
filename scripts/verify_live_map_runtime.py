import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def assert_true(name: str, value: bool) -> None:
    if not value:
        raise AssertionError(name)


def main() -> None:
    global TOKEN
    init_db()

    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    drivers = request("GET", "/api/dispatch/drivers").get("drivers", [])
    vehicles = request("GET", "/api/dispatch/vehicles").get("vehicles", [])
    assert_true("drivers_available", len(drivers) > 0)
    assert_true("vehicles_available", len(vehicles) > 0)

    driver = drivers[0]
    vehicle = vehicles[0]
    order_date = (date.today() + timedelta(days=180)).isoformat()
    order = request(
        "POST",
        "/api/orders",
        {
            "order_date": order_date,
            "start_time": "09:10",
            "end_time": "10:30",
            "pickup_location": "KIX",
            "dropoff_location": "心斋桥微笑酒店",
            "order_type": "airport_pickup",
            "vehicle_type": vehicle.get("vehicle_type") or "商务车",
            "guest_name": "Live Map Smoke",
            "guest_contact": "090-0000-0000",
            "agency_name": "地图验证旅行社",
            "price": 800,
            "remark": "verify live map runtime",
        },
    )
    order_id = order.get("order", {}).get("id") or order.get("id")
    assert_true("order_created", bool(order_id))

    assigned = request(
        "POST",
        "/api/dispatch/assign",
        {
            "order_ids": [order_id],
            "driver_id": driver["id"],
            "vehicle_id": vehicle["id"],
        },
    )
    if assigned.get("success") is not True:
        raise AssertionError(f"dispatch_assigned: {assigned}")
    assignment_id = (assigned.get("assignment_ids") or [None])[0]
    assert_true("assignment_id", bool(assignment_id))

    location = request(
        "POST",
        "/api/driver/location",
        {
            "driver_id": driver["id"],
            "vehicle_id": vehicle["id"],
            "assignment_id": assignment_id,
            "order_id": order_id,
            "latitude": 34.4347,
            "longitude": 135.2441,
            "location_text": "KIX 第 1 航站楼附近",
            "source": "verify_live_map_runtime",
        },
    )
    assert_true("location_written", location.get("success") is True)

    latest = request("GET", f"/api/fleet/latest-locations?driver_id={driver['id']}&limit=20").get("locations", [])
    assert_true("latest_location_visible", any(item.get("driver_id") == driver["id"] for item in latest))
    latest_for_driver = next(item for item in latest if item.get("driver_id") == driver["id"])
    assert_true("latest_has_assignment_overlay", latest_for_driver.get("assignment_id") == assignment_id)
    assert_true("latest_has_order_overlay", latest_for_driver.get("order_id") == order_id)

    online = request("GET", "/api/fleet/latest-locations?online_status=online&limit=100").get("locations", [])
    summary = request("GET", "/api/fleet/location-summary")
    alerts = request("GET", "/api/driver/safety-alerts").get("alerts", [])

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "driver_id": driver["id"],
        "vehicle_id": vehicle["id"],
        "assignment_id": assignment_id,
        "order_id": order_id,
        "location_id": location.get("location_id"),
        "latest_location_visible": True,
        "assignment_overlay_visible": True,
        "online_filter_count": len(online),
        "fleet_summary_total": summary.get("total"),
        "safety_alert_count": len(alerts),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

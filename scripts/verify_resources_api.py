import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None and method in {"POST", "PUT"} and path.startswith("/api/resources/"):
        payload = {**payload, "tenant_id": payload.get("tenant_id") or 1}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    global TOKEN
    init_db(seed=True)
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    today = date.today()
    suffix = str(int(datetime.now().timestamp()))

    driver = request(
        "POST",
        "/api/resources/drivers",
        {
            "name": f"R014测试司机{suffix}",
            "phone": "090-R014-0001",
            "driver_code": "R14",
            "driver_language": "中文/日文",
            "office": "资源台账验证",
            "license_expires_at": (today + timedelta(days=10)).isoformat(),
            "medical_check_expires_at": (today - timedelta(days=1)).isoformat(),
            "status": "available",
            "tenant_id": 1,
        },
    )["driver"]
    vehicle = request(
        "POST",
        "/api/resources/vehicles",
        {
            "plate_number": f"R014-{suffix}",
            "plate_short_code": "R014",
            "vehicle_type": "10座",
            "vehicle_type_code": "10S",
            "seat_count": 10,
            "vehicle_color": "黑色",
            "snow_tire": "yes",
            "inspection_expires_at": (today + timedelta(days=20)).isoformat(),
            "insurance_expires_at": (today - timedelta(days=2)).isoformat(),
            "maintenance_status": "左侧电门检查中",
            "status": "maintenance",
            "tenant_id": 1,
        },
    )["vehicle"]

    updated_driver = request("PUT", f"/api/resources/drivers/{driver['id']}", {"office": "资源台账验证-已更新"})["driver"]
    updated_vehicle = request("PUT", f"/api/resources/vehicles/{vehicle['id']}", {"maintenance_status": "维修跟进中"})["vehicle"]
    drivers = request("GET", "/api/resources/drivers")["drivers"]
    vehicles = request("GET", "/api/resources/vehicles")["vehicles"]
    reminders = request("GET", "/api/resources/reminders")
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "login_user": login["user"]["username"],
        "created_driver_id": driver["id"],
        "created_vehicle_id": vehicle["id"],
        "updated_driver_office": updated_driver.get("office"),
        "updated_vehicle_maintenance": updated_vehicle.get("maintenance_status"),
        "drivers_count": len(drivers),
        "vehicles_count": len(vehicles),
        "driver_alert_count": len(updated_driver.get("alerts", [])),
        "vehicle_alert_count": len(updated_vehicle.get("alerts", [])),
        "reminder_total": reminders.get("total"),
        "reminder_expired": reminders.get("expired"),
        "reminder_upcoming": reminders.get("upcoming"),
        "reminder_maintenance": reminders.get("maintenance"),
        "dashboard_resource_alerts": summary.get("resource_alerts"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

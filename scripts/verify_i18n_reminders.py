import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from time import time
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
    suffix = str(int(time()))

    settings = request(
        "PUT",
        "/api/settings/reminders",
        {
            "vehicle_inspection_days": 18,
            "vehicle_shaken_days": 25,
            "driver_health_check_days": 30,
            "driver_license_days": 25,
        },
    )["settings"]
    driver = request(
        "POST",
        "/api/resources/drivers",
        {
            "name": "提醒验证司机",
            "phone": f"090-R032-{suffix[-4:]}",
            "status": "available",
            "driver_status": "available",
            "license_due_date": (today + timedelta(days=20)).isoformat(),
            "health_check_due_date": (today + timedelta(days=29)).isoformat(),
        },
    )["driver"]
    vehicle = request(
        "POST",
        "/api/resources/vehicles",
        {
            "plate_number": f"R032-提醒验证-{suffix[-6:]}",
            "vehicle_type": "10座",
            "seat_count": 10,
            "status": "available",
            "last_inspection_date": (today - timedelta(days=70)).isoformat(),
            "next_inspection_due_date": (today + timedelta(days=17)).isoformat(),
            "shaken_due_date": (today + timedelta(days=24)).isoformat(),
            "insurance_due_date": (today + timedelta(days=90)).isoformat(),
        },
    )["vehicle"]
    reminders = request("GET", "/api/resources/reminders")
    notifications = request("GET", "/api/notifications/summary")
    summary = request("GET", "/api/dashboard/summary")

    driver_fields = {alert["field"] for alert in driver.get("alerts", [])}
    vehicle_fields = {alert["field"] for alert in vehicle.get("alerts", [])}
    result = {
        "login_user": login["user"]["username"],
        "settings": settings,
        "driver_license_alert": "license_due_date" in driver_fields,
        "driver_health_alert": "health_check_due_date" in driver_fields,
        "vehicle_inspection_alert": "next_inspection_due_date" in vehicle_fields,
        "vehicle_shaken_alert": "shaken_due_date" in vehicle_fields,
        "reminder_total": reminders.get("total"),
        "notification_unread": notifications.get("unread"),
        "dashboard_resource_alerts": summary.get("resource_alerts"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

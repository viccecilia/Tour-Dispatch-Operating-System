import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import BASE_URL


BASE = os.environ.get("WX_DISPATCH_BASE_URL", BASE_URL).rstrip("/")
TOKEN = ""


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def main() -> None:
    global TOKEN
    login = request("POST", "/api/dispatch-mobile/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    orders = request("GET", "/api/dispatch/unassigned-orders").get("orders", [])
    drivers = request("GET", "/api/dispatch/drivers").get("drivers", [])
    vehicles = request("GET", "/api/dispatch/vehicles").get("vehicles", [])
    if not orders or not drivers or not vehicles:
        raise AssertionError("missing unassigned orders, available drivers, or available vehicles")

    assigned = None
    attempts = []
    for order in orders[:8]:
        for driver in drivers[:6]:
            for vehicle in vehicles[:6]:
                result = request(
                    "POST",
                    "/api/dispatch/assign",
                    {"order_ids": [order["id"]], "driver_id": driver["id"], "vehicle_id": vehicle["id"]},
                )
                attempts.append({"order_id": order["id"], "driver_id": driver["id"], "vehicle_id": vehicle["id"], "success": result.get("success")})
                if result.get("success"):
                    assigned = {"order": order, "driver": driver, "vehicle": vehicle, "result": result}
                    break
            if assigned:
                break
        if assigned:
            break

    if not assigned:
        raise AssertionError(f"no assignable combination found: {attempts[:5]}")

    notifications = request("GET", f"/api/driver/notifications?driver_id={assigned['driver']['id']}").get("notifications", [])
    if not any(item.get("notification_type") == "new_order" for item in notifications):
        raise AssertionError("driver new_order notification was not generated")

    assignments = request("GET", "/api/dispatch/assignments").get("assignments", [])
    if not any(item.get("id") in assigned["result"].get("assignment_ids", []) for item in assignments):
        raise AssertionError("new assignment is not visible in dispatch assignments")

    print(json.dumps({
        "assigned_order_id": assigned["order"]["id"],
        "driver_id": assigned["driver"]["id"],
        "vehicle_id": assigned["vehicle"]["id"],
        "assignment_ids": assigned["result"].get("assignment_ids"),
        "driver_new_order_notification": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

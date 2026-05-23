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
    dispatcher = login["dispatcher"]

    parsed = request(
        "POST",
        "/api/dispatch-mobile/parser/text",
        {
            **dispatcher,
            "text": "5.30 08:00 KIX接机心斋桥微笑酒店 3代 绿600\n5.30 13:30 大阪市内-京都市内 包车 10座 1500",
            "batch": True,
        },
    )
    draft_ids = [draft["id"] for draft in parsed.get("drafts", [])]
    if len(draft_ids) < 2:
        raise AssertionError("pilot parser did not create enough drafts")

    order_ids = []
    for draft_id in draft_ids[:2]:
        confirmed = request("POST", f"/api/parser/drafts/{draft_id}/confirm", dispatcher)
        order_ids.append(confirmed["order_id"])

    dashboard = request("GET", f"/api/dispatch-mobile/dashboard?dispatcher_id={dispatcher['dispatcher_id']}")
    if dashboard.get("counts", {}).get("unassigned_orders", 0) < 2:
        raise AssertionError("mobile dashboard does not show dispatcher-owned unassigned orders")

    mobile_pool = request("GET", f"/api/dispatch-mobile/unassigned-orders?dispatcher_id={dispatcher['dispatcher_id']}").get("orders", [])
    mobile_ids = {item["id"] for item in mobile_pool}
    if not set(order_ids).issubset(mobile_ids):
        raise AssertionError("mobile unassigned pool is not isolated to dispatcher-owned created orders")

    drivers = request("GET", "/api/dispatch/drivers").get("drivers", [])
    vehicles = request("GET", "/api/dispatch/vehicles").get("vehicles", [])
    if not drivers or not vehicles:
        raise AssertionError("missing available driver or vehicle")

    assigned = request(
        "POST",
        "/api/dispatch/assign",
        {
            **dispatcher,
            "order_ids": [order_ids[0]],
            "driver_id": drivers[0]["id"],
            "vehicle_id": vehicles[0]["id"],
        },
    )
    if not assigned.get("success"):
        raise AssertionError(f"mobile dispatch assign failed: {assigned}")

    notifications = request("GET", "/api/dispatch-mobile/notifications").get("notifications", [])
    if not any(item.get("notification_type") in {"dispatch_assigned", "new_order"} for item in notifications):
        raise AssertionError("pilot notification runtime did not expose dispatch notifications")

    logs = request("GET", f"/api/dispatch-mobile/audit-logs?dispatcher_id={dispatcher['dispatcher_id']}").get("logs", [])
    actions = {item.get("action") for item in logs}
    required = {"mobile_parse", "mobile_confirm_order", "mobile_dispatch_assign"}
    if not required.issubset(actions):
        raise AssertionError(f"missing dispatch mobile audit actions: {sorted(required - actions)}")

    result = {
        "dispatcher_id": dispatcher["dispatcher_id"],
        "created_order_ids": order_ids,
        "assigned_order_id": order_ids[0],
        "assignment_ids": assigned.get("assignment_ids"),
        "dashboard_counts": dashboard.get("counts"),
        "audit_actions": sorted(actions),
        "notifications_visible": len(notifications),
        "multi_dispatcher_isolation": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

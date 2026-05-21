import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import LOG_DIR


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as parse_exc:
            raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from parse_exc
        payload["_status"] = exc.code
        return payload


def assert_true(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)


def sample_lines(count: int = 120) -> list[str]:
    lines = []
    for index in range(count):
        day = 20 + (index // 24)
        hour = 6 + (index % 12)
        minute = "00" if index % 2 == 0 else "30"
        vehicle = "3代 绿" if index % 3 else "10座绿牌"
        price = 600 + (index % 8) * 100
        route = "大阪-奈良-宇治-京都" if index % 5 == 0 else "关西接机大阪"
        order_type = "包车" if index % 5 == 0 else "接机"
        note = " 儿童座椅*2" if index % 11 == 0 else ""
        lines.append(f"6.{day:02d} {hour:02d}:{minute} {route} {order_type} {vehicle}{note} {price} R015客人{index:03d}")
    return lines


def main() -> None:
    request("GET", "/api/ping")
    admin = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    dispatcher = request("POST", "/api/auth/login", {"username": "dispatcher", "password": "dispatcher123"})
    driver_login = request("POST", "/api/auth/login", {"username": "driver_demo", "password": "driver123"})
    assert_true("admin_login", admin.get("user", {}).get("role") == "admin")
    assert_true("dispatcher_login", dispatcher.get("user", {}).get("role") == "dispatcher")
    assert_true("driver_admin_login_blocked", driver_login.get("error") == "invalid_credentials")

    parsed = request("POST", "/api/parser/text", {"text": "\n".join(sample_lines()), "batch": True})
    drafts = parsed.get("drafts", [])
    assert_true("pressure_drafts_count", len(drafts) == 120)
    assert_true("pressure_raw_text_kept", all(draft.get("raw_text") for draft in drafts))

    confirmed_order_ids = []
    for draft in drafts:
        confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm")
        confirmed_order_ids.append(confirmed["order_id"])
    assert_true("confirmed_count", len(confirmed_order_ids) == 120)

    drivers = request("GET", "/api/dispatch/drivers")["drivers"]
    vehicles = request("GET", "/api/dispatch/vehicles")["vehicles"]
    assert_true("has_driver_vehicle", bool(drivers and vehicles))
    assigned = request(
        "POST",
        "/api/dispatch/assign",
        {"order_ids": confirmed_order_ids[:8], "driver_id": drivers[0]["id"], "vehicle_id": vehicles[0]["id"]},
    )
    assert_true("pressure_assign_success", assigned.get("success") is True)
    assert_true("pressure_assign_count", len(assigned.get("assignment_ids", [])) == 8)

    calendar = request("GET", "/api/calendar/dispatch?view=week&date=2026-06-20")
    assert_true("calendar_after_pressure", calendar.get("ok") is True and len(calendar.get("items", [])) >= 8)
    summary = request("GET", "/api/dashboard/summary")
    log_file = LOG_DIR / "operations.log"
    assert_true("operation_log_exists", log_file.exists() and log_file.stat().st_size > 0)

    result = {
        "admin_login": admin.get("user", {}).get("role"),
        "dispatcher_login": dispatcher.get("user", {}).get("role"),
        "driver_admin_login_blocked": driver_login.get("error"),
        "drafts_created": len(drafts),
        "orders_confirmed": len(confirmed_order_ids),
        "assign_success": assigned.get("success"),
        "assignment_count": len(assigned.get("assignment_ids", [])),
        "calendar_items": len(calendar.get("items", [])),
        "dashboard_today_orders": summary.get("today_orders"),
        "operation_log": str(log_file),
        "operation_log_bytes": log_file.stat().st_size,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

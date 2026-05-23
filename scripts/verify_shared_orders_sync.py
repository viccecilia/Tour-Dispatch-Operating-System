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
from backend.db.database import get_connection


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
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]

    shared = request("GET", "/api/dispatch-mobile/shared-state")
    web_orders = request("GET", "/api/orders")
    web_drafts = request("GET", "/api/parser/drafts")
    web_assignments = request("GET", "/api/dispatch/assignments")
    web_notifications = request("GET", "/api/notifications")

    direct = _direct_counts()
    api_counts = shared["tables"]
    mismatches = {
        key: {"api": api_counts.get(key), "db": direct.get(key)}
        for key in direct
        if int(api_counts.get(key, -1)) != int(direct.get(key, -2))
    }
    if mismatches:
        raise AssertionError(f"shared state mismatch: {mismatches}")

    web_counts = {
        "orders": len(web_orders.get("orders", [])),
        "drafts": len(web_drafts.get("drafts", [])),
        "assignments": len(web_assignments.get("assignments", [])),
        "notifications": len(web_notifications.get("notifications", [])),
    }
    if web_counts["orders"] > api_counts["orders"] or web_counts["drafts"] > api_counts["drafts"]:
        raise AssertionError(f"web counts exceed shared counts: {web_counts} vs {api_counts}")

    print(json.dumps({"shared_state": api_counts, "direct_db": direct, "web_visible": web_counts}, ensure_ascii=False, indent=2))


def _direct_counts() -> dict[str, int]:
    with get_connection() as conn:
        return {
            "orders": int(conn.execute("SELECT COUNT(*) AS c FROM orders WHERE tenant_id = 1 AND COALESCE(is_deleted, 0) = 0").fetchone()["c"]),
            "drafts": int(conn.execute("SELECT COUNT(*) AS c FROM order_drafts WHERE tenant_id = 1").fetchone()["c"]),
            "assignments": int(conn.execute("SELECT COUNT(*) AS c FROM assignments WHERE tenant_id = 1").fetchone()["c"]),
            "notifications": int(conn.execute("SELECT COUNT(*) AS c FROM notifications WHERE tenant_id = 1").fetchone()["c"]),
        }


if __name__ == "__main__":
    main()

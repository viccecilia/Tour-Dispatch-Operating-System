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
    login = request("POST", "/api/dispatch-mobile/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    dispatcher = login["dispatcher"]

    context = request("GET", f"/api/dispatch-mobile/context?dispatcher_id={dispatcher['dispatcher_id']}")
    dashboard = request("GET", f"/api/dispatch-mobile/dashboard?dispatcher_id={dispatcher['dispatcher_id']}")
    parsed = request(
        "POST",
        "/api/dispatch-mobile/parser/text",
        {
            "text": "5.29 08:00 KIX接机大阪 3代 绿450\n5.29 10:20 大阪市内-京都市内 包车 3代 1500",
            "batch": True,
            **dispatcher,
        },
    )
    if parsed.get("count", 0) < 2:
        raise AssertionError("dispatch mobile parser did not create batch drafts")

    draft = parsed["drafts"][0]
    if draft.get("created_by_dispatcher_id") != dispatcher["dispatcher_id"]:
        raise AssertionError("draft dispatcher context was not written")
    if draft.get("source_channel") != "mobile_dispatch":
        raise AssertionError("draft source_channel was not marked mobile_dispatch")

    updated = request(
        "PUT",
        f"/api/dispatch-mobile/drafts/{draft['id']}",
        {
            **dispatcher,
            "price": 999,
            "agency_name": "移动调度测试社",
            "remark": "mobile correction smoke",
        },
    )["draft"]
    if int(float(updated.get("price") or 0)) != 999 or updated.get("updated_by_dispatcher_id") != dispatcher["dispatcher_id"]:
        raise AssertionError("mobile draft correction did not persist dispatcher context")

    confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm", dispatcher)
    order = confirmed.get("order") or {}
    if order.get("created_by_dispatcher_id") != dispatcher["dispatcher_id"]:
        raise AssertionError("confirmed order dispatcher context was not written")
    if order.get("source_channel") != "mobile_dispatch":
        raise AssertionError("confirmed order source_channel was not marked mobile_dispatch")

    columns = _columns("orders")
    draft_columns = _columns("order_drafts")
    required_columns = {
        "created_by_dispatcher",
        "created_by_dispatcher_id",
        "created_by_dispatcher_code",
        "updated_by_dispatcher",
        "updated_by_dispatcher_id",
        "updated_by_dispatcher_code",
    }
    missing = sorted(required_columns - columns)
    missing_draft = sorted(required_columns - draft_columns)
    if missing or missing_draft:
        raise AssertionError(f"missing dispatcher columns orders={missing} drafts={missing_draft}")

    result = {
        "dispatcher_login": dispatcher,
        "context_ok": context.get("ok") is True,
        "dashboard_counts": dashboard.get("counts", {}),
        "draft_count": parsed.get("count"),
        "corrected_draft_price": updated.get("price"),
        "confirmed_order_id": confirmed.get("order_id"),
        "dispatcher_context_written": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _columns(table: str) -> set[str]:
    with get_connection() as conn:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


if __name__ == "__main__":
    main()

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
AUTH_TOKEN = ""
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
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
    global AUTH_TOKEN
    init_db(seed=True)

    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    AUTH_TOKEN = login.get("token", "")
    text = "5.09 11:00 大阪往返天桥立美山 包车 3代 绿 1900 Ashwin Arora"
    parsed = request("POST", "/api/parser/text", {"text": text})
    draft = parsed["draft"]
    parse_result = draft.get("parse_result") or {}
    drafts = request("GET", "/api/parser/drafts")
    fetched = request("GET", f"/api/parser/drafts/{draft['id']}")["draft"]
    updated = request(
        "PUT",
        f"/api/parser/drafts/{draft['id']}",
        {
            "agency_name": "人工修正旅行社",
            "pickup_location": fetched.get("pickup_location") or "大阪市",
            "dropoff_location": fetched.get("dropoff_location") or "天桥立美山",
            "remark": "人工修正确认",
            "parse_status": "parsed",
        },
    )["draft"]
    confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm")
    order = request("GET", f"/api/orders/{confirmed['order_id']}")["order"]
    failed_text = "完全无法识别但必须保留的自由文本"
    failed = request("POST", "/api/parser/text", {"text": failed_text})
    discarded = request("DELETE", f"/api/parser/drafts/{failed['draft']['id']}")
    excel = request(
        "POST",
        "/api/parser/excel",
        {"csv": "3.29,08:05,关西接机大阪,10座,600\n3.29,08:00/20:00,环球往返接送,3代,600"},
    )
    voice = request("POST", "/api/parser/voice", {"voice_text": "5月10日 15:30 羽田接机 银座 2位客人"})
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "text_parse_status": parsed.get("parse_status"),
        "parser_confidence": parse_result.get("confidence"),
        "parser_confidence_level": parse_result.get("confidence_level"),
        "parser_low_confidence": parse_result.get("low_confidence"),
        "parser_has_diff_preview": bool(parse_result.get("diff_preview")),
        "draft_id": draft["id"],
        "draft_list_contains": any(item["id"] == draft["id"] for item in drafts.get("drafts", [])),
        "fetched_raw_text_kept": fetched.get("raw_text") == text,
        "normalized_pickup": fetched.get("pickup_location"),
        "normalized_dropoff": fetched.get("dropoff_location"),
        "updated_agency_name": updated.get("agency_name"),
        "confirmed_order_id": confirmed.get("order_id"),
        "confirmed_status": confirmed.get("draft", {}).get("parse_status"),
        "order_created_agency": order.get("agency_name"),
        "failed_status": failed.get("parse_status"),
        "failed_raw_text_kept": failed.get("draft", {}).get("raw_text") == failed_text,
        "discarded_kept_raw_text": discarded.get("draft", {}).get("raw_text") == failed_text,
        "excel_count": excel.get("count"),
        "voice_status": voice.get("parse_status"),
        "dashboard_pending_drafts": summary.get("pending_drafts"),
        "dashboard_today_parsed_drafts": summary.get("today_parsed_drafts"),
        "dashboard_failed_drafts": summary.get("failed_drafts"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

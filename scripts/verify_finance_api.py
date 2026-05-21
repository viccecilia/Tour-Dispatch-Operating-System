import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def request(method: str, path: str, payload: dict | None = None, parse_json: bool = True):
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=8) as response:
        body = response.read().decode("utf-8-sig")
        return json.loads(body) if parse_json else body


def main() -> None:
    global TOKEN
    init_db(seed=True)
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    today = date.today().isoformat()
    order = request(
        "POST",
        "/api/orders",
        {
            "order_date": today,
            "start_time": "09:00",
            "end_time": "10:30",
            "pickup_location": "大阪酒店",
            "dropoff_location": "关西机场",
            "order_type": "送机",
            "vehicle_type": "10座",
            "agency_name": "R015财务测试旅行社",
            "price": 88000,
            "fee_remark": "停车费另计",
            "settlement_status": "pending",
        },
    )["order"]
    summary_before = request("GET", "/api/finance/summary")
    filtered = request("GET", f"/api/finance/summary?{urllib.parse.urlencode({'agency_name': 'R015财务测试'})}")
    updated = request("PUT", f"/api/finance/orders/{order['id']}", {"settlement_status": "settled"})["order"]
    summary_after = request("GET", "/api/finance/summary")
    csv_text = request("GET", "/api/finance/export", parse_json=False)
    result = {
        "login_user": login["user"]["username"],
        "created_order_id": order["id"],
        "summary_order_count": summary_before.get("order_count"),
        "filtered_order_count": filtered.get("order_count"),
        "updated_settlement_status": updated.get("settlement_status"),
        "pending_amount_before": summary_before.get("pending_amount"),
        "settled_amount_after": summary_after.get("settled_amount"),
        "export_has_header": "订单号" in csv_text and "结算状态" in csv_text,
        "export_has_created_order": str(order.get("oid") or order["id"]) in csv_text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

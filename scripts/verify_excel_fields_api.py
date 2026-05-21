import json
import os
import sys
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import get_connection, init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    init_db(seed=True)

    payload = {
        "order_date": "2026-05-20",
        "end_date": "2026-05-20",
        "start_time": "08:00",
        "end_time": "10:30",
        "pickup_location": "大阪市",
        "dropoff_location": "KIX",
        "order_type": "送迎",
        "vehicle_type": "3代 绿牌",
        "order_note_code": "D",
        "order_source": "大寅",
        "vehicle_class": "绿",
        "vehicle_type_code": "A",
        "driver_code": "LCZ",
        "driver_language": "韩语可",
        "vehicle_color": "黑",
        "snow_tire": "雪",
        "price": 500,
        "price_rmb": 500,
        "price_jpy": 10000,
        "fee_remark": "儿童座椅；代收2000日元",
        "collection_amount_jpy": 2000,
        "parking_fee_jpy": 300,
        "other_fee_jpy": 500,
        "driver_salary_jpy": 4000,
        "remark": "Excel 字段映射测试",
    }
    created = request("POST", "/api/orders", payload)["order"]
    fetched = request("GET", f"/api/orders/{created['id']}")["order"]

    draft = request("POST", "/api/parser/text", {"text": "5.12 10:00 铃鹿-京都 包车 10座绿牌 儿童座椅*2 2000若綺 黃"})["draft"]
    confirmed = request("POST", f"/api/parser/drafts/{draft['id']}/confirm")
    confirmed_order = request("GET", f"/api/orders/{confirmed['order_id']}")["order"]

    drivers = request("GET", "/api/dispatch/drivers")["drivers"]
    vehicles = request("GET", "/api/dispatch/vehicles")["vehicles"]
    assign_result = request(
        "POST",
        "/api/dispatch/assign",
        {"order_ids": [created["id"]], "driver_id": drivers[0]["id"], "vehicle_id": vehicles[0]["id"]},
    )
    assigned = request("GET", f"/api/orders/{created['id']}")["order"]

    with get_connection() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()]

    result = {
        "new_columns_present": all(
            name in columns
            for name in [
                "order_note_code",
                "order_source",
                "vehicle_type_code",
                "driver_code",
                "price_rmb",
                "price_jpy",
                "fee_remark",
                "collection_amount_jpy",
                "parking_fee_jpy",
                "other_fee_jpy",
                "driver_salary_jpy",
            ]
        ),
        "created_oid_temp": created["oid"],
        "created_fields_written": {
            "order_note_code": fetched.get("order_note_code"),
            "order_source": fetched.get("order_source"),
            "vehicle_type_code": fetched.get("vehicle_type_code"),
            "driver_code": fetched.get("driver_code"),
            "price_rmb": fetched.get("price_rmb"),
            "price_jpy": fetched.get("price_jpy"),
            "fee_remark": fetched.get("fee_remark"),
        },
        "draft_confirmed_vehicle_type_code": confirmed_order.get("vehicle_type_code"),
        "draft_confirmed_fee_remark": confirmed_order.get("fee_remark"),
        "assign_success": assign_result.get("success"),
        "assigned_oid": assigned.get("oid"),
        "assigned_plate_short_code": assigned.get("plate_short_code"),
        "assigned_driver_code": assigned.get("driver_code"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

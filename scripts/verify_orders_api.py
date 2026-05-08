import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
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
    today = date.today().isoformat()
    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})

    created = request(
        "POST",
        "/api/orders",
        {
            "order_date": today,
            "start_time": "09:00",
            "end_time": "11:00",
            "pickup_location": "东京站",
            "dropoff_location": "成田机场",
            "order_type": "送机",
            "vehicle_type": "商务车",
            "passenger_count": 2,
            "luggage_count": 2,
            "guest_name": "测试客人",
            "guest_contact": "09000000000",
            "agency_name": "测试旅行社",
            "price": 18000,
            "remark": "R002 API smoke",
        },
    )["order"]
    order_id = created["id"]

    listed = request(
        "GET",
        f"/api/orders?{urllib.parse.urlencode({'order_date': today, 'agency_name': '测试旅行社'})}",
    )
    fetched = request("GET", f"/api/orders/{order_id}")["order"]
    updated = request(
        "PUT",
        f"/api/orders/{order_id}",
        {"price": 19000, "settlement_status": "pending", "remark": "updated"},
    )["order"]
    deleted = request("DELETE", f"/api/orders/{order_id}")
    after_delete = request("GET", f"/api/orders/{order_id}")
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "created_id": order_id,
        "list_count": len(listed.get("orders", [])),
        "fetched_oid": fetched.get("oid"),
        "updated_price": updated.get("price"),
        "deleted": deleted.get("deleted") is True,
        "after_delete_error": after_delete.get("error"),
        "summary_keys": sorted(summary.keys()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

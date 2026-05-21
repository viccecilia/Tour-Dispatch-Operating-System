import json
import os
import urllib.error
import urllib.request
from datetime import date


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")


def request(method: str, path: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body)


def login(username: str, password: str = "admin123") -> tuple[str, dict]:
    status, payload = request("POST", "/api/auth/login", {"username": username, "password": password})
    assert status == 200, payload
    return payload["token"], payload["user"]


def main() -> None:
    unauth_status, unauth_payload = request("GET", "/api/orders")
    admin_token, admin_user = login("admin")
    tenant2_token, tenant2_user = login("tenant2_admin")

    today = date.today().isoformat()
    status, created_payload = request(
        "POST",
        "/api/orders",
        {
            "order_date": today,
            "start_time": "22:00",
            "end_time": "23:00",
            "pickup_location": "Tenant1 起点",
            "dropoff_location": "Tenant1 终点",
            "order_type": "测试",
            "vehicle_type": "测试车",
            "price": 100,
        },
        admin_token,
    )
    assert status == 201, created_payload
    oid = created_payload["order"]["oid"]

    _, admin_orders = request("GET", f"/api/orders?keyword={oid}", token=admin_token)
    _, tenant2_orders = request("GET", f"/api/orders?keyword={oid}", token=tenant2_token)

    result = {
        "unauthorized_without_token": unauth_status == 401 and unauth_payload.get("error") == "unauthorized",
        "admin_tenant_id": admin_user.get("tenant_id"),
        "tenant2_tenant_id": tenant2_user.get("tenant_id"),
        "admin_can_see_created_order": len(admin_orders.get("orders", [])) == 1,
        "tenant2_cannot_see_admin_order": len(tenant2_orders.get("orders", [])) == 0,
        "created_oid": oid,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert all(value is True for key, value in result.items() if key.endswith("token") or key.startswith("admin_can") or key.startswith("tenant2_cannot"))
    assert result["admin_tenant_id"] != result["tenant2_tenant_id"]


if __name__ == "__main__":
    main()

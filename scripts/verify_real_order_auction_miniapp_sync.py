from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import get_connection  # noqa: E402
from backend.services.auction_service import claim_auction_listing, create_auction_listings  # noqa: E402


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")


def request(method: str, path: str, payload: dict | None = None, token: str = "", headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"error": body}
        return exc.code, parsed


def assert_true(name: str, condition: bool, detail: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def main() -> None:
    suffix = str(int(time.time()))
    today = date.today().isoformat()
    real_order = {
        "order_date": today,
        "end_date": today,
        "start_time": "09:35",
        "end_time": "11:05",
        "pickup_location": "Kansai International Airport T1",
        "dropoff_location": "Osaka Namba Swissotel",
        "order_type": "airport_transfer",
        "vehicle_type": "Hiace",
        "passenger_count": 4,
        "luggage_count": 5,
        "guest_name": f"REAL-LINK-Zhang-{suffix}",
        "guest_contact": "080-1111-2222",
        "price": 52000,
        "fee_remark": "真实格式联动测试：关西机场到大阪难波酒店，含 5 件行李。",
        "remark": "real order to auction sync smoke",
    }

    ping_status, ping = request("GET", "/api/ping")
    assert_true("backend_ping", ping_status == 200 and ping.get("ok") is True, ping)

    admin_status, admin_login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    assert_true("admin_login", admin_status == 200 and admin_login.get("token"), admin_login)
    admin_token = admin_login["token"]

    dispatch_status, dispatch_login = request("POST", "/api/dispatch-mobile/login", {"username": "admin", "password": "admin123"})
    assert_true("dispatch_miniapp_login", dispatch_status == 200 and dispatch_login.get("token"), dispatch_login)
    dispatch_token = dispatch_login["token"]
    dispatcher = dispatch_login.get("dispatcher") or {}
    dispatcher_id = dispatcher.get("dispatcher_id") or 1

    agency_id, portal_code = _ensure_agency_portal(admin_token, suffix)
    agency_status, agency_login = request("POST", "/api/agency-portal/login", {"agency_id": agency_id, "portal_code": portal_code})
    assert_true("agency_login", agency_status == 200 and agency_login.get("token"), agency_login)
    agency_token = agency_login["token"]

    agency_before_status, agency_before = request("GET", "/api/agency-portal/orders", headers={"X-Agency-Token": agency_token})
    assert_true("agency_before_orders", agency_before_status == 200, agency_before)

    create_status, created = request("POST", "/api/agency-portal/orders", real_order, headers={"X-Agency-Token": agency_token})
    assert_true("agency_order_create", create_status == 201 and created.get("order", {}).get("id"), created)
    order = created["order"]
    order_id = order["id"]

    agency_after_status, agency_after = request("GET", "/api/agency-portal/orders", headers={"X-Agency-Token": agency_token})
    agency_orders = agency_after.get("orders", [])
    assert_true("agency_order_visible", any(item.get("id") == order_id for item in agency_orders), agency_after)

    order_status, order_detail = request("GET", f"/api/orders/{order_id}", token=admin_token)
    assert_true("web_admin_order_visible", order_status == 200 and order_detail.get("order", {}).get("id") == order_id, order_detail)

    shared_before_status, shared_before = request("GET", "/api/dispatch-mobile/shared-state", token=dispatch_token)
    assert_true("dispatch_miniapp_shared_state", shared_before_status == 200 and shared_before.get("ok") is True, shared_before)

    unassigned_status, unassigned = request("GET", f"/api/dispatch-mobile/unassigned-orders?dispatcher_id={dispatcher_id}", token=dispatch_token)
    assert_true("dispatch_miniapp_unassigned_endpoint_ok", unassigned_status == 200, unassigned)
    visible_in_dispatcher_personal_queue = any(item.get("id") == order_id for item in unassigned.get("orders", []))

    publish_payload = {
        "order_ids": [order_id],
        "start_price_jpy": 41000,
        "buyout_price_jpy": 47000,
        "note": "真实格式联动测试发布到订单大厅",
    }
    publish_status, published = request("POST", "/api/auction/listings", publish_payload, token=admin_token)
    publish_path = "api"
    if publish_status == 404:
        published = create_auction_listings(publish_payload, admin_login.get("user"))
        publish_status = 201
        publish_path = "service_fallback"
    assert_true("auction_publish", publish_status == 201 and published.get("count") == 1, published)
    listing_id = published["listings"][0]["listing_id"]

    listed_status, listed = request("GET", "/api/auction/listings?status=listed", token=dispatch_token)
    assert_true("dispatch_miniapp_auction_listed_endpoint", listed_status == 200, listed)
    listed_match = next((item for item in listed.get("listings", []) if item.get("id") == listing_id), None)
    assert_true("dispatch_miniapp_auction_listing_visible", bool(listed_match), listed)

    claim_status, claimed = request(
        "POST",
        f"/api/auction/listings/{listing_id}/claim",
        {"buyer_tenant_id": 2, "claim_price_jpy": 47000},
        token=admin_token,
    )
    claim_path = "api"
    if claim_status == 404:
        claimed_listing = claim_auction_listing(listing_id, {"buyer_tenant_id": 2, "claim_price_jpy": 47000}, admin_login.get("user"))
        claim_status = 200
        claimed = {"listing": claimed_listing}
        claim_path = "service_fallback"
    assert_true("carrier_claim_listing", claim_status == 200 and claimed.get("listing", {}).get("status") == "claimed", claimed)

    claimed_status, claimed_list = request("GET", "/api/auction/listings?status=claimed", token=dispatch_token)
    assert_true("claimed_list_endpoint", claimed_status == 200, claimed_list)
    claimed_match = next((item for item in claimed_list.get("listings", []) if item.get("id") == listing_id), None)
    assert_true("claimed_listing_visible", bool(claimed_match), claimed_list)

    listed_after_status, listed_after = request("GET", "/api/auction/listings?status=listed", token=dispatch_token)
    assert_true("listed_after_endpoint", listed_after_status == 200, listed_after)
    no_longer_listed = not any(item.get("id") == listing_id for item in listed_after.get("listings", []))

    order_after_status, order_after = request("GET", f"/api/orders/{order_id}", token=admin_token)
    assert_true("order_after_claim_visible", order_after_status == 200, order_after)
    order_after_data = order_after["order"]
    assert_true("order_status_written_back", order_after_data.get("dispatch_status") == "auction_claimed", order_after_data)

    driver_id = _first_driver_id()
    driver_assign_status, driver_assign = request("GET", f"/api/driver/assignments?driver_id={driver_id}")
    driver_workbench_status, driver_workbench = request("GET", f"/api/driver/workbench?driver_id={driver_id}")
    driver_can_fetch = driver_assign_status == 200 and driver_workbench_status == 200
    driver_wrongly_sees_unassigned_or_auction_order = any(
        item.get("order_id") == order_id or item.get("id") == order_id for item in driver_assign.get("assignments", [])
    )

    result = {
        "ok": True,
        "base_url": BASE_URL,
        "created_order": {
            "id": order_id,
            "oid": order.get("oid"),
            "agency_name": order.get("agency_name"),
            "route": f"{order.get('pickup_location')} -> {order.get('dropoff_location')}",
            "price": order.get("price"),
            "dispatch_status_initial": order.get("dispatch_status"),
        },
        "auction": {
            "listing_id": listing_id,
            "publish_path": publish_path,
            "listed_visible_in_dispatch_miniapp": bool(listed_match),
            "claim_status": claimed.get("listing", {}).get("status"),
            "claim_path": claim_path,
            "buyer_tenant_id": claimed.get("listing", {}).get("buyer_tenant_id"),
            "claimed_visible_in_dispatch_miniapp": bool(claimed_match),
            "no_longer_in_listed_after_claim": no_longer_listed,
            "order_dispatch_status_after_claim": order_after_data.get("dispatch_status"),
            "order_execution_status_after_claim": order_after_data.get("execution_status"),
        },
        "miniapp_watch": {
            "agency_web_orders_visible": any(item.get("id") == order_id for item in agency_orders),
            "dispatch_mobile_shared_state_ok": shared_before.get("ok") is True,
            "dispatch_mobile_personal_unassigned_visible": visible_in_dispatcher_personal_queue,
            "dispatch_mobile_personal_unassigned_note": "agency portal orders are not in dispatcher personal queue unless created_by_dispatcher_id is set",
            "dispatch_mobile_auction_list_visible": bool(listed_match),
            "driver_miniapp_fetch_ok": driver_can_fetch,
            "driver_miniapp_order_visible_before_assignment": driver_wrongly_sees_unassigned_or_auction_order,
            "driver_miniapp_note": "driver app should not see marketplace orders before dispatch assignment",
        },
        "raw_counts": {
            "agency_orders_before": len(agency_before.get("orders", [])),
            "agency_orders_after": len(agency_orders),
            "dispatch_personal_unassigned_count": len(unassigned.get("orders", [])),
            "listed_count_before_claim": len(listed.get("listings", [])),
            "listed_count_after_claim": len(listed_after.get("listings", [])),
            "claimed_count": len(claimed_list.get("listings", [])),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _first_driver_id() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM drivers WHERE COALESCE(status, '') != 'deleted' ORDER BY id LIMIT 1").fetchone()
    if not row:
        return 1
    return int(row["id"])


def _ensure_agency_portal(admin_token: str, suffix: str) -> tuple[int, str]:
    status, agencies = request("GET", "/api/agency-portal/agencies")
    if status == 200 and agencies.get("agencies"):
        item = agencies["agencies"][0]
        with get_connection() as conn:
            row = conn.execute("SELECT portal_code FROM agencies WHERE id = ?", (item["id"],)).fetchone()
        if row and row["portal_code"]:
            return int(item["id"]), str(row["portal_code"])

    portal_code = f"SYNC{suffix[-6:]}"
    status, created = request(
        "POST",
        "/api/agencies",
        {
            "agency_code": "SYNC",
            "company_name": f"真实联动旅行社 {suffix}",
            "name": f"真实联动旅行社 {suffix}",
            "contact_name": "测试客服",
            "contact_phone": "080-1111-2222",
            "portal_code": portal_code,
            "is_portal_enabled": 1,
            "status": "active",
        },
        token=admin_token,
    )
    assert_true("create_agency_portal", status == 201 and created.get("agency", {}).get("id"), created)
    return int(created["agency"]["id"]), portal_code


if __name__ == "__main__":
    main()

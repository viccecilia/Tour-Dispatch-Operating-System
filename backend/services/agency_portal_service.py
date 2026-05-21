from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from backend.config import JWT_EXPIRES_SECONDS, JWT_SECRET
from backend.db.database import get_connection
from backend.services.order_service import create_order
from backend.services.tenant_context import get_current_tenant_id, set_current_tenant_id


def agency_portal_login(payload: dict[str, Any]) -> dict[str, Any] | None:
    agency_id = _to_int(payload.get("agency_id"))
    portal_code = str(payload.get("portal_code") or "").strip()
    if not agency_id or not portal_code:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, tenant_id, name, contact_name, contact_phone, portal_code, is_portal_enabled
            FROM agencies
            WHERE id = ? AND portal_code = ? AND COALESCE(is_portal_enabled, 1) = 1
            """,
            (agency_id, portal_code),
        ).fetchone()
    if not row:
        return None
    agency = dict(row)
    token = create_agency_token(agency)
    return {"token": token, "agency": _public_agency(agency)}


def list_public_agencies() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, tenant_id, name, contact_name, contact_phone
            FROM agencies
            WHERE COALESCE(is_portal_enabled, 1) = 1
            ORDER BY tenant_id, name, id
            LIMIT 100
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_agency_by_token(token: str) -> dict[str, Any] | None:
    payload = verify_agency_token(token)
    if not payload:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, tenant_id, name, contact_name, contact_phone, is_portal_enabled
            FROM agencies
            WHERE id = ? AND tenant_id = ? AND COALESCE(is_portal_enabled, 1) = 1
            """,
            (payload.get("agency_id"), payload.get("tenant_id")),
        ).fetchone()
    if not row:
        return None
    agency = dict(row)
    set_current_tenant_id(agency["tenant_id"])
    return agency


def create_agency_order(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    data = {
        "order_date": payload.get("order_date"),
        "end_date": payload.get("end_date") or payload.get("order_date"),
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "pickup_location": payload.get("pickup_location"),
        "dropoff_location": payload.get("dropoff_location"),
        "order_type": payload.get("order_type") or "agency_booking",
        "vehicle_type": payload.get("vehicle_type"),
        "passenger_count": payload.get("passenger_count") or 0,
        "luggage_count": payload.get("luggage_count") or 0,
        "guest_name": payload.get("guest_name"),
        "guest_contact": payload.get("guest_contact"),
        "agency_id": agency["id"],
        "agency_name": agency["name"],
        "order_source": "agency_portal",
        "order_note_code": "A",
        "price": payload.get("price"),
        "price_jpy": payload.get("price_jpy") or payload.get("price"),
        "fee_remark": payload.get("fee_remark"),
        "remark": payload.get("remark"),
        "dispatch_status": "unassigned",
        "settlement_status": "pending",
    }
    return create_order(data)


def list_agency_orders(token: str) -> list[dict[str, Any]]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, oid, order_date, end_date, start_time, end_time,
                   pickup_location, dropoff_location, order_type, vehicle_type,
                   passenger_count, luggage_count, guest_name, guest_contact,
                   agency_name, price, price_jpy, fee_remark, remark,
                   dispatch_status, settlement_status, execution_status, created_at
            FROM orders
            WHERE tenant_id = ?
              AND agency_id = ?
              AND COALESCE(is_deleted, 0) = 0
            ORDER BY order_date DESC, start_time DESC, id DESC
            LIMIT 200
            """,
            (agency["tenant_id"], agency["id"]),
        ).fetchall()
    return [dict(row) for row in rows]


def create_agency_token(agency: dict[str, Any]) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "kind": "agency",
        "agency_id": agency["id"],
        "tenant_id": agency["tenant_id"],
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _b64_bytes(hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def verify_agency_token(token: str) -> dict[str, Any] | None:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}"
        expected = _b64_bytes(hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_part):
            return None
        payload = json.loads(_b64_decode(payload_part).decode("utf-8"))
        if payload.get("kind") != "agency":
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def _public_agency(agency: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": agency["id"],
        "tenant_id": agency["tenant_id"],
        "name": agency["name"],
        "contact_name": agency.get("contact_name"),
        "contact_phone": agency.get("contact_phone"),
    }


def _b64_json(payload: dict[str, Any]) -> str:
    return _b64_bytes(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

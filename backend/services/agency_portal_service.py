from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import time
from typing import Any
import uuid

from backend.config import JWT_EXPIRES_SECONDS, JWT_SECRET
from backend.db.database import get_connection
from backend.services.auction_service import create_auction_listings, ensure_auction_listing_schema, list_auction_listings, refresh_expired_auction_listings
from backend.services.flight_info_service import (
    FLIGHT_INFO_FIELDS,
    build_flight_update,
    ensure_flight_info_schema,
    extract_flight_number,
    query_flight_info,
)
from backend.services.order_service import create_order
from backend.services.parser_service import parse_chinese_order, split_batch_order_text
from backend.services.tenant_context import get_current_tenant_id, set_current_tenant_id

REQUEST_FIELDS = {
    "order_date",
    "end_date",
    "start_time",
    "end_time",
    "pickup_location",
    "dropoff_location",
    "order_type",
    "vehicle_type",
    "passenger_count",
    "luggage_count",
    *FLIGHT_INFO_FIELDS,
    "guest_name",
    "guest_contact",
    "price",
    "price_jpy",
    "fee_remark",
    "remark",
}

PDF_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "uploads" / "agency_itineraries"
PAYMENT_RECEIPT_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "uploads" / "agency_payment_receipts"
AGENCY_PROFILE_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "uploads" / "agency_profiles"
MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_RECEIPT_BYTES = 12 * 1024 * 1024

AGENCY_PROFILE_COLUMNS = {
    "company_address": "TEXT",
    "bank_name": "TEXT",
    "bank_branch": "TEXT",
    "bank_account_type": "TEXT",
    "bank_account_number": "TEXT",
    "bank_account_holder": "TEXT",
    "registry_pdf_url": "TEXT",
    "registry_pdf_name": "TEXT",
}

AGENCY_SETTLEMENT_COLUMNS = {
    "agency_settlement_status": "TEXT NOT NULL DEFAULT 'pending'",
    "payment_amount_jpy": "REAL",
    "carrier_payment_requested_at": "TEXT",
    "carrier_payment_request_note": "TEXT",
    "agency_payment_receipt_url": "TEXT",
    "agency_payment_receipt_name": "TEXT",
    "agency_payment_uploaded_at": "TEXT",
    "carrier_payment_confirmed_at": "TEXT",
    "carrier_payment_confirmed_by": "TEXT",
}


AGENCY_PORTAL_AUTH_COLUMNS = {
    "portal_password_hash": "TEXT",
    "portal_password_updated_at": "TEXT",
}


def ensure_agency_portal_auth_schema(conn=None) -> None:
    owns_connection = conn is None
    connection = conn or get_connection()
    try:
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(agencies)").fetchall()}
        for column, definition in AGENCY_PORTAL_AUTH_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE agencies ADD COLUMN {column} {definition}")
        rows = connection.execute(
            """
            SELECT id, portal_code
            FROM agencies
            WHERE COALESCE(portal_code, '') <> ''
              AND COALESCE(portal_password_hash, '') = ''
            """
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                UPDATE agencies
                SET portal_password_hash = ?,
                    portal_password_updated_at = COALESCE(portal_password_updated_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_hash_portal_password(row["portal_code"]), row["id"]),
            )
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def ensure_agency_profile_schema(conn=None) -> None:
    owns_connection = conn is None
    connection = conn or get_connection()
    try:
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(agencies)").fetchall()}
        for column, definition in AGENCY_PROFILE_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE agencies ADD COLUMN {column} {definition}")
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def resolve_agency_portal_account(payload: dict[str, Any]) -> dict[str, Any] | None:
    portal_code = _portal_login_code(payload)
    if not portal_code:
        return None
    with get_connection() as conn:
        ensure_agency_portal_auth_schema(conn)
        try:
            from backend.services.travel_agency_service import ensure_travel_agency_schema

            ensure_travel_agency_schema()
        except Exception:
            pass
        row = conn.execute(
            """
            SELECT id, tenant_id, name, contact_name, contact_phone, portal_code, is_portal_enabled
            FROM agencies
            WHERE UPPER(portal_code) = UPPER(?)
              AND COALESCE(is_portal_enabled, 1) = 1
            LIMIT 1
            """,
            (portal_code,),
        ).fetchone()
    return _public_agency(dict(row)) if row else None


def agency_portal_login(payload: dict[str, Any]) -> dict[str, Any] | None:
    portal_code = _portal_login_code(payload)
    password = str(payload.get("password") or "").strip()
    if not portal_code or not password:
        return None
    if re.search(r"\d", portal_code) and not re.fullmatch(r"[A-Za-z]{2,5}\d{4,}", portal_code):
        internal_result = _agency_internal_account_login(portal_code, password)
        if internal_result:
            return internal_result
    with get_connection() as conn:
        ensure_agency_portal_auth_schema(conn)
        row = conn.execute(
            """
            SELECT id, tenant_id, name, contact_name, contact_phone, portal_code, portal_password_hash, is_portal_enabled
            FROM agencies
            WHERE UPPER(portal_code) = UPPER(?)
              AND COALESCE(is_portal_enabled, 1) = 1
            LIMIT 1
            """,
            (portal_code,),
        ).fetchone()
        if row and _verify_portal_password(password, row["portal_password_hash"]):
            agency = dict(row)
            token = create_agency_token(agency)
            return {"token": token, "agency": _public_agency(agency)}

        internal = conn.execute(
            """
            SELECT
                a.id AS account_id,
                a.tenant_id,
                a.company_id,
                a.role,
                a.display_name,
                a.phone,
                a.password_seed,
                c.company_code,
                c.company_name,
                ag.id AS agency_id,
                ag.tenant_id AS agency_tenant_id,
                ag.name AS agency_name,
                ag.contact_name,
                ag.contact_phone,
                ag.portal_code,
                ag.is_portal_enabled
            FROM travel_agency_accounts a
            JOIN travel_agency_companies c
              ON c.id = a.company_id
             AND c.tenant_id = a.tenant_id
            JOIN agencies ag
              ON UPPER(ag.agency_code) = UPPER(c.company_code)
             AND COALESCE(ag.is_portal_enabled, 1) = 1
            WHERE REPLACE(REPLACE(REPLACE(COALESCE(a.phone, ''), '-', ''), ' ', ''), '+', '') =
                  REPLACE(REPLACE(REPLACE(COALESCE(?, ''), '-', ''), ' ', ''), '+', '')
              AND COALESCE(a.status, 'active') = 'active'
            LIMIT 1
            """,
            (portal_code,),
        ).fetchone()
    if not internal or str(internal["password_seed"] or "") != password:
        return None
    agency = {
        "id": internal["agency_id"],
        "tenant_id": internal["agency_tenant_id"],
        "name": internal["agency_name"],
        "contact_name": internal["contact_name"],
        "contact_phone": internal["contact_phone"],
    }
    token = create_agency_token(
        agency,
        {
            "role": internal["role"],
            "phone": internal["phone"],
            "display_name": internal["display_name"],
            "account_id": internal["account_id"],
        },
    )
    return {
        "token": token,
        "agency": _public_agency(agency),
        "account": {
            "id": internal["account_id"],
            "role": internal["role"],
            "display_name": internal["display_name"],
            "phone": internal["phone"],
            "company_id": internal["company_id"],
            "company_code": internal["company_code"],
            "company_name": internal["company_name"],
        },
    }


def _agency_internal_account_login(login_code: str, password: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        internal = conn.execute(
            """
            SELECT
                a.id AS account_id,
                a.tenant_id,
                a.company_id,
                a.role,
                a.display_name,
                a.phone,
                a.password_seed,
                c.company_code,
                c.company_name,
                ag.id AS agency_id,
                ag.tenant_id AS agency_tenant_id,
                ag.name AS agency_name,
                ag.contact_name,
                ag.contact_phone,
                ag.portal_code,
                ag.is_portal_enabled
            FROM travel_agency_accounts a
            JOIN travel_agency_companies c
              ON c.id = a.company_id
             AND c.tenant_id = a.tenant_id
            JOIN agencies ag
              ON UPPER(ag.agency_code) = UPPER(c.company_code)
             AND COALESCE(ag.is_portal_enabled, 1) = 1
            WHERE REPLACE(REPLACE(REPLACE(COALESCE(a.phone, ''), '-', ''), ' ', ''), '+', '') =
                  REPLACE(REPLACE(REPLACE(COALESCE(?, ''), '-', ''), ' ', ''), '+', '')
              AND COALESCE(a.status, 'active') = 'active'
            LIMIT 1
            """,
            (login_code,),
        ).fetchone()
    if not internal or str(internal["password_seed"] or "") != password:
        return None
    agency = {
        "id": internal["agency_id"],
        "tenant_id": internal["agency_tenant_id"],
        "name": internal["agency_name"],
        "contact_name": internal["contact_name"],
        "contact_phone": internal["contact_phone"],
    }
    token = create_agency_token(
        agency,
        {
            "role": internal["role"],
            "phone": internal["phone"],
            "display_name": internal["display_name"],
            "account_id": internal["account_id"],
        },
    )
    return {
        "token": token,
        "agency": _public_agency(agency),
        "account": {
            "id": internal["account_id"],
            "role": internal["role"],
            "display_name": internal["display_name"],
            "phone": internal["phone"],
            "company_id": internal["company_id"],
            "company_code": internal["company_code"],
            "company_name": internal["company_name"],
        },
    }


def change_agency_portal_password(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    current_password = str(payload.get("current_password") or "").strip()
    new_password = str(payload.get("new_password") or "").strip()
    if len(new_password) < 6:
        raise ValueError("password_too_short")
    with get_connection() as conn:
        ensure_agency_portal_auth_schema(conn)
        row = conn.execute(
            """
            SELECT portal_password_hash
            FROM agencies
            WHERE id = ? AND tenant_id = ?
            """,
            (agency["id"], agency["tenant_id"]),
        ).fetchone()
        if not row or not _verify_portal_password(current_password, row["portal_password_hash"]):
            raise ValueError("invalid_current_password")
        conn.execute(
            """
            UPDATE agencies
            SET portal_password_hash = ?,
                portal_password_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (_hash_portal_password(new_password), agency["id"], agency["tenant_id"]),
        )
        conn.commit()
    return {"success": True}


def list_public_agencies() -> list[dict[str, Any]]:
    with get_connection() as conn:
        ensure_agency_portal_auth_schema(conn)
        ensure_auction_listing_schema(conn)
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
    agency["account_id"] = payload.get("account_id")
    agency["account_role"] = payload.get("account_role")
    agency["account_phone"] = payload.get("account_phone")
    agency["account_display_name"] = payload.get("account_display_name")
    set_current_tenant_id(agency["tenant_id"])
    return agency


def get_agency_profile(token: str) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    with get_connection() as conn:
        ensure_agency_profile_schema(conn)
        row = conn.execute(
            """
            SELECT id,
                   tenant_id,
                   name,
                   portal_code,
                   contact_name,
                   contact_phone,
                   company_address,
                   bank_name,
                   bank_branch,
                   bank_account_type,
                   bank_account_number,
                   bank_account_holder,
                   registry_pdf_url,
                   registry_pdf_name
            FROM agencies
            WHERE id = ? AND tenant_id = ?
            """,
            (agency["id"], agency["tenant_id"]),
        ).fetchone()
    return dict(row) if row else {}


def update_agency_profile(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_agency_profile_schema()
    allowed_fields = [
        "contact_name",
        "contact_phone",
        "company_address",
        "bank_name",
        "bank_branch",
        "bank_account_type",
        "bank_account_number",
        "bank_account_holder",
    ]
    updates: dict[str, str] = {}
    for field in allowed_fields:
        if field in payload:
            updates[field] = str(payload.get(field) or "").strip()
    if updates:
        assignments = ", ".join([f"{field} = ?" for field in updates])
        values = list(updates.values())
        with get_connection() as conn:
            ensure_agency_profile_schema(conn)
            conn.execute(
                f"""
                UPDATE agencies
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                [*values, agency["id"], agency["tenant_id"]],
            )
            conn.commit()
    return get_agency_profile(token)


def upload_agency_profile_registry_pdf(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    file_name = str(payload.get("file_name") or "registry.pdf").strip()
    pdf_data = str(payload.get("file_base64") or payload.get("pdf_base64") or "").strip()
    if not file_name.lower().endswith(".pdf") or not pdf_data:
        raise ValueError("invalid_pdf_upload_request")
    raw = _decode_pdf_payload(pdf_data)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).strip("._") or "registry.pdf"
    AGENCY_PROFILE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_name = f"tenant{agency['tenant_id']}_agency{agency['id']}_registry_{uuid.uuid4().hex[:10]}_{safe_name}"
    file_path = AGENCY_PROFILE_UPLOAD_ROOT / stored_name
    file_path.write_bytes(raw)
    file_url = f"/uploads/agency_profiles/{stored_name}"
    with get_connection() as conn:
        ensure_agency_profile_schema(conn)
        conn.execute(
            """
            UPDATE agencies
            SET registry_pdf_url = ?,
                registry_pdf_name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (file_url, file_name, agency["id"], agency["tenant_id"]),
        )
        conn.commit()
    return {
        "success": True,
        "file_url": file_url,
        "file_name": file_name,
        "profile": get_agency_profile(token),
    }


def create_agency_order(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_flight_info_schema()
    data = {
        "order_date": payload.get("order_date"),
        "end_date": payload.get("end_date") or payload.get("order_date"),
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "pickup_location": payload.get("pickup_location"),
        "dropoff_location": payload.get("dropoff_location"),
        "order_type": payload.get("order_type") or "agency_booking",
        "vehicle_type": payload.get("vehicle_type"),
        "vehicle_color": payload.get("vehicle_color"),
        "passenger_count": payload.get("passenger_count") or 0,
        "luggage_count": payload.get("luggage_count") or 0,
        **{field: payload.get(field) for field in FLIGHT_INFO_FIELDS if payload.get(field) not in (None, "")},
        "guest_name": payload.get("guest_name"),
        "guest_contact": payload.get("guest_contact"),
        "guide_name": payload.get("guide_name"),
        "guide_phone": payload.get("guide_phone"),
        "guide_wechat": payload.get("guide_wechat"),
        "guide_line": payload.get("guide_line"),
        "guide_whatsapp": payload.get("guide_whatsapp"),
        "itinerary_pdf_url": payload.get("itinerary_pdf_url"),
        "itinerary_pdf_name": payload.get("itinerary_pdf_name"),
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


def update_agency_order(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    clean_order_id = _to_int(order_id)
    if not clean_order_id:
        raise ValueError("order_not_found")
    allowed_fields = {
        "order_date",
        "end_date",
        "start_time",
        "end_time",
        "pickup_location",
        "dropoff_location",
        "order_type",
        "vehicle_type",
        "passenger_count",
        "luggage_count",
        "guest_name",
        "guest_contact",
        "guide_name",
        "guide_phone",
        "guide_wechat",
        "guide_line",
        "guide_whatsapp",
        "price",
        "price_jpy",
        "fee_remark",
        "remark",
    }
    updates = {field: payload.get(field) for field in allowed_fields if field in payload}
    if "end_date" not in updates and "order_date" in updates:
        updates["end_date"] = updates["order_date"]
    if "price" in updates and "price_jpy" not in updates:
        updates["price_jpy"] = updates["price"]
    if not updates:
        raise ValueError("no_update_fields")
    with get_connection() as conn:
        row = _agency_order(conn, agency["tenant_id"], agency["id"], clean_order_id)
        if not row:
            raise ValueError("order_not_found")
        order = dict(row)
        status = order.get("auction_status") or order.get("dispatch_status") or ""
        if status and status != "unassigned":
            raise ValueError("agency_order_locked")
        assignments = ", ".join(f"{field} = ?" for field in updates)
        conn.execute(
            f"""
            UPDATE orders
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND tenant_id = ?
              AND agency_id = ?
            """,
            [*updates.values(), clean_order_id, agency["tenant_id"], agency["id"]],
        )
        conn.commit()
        updated = _agency_order(conn, agency["tenant_id"], agency["id"], clean_order_id)
        return dict(updated)


def parse_agency_order_text(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    text = str(payload.get("text") or payload.get("raw_text") or "").strip()
    if not text:
        raise ValueError("missing_parse_text")
    mode = str(payload.get("mode") or payload.get("order_type") or "").strip()
    batch = bool(payload.get("batch")) or mode in {"airport_batch", "batch_airport", "charter_batch", "batch_charter"}
    chunks = split_batch_order_text(text) if batch else [text]
    parsed_orders = [_agency_parsed_order(chunk, mode) for chunk in chunks if str(chunk).strip()]
    return {"orders": parsed_orders, "count": len(parsed_orders), "mode": mode or ("airport_batch" if batch else "charter")}


def query_agency_flight_info(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    return query_flight_info(payload)


def update_agency_order_flight_info(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    ensure_flight_info_schema()
    with get_connection() as conn:
        order = _agency_order(conn, agency["tenant_id"], agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
        data = build_flight_update(payload, dict(order))
        if not data:
            raise ValueError("missing_flight_info")
        assignments = ", ".join(f"{field} = ?" for field in data)
        conn.execute(
            f"""
            UPDATE orders
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND agency_id = ? AND id = ?
            """,
            [*data.values(), agency["tenant_id"], agency["id"], order_id_int],
        )
        conn.commit()
        updated = _agency_order(conn, agency["tenant_id"], agency["id"], order_id_int)
    if not updated:
        raise ValueError("order_not_found")
    return {"success": True, "order": dict(updated), "flight": {field: dict(updated).get(field) for field in FLIGHT_INFO_FIELDS}}


def list_agency_orders(token: str) -> list[dict[str, Any]]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_agency_request_schema()
    ensure_agency_settlement_schema()
    ensure_flight_info_schema()
    refresh_expired_auction_listings()
    tenant_id = agency["tenant_id"]
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.id, o.oid, o.order_date, o.end_date, o.start_time, o.end_time,
                   o.pickup_location, o.dropoff_location, o.order_type, o.vehicle_type,
                   o.vehicle_color,
                   o.passenger_count, o.luggage_count, o.guest_name, o.guest_contact,
                   o.flight_number, o.flight_date, o.flight_airline, o.flight_origin, o.flight_destination,
                   o.flight_terminal, o.flight_gate, o.flight_status,
                   o.flight_scheduled_departure, o.flight_scheduled_arrival,
                   o.flight_estimated_departure, o.flight_estimated_arrival,
                   o.flight_actual_departure, o.flight_actual_arrival,
                   o.flight_provider, o.flight_last_checked_at, o.flight_manual_note,
                   o.guide_name, o.guide_phone, o.guide_wechat, o.guide_line, o.guide_whatsapp,
                   o.itinerary_pdf_url, o.itinerary_pdf_name,
                   o.agency_name, o.price, o.price_jpy, o.fee_remark, o.remark,
                   o.dispatch_status, o.settlement_status, o.execution_status,
                   o.agency_settlement_status, o.payment_amount_jpy,
                   o.carrier_payment_requested_at, o.carrier_payment_request_note,
                   o.agency_payment_receipt_url, o.agency_payment_receipt_name, o.agency_payment_uploaded_at,
                   o.carrier_payment_confirmed_at, o.carrier_payment_confirmed_by,
                   o.created_at,
                   a.id AS assignment_id,
                   a.driver_id,
                   a.vehicle_id,
                   a.status AS assignment_status,
                   a.assigned_at,
                   d.name AS driver_name,
                   d.phone AS driver_phone,
                   d.driver_code AS assigned_driver_code,
                   d.driver_language AS assigned_driver_language,
                   v.plate_number,
                   v.plate_no,
                   v.vehicle_type AS assigned_vehicle_type,
                   v.seat_count,
                   v.vehicle_color AS assigned_vehicle_color,
                   COALESCE(alll.latitude, dll.latitude) AS driver_latitude,
                   COALESCE(alll.longitude, dll.longitude) AS driver_longitude,
                   COALESCE(alll.location_text, dll.location_text) AS driver_location_text,
                   COALESCE(alll.reported_at, dll.reported_at) AS driver_location_reported_at,
                   req.id AS latest_change_request_id,
                   req.request_type AS latest_change_request_type,
                   req.status AS latest_change_request_status,
                   req.fee_percent AS latest_cancel_fee_percent,
                   req.fee_amount_jpy AS latest_cancel_fee_amount_jpy,
                   req.policy_message AS latest_change_request_policy,
                   auc.id AS auction_listing_id,
                   auc.listing_code AS auction_listing_code,
                   auc.publish_round AS auction_publish_round,
                   auc.status AS auction_status,
                   auc.start_price_jpy AS auction_start_price_jpy,
                   auc.buyout_price_jpy AS auction_buyout_price_jpy,
                   auc.current_bid_jpy AS auction_current_bid_jpy,
                   auc.bid_count AS auction_bid_count,
                   auc.published_at AS auction_published_at,
                   auc.expires_at AS auction_expires_at,
                   auc.buyer_tenant_id AS carrier_tenant_id,
                   auc.sold_at AS carrier_claimed_at,
                   auc.carrier_claim_serial AS carrier_claim_serial,
                   buyer.name AS carrier_company_name,
                   buyer.slug AS carrier_company_code,
                   CASE WHEN auc.expires_at IS NOT NULL THEN CAST(ROUND((julianday(auc.expires_at) - julianday(auc.published_at)) * 24) AS INTEGER) END AS auction_duration_hours
            FROM orders o
            LEFT JOIN (
                SELECT *
                FROM (
                    SELECT a.*,
                           ROW_NUMBER() OVER (PARTITION BY a.order_id ORDER BY a.assigned_at DESC, a.id DESC) AS rn
                    FROM assignments a
                    WHERE a.tenant_id = ? AND a.status = 'active'
                )
                WHERE rn = 1
            ) a ON a.order_id = o.id
            LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = o.tenant_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = o.tenant_id
            LEFT JOIN (
                SELECT *
                FROM (
                    SELECT ll.*,
                           ROW_NUMBER() OVER (PARTITION BY ll.assignment_id ORDER BY ll.reported_at DESC, ll.id DESC) AS rn
                    FROM location_logs ll
                    WHERE ll.tenant_id = ? AND ll.assignment_id IS NOT NULL
                )
                WHERE rn = 1
            ) alll ON alll.assignment_id = a.id
            LEFT JOIN (
                SELECT *
                FROM (
                    SELECT ll.*,
                           ROW_NUMBER() OVER (PARTITION BY ll.driver_id ORDER BY ll.reported_at DESC, ll.id DESC) AS rn
                    FROM location_logs ll
                    WHERE ll.tenant_id = ?
                )
                WHERE rn = 1
            ) dll ON dll.driver_id = a.driver_id
            LEFT JOIN (
                SELECT *
                FROM (
                    SELECT r.*,
                           ROW_NUMBER() OVER (PARTITION BY r.order_id ORDER BY r.created_at DESC, r.id DESC) AS rn
                    FROM agency_order_change_requests r
                    WHERE r.tenant_id = ?
                )
                WHERE rn = 1
            ) req ON req.order_id = o.id
            LEFT JOIN (
                SELECT *
                FROM (
                    SELECT l.*,
                           ROW_NUMBER() OVER (PARTITION BY l.order_id ORDER BY l.published_at DESC, l.id DESC) AS rn,
                           ROW_NUMBER() OVER (
                               PARTITION BY l.buyer_tenant_id, DATE(COALESCE(l.sold_at, l.updated_at, l.published_at))
                               ORDER BY COALESCE(l.sold_at, l.updated_at, l.published_at), l.id
                           ) AS carrier_claim_serial
                    FROM auction_listings l
                    WHERE l.seller_tenant_id = ?
                )
                WHERE rn = 1
            ) auc ON auc.order_id = o.id
            LEFT JOIN tenants buyer ON buyer.id = auc.buyer_tenant_id
            WHERE o.tenant_id = ?
              AND o.agency_id = ?
              AND COALESCE(o.is_deleted, 0) = 0
            ORDER BY o.order_date DESC, o.start_time DESC, o.id DESC
            LIMIT 200
            """,
            (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, agency["id"]),
        ).fetchall()
    result = [dict(row) for row in rows]
    if _is_guide_account(agency):
        result = [row for row in result if _order_matches_guide_account(row, agency)]
    return result


def _is_guide_account(agency: dict[str, Any]) -> bool:
    role = str(agency.get("account_role") or "").lower()
    return "guide" in role or "导游" in role


def _order_matches_guide_account(order: dict[str, Any], agency: dict[str, Any]) -> bool:
    phone = re.sub(r"\D+", "", str(agency.get("account_phone") or ""))
    guide_phone = re.sub(r"\D+", "", str(order.get("guide_phone") or order.get("guide_whatsapp") or ""))
    if phone and guide_phone and phone[-8:] in guide_phone:
        return True
    display_name = str(agency.get("account_display_name") or "").strip().lower()
    guide_name = str(order.get("guide_name") or "").strip().lower()
    if display_name and guide_name and (display_name in guide_name or guide_name in display_name):
        return True
    return False


def withdraw_agency_order_from_hall(token: str, order_id: Any) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_agency_request_schema()
    tenant_id = agency["tenant_id"]
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        order = _agency_order(conn, tenant_id, agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
        listing = conn.execute(
            """
            SELECT *
            FROM auction_listings
            WHERE order_id = ?
              AND seller_tenant_id = ?
              AND status IN ('listed', 'bidding', 'claimed')
            ORDER BY id DESC
            LIMIT 1
            """,
            (order_id_int, tenant_id),
        ).fetchone()
        if listing and listing["status"] in ("listed", "bidding") and not listing["buyer_tenant_id"]:
            conn.execute(
                """
                UPDATE auction_listings
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (listing["id"],),
            )
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'auction_cancelled',
                    execution_status = 'unassigned',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (order_id_int, tenant_id),
            )
            conn.commit()
            return {"success": True, "mode": "direct_withdraw", "order_id": order_id_int, "listing_id": listing["id"]}
        if order["dispatch_status"] in ("unassigned", "auction_cancelled"):
            return {"success": True, "mode": "nothing_to_withdraw", "order_id": order_id_int}
    raise ValueError("order_already_claimed_requires_carrier_confirmation")


def list_agency_auction_hall(token: str, status: str | None = "listed") -> list[dict[str, Any]]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    return list_auction_listings(status or "listed")


def publish_agency_order_to_hall(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    with get_connection() as conn:
        order = _agency_order(conn, agency["tenant_id"], agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
    result = create_auction_listings(
        {
            "order_ids": [order_id_int],
            "start_price_jpy": payload.get("start_price_jpy") or payload.get("start_price"),
            "buyout_price_jpy": payload.get("buyout_price_jpy") or payload.get("buyout_price"),
            "auction_duration_hours": payload.get("auction_duration_hours"),
            "note": payload.get("note"),
        },
        {"id": None, "username": f"agency:{agency['name']}", "tenant_id": agency["tenant_id"]},
    )
    return result


def upload_agency_order_itinerary_pdf(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    file_name = str(payload.get("file_name") or "itinerary.pdf").strip()
    pdf_data = str(payload.get("file_base64") or payload.get("pdf_base64") or "").strip()
    if not file_name.lower().endswith(".pdf") or not pdf_data:
        raise ValueError("invalid_pdf_upload_request")
    raw = _decode_pdf_payload(pdf_data)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).strip("._") or "itinerary.pdf"
    PDF_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_name = f"tenant{agency['tenant_id']}_agency{agency['id']}_order{order_id_int}_{uuid.uuid4().hex[:10]}_{safe_name}"
    file_path = PDF_UPLOAD_ROOT / stored_name
    file_path.write_bytes(raw)
    file_url = f"/uploads/agency_itineraries/{stored_name}"
    with get_connection() as conn:
        order = _agency_order(conn, agency["tenant_id"], agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
        conn.execute(
            """
            UPDATE orders
            SET itinerary_pdf_url = ?,
                itinerary_pdf_name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND agency_id = ? AND id = ?
            """,
            (file_url, file_name, agency["tenant_id"], agency["id"], order_id_int),
        )
        conn.commit()
    return {"success": True, "order_id": order_id_int, "file_url": file_url, "file_name": file_name}


def request_carrier_payment(order_id: Any, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_agency_settlement_schema()
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    actor_name = (actor or {}).get("username") or (actor or {}).get("name") or "carrier"
    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
              AND COALESCE(is_deleted, 0) = 0
            """,
            (order_id_int,),
        ).fetchone()
        if not order:
            raise ValueError("order_not_found")
        if not _actor_can_settle_order(conn, dict(order), actor):
            raise ValueError("order_settlement_forbidden")
        amount = _money(payload.get("amount_jpy") or payload.get("payment_amount_jpy") or order["price_jpy"] or order["price"])
        if amount <= 0:
            raise ValueError("missing_payment_amount")
        conn.execute(
            """
            UPDATE orders
            SET payment_amount_jpy = ?,
                carrier_payment_requested_at = CURRENT_TIMESTAMP,
                carrier_payment_request_note = ?,
                agency_settlement_status = 'payment_requested',
                settlement_status = 'payment_requested',
                execution_status = CASE
                    WHEN execution_status IN ('completed', 'returned') THEN execution_status
                    ELSE 'completed'
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (amount, payload.get("note") or payload.get("carrier_note") or f"付款请求：{actor_name}", order_id_int),
        )
        conn.commit()
    return get_agency_settlement_order(order_id_int) or {"id": order_id_int}


def upload_agency_payment_receipt(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_agency_settlement_schema()
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    file_name = str(payload.get("file_name") or "payment-receipt").strip()
    file_data = str(payload.get("file_base64") or payload.get("receipt_base64") or "").strip()
    if not file_data:
        raise ValueError("missing_receipt_file")
    raw = _decode_receipt_payload(file_data)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).strip("._") or "payment-receipt"
    PAYMENT_RECEIPT_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_name = f"tenant{agency['tenant_id']}_agency{agency['id']}_order{order_id_int}_{uuid.uuid4().hex[:10]}_{safe_name}"
    file_path = PAYMENT_RECEIPT_UPLOAD_ROOT / stored_name
    file_path.write_bytes(raw)
    file_url = f"/uploads/agency_payment_receipts/{stored_name}"
    with get_connection() as conn:
        order = _agency_order(conn, agency["tenant_id"], agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
        if order["settlement_status"] not in ("payment_requested", "receipt_uploaded", "pending", "unsettled"):
            raise ValueError("payment_receipt_not_allowed_for_status")
        conn.execute(
            """
            UPDATE orders
            SET agency_payment_receipt_url = ?,
                agency_payment_receipt_name = ?,
                agency_payment_uploaded_at = CURRENT_TIMESTAMP,
                agency_settlement_status = 'receipt_uploaded',
                settlement_status = 'receipt_uploaded',
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND agency_id = ? AND id = ?
            """,
            (file_url, file_name, agency["tenant_id"], agency["id"], order_id_int),
        )
        conn.commit()
    return {"success": True, "order_id": order_id_int, "file_url": file_url, "file_name": file_name}


def confirm_carrier_payment(order_id: Any, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_agency_settlement_schema()
    order_id_int = _to_int(order_id)
    if not order_id_int:
        raise ValueError("missing_order_id")
    reviewer = (actor or {}).get("username") or (actor or {}).get("name") or "carrier"
    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
              AND COALESCE(is_deleted, 0) = 0
            """,
            (order_id_int,),
        ).fetchone()
        if not order:
            raise ValueError("order_not_found")
        if not _actor_can_settle_order(conn, dict(order), actor):
            raise ValueError("order_settlement_forbidden")
        if order["settlement_status"] not in ("receipt_uploaded", "payment_requested", "pending", "unsettled"):
            raise ValueError("payment_confirm_not_allowed_for_status")
        conn.execute(
            """
            UPDATE orders
            SET agency_settlement_status = 'paid',
                settlement_status = 'paid',
                execution_status = 'completed',
                carrier_payment_confirmed_at = CURRENT_TIMESTAMP,
                carrier_payment_confirmed_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.get("confirmed_by") or reviewer, order_id_int),
        )
        conn.execute(
            """
            UPDATE auction_listings
            SET status = CASE WHEN status = 'claimed' THEN 'sold' ELSE status END,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND status IN ('claimed', 'sold')
            """,
            (order_id_int,),
        )
        conn.commit()
    return get_agency_settlement_order(order_id_int) or {"id": order_id_int}


def submit_agency_order_change_request(token: str, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    ensure_agency_request_schema()
    tenant_id = agency["tenant_id"]
    order_id_int = _to_int(order_id)
    request_type = str(payload.get("request_type") or "modify").strip()
    if request_type not in {"modify", "cancel"}:
        raise ValueError("invalid_request_type")
    with get_connection() as conn:
        order = _agency_order(conn, tenant_id, agency["id"], order_id_int)
        if not order:
            raise ValueError("order_not_found")
        existing = conn.execute(
            """
            SELECT id
            FROM agency_order_change_requests
            WHERE tenant_id = ? AND order_id = ? AND status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            (tenant_id, order_id_int),
        ).fetchone()
        if existing:
            raise ValueError("change_request_already_pending")
        changes = _requested_changes(payload.get("changes") or payload)
        if request_type == "modify" and not changes:
            raise ValueError("missing_change_fields")
        policy = _cancel_policy(conn, tenant_id, dict(order), force=bool(payload.get("force"))) if request_type == "cancel" else {}
        cursor = conn.execute(
            """
            INSERT INTO agency_order_change_requests (
                tenant_id, agency_id, order_id, request_type, status,
                requested_changes_json, reason, force_cancel,
                fee_percent, fee_amount_jpy, free_quota_used, policy_message, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                agency["id"],
                order_id_int,
                request_type,
                json.dumps(changes, ensure_ascii=False, separators=(",", ":")),
                payload.get("reason") or "",
                1 if payload.get("force") else 0,
                policy.get("fee_percent", 0),
                policy.get("fee_amount_jpy", 0),
                policy.get("free_quota_used", 0),
                policy.get("policy_message", "等待车公司确认"),
            ),
        )
        conn.commit()
    return get_agency_change_request(cursor.lastrowid) or {}


def list_agency_change_requests(token: str) -> list[dict[str, Any]]:
    agency = get_agency_by_token(token)
    if not agency:
        raise ValueError("agency_unauthorized")
    return list_carrier_change_requests({"agency_id": agency["id"]})


def list_carrier_change_requests(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_agency_request_schema()
    params = params or {}
    tenant_id = get_current_tenant_id()
    sql = [
        """
        SELECT r.*,
               o.oid, o.order_date, o.start_time, o.end_time,
               o.pickup_location, o.dropoff_location, o.vehicle_type, o.price, o.price_jpy,
               o.dispatch_status, o.execution_status,
               ag.name AS agency_name
        FROM agency_order_change_requests r
        JOIN orders o ON o.id = r.order_id AND o.tenant_id = r.tenant_id
        LEFT JOIN agencies ag ON ag.id = r.agency_id AND ag.tenant_id = r.tenant_id
        WHERE r.tenant_id = ?
        """
    ]
    values: list[Any] = [tenant_id]
    if params.get("status"):
        sql.append("AND r.status = ?")
        values.append(params["status"])
    if params.get("agency_id"):
        sql.append("AND r.agency_id = ?")
        values.append(_to_int(params["agency_id"]))
    sql.append("ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.id DESC LIMIT 200")
    with get_connection() as conn:
        return [_decode_request(dict(row)) for row in conn.execute(" ".join(sql), values).fetchall()]


def review_agency_change_request(request_id: Any, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_agency_request_schema()
    tenant_id = get_current_tenant_id()
    request_id_int = _to_int(request_id)
    decision = str(payload.get("decision") or payload.get("status") or "").strip()
    if decision not in {"approved", "rejected"}:
        raise ValueError("invalid_decision")
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, o.price, o.price_jpy, o.order_date, o.start_time
            FROM agency_order_change_requests r
            JOIN orders o ON o.id = r.order_id AND o.tenant_id = r.tenant_id
            WHERE r.tenant_id = ? AND r.id = ?
            """,
            (tenant_id, request_id_int),
        ).fetchone()
        if not row:
            raise ValueError("change_request_not_found")
        if row["status"] != "pending":
            raise ValueError("change_request_not_pending")
        reviewer = (actor or {}).get("display_name") or (actor or {}).get("username") or (actor or {}).get("name") or "carrier"
        if decision == "rejected":
            conn.execute(
                """
                UPDATE agency_order_change_requests
                SET status = 'rejected', carrier_note = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (payload.get("carrier_note") or payload.get("note") or "", reviewer, request_id_int, tenant_id),
            )
            conn.commit()
            return get_agency_change_request(request_id_int) or {}
        if row["request_type"] == "modify":
            changes = _requested_changes(json.loads(row["requested_changes_json"] or "{}"))
            if changes:
                assignments = ", ".join(f"{key} = ?" for key in changes)
                conn.execute(
                    f"UPDATE orders SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?",
                    [*changes.values(), row["order_id"], tenant_id],
                )
        elif row["request_type"] == "cancel":
            policy = _cancel_policy(conn, tenant_id, dict(row), force=bool(row["force_cancel"]))
            conn.execute(
                """
                UPDATE auction_listings
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ? AND seller_tenant_id = ? AND status IN ('listed', 'bidding', 'claimed')
                """,
                (row["order_id"], tenant_id),
            )
            conn.execute(
                """
                UPDATE assignments
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ? AND tenant_id = ? AND status = 'active'
                """,
                (row["order_id"], tenant_id),
            )
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'agency_cancelled',
                    execution_status = 'cancelled',
                    settlement_status = CASE WHEN ? > 0 THEN 'pending' ELSE settlement_status END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (policy.get("fee_percent", 0), row["order_id"], tenant_id),
            )
            conn.execute(
                """
                UPDATE agency_order_change_requests
                SET fee_percent = ?, fee_amount_jpy = ?, free_quota_used = ?, policy_message = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    policy.get("fee_percent", 0),
                    policy.get("fee_amount_jpy", 0),
                    policy.get("free_quota_used", 0),
                    policy.get("policy_message", ""),
                    request_id_int,
                    tenant_id,
                ),
            )
        conn.execute(
            """
            UPDATE agency_order_change_requests
            SET status = 'approved', carrier_note = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (payload.get("carrier_note") or payload.get("note") or "", reviewer, request_id_int, tenant_id),
        )
        conn.commit()
    return get_agency_change_request(request_id_int) or {}


def get_agency_change_request(request_id: Any) -> dict[str, Any] | None:
    ensure_agency_request_schema()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*,
                   o.oid, o.order_date, o.start_time, o.end_time,
                   o.pickup_location, o.dropoff_location, o.vehicle_type, o.price, o.price_jpy,
                   o.dispatch_status, o.execution_status,
                   ag.name AS agency_name
            FROM agency_order_change_requests r
            JOIN orders o ON o.id = r.order_id AND o.tenant_id = r.tenant_id
            LEFT JOIN agencies ag ON ag.id = r.agency_id AND ag.tenant_id = r.tenant_id
            WHERE r.id = ?
            """,
            (_to_int(request_id),),
        ).fetchone()
    return _decode_request(dict(row)) if row else None


def ensure_agency_request_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agency_order_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                agency_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                request_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_changes_json TEXT NOT NULL DEFAULT '{}',
                reason TEXT,
                force_cancel INTEGER NOT NULL DEFAULT 0,
                fee_percent REAL NOT NULL DEFAULT 0,
                fee_amount_jpy REAL NOT NULL DEFAULT 0,
                free_quota_used INTEGER NOT NULL DEFAULT 0,
                policy_message TEXT,
                carrier_note TEXT,
                reviewed_by TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agency_id) REFERENCES agencies(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
            """
        )
        conn.commit()


def ensure_agency_settlement_schema() -> None:
    with get_connection() as conn:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
        for column, definition in AGENCY_SETTLEMENT_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")
        conn.commit()


def get_agency_settlement_order(order_id: Any) -> dict[str, Any] | None:
    ensure_agency_settlement_schema()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, oid, tenant_id, agency_id, agency_name, order_date, start_time, end_time,
                   pickup_location, dropoff_location, order_type, vehicle_type,
                   price, price_jpy, dispatch_status, execution_status, settlement_status,
                   agency_settlement_status, payment_amount_jpy,
                   carrier_payment_requested_at, carrier_payment_request_note,
                   agency_payment_receipt_url, agency_payment_receipt_name, agency_payment_uploaded_at,
                   carrier_payment_confirmed_at, carrier_payment_confirmed_by
            FROM orders
            WHERE id = ?
            """,
            (_to_int(order_id),),
        ).fetchone()
    return dict(row) if row else None


def create_agency_token(agency: dict[str, Any], account: dict[str, Any] | None = None) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "kind": "agency",
        "agency_id": agency["id"],
        "tenant_id": agency["tenant_id"],
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    if account:
        payload.update(
            {
                "account_id": account.get("account_id") or account.get("id"),
                "account_role": account.get("role"),
                "account_phone": account.get("phone"),
                "account_display_name": account.get("display_name"),
            }
        )
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


def _portal_login_code(payload: dict[str, Any]) -> str:
    return str(payload.get("portal_code") or payload.get("login_code") or payload.get("account") or "").strip()


def _hash_portal_password(password: Any) -> str:
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def _verify_portal_password(password: str, password_hash: Any) -> bool:
    expected = str(password_hash or "")
    if not expected:
        return False
    return hmac.compare_digest(_hash_portal_password(password), expected)


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


def _agency_order(conn, tenant_id: int, agency_id: int, order_id: int):
    return conn.execute(
        """
        SELECT *
        FROM orders
        WHERE tenant_id = ?
          AND agency_id = ?
          AND id = ?
          AND COALESCE(is_deleted, 0) = 0
        """,
        (tenant_id, agency_id, order_id),
    ).fetchone()


def _actor_can_settle_order(conn, order: dict[str, Any], actor: dict[str, Any] | None) -> bool:
    actor_tenant_id = _to_int((actor or {}).get("tenant_id")) or get_current_tenant_id()
    listing = conn.execute(
        """
        SELECT seller_tenant_id, buyer_tenant_id
        FROM auction_listings
        WHERE order_id = ?
          AND status IN ('claimed', 'sold')
        ORDER BY id DESC
        LIMIT 1
        """,
        (order.get("id"),),
    ).fetchone()
    if listing:
        allowed = {_to_int(listing["seller_tenant_id"]), _to_int(listing["buyer_tenant_id"])}
        return actor_tenant_id in allowed
    return actor_tenant_id == _to_int(order.get("tenant_id"))


def _requested_changes(payload: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key in REQUEST_FIELDS:
        if key in payload:
            changes[key] = payload.get(key)
    if "price" in changes and "price_jpy" not in changes:
        changes["price_jpy"] = changes["price"]
    return changes


def _decode_request(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["requested_changes"] = json.loads(row.get("requested_changes_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        row["requested_changes"] = {}
    return row


def _cancel_policy(conn, tenant_id: int, order: dict[str, Any], force: bool = False) -> dict[str, Any]:
    price = float(order.get("price_jpy") or order.get("price") or 0)
    hours = _hours_until_start(order.get("order_date"), order.get("start_time"))
    month = str(order.get("order_date") or "")[:7]
    free_used = 0
    if month:
        free_used = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM agency_order_change_requests r
            JOIN orders o ON o.id = r.order_id AND o.tenant_id = r.tenant_id
            WHERE r.tenant_id = ?
              AND r.request_type = 'cancel'
              AND r.status = 'approved'
              AND r.fee_percent = 0
              AND substr(o.order_date, 1, 7) = ?
            """,
            (tenant_id, month),
        ).fetchone()["count"]
    if hours is not None and hours > 24 and free_used < 10 and not force:
        return {
            "fee_percent": 0,
            "fee_amount_jpy": 0,
            "free_quota_used": 1,
            "policy_message": f"距开始时间超过24小时，且本月免费撤销已用{free_used}/10单；车公司确认后免费撤销。",
        }
    if hours is not None and hours <= 6:
        return {
            "fee_percent": 100,
            "fee_amount_jpy": price,
            "free_quota_used": 0,
            "policy_message": "距开始时间不足或等于6小时，未获确认强制取消按全额费用处理。",
        }
    return {
        "fee_percent": 50,
        "fee_amount_jpy": round(price * 0.5, 2),
        "free_quota_used": 0,
        "policy_message": "不满足免费撤销条件；强制取消或短时取消按50%费用处理，仍需车公司确认。",
    }


def _hours_until_start(order_date: Any, start_time: Any) -> float | None:
    if not order_date:
        return None
    start_text = str(start_time or "00:00")[:5]
    try:
        start_at = datetime.strptime(f"{str(order_date)[:10]} {start_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return (start_at - datetime.now()).total_seconds() / 3600


def _decode_pdf_payload(pdf_data: str) -> bytes:
    match = re.match(r"^data:application/pdf;base64,(.+)$", pdf_data, re.IGNORECASE | re.DOTALL)
    data = match.group(1) if match else pdf_data
    try:
        raw = base64.b64decode(data, validate=True)
    except Exception as exc:
        raise ValueError("invalid_pdf_base64") from exc
    if not raw.startswith(b"%PDF"):
        raise ValueError("invalid_pdf_file")
    if len(raw) > MAX_PDF_BYTES:
        raise ValueError("pdf_too_large")
    return raw


def _decode_receipt_payload(file_data: str) -> bytes:
    match = re.match(r"^data:[^;]+;base64,(.+)$", file_data, re.IGNORECASE | re.DOTALL)
    data = match.group(1) if match else file_data
    try:
        raw = base64.b64decode(data, validate=True)
    except Exception as exc:
        raise ValueError("invalid_receipt_base64") from exc
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt_too_large")
    if len(raw) < 8:
        raise ValueError("invalid_receipt_file")
    return raw


def _money(value: Any) -> float:
    if value is None or value == "":
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _agency_parsed_order(text: str, mode: str = "") -> dict[str, Any]:
    parsed = parse_chinese_order(text)
    order_type = _agency_order_type(parsed.get("order_type"), text, mode)
    flight_number = _extract_strict_flight_number(text) if order_type in {"接机", "送机", "airport_transfer"} else ""
    result = {
        "order_date": parsed.get("order_date"),
        "end_date": parsed.get("end_date") or parsed.get("order_date"),
        "start_time": parsed.get("start_time"),
        "end_time": parsed.get("end_time"),
        "pickup_location": parsed.get("pickup_location"),
        "dropoff_location": parsed.get("dropoff_location"),
        "order_type": order_type,
        "vehicle_type": parsed.get("vehicle_type"),
        "passenger_count": parsed.get("passenger_count") or 0,
        "luggage_count": parsed.get("luggage_count") or 0,
        "flight_number": flight_number,
        "guest_name": parsed.get("guest_name"),
        "guest_contact": parsed.get("guest_contact"),
        "price": parsed.get("price"),
        "price_jpy": parsed.get("price_jpy") or parsed.get("price"),
        "fee_remark": parsed.get("fee_remark"),
        "remark": _merge_text(parsed.get("remark"), f"原始解析文本：{text}"),
    }
    if order_type in {"包车", "charter"}:
        result.update(_extract_charter_fields(text))
    result.update(_extract_structured_agency_fields(text, order_type))
    result.update(_extract_guide_fields(text))
    if result.get("flight_number") and result.get("order_date"):
        result["flight_date"] = result.get("order_date")
    result["remark"] = _merge_text(result.get("remark"), f"原始解析文本：{text}")
    return {key: value for key, value in result.items() if value not in (None, "")}


def _agency_order_type(parsed_type: Any, text: str, mode: str) -> str:
    mode_text = mode.lower()
    raw = f"{parsed_type or ''} {text}".lower()
    if any(token in raw for token in ["接机", "接機", "arrival", "pickup"]):
        return "接机"
    if any(token in raw for token in ["送机", "送機", "单送", "單送", "departure", "dropoff"]):
        return "送机"
    if "airport" in mode_text or "airport" in raw or any(token in raw for token in ["机场", "空港", "接机", "送机", "haneda", "narita", "kansai"]):
        return "接机"
    if "charter" in mode_text or "包车" in raw or "往返" in raw:
        return "包车"
    return str(parsed_type or "包车")


def _extract_structured_agency_fields(text: str, order_type: str = "") -> dict[str, Any]:
    normalized = _normalize_full_width(text.replace("\r\n", "\n").replace("\r", "\n"))
    line = " ".join(part.strip() for part in normalized.splitlines() if part.strip())
    fields: dict[str, Any] = {}

    date_match = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2})", line)
    if date_match:
        fields["order_date"] = _normalize_agency_date(date_match.group(1))
        fields["end_date"] = fields["order_date"]

    time_range = re.search(r"(\d{1,2}:\d{2})\s*[-~到至]\s*(\d{1,2}:\d{2})", line)
    if time_range:
        fields["start_time"] = time_range.group(1)
        fields["end_time"] = time_range.group(2)
    else:
        time_match = re.search(r"(\d{1,2}:\d{2})", line)
        if time_match:
            fields["start_time"] = time_match.group(1)

    compact_transfer = _extract_compact_airport_transfer(line, order_type)
    if compact_transfer:
        fields.update(compact_transfer)

    hotel = _structured_label_value(normalized, ["酒店", "hotel"])
    itinerary = _structured_label_value(normalized, ["行程", "路线", "route", "itinerary"])
    if hotel:
        fields["pickup_location"] = hotel
    if itinerary:
        stops = _split_route_stops(itinerary)
        if stops:
            fields["dropoff_location"] = stops[-1]
            if not hotel:
                fields["pickup_location"] = stops[0]
            fields["remark"] = f"完整路线：{' -> '.join(stops)}"
    elif "->" in line:
        route_source = _route_segment_from_line(line)
        stops = _split_route_stops(route_source)
        if len(stops) >= 2:
            fields["pickup_location"] = stops[0]
            fields["dropoff_location"] = stops[-1]

    vehicle_text = _structured_label_value(normalized, ["车型", "车辆", "车种", "vehicle", "car"])
    vehicle_source = vehicle_text or line
    vehicle = _extract_vehicle_type(vehicle_source)
    if vehicle:
        fields["vehicle_type"] = vehicle

    passenger = re.search(r"(\d+)\s*(?:人|名|pax|PAX)", vehicle_source)
    if not passenger:
        passenger = re.search(r"(\d+)\s*(?:人|名|pax|PAX)", line)
    if passenger:
        fields["passenger_count"] = int(passenger.group(1))

    luggage = re.search(r"(\d+)\s*(?:件|个行李|行李|bags?|BAGS?)", vehicle_source)
    if not luggage:
        luggage = re.search(r"(\d+)\s*(?:件|个行李|行李|bags?|BAGS?)", line)
    if luggage:
        fields["luggage_count"] = int(luggage.group(1))

    guest_text = _structured_label_value(normalized, ["客人", "游客", "guest", "customer"])
    if not guest_text:
        guest_match = re.search(r"(?:客人|游客|guest|customer)\s*[:：]?\s*(.+)", line, re.IGNORECASE)
        if guest_match:
            guest_text = re.split(r"\s+\d{4,7}\s*$", guest_match.group(1).strip(), maxsplit=1)[0].strip()
    if guest_text:
        name, phone = _split_name_phone(guest_text)
        if name:
            fields["guest_name"] = name
        if phone:
            fields["guest_contact"] = phone

    price_text = _structured_label_value(normalized, ["报价", "价格", "费用", "price"])
    price_source = price_text or line
    price = _extract_agency_price(price_source)
    if price:
        fields["price"] = price
        fields["price_jpy"] = price

    if order_type in {"接机", "送机", "airport_transfer"}:
        flight_number = _extract_strict_flight_number(normalized)
        if flight_number:
            fields["flight_number"] = flight_number
            if fields.get("order_date"):
                fields["flight_date"] = fields["order_date"]
    return {key: value for key, value in fields.items() if value not in (None, "", 0)}


_AIRPORT_ALIASES = [
    ("关西机场", ["关西机场", "关西空港", "関西空港", "関西国際空港", "关西", "関空", "KIX", "Kansai International Airport"]),
    ("神户机场", ["神户机场", "神戸空港", "神户空港", "UKB"]),
    ("伊丹机场", ["伊丹机场", "伊丹空港", "大阪机场", "ITM"]),
    ("羽田机场", ["羽田机场", "羽田空港", "HND"]),
    ("成田机场", ["成田机场", "成田空港", "NRT"]),
]


def _compact_route_segment(line: str) -> str:
    source = re.sub(r"^.*?\d{1,2}:\d{2}\s*", "", line).strip()
    source = re.split(r"\s*(?:Hiace|Alphard|Vellfire|Toyota|Benz|Mercedes|ハイエース|アルファード|\d+\s*座|\d+\s*代)", source, maxsplit=1, flags=re.IGNORECASE)[0]
    source = re.split(r"\s*绿\s*\d+", source, maxsplit=1)[0]
    source = re.split(r"\s+\d{3,7}(?:\+\d{3,7})?\b", source, maxsplit=1)[0]
    return source.strip()


def _find_airport_alias(value: str) -> tuple[str, str, int] | None:
    compact = re.sub(r"\s+", "", value)
    best: tuple[str, str, int] | None = None
    for std, aliases in _AIRPORT_ALIASES:
        for alias in aliases:
            needle = re.sub(r"\s+", "", alias)
            index = compact.lower().find(needle.lower())
            if index >= 0 and (best is None or index < best[2] or len(alias) > len(best[1])):
                best = (std, alias, index)
    return best


def _normalize_compact_place(value: str) -> str:
    clean = re.sub(r"接机|接機|送机|送機|单送|單送", "", value).strip(" ,，;；")
    if not clean:
        return ""
    if re.search(r"酒店|hotel", clean, re.IGNORECASE):
        return clean
    airport = _find_airport_alias(clean)
    if not airport:
        return clean
    std, alias, _index = airport
    if len(re.sub(r"\s+", "", clean)) <= len(re.sub(r"\s+", "", alias)) + 2:
        return std
    if re.search(r"机场|空港|関空|KIX|ITM|UKB|HND|NRT", clean, re.IGNORECASE):
        return std
    return clean


def _extract_compact_airport_transfer(line: str, fallback_type: str = "") -> dict[str, Any]:
    normalized = _normalize_full_width(line).replace("緑", "绿")
    segment = _compact_route_segment(normalized)
    airport = _find_airport_alias(segment)
    if not airport and not re.search(r"接机|接機|送机|送機|单送|單送", segment):
        return {}

    compact = re.sub(r"\s+", "", segment)
    order_type = "接机" if fallback_type not in {"送机", "送機"} else "送机"
    pickup = ""
    dropoff = ""
    if re.search(r"接机|接機", compact):
        order_type = "接机"
        parts = re.split(r"接机|接機", compact, maxsplit=1)
        pickup = _normalize_compact_place(parts[0] or (airport[0] if airport else ""))
        dropoff = _normalize_compact_place(parts[1] if len(parts) > 1 else "")
    elif re.search(r"送机|送機|单送|單送", compact):
        order_type = "送机"
        parts = re.split(r"送机|送機|单送|單送", compact, maxsplit=1)
        pickup = _normalize_compact_place(parts[0] if parts else "")
        dropoff = _normalize_compact_place(parts[1] if len(parts) > 1 else (airport[0] if airport else ""))
    elif airport:
        std, alias, index = airport
        alias_len = len(re.sub(r"\s+", "", alias))
        before = compact[:index]
        after = compact[index + alias_len :]
        order_type = "送机" if before else "接机"
        pickup = _normalize_compact_place(before or std)
        dropoff = _normalize_compact_place(after or std)

    fields: dict[str, Any] = {"order_type": order_type}
    if pickup:
        fields["pickup_location"] = pickup
    if dropoff:
        fields["dropoff_location"] = dropoff
    vehicle = _extract_vehicle_type(normalized)
    if vehicle:
        fields["vehicle_type"] = vehicle
    price = _extract_agency_price(normalized)
    if price:
        fields["price"] = price
        fields["price_jpy"] = price
    luggage = re.search(r"(\d+)\s*(?:件|个行李|行李|bags?)", normalized, re.IGNORECASE)
    if luggage:
        fields["luggage_count"] = int(luggage.group(1))
    if re.search(r"儿童座椅|child seat", normalized, re.IGNORECASE):
        fields["remark"] = "儿童座椅"
    return fields


def _extract_agency_price(value: str) -> float:
    normalized = _normalize_full_width(value).replace("緑", "绿")
    green = re.search(r"(?:绿|绿色|green)\s*(\d{3,7})(?:\s*\+\s*(\d{3,7}))?", normalized, re.IGNORECASE)
    if green:
        return float(green.group(2) or green.group(1))
    plus = re.search(r"(?<![-\d])(\d{3,7})\s*\+\s*(\d{3,7})(?![-\d])", normalized)
    if plus:
        return float(plus.group(2))
    without_phones = re.sub(r"\+?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}", " ", normalized)
    without_phones = re.sub(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", " ", without_phones)
    without_phones = re.sub(r"\b\d{1,2}:\d{2}\b", " ", without_phones)
    matches = [int(item) for item in re.findall(r"(?<![-\d])(\d{3,7})(?![-\d])", without_phones)]
    matches = [item for item in matches if item >= 300 and item != datetime.now().year]
    return float(matches[-1]) if matches else 0


def _normalize_full_width(value: str) -> str:
    table = str.maketrans({
        "：": ":",
        "－": "-",
        "〜": "~",
        "～": "~",
        "　": " ",
    })
    return value.translate(table)


def _structured_label_value(text: str, labels: list[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:^|\n)\s*(?:{label_pattern})\s*[:：]\s*(.+)", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).splitlines()[0].strip(" ,;；")


def _split_route_stops(value: str) -> list[str]:
    return [part.strip(" ,;；") for part in re.split(r"\s*(?:->|→|>|-)\s*", value) if part.strip(" ,;；")]


def _route_segment_from_line(line: str) -> str:
    start = re.search(r"(\d{1,2}:\d{2})", line)
    source = line[start.end():].strip() if start else line
    source = re.split(r"\s+\d+\s*(?:人|名|pax|PAX)", source, maxsplit=1)[0]
    return source.strip()


def _extract_vehicle_type(value: str) -> str:
    match = re.search(r"\b(Hiace|Alphard|Vellfire|Coaster|Sedan|Van|Bus)\b|(\d+\s*座)|(\d+\s*代)", value, re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"\s+", "", match.group(0)).strip()


def _split_name_phone(value: str) -> tuple[str, str]:
    phone_match = re.search(r"(\+?\d[\d -]{7,}\d)", value)
    if not phone_match:
        return value.strip(" ,;；"), ""
    phone = re.sub(r"\s+", "", phone_match.group(1))
    name = value[: phone_match.start()].strip(" ,;；")
    return name, phone


def _extract_strict_flight_number(value: str) -> str:
    match = re.search(r"(?<![A-Za-z])([A-Z]{2,3}\d{2,4})(?!\d)", value)
    return match.group(1) if match else ""


def _extract_guide_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    guide_line = ""
    for line in text.splitlines():
        if re.search(r"(导游|guide|ガイド)", line, re.IGNORECASE):
            guide_line = line.strip()
            break
    if not guide_line:
        return fields
    source = guide_line or text
    name_match = re.search(r"(?:导游|guide|ガイド)\s*[:：]?\s*([A-Za-z\u4e00-\u9fffぁ-んァ-ヶー]{2,24})", source, re.IGNORECASE)
    if name_match:
        fields["guide_name"] = name_match.group(1).strip()
    phone_match = re.search(r"(\+?\d[\d\s-]{7,}\d)", source)
    if phone_match:
        fields["guide_phone"] = re.sub(r"\s+", "", phone_match.group(1))
    wechat_match = re.search(r"(?:微信|wechat|weixin)\s*[:：]?\s*([A-Za-z0-9_.-]{3,40})", source, re.IGNORECASE)
    if wechat_match:
        fields["guide_wechat"] = wechat_match.group(1)
    line_match = re.search(r"(?:line)\s*[:：]?\s*([A-Za-z0-9_.@-]{3,40})", source, re.IGNORECASE)
    if line_match:
        fields["guide_line"] = line_match.group(1)
    whatsapp_match = re.search(r"(?:whatsapp|wa)\s*[:：]?\s*(\+?\d[\d\s-]{7,}\d)", source, re.IGNORECASE)
    if whatsapp_match:
        fields["guide_whatsapp"] = re.sub(r"\s+", "", whatsapp_match.group(1))
    return fields


def _extract_charter_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"order_type": "charter"}
    fields.update(_extract_unlabeled_charter_line(text))
    normalized = text.replace("\r\n", "\n")
    first_line = normalized.splitlines()[0] if normalized.splitlines() else normalized
    date_match = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}|\d{1,2}月\d{1,2}日?)", normalized)
    if date_match and not fields.get("order_date"):
        fields["order_date"] = _normalize_agency_date(date_match.group(1))
        fields["end_date"] = fields["order_date"]
    time_match = re.search(r"(\d{1,2}[:：]\d{2})\s*[-~～至到]\s*(\d{1,2}[:：]\d{2})", normalized)
    if time_match and not fields.get("start_time"):
        fields["start_time"] = time_match.group(1).replace("：", ":")
        fields["end_time"] = time_match.group(2).replace("：", ":")
    elif not fields.get("start_time") and (single_time := re.search(r"(\d{1,2}[:：]\d{2})", first_line)):
        fields["start_time"] = single_time.group(1).replace("：", ":")
    hotel = _labeled_value(normalized, ["酒店", "hotel"])
    itinerary = _labeled_value(normalized, ["行程", "itinerary", "route"])
    if hotel:
        fields["pickup_location"] = hotel
        fields["dropoff_location"] = hotel
    if itinerary and not hotel and not fields.get("pickup_location"):
        stops = [part.strip() for part in re.split(r"->|→|>|-", itinerary) if part.strip()]
        if stops:
            fields["pickup_location"] = stops[0]
            fields["dropoff_location"] = stops[-1]
    vehicle = _labeled_value(normalized, ["车型", "vehicle", "car"])
    if vehicle and not fields.get("vehicle_type"):
        vehicle_clean = re.split(r"\s+\d+\s*(?:人|pax|件|bags?)", vehicle, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        fields["vehicle_type"] = vehicle_clean or vehicle
    guest = _labeled_value(normalized, ["客人", "游客", "guest", "customer"])
    if guest:
        phone = re.search(r"(\+?\d[\d\s-]{7,}\d)", guest)
        if phone:
            fields["guest_contact"] = re.sub(r"\s+", "", phone.group(1))
            fields["guest_name"] = guest[: phone.start()].strip(" :：,，")
        else:
            fields["guest_name"] = guest
    people = re.search(r"(\d+)\s*(?:人|pax|名)", normalized, re.IGNORECASE)
    if people and not fields.get("passenger_count"):
        fields["passenger_count"] = int(people.group(1))
    luggage = re.search(r"(\d+)\s*(?:件|行李|bags?)", normalized, re.IGNORECASE)
    if luggage and not fields.get("luggage_count"):
        fields["luggage_count"] = int(luggage.group(1))
    price_text = _labeled_value(normalized, ["报价", "价格", "price"])
    price_match = re.search(r"(\d{4,7})", price_text or normalized)
    if price_match and not fields.get("price"):
        fields["price"] = float(price_match.group(1))
        fields["price_jpy"] = fields["price"]
    if itinerary:
        fields["remark"] = f"包车行程：{itinerary}"
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _extract_unlabeled_charter_line(text: str) -> dict[str, Any]:
    line = " ".join(part.strip() for part in text.strip().splitlines() if part.strip())
    fields: dict[str, Any] = {}
    date_match = re.search(r"(\d{1,2}[./-]\d{1,2}|\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}月\d{1,2}日?)", line)
    if date_match:
        fields["order_date"] = _normalize_agency_date(date_match.group(1))
        fields["end_date"] = fields["order_date"]
    time_match = re.search(r"(\d{1,2}[:：]\d{2})", line)
    if time_match:
        fields["start_time"] = time_match.group(1).replace("：", ":")

    route_text = ""
    if time_match:
        after_time = line[time_match.end():].strip()
        route_text = re.split(r"\s*包车\s*", after_time, maxsplit=1)[0].strip()
    elif date_match:
        after_date = line[date_match.end():].strip()
        route_text = re.split(r"\s*包车\s*", after_date, maxsplit=1)[0].strip()
    if route_text:
        pickup, dropoff = _charter_route_endpoints(route_text)
        fields["pickup_location"] = pickup
        fields["dropoff_location"] = dropoff
        fields["remark"] = f"包车行程：{route_text}"

    vehicle_match = re.search(r"包车\s*([^\s（）()]*?(?:3代|10座|阿尔法|埃尔法|Alphard|Hiace|海狮)[^\s（）()]*)", line, re.IGNORECASE)
    if vehicle_match:
        fields["vehicle_type"] = _clean_charter_vehicle_type(vehicle_match.group(1))
    elif vehicle_match_alt := re.search(r"\b(3代|10座|Alphard|Hiace|海狮)\b", line, re.IGNORECASE):
        fields["vehicle_type"] = _clean_charter_vehicle_type(vehicle_match_alt.group(1))

    if "绿" in line:
        fields["vehicle_color"] = "绿牌"

    driver_note = ""
    note_match = re.search(r"[（(]([^）)]*(?:司机|KAKAO|英文)[^）)]*)[）)]", line, re.IGNORECASE)
    if note_match:
        driver_note = note_match.group(1).strip()

    price_match = re.search(r"(?:绿\s*)?(\d{3,7})(?=\s*[A-Za-z\u4e00-\u9fffぁ-んァ-ヶー（(]|$)", line)
    if price_match:
        fields["price"] = float(price_match.group(1))
        fields["price_jpy"] = fields["price"]
        guest = line[price_match.end():].strip(" 　,，")
        guest = re.sub(r"^[（(][^）)]*[）)]", "", guest).strip()
        guest = re.sub(r"^[）)]", "", guest).strip()
        if guest:
            fields["guest_name"] = guest

    if driver_note:
        fields["remark"] = _merge_text(fields.get("remark"), f"司机要求：{driver_note}")
    return fields


def _charter_route_endpoints(route_text: str) -> tuple[str, str]:
    clean = route_text.strip(" 　,，")
    if not clean:
        return "待确认起点", "待确认终点"
    if "往返" in clean:
        left, _, _right = clean.partition("往返")
        base = left.strip() or clean
        return base, base
    parts = [part.strip() for part in re.split(r"->|→|>|-|－|—|–", clean) if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return clean, clean


def _clean_charter_vehicle_type(value: str) -> str:
    cleaned = str(value or "").strip()
    cleaned = cleaned.replace("绿牌", "").replace("綠牌", "")
    cleaned = cleaned.replace("绿", "").replace("綠", "")
    return cleaned.strip() or str(value or "").strip()


def _labeled_value(text: str, labels: list[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:：]\s*(.+)", text, re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).splitlines()[0].strip()
    return value.strip(" ,，;；")


def _normalize_agency_date(value: str) -> str:
    value = value.replace("/", "-").replace(".", "-")
    if "月" in value:
        match = re.search(r"(\d{1,2})月(\d{1,2})", value)
        if match:
            return f"{datetime.now().year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"
    parts = value.split("-")
    if len(parts) == 3:
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    if len(parts) == 2:
        return f"{datetime.now().year}-{int(parts[0]):02d}-{int(parts[1]):02d}"
    return value


def _merge_text(left: Any, right: str) -> str:
    parts = [str(item).strip() for item in (left, right) if str(item or "").strip()]
    return "\n".join(dict.fromkeys(parts))

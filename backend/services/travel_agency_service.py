from __future__ import annotations

import csv
import io
import json
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


ROLE_MATRIX = {
    "agency_owner": [
        "company_settings",
        "accounts",
        "customers",
        "orders",
        "guides",
        "finance",
        "marketplace",
        "audit",
    ],
    "agency_customer_service": ["customers", "orders", "marketplace"],
    "agency_guide": ["guide_tasks", "guide_reports", "profile"],
    "agency_finance": ["finance", "exports"],
}


def ensure_travel_agency_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                master_phone TEXT NOT NULL,
                master_display_name TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                must_change_password INTEGER NOT NULL DEFAULT 1,
                wx_bind_required INTEGER NOT NULL DEFAULT 0,
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, company_code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                password_seed TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                wx_openid TEXT,
                wx_bind_status TEXT NOT NULL DEFAULT 'unbound',
                status TEXT NOT NULL DEFAULT 'active',
                permissions_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES travel_agency_companies(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_guides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                languages TEXT,
                certificate_no TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES travel_agency_companies(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                source_channel TEXT,
                contact_name TEXT,
                contact_phone TEXT,
                route_preference TEXT,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES travel_agency_companies(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                customer_id INTEGER,
                guide_id INTEGER,
                order_no TEXT,
                order_date TEXT,
                start_time TEXT,
                end_time TEXT,
                pickup_location TEXT,
                dropoff_location TEXT,
                itinerary TEXT,
                passenger_count INTEGER NOT NULL DEFAULT 0,
                luggage_count INTEGER NOT NULL DEFAULT 0,
                vehicle_type TEXT,
                customer_budget_jpy REAL NOT NULL DEFAULT 0,
                carrier_payable_jpy REAL NOT NULL DEFAULT 0,
                guide_payable_jpy REAL NOT NULL DEFAULT 0,
                marketplace_status TEXT NOT NULL DEFAULT 'not_published',
                order_status TEXT NOT NULL DEFAULT 'draft',
                dispatch_status TEXT NOT NULL DEFAULT 'unrequested',
                settlement_status TEXT NOT NULL DEFAULT 'pending',
                raw_text TEXT,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES travel_agency_companies(id),
                FOREIGN KEY (customer_id) REFERENCES travel_agency_customers(id),
                FOREIGN KEY (guide_id) REFERENCES travel_agency_guides(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_marketplace_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                start_price_jpy REAL NOT NULL DEFAULT 0,
                buyout_price_jpy REAL NOT NULL DEFAULT 0,
                protected_floor_jpy REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'draft',
                awarded_carrier_name TEXT,
                awarded_price_jpy REAL,
                expires_at TEXT,
                responsibility_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES travel_agency_orders(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_marketplace_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                listing_id INTEGER NOT NULL,
                carrier_name TEXT NOT NULL,
                quote_price_jpy REAL NOT NULL DEFAULT 0,
                service_level TEXT,
                status TEXT NOT NULL DEFAULT 'submitted',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES travel_agency_marketplace_drafts(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_guide_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER NOT NULL,
                guide_id INTEGER,
                order_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_status TEXT NOT NULL DEFAULT 'submitted',
                location_text TEXT,
                note TEXT,
                evidence_url TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_agency_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                company_id INTEGER,
                actor TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                before_json TEXT,
                after_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def stage_summary() -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        return {
            "tenant_id": tenant_id,
            "companies": _count(conn, "travel_agency_companies", tenant_id),
            "accounts": _count(conn, "travel_agency_accounts", tenant_id),
            "guides": _count(conn, "travel_agency_guides", tenant_id),
            "customers": _count(conn, "travel_agency_customers", tenant_id),
            "orders": _count(conn, "travel_agency_orders", tenant_id),
            "marketplace_listings": _count(conn, "travel_agency_marketplace_drafts", tenant_id),
            "audit_logs": _count(conn, "travel_agency_audit_logs", tenant_id),
            "role_matrix": ROLE_MATRIX,
        }


def create_company(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    company_code = _text(payload.get("company_code") or payload.get("code")).upper()
    company_name = _text(payload.get("company_name") or payload.get("name"))
    master_phone = _text(payload.get("master_phone") or payload.get("phone"))
    if not company_code or not company_name or not master_phone:
        raise ValueError("company_code_name_phone_required")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_companies (
                tenant_id, company_code, company_name, master_phone, master_display_name,
                must_change_password, wx_bind_required, settings_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                company_code,
                company_name,
                master_phone,
                _text(payload.get("master_display_name") or payload.get("display_name") or company_name),
                _bool_int(payload.get("wx_bind_required")),
                _json(payload.get("settings") or {}),
            ),
        )
        company_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO travel_agency_accounts (
                tenant_id, company_id, role, display_name, phone, password_seed,
                must_change_password, permissions_json, updated_at
            )
            VALUES (?, ?, 'agency_owner', ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                company_id,
                _text(payload.get("master_display_name") or company_name),
                master_phone,
                _phone_tail(master_phone),
                _json(ROLE_MATRIX["agency_owner"]),
            ),
        )
        _audit(conn, tenant_id, company_id, actor, "company_create", "travel_agency_company", company_id, None, payload)
        conn.commit()
    return get_company(company_id) or {}


def list_companies(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    params = params or {}
    sql = ["SELECT * FROM travel_agency_companies WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if params.get("status"):
        sql.append("AND status = ?")
        values.append(params["status"])
    if params.get("keyword"):
        sql.append("AND (company_code LIKE ? OR company_name LIKE ? OR master_phone LIKE ?)")
        like = f"%{params['keyword']}%"
        values.extend([like, like, like])
    sql.append("ORDER BY company_code, id")
    with get_connection() as conn:
        return [_row(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def get_company(company_id: int | str) -> dict[str, Any] | None:
    ensure_travel_agency_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM travel_agency_companies WHERE tenant_id = ? AND id = ?",
            (get_current_tenant_id(), _to_int(company_id)),
        ).fetchone()
    return _row(row) if row else None


def create_account(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    company_id = _to_int(payload.get("company_id"))
    role = _text(payload.get("role") or "agency_customer_service")
    if role not in ROLE_MATRIX:
        raise ValueError("invalid_agency_role")
    display_name = _text(payload.get("display_name") or payload.get("name"))
    phone = _text(payload.get("phone"))
    if not company_id or not display_name or not phone:
        raise ValueError("company_display_name_phone_required")
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        _require_company(conn, tenant_id, company_id)
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_accounts (
                tenant_id, company_id, role, display_name, phone, password_seed,
                must_change_password, permissions_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            """,
            (tenant_id, company_id, role, display_name, phone, _phone_tail(phone), _json(ROLE_MATRIX[role])),
        )
        account_id = cursor.lastrowid
        _audit(conn, tenant_id, company_id, actor, "account_create", "travel_agency_account", account_id, None, payload)
        conn.commit()
    return get_record("travel_agency_accounts", account_id) or {}


def list_accounts(company_id: int | str | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    sql = ["SELECT * FROM travel_agency_accounts WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if company_id:
        sql.append("AND company_id = ?")
        values.append(_to_int(company_id))
    sql.append("ORDER BY company_id, role, id")
    return _query(sql, values)


def create_guide(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    company_id = _to_int(payload.get("company_id"))
    name = _text(payload.get("name"))
    if not company_id or not name:
        raise ValueError("company_id_and_guide_name_required")
    with get_connection() as conn:
        _require_company(conn, tenant_id, company_id)
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_guides (
                tenant_id, company_id, name, phone, languages, certificate_no, status, note, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                company_id,
                name,
                _text(payload.get("phone")),
                _text(payload.get("languages")),
                _text(payload.get("certificate_no")),
                _text(payload.get("status") or "active"),
                _text(payload.get("note")),
            ),
        )
        guide_id = cursor.lastrowid
        _audit(conn, tenant_id, company_id, actor, "guide_create", "travel_agency_guide", guide_id, None, payload)
        conn.commit()
    return get_record("travel_agency_guides", guide_id) or {}


def list_guides(company_id: int | str | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    sql = ["SELECT * FROM travel_agency_guides WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if company_id:
        sql.append("AND company_id = ?")
        values.append(_to_int(company_id))
    sql.append("ORDER BY company_id, status, name")
    return _query(sql, values)


def create_customer(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    company_id = _to_int(payload.get("company_id"))
    customer_name = _text(payload.get("customer_name") or payload.get("name"))
    if not company_id or not customer_name:
        raise ValueError("company_id_and_customer_name_required")
    with get_connection() as conn:
        _require_company(conn, tenant_id, company_id)
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_customers (
                tenant_id, company_id, customer_name, source_channel, contact_name,
                contact_phone, route_preference, note, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                company_id,
                customer_name,
                _text(payload.get("source_channel")),
                _text(payload.get("contact_name")),
                _text(payload.get("contact_phone")),
                _text(payload.get("route_preference")),
                _text(payload.get("note")),
                _text(payload.get("status") or "active"),
            ),
        )
        customer_id = cursor.lastrowid
        _audit(conn, tenant_id, company_id, actor, "customer_create", "travel_agency_customer", customer_id, None, payload)
        conn.commit()
    return get_record("travel_agency_customers", customer_id) or {}


def list_customers(company_id: int | str | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    sql = ["SELECT * FROM travel_agency_customers WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if company_id:
        sql.append("AND company_id = ?")
        values.append(_to_int(company_id))
    sql.append("ORDER BY company_id, customer_name")
    return _query(sql, values)


def parse_order_text(payload: dict[str, Any]) -> dict[str, Any]:
    text = _text(payload.get("raw_text") or payload.get("text"))
    return {
        "raw_text": text,
        "order_date": _first_token(text, "-") or payload.get("order_date"),
        "start_time": _find_time(text) or payload.get("start_time"),
        "pickup_location": _between(text, "from ", " to ") or payload.get("pickup_location") or "",
        "dropoff_location": _after(text, " to ") or payload.get("dropoff_location") or "",
        "passenger_count": _find_count(text, "pax") or payload.get("passenger_count") or 0,
        "vehicle_type": payload.get("vehicle_type") or ("hiace" if "hiace" in text.lower() else ""),
        "note": "parsed_preview",
    }


def create_order(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    company_id = _to_int(payload.get("company_id"))
    if not company_id:
        raise ValueError("company_id_required")
    with get_connection() as conn:
        _require_company(conn, tenant_id, company_id)
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_orders (
                tenant_id, company_id, customer_id, guide_id, order_no, order_date,
                start_time, end_time, pickup_location, dropoff_location, itinerary,
                passenger_count, luggage_count, vehicle_type, customer_budget_jpy,
                carrier_payable_jpy, guide_payable_jpy, marketplace_status,
                order_status, dispatch_status, settlement_status, raw_text, note,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                company_id,
                _to_int(payload.get("customer_id")) or None,
                _to_int(payload.get("guide_id")) or None,
                _text(payload.get("order_no")),
                _text(payload.get("order_date")),
                _text(payload.get("start_time")),
                _text(payload.get("end_time")),
                _text(payload.get("pickup_location")),
                _text(payload.get("dropoff_location")),
                _text(payload.get("itinerary")),
                _to_int(payload.get("passenger_count")),
                _to_int(payload.get("luggage_count")),
                _text(payload.get("vehicle_type")),
                _to_float(payload.get("customer_budget_jpy") or payload.get("price")),
                _to_float(payload.get("carrier_payable_jpy")),
                _to_float(payload.get("guide_payable_jpy")),
                _text(payload.get("marketplace_status") or "not_published"),
                _text(payload.get("order_status") or "draft"),
                _text(payload.get("dispatch_status") or "unrequested"),
                _text(payload.get("settlement_status") or "pending"),
                _text(payload.get("raw_text")),
                _text(payload.get("note")),
            ),
        )
        order_id = cursor.lastrowid
        if not payload.get("order_no"):
            conn.execute("UPDATE travel_agency_orders SET order_no = ? WHERE id = ?", (f"TA{tenant_id:02d}-{order_id:06d}", order_id))
        _audit(conn, tenant_id, company_id, actor, "order_create", "travel_agency_order", order_id, None, payload)
        conn.commit()
    return get_record("travel_agency_orders", order_id) or {}


def list_orders(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    params = params or {}
    sql = ["SELECT * FROM travel_agency_orders WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    for key in ("company_id", "order_status", "dispatch_status", "settlement_status", "marketplace_status"):
        if params.get(key):
            sql.append(f"AND {key} = ?")
            values.append(params[key])
    sql.append("ORDER BY order_date DESC, start_time DESC, id DESC")
    return _query(sql, values)


def transition_order(order_id: int | str, action: str, payload: dict[str, Any] | None = None, actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    payload = payload or {}
    fields: dict[str, Any]
    if action == "confirm":
        fields = {"order_status": "confirmed"}
    elif action == "assign-guide":
        fields = {"guide_id": _to_int(payload.get("guide_id")), "order_status": "guide_assigned"}
    elif action == "vehicle-request":
        fields = {"dispatch_status": "vehicle_requested"}
    elif action == "settle":
        fields = {"settlement_status": _text(payload.get("settlement_status") or "settled")}
    else:
        raise ValueError("invalid_order_action")
    return _update_order(order_id, fields, actor, action)


def create_marketplace_draft(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    order_id = _to_int(payload.get("order_id"))
    with get_connection() as conn:
        order = conn.execute(
            "SELECT * FROM travel_agency_orders WHERE tenant_id = ? AND id = ?",
            (tenant_id, order_id),
        ).fetchone()
        if not order:
            raise ValueError("order_not_found")
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_marketplace_drafts (
                tenant_id, company_id, order_id, start_price_jpy, buyout_price_jpy,
                protected_floor_jpy, status, expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                order["company_id"],
                order_id,
                _to_float(payload.get("start_price_jpy")),
                _to_float(payload.get("buyout_price_jpy")),
                _to_float(payload.get("protected_floor_jpy")),
                _text(payload.get("status") or "published"),
                _text(payload.get("expires_at")),
            ),
        )
        listing_id = cursor.lastrowid
        conn.execute(
            "UPDATE travel_agency_orders SET marketplace_status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (order_id,),
        )
        _audit(conn, tenant_id, order["company_id"], actor, "marketplace_publish", "travel_agency_marketplace_draft", listing_id, None, payload)
        conn.commit()
    return get_record("travel_agency_marketplace_drafts", listing_id) or {}


def list_marketplace(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    params = params or {}
    sql = [
        """
        SELECT m.*, o.order_no, o.pickup_location, o.dropoff_location, o.order_date, o.vehicle_type
        FROM travel_agency_marketplace_drafts m
        JOIN travel_agency_orders o ON o.id = m.order_id AND o.tenant_id = m.tenant_id
        WHERE m.tenant_id = ?
        """
    ]
    values: list[Any] = [get_current_tenant_id()]
    if params.get("status"):
        sql.append("AND m.status = ?")
        values.append(params["status"])
    sql.append("ORDER BY m.id DESC")
    return _query(sql, values)


def submit_quote(listing_id: int | str, payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    carrier_name = _text(payload.get("carrier_name"))
    if not carrier_name:
        raise ValueError("carrier_name_required")
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT * FROM travel_agency_marketplace_drafts WHERE tenant_id = ? AND id = ?",
            (tenant_id, _to_int(listing_id)),
        ).fetchone()
        if not listing:
            raise ValueError("listing_not_found")
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_marketplace_quotes (
                tenant_id, listing_id, carrier_name, quote_price_jpy, service_level, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (tenant_id, listing_id, carrier_name, _to_float(payload.get("quote_price_jpy")), _text(payload.get("service_level"))),
        )
        quote_id = cursor.lastrowid
        _audit(conn, tenant_id, listing["company_id"], actor, "marketplace_quote", "travel_agency_marketplace_quote", quote_id, None, payload)
        conn.commit()
    return get_record("travel_agency_marketplace_quotes", quote_id) or {}


def award_listing(listing_id: int | str, payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT * FROM travel_agency_marketplace_drafts WHERE tenant_id = ? AND id = ?",
            (tenant_id, _to_int(listing_id)),
        ).fetchone()
        if not listing:
            raise ValueError("listing_not_found")
        conn.execute(
            """
            UPDATE travel_agency_marketplace_drafts
            SET status = 'awarded',
                awarded_carrier_name = ?,
                awarded_price_jpy = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (
                _text(payload.get("awarded_carrier_name") or payload.get("carrier_name")),
                _to_float(payload.get("awarded_price_jpy") or payload.get("quote_price_jpy")),
                tenant_id,
                _to_int(listing_id),
            ),
        )
        conn.execute(
            """
            UPDATE travel_agency_orders
            SET marketplace_status = 'awarded',
                dispatch_status = 'carrier_awarded',
                carrier_payable_jpy = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (_to_float(payload.get("awarded_price_jpy") or payload.get("quote_price_jpy")), tenant_id, listing["order_id"]),
        )
        _audit(conn, tenant_id, listing["company_id"], actor, "marketplace_award", "travel_agency_marketplace_draft", listing_id, None, payload)
        conn.commit()
    return get_record("travel_agency_marketplace_drafts", listing_id) or {}


def record_guide_event(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    ensure_travel_agency_schema()
    tenant_id = get_current_tenant_id()
    order_id = _to_int(payload.get("order_id"))
    with get_connection() as conn:
        order = conn.execute(
            "SELECT * FROM travel_agency_orders WHERE tenant_id = ? AND id = ?",
            (tenant_id, order_id),
        ).fetchone()
        if not order:
            raise ValueError("order_not_found")
        cursor = conn.execute(
            """
            INSERT INTO travel_agency_guide_events (
                tenant_id, company_id, guide_id, order_id, event_type, event_status,
                location_text, note, evidence_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                order["company_id"],
                _to_int(payload.get("guide_id") or order["guide_id"]) or None,
                order_id,
                _text(payload.get("event_type") or "checkpoint"),
                _text(payload.get("event_status") or "submitted"),
                _text(payload.get("location_text")),
                _text(payload.get("note")),
                _text(payload.get("evidence_url")),
            ),
        )
        event_id = cursor.lastrowid
        _audit(conn, tenant_id, order["company_id"], actor, "guide_event", "travel_agency_guide_event", event_id, None, payload)
        conn.commit()
    return get_record("travel_agency_guide_events", event_id) or {}


def list_guide_events(order_id: int | str | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    sql = ["SELECT * FROM travel_agency_guide_events WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if order_id:
        sql.append("AND order_id = ?")
        values.append(_to_int(order_id))
    sql.append("ORDER BY id DESC")
    return _query(sql, values)


def finance_ledger(params: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_travel_agency_schema()
    rows = list_orders(params)
    receivable = sum(float(row.get("customer_budget_jpy") or 0) for row in rows)
    carrier_payable = sum(float(row.get("carrier_payable_jpy") or 0) for row in rows)
    guide_payable = sum(float(row.get("guide_payable_jpy") or 0) for row in rows)
    return {
        "rows": rows,
        "summary": {
            "receivable_jpy": receivable,
            "carrier_payable_jpy": carrier_payable,
            "guide_payable_jpy": guide_payable,
            "gross_profit_jpy": receivable - carrier_payable - guide_payable,
            "order_count": len(rows),
        },
    }


def finance_export_csv(params: dict[str, Any] | None = None) -> str:
    ledger = finance_ledger(params)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_no", "order_date", "customer_budget_jpy", "carrier_payable_jpy", "guide_payable_jpy", "settlement_status"])
    for row in ledger["rows"]:
        writer.writerow([
            row.get("order_no"),
            row.get("order_date"),
            row.get("customer_budget_jpy"),
            row.get("carrier_payable_jpy"),
            row.get("guide_payable_jpy"),
            row.get("settlement_status"),
        ])
    return output.getvalue()


def list_audit(company_id: int | str | None = None) -> list[dict[str, Any]]:
    ensure_travel_agency_schema()
    sql = ["SELECT * FROM travel_agency_audit_logs WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if company_id:
        sql.append("AND company_id = ?")
        values.append(_to_int(company_id))
    sql.append("ORDER BY id DESC LIMIT 200")
    return _query(sql, values)


def get_record(table: str, record_id: int | str) -> dict[str, Any] | None:
    ensure_travel_agency_schema()
    allowed = {
        "travel_agency_accounts",
        "travel_agency_guides",
        "travel_agency_customers",
        "travel_agency_orders",
        "travel_agency_marketplace_drafts",
        "travel_agency_marketplace_quotes",
        "travel_agency_guide_events",
    }
    if table not in allowed:
        raise ValueError("invalid_table")
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE tenant_id = ? AND id = ?",
            (get_current_tenant_id(), _to_int(record_id)),
        ).fetchone()
    return _row(row) if row else None


def _update_order(order_id: int | str, fields: dict[str, Any], actor: str, action: str) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    keys = [key for key, value in fields.items() if value is not None]
    if not keys:
        raise ValueError("no_update_fields")
    with get_connection() as conn:
        before = conn.execute(
            "SELECT * FROM travel_agency_orders WHERE tenant_id = ? AND id = ?",
            (tenant_id, _to_int(order_id)),
        ).fetchone()
        if not before:
            raise ValueError("order_not_found")
        assignments = ", ".join([f"{key} = ?" for key in keys])
        conn.execute(
            f"UPDATE travel_agency_orders SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
            [fields[key] for key in keys] + [tenant_id, _to_int(order_id)],
        )
        _audit(conn, tenant_id, before["company_id"], actor, f"order_{action}", "travel_agency_order", order_id, dict(before), fields)
        conn.commit()
    return get_record("travel_agency_orders", order_id) or {}


def _query(sql: list[str], values: list[Any]) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [_row(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def _row(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key, value in list(data.items()):
        if key.endswith("_json") and isinstance(value, str):
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return data


def _count(conn: Any, table: str, tenant_id: int) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE tenant_id = ?", (tenant_id,)).fetchone()["c"])


def _audit(conn: Any, tenant_id: int, company_id: int | None, actor: str, action: str, entity_type: str, entity_id: Any, before: Any, after: Any) -> None:
    conn.execute(
        """
        INSERT INTO travel_agency_audit_logs (
            tenant_id, company_id, actor, action, entity_type, entity_id, before_json, after_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tenant_id, company_id, actor, action, entity_type, str(entity_id), _json(before), _json(after)),
    )


def _require_company(conn: Any, tenant_id: int, company_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM travel_agency_companies WHERE tenant_id = ? AND id = ?",
        (tenant_id, company_id),
    ).fetchone()
    if not row:
        raise ValueError("company_not_found")


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _bool_int(value: Any) -> int:
    return 1 if value in (True, 1, "1", "true", "yes", "on", "required") else 0


def _phone_tail(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else digits


def _find_time(text: str) -> str:
    import re

    match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", text)
    return match.group(0) if match else ""


def _find_count(text: str, suffix: str) -> int:
    import re

    match = re.search(rf"\b(\d+)\s*{suffix}\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _first_token(text: str, marker: str) -> str:
    for token in text.split():
        if marker in token and any(ch.isdigit() for ch in token):
            return token
    return ""


def _between(text: str, start: str, end: str) -> str:
    lower = text.lower()
    s = lower.find(start)
    if s < 0:
        return ""
    s += len(start)
    e = lower.find(end, s)
    if e < 0:
        return ""
    return text[s:e].strip()


def _after(text: str, marker: str) -> str:
    lower = text.lower()
    index = lower.find(marker)
    if index < 0:
        return ""
    return text[index + len(marker) :].strip()

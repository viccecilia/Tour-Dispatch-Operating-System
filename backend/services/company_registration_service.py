from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path
from typing import Any

from backend.config import RUNTIME_DIR
from backend.db.database import get_connection, hash_password
from backend.services.auth_service import company_login_name, normalize_phone, phone_password_tail
from backend.services.tenant_context import get_current_tenant_id


UPLOAD_ROOT = RUNTIME_DIR / "uploads" / "company_registrations"

COMPANY_REGISTRATION_COLUMNS = {
    "managing_tenant_id": "INTEGER NOT NULL DEFAULT 1",
    "company_type": "TEXT NOT NULL DEFAULT 'carrier'",
    "tenant_id": "INTEGER",
    "agency_id": "INTEGER",
    "company_code": "TEXT NOT NULL",
    "company_name": "TEXT NOT NULL",
    "registered_name": "TEXT",
    "corporate_number": "TEXT",
    "invoice_registration_number": "TEXT",
    "business_license_number": "TEXT",
    "representative_name": "TEXT",
    "postal_code": "TEXT",
    "address": "TEXT",
    "contact_name": "TEXT",
    "contact_phone": "TEXT",
    "contact_email": "TEXT",
    "bank_name": "TEXT",
    "bank_branch": "TEXT",
    "bank_account_type": "TEXT",
    "bank_account_number": "TEXT",
    "bank_account_holder": "TEXT",
    "registry_certificate_url": "TEXT",
    "registry_certificate_name": "TEXT",
    "business_license_url": "TEXT",
    "business_license_name": "TEXT",
    "bank_book_url": "TEXT",
    "bank_book_name": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'draft'",
    "review_note": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

TEXT_FIELDS = [
    "company_type",
    "company_code",
    "company_name",
    "registered_name",
    "corporate_number",
    "invoice_registration_number",
    "business_license_number",
    "representative_name",
    "postal_code",
    "address",
    "contact_name",
    "contact_phone",
    "contact_email",
    "bank_name",
    "bank_branch",
    "bank_account_type",
    "bank_account_number",
    "bank_account_holder",
    "registry_certificate_url",
    "registry_certificate_name",
    "business_license_url",
    "business_license_name",
    "bank_book_url",
    "bank_book_name",
    "status",
    "review_note",
]

READABLE_TEXT_FIELDS = [
    ("company_name", "公司名"),
    ("registered_name", "登记会社名"),
    ("representative_name", "法人姓名"),
    ("address", "公司地址"),
    ("contact_name", "业务联系人"),
    ("bank_name", "银行名称"),
    ("bank_branch", "支店名"),
    ("bank_account_holder", "账户名义"),
]

REVIEW_READY_STATUSES = {"submitted", "approved"}


def list_company_registrations(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_company_registration_schema()
    params = params or {}
    sql = [
        """
        SELECT cr.*,
               t.name AS tenant_name,
               t.slug AS tenant_slug,
               ag.name AS agency_name,
               ag.agency_code
        FROM company_registrations cr
        LEFT JOIN tenants t ON t.id = cr.tenant_id
        LEFT JOIN agencies ag ON ag.id = cr.agency_id AND ag.tenant_id = cr.managing_tenant_id
        WHERE cr.managing_tenant_id = ?
        """
    ]
    values: list[Any] = [get_current_tenant_id()]
    company_type = str(params.get("company_type") or "").strip()
    status = str(params.get("status") or "").strip()
    keyword = str(params.get("keyword") or "").strip()
    if company_type:
        sql.append("AND cr.company_type = ?")
        values.append(company_type)
    if status:
        sql.append("AND cr.status = ?")
        values.append(status)
    else:
        sql.append("AND COALESCE(cr.status, '') != 'archived'")
    if keyword:
        like = f"%{keyword}%"
        sql.append(
            """
            AND (
                cr.company_code LIKE ? OR cr.company_name LIKE ? OR cr.registered_name LIKE ?
                OR cr.representative_name LIKE ? OR cr.contact_phone LIKE ? OR cr.contact_email LIKE ?
                OR cr.corporate_number LIKE ?
            )
            """
        )
        values.extend([like] * 7)
    sql.append("ORDER BY cr.updated_at DESC, cr.id DESC")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def create_company_registration(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_company_registration_schema()
    data = _normalize(payload, partial=False)
    _validate_readable_text(data)
    managing_tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        tenant_id = _linked_tenant(conn, data) if data["company_type"] == "carrier" else managing_tenant_id
        agency_id = _linked_agency(conn, data, managing_tenant_id) if data["company_type"] == "agency" else None
        cursor = conn.execute(
            f"""
            INSERT INTO company_registrations (
                managing_tenant_id, tenant_id, agency_id, {", ".join(TEXT_FIELDS)}
            )
            VALUES (?, ?, ?, {", ".join("?" for _ in TEXT_FIELDS)})
            """,
            [managing_tenant_id, tenant_id, agency_id, *[data.get(field) for field in TEXT_FIELDS]],
        )
        if data["company_type"] == "carrier" and data.get("status") == "approved":
            _ensure_carrier_admin_account(conn, tenant_id, data)
        conn.commit()
        return get_company_registration(cursor.lastrowid) or {}


def update_company_registration(registration_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    ensure_company_registration_schema()
    data = _normalize(payload, partial=True)
    if not data:
        return get_company_registration(registration_id)
    with get_connection() as conn:
        before = conn.execute(
            "SELECT * FROM company_registrations WHERE id = ? AND managing_tenant_id = ?",
            (_to_int(registration_id), get_current_tenant_id()),
        ).fetchone()
        if not before:
            return None
        merged = {**dict(before), **data}
        _validate_readable_text(merged)
        if "company_code" in data or "company_name" in data or "registered_name" in data:
            if merged["company_type"] == "carrier":
                tenant_id = _linked_tenant(conn, merged)
                merged["tenant_id"] = tenant_id
                conn.execute(
                    "UPDATE company_registrations SET tenant_id = ? WHERE id = ? AND managing_tenant_id = ?",
                    (tenant_id, _to_int(registration_id), get_current_tenant_id()),
                )
            elif merged["company_type"] == "agency":
                _linked_agency(conn, merged, get_current_tenant_id(), agency_id=merged.get("agency_id"))
        if merged["company_type"] == "carrier" and merged.get("status") == "approved":
            tenant_id = int(merged.get("tenant_id") or _linked_tenant(conn, merged))
            _ensure_carrier_admin_account(conn, tenant_id, merged)
        assignments = ", ".join(f"{key} = ?" for key in data)
        conn.execute(
            f"""
            UPDATE company_registrations
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND managing_tenant_id = ?
            """,
            [*data.values(), _to_int(registration_id), get_current_tenant_id()],
        )
        conn.commit()
    return get_company_registration(registration_id)


def upload_company_registration_file(registration_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_company_registration_schema()
    file_type = str(payload.get("file_type") or "").strip()
    column_map = {
        "registry_certificate": ("registry_certificate_url", "registry_certificate_name"),
        "business_license": ("business_license_url", "business_license_name"),
        "bank_book": ("bank_book_url", "bank_book_name"),
    }
    if file_type not in column_map:
        raise ValueError("invalid_company_file_type")
    registration = get_company_registration(registration_id)
    if not registration:
        raise ValueError("company_registration_not_found")
    file_name = str(payload.get("file_name") or f"{file_type}.pdf").strip()
    file_data = str(payload.get("file_base64") or "").strip()
    if not file_data:
        raise ValueError("missing_company_file")
    raw = _decode_file_payload(file_data)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).strip("._") or f"{file_type}.pdf"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_name = f"tenant{get_current_tenant_id()}_company{registration_id}_{file_type}_{uuid.uuid4().hex[:10]}_{safe_name}"
    file_path = UPLOAD_ROOT / stored_name
    file_path.write_bytes(raw)
    url_column, name_column = column_map[file_type]
    file_url = f"/uploads/company_registrations/{stored_name}"
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE company_registrations
            SET {url_column} = ?,
                {name_column} = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND managing_tenant_id = ?
            """,
            (file_url, file_name, _to_int(registration_id), get_current_tenant_id()),
        )
        conn.commit()
    return {"success": True, "file_type": file_type, "file_url": file_url, "file_name": file_name}


def delete_company_registration(registration_id: Any) -> bool:
    ensure_company_registration_schema()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE company_registrations
            SET status = 'archived',
                review_note = COALESCE(NULLIF(review_note, ''), '已归档，不在默认列表显示。'),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND managing_tenant_id = ?
            """,
            (_to_int(registration_id), get_current_tenant_id()),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_company_registration(registration_id: Any) -> dict[str, Any] | None:
    ensure_company_registration_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM company_registrations WHERE id = ? AND managing_tenant_id = ?",
            (_to_int(registration_id), get_current_tenant_id()),
        ).fetchone()
    return dict(row) if row else None


def ensure_company_registration_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS company_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                managing_tenant_id INTEGER NOT NULL DEFAULT 1,
                company_type TEXT NOT NULL DEFAULT 'carrier',
                tenant_id INTEGER,
                agency_id INTEGER,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                registered_name TEXT,
                corporate_number TEXT,
                invoice_registration_number TEXT,
                business_license_number TEXT,
                representative_name TEXT,
                postal_code TEXT,
                address TEXT,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                bank_name TEXT,
                bank_branch TEXT,
                bank_account_type TEXT,
                bank_account_number TEXT,
                bank_account_holder TEXT,
                registry_certificate_url TEXT,
                registry_certificate_name TEXT,
                business_license_url TEXT,
                business_license_name TEXT,
                bank_book_url TEXT,
                bank_book_name TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                review_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(company_registrations)").fetchall()}
        for column, definition in COMPANY_REGISTRATION_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE company_registrations ADD COLUMN {column} {definition}")
        conn.commit()


def _normalize(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field in TEXT_FIELDS:
        if field not in payload:
            continue
        value = str(payload.get(field) or "").strip()
        if field == "company_code":
            value = _code(value)
        if field == "company_type" and value not in {"carrier", "agency"}:
            raise ValueError("invalid_company_type")
        if field == "status" and value not in {"draft", "submitted", "approved", "rejected", "inactive", "archived"}:
            raise ValueError("invalid_company_status")
        data[field] = value
    if not partial:
        data.setdefault("company_type", "carrier")
        data.setdefault("company_code", _code(payload.get("company_code") or ""))
        data.setdefault("company_name", str(payload.get("company_name") or payload.get("registered_name") or "").strip())
        data.setdefault("registered_name", str(payload.get("registered_name") or data["company_name"]).strip())
        data.setdefault("status", "draft")
        for field in TEXT_FIELDS:
            data.setdefault(field, "")
        if not data["company_code"] or not data["company_name"]:
            raise ValueError("company_code_name_required")
    return data


def _validate_readable_text(data: dict[str, Any]) -> None:
    status = str(data.get("status") or "").strip()
    if status not in REVIEW_READY_STATUSES:
        return
    bad_fields = [label for field, label in READABLE_TEXT_FIELDS if _looks_unreadable(data.get(field))]
    if bad_fields:
        raise ValueError(f"company_registration_text_encoding_invalid:{','.join(bad_fields)}")


def _looks_unreadable(value: Any) -> bool:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return False
    question_count = text.count("?")
    return question_count >= 2 and question_count / max(len(text), 1) >= 0.25


def _linked_tenant(conn, data: dict[str, Any]) -> int:
    code = _code(data.get("company_code"))
    name = str(data.get("company_name") or data.get("registered_name") or code).strip()
    row = conn.execute("SELECT id FROM tenants WHERE slug = ?", (code,)).fetchone()
    if row:
        conn.execute("UPDATE tenants SET name = COALESCE(NULLIF(?, ''), name), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, row["id"]))
        return int(row["id"])
    cursor = conn.execute("INSERT INTO tenants (name, slug, status, updated_at) VALUES (?, ?, 'active', CURRENT_TIMESTAMP)", (name, code))
    return int(cursor.lastrowid)


def _ensure_carrier_admin_account(conn, tenant_id: int, data: dict[str, Any]) -> int | None:
    phone = str(data.get("contact_phone") or "").strip()
    normalized_phone = normalize_phone(phone)
    if len(normalized_phone) < 6:
        return None
    tenant = conn.execute("SELECT name, slug FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    if not tenant:
        return None
    username = company_login_name(normalized_phone, tenant["slug"], tenant["name"])
    existing = conn.execute(
        """
        SELECT id
        FROM users
        WHERE tenant_id = ?
          AND role = 'admin'
          AND (
            REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
            OR username = ?
          )
        ORDER BY id ASC
        LIMIT 1
        """,
        (tenant_id, normalized_phone, username),
    ).fetchone()
    if existing:
        return int(existing["id"])
    username = _unique_username(conn, username)
    password = phone_password_tail(phone)
    display_name = f"{data.get('company_name') or tenant['name']} Admin"
    cursor = conn.execute(
        """
        INSERT INTO users (
            tenant_id, username, password_hash, role, display_name, phone,
            profile_type, wx_bind_status, is_active, password_changed_at,
            must_change_password, updated_at
        )
        VALUES (?, ?, ?, 'admin', ?, ?, 'operator', 'unbound', 1, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
        """,
        (tenant_id, username, hash_password(password), display_name, phone),
    )
    return int(cursor.lastrowid)


def _unique_username(conn, base: str) -> str:
    username = base
    suffix = 2
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        username = f"{base}-{suffix}"
        suffix += 1
    return username


def _linked_agency(conn, data: dict[str, Any], tenant_id: int, agency_id: Any | None = None) -> int:
    code = _code(data.get("company_code"))
    name = str(data.get("company_name") or data.get("registered_name") or code).strip()
    if agency_id:
        row = conn.execute("SELECT id FROM agencies WHERE tenant_id = ? AND id = ?", (tenant_id, _to_int(agency_id))).fetchone()
        if row:
            conn.execute(
                """
                UPDATE agencies
                SET agency_code = ?, company_name = ?, name = ?, address = COALESCE(NULLIF(?, ''), address),
                    contact_name = COALESCE(NULLIF(?, ''), contact_name),
                    contact_phone = COALESCE(NULLIF(?, ''), contact_phone),
                    responsible_person = COALESCE(NULLIF(?, ''), responsible_person),
                    contact_email = COALESCE(NULLIF(?, ''), contact_email),
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (
                    code,
                    name,
                    name,
                    data.get("address"),
                    data.get("contact_name"),
                    data.get("contact_phone"),
                    data.get("representative_name"),
                    data.get("contact_email"),
                    tenant_id,
                    _to_int(agency_id),
                ),
            )
            return int(row["id"])
    row = conn.execute("SELECT id FROM agencies WHERE tenant_id = ? AND agency_code = ?", (tenant_id, code)).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute(
        """
        INSERT INTO agencies (
            tenant_id, agency_code, company_name, name, address, contact_name, contact_phone,
            responsible_person, contact_email, status, portal_code, is_portal_enabled, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 1, CURRENT_TIMESTAMP)
        """,
        (
            tenant_id,
            code,
            name,
            name,
            data.get("address") or "",
            data.get("contact_name") or "",
            data.get("contact_phone") or "",
            data.get("representative_name") or "",
            data.get("contact_email") or "",
            f"{code}{tenant_id}".upper(),
        ),
    )
    return int(cursor.lastrowid)


def _decode_file_payload(value: str) -> bytes:
    if "," in value and value.lower().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid_company_file_base64") from exc
    if len(raw) < 8:
        raise ValueError("company_file_too_small")
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("company_file_too_large")
    return raw


def _code(value: Any) -> str:
    raw = str(value or "").upper().strip()
    code = re.sub(r"[^A-Z0-9]", "", raw)
    return code[:12]


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

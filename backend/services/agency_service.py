from __future__ import annotations

from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


AGENCY_FIELDS = [
    "agency_code",
    "company_name",
    "name",
    "address",
    "contact_name",
    "contact_phone",
    "responsible_person",
    "contact_email",
    "fax",
    "status",
    "remark",
    "portal_code",
    "is_portal_enabled",
]

AGENCY_COLUMNS = {
    "agency_code": "TEXT",
    "company_name": "TEXT",
    "address": "TEXT",
    "responsible_person": "TEXT",
    "contact_email": "TEXT",
    "fax": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'active'",
    "remark": "TEXT",
    "portal_code": "TEXT",
    "is_portal_enabled": "INTEGER NOT NULL DEFAULT 1",
    "updated_at": "TEXT",
}


def list_agencies(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    _ensure_agency_columns()
    params = params or {}
    sql = [
        """
        SELECT id, tenant_id, agency_code, company_name, name, address,
               contact_name, contact_phone, responsible_person, contact_email,
               fax, status, remark, portal_code, is_portal_enabled,
               created_at, updated_at
        FROM agencies
        WHERE tenant_id = ? AND COALESCE(status, '') != 'deleted'
        """
    ]
    values: list[Any] = [get_current_tenant_id()]
    keyword = str(params.get("keyword") or "").strip()
    status = str(params.get("status") or "").strip()
    if status:
        sql.append("AND status = ?")
        values.append(status)
    if keyword:
        like = f"%{keyword}%"
        sql.append(
            """
            AND (
                agency_code LIKE ? OR company_name LIKE ? OR name LIKE ?
                OR address LIKE ? OR contact_name LIKE ? OR contact_phone LIKE ?
                OR responsible_person LIKE ? OR contact_email LIKE ?
            )
            """
        )
        values.extend([like] * 8)
    sql.append("ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, agency_code, name, id")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def create_agency(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_agency_columns()
    data = _normalize_agency(payload, partial=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agencies (
                tenant_id, agency_code, company_name, name, address,
                contact_name, contact_phone, responsible_person, contact_email,
                fax, status, remark, portal_code, is_portal_enabled, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                data["agency_code"],
                data["company_name"],
                data["name"],
                data["address"],
                data["contact_name"],
                data["contact_phone"],
                data["responsible_person"],
                data["contact_email"],
                data["fax"],
                data["status"],
                data["remark"],
                data["portal_code"],
                data["is_portal_enabled"],
            ),
        )
        agency_id = cursor.lastrowid
        if not data["portal_code"]:
            portal_code = f"{data['agency_code'] or 'AG'}{get_current_tenant_id()}{agency_id:04d}".upper()
            conn.execute("UPDATE agencies SET portal_code = ? WHERE id = ?", (portal_code, agency_id))
        conn.commit()
    return get_agency(agency_id) or {}


def update_agency(agency_id: int | str, payload: dict[str, Any]) -> dict[str, Any] | None:
    _ensure_agency_columns()
    data = _normalize_agency(payload, partial=True)
    if not data:
        return get_agency(agency_id)
    assignments = ", ".join([f"{key} = ?" for key in data])
    values = list(data.values()) + [agency_id, get_current_tenant_id()]
    with get_connection() as conn:
        cursor = conn.execute(
            f"""
            UPDATE agencies
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_agency(agency_id)


def delete_agency(agency_id: int | str) -> bool:
    _ensure_agency_columns()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE agencies
            SET status = 'deleted',
                is_portal_enabled = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (agency_id, get_current_tenant_id()),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_agency(agency_id: int | str) -> dict[str, Any] | None:
    _ensure_agency_columns()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, tenant_id, agency_code, company_name, name, address,
                   contact_name, contact_phone, responsible_person, contact_email,
                   fax, status, remark, portal_code, is_portal_enabled,
                   created_at, updated_at
            FROM agencies
            WHERE id = ? AND tenant_id = ?
            """,
            (agency_id, get_current_tenant_id()),
        ).fetchone()
    return dict(row) if row else None


def _normalize_agency(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field in AGENCY_FIELDS:
        if field not in payload:
            continue
        value = payload.get(field)
        if field == "is_portal_enabled":
            data[field] = 1 if value in (True, 1, "1", "true", "enabled", "active") else 0
        elif field in {"agency_code", "status"}:
            data[field] = str(value or "").strip()
        else:
            data[field] = str(value or "").strip()
    company_name = str(payload.get("company_name") or payload.get("name") or "").strip()
    name = str(payload.get("name") or payload.get("company_name") or "").strip()
    if not partial and not (company_name or name):
        raise ValueError("agency_name_required")
    if not partial:
        data.setdefault("agency_code", "D")
        data.setdefault("company_name", company_name or name)
        data.setdefault("name", name or company_name)
        data.setdefault("address", "")
        data.setdefault("contact_name", "")
        data.setdefault("contact_phone", "")
        data.setdefault("responsible_person", "")
        data.setdefault("contact_email", "")
        data.setdefault("fax", "")
        data.setdefault("status", "active")
        data.setdefault("remark", "")
        data.setdefault("portal_code", "")
        data.setdefault("is_portal_enabled", 1)
    elif "company_name" in data and "name" not in data:
        data["name"] = data["company_name"]
    elif "name" in data and "company_name" not in data:
        data["company_name"] = data["name"]
    return data


def _ensure_agency_columns() -> None:
    with get_connection() as conn:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(agencies)").fetchall()}
        for column, definition in AGENCY_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE agencies ADD COLUMN {column} {definition}")
        conn.execute(
            """
            UPDATE agencies
            SET company_name = COALESCE(NULLIF(company_name, ''), name),
                status = COALESCE(NULLIF(status, ''), 'active'),
                is_portal_enabled = COALESCE(is_portal_enabled, 1),
                updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE company_name IS NULL OR company_name = ''
               OR status IS NULL OR status = ''
               OR is_portal_enabled IS NULL
               OR updated_at IS NULL OR updated_at = ''
            """
        )
        conn.commit()

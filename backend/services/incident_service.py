from __future__ import annotations

from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


INCIDENT_TYPES = {"exception", "delay", "complaint", "accident"}
SEVERITIES = {"low", "medium", "high", "critical"}
ACTIVE_STATUSES = {"open", "processing"}


def list_incidents(filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    sql = [
        """
        SELECT i.*,
               o.oid,
               o.order_date,
               o.start_time,
               o.end_time,
               o.pickup_location,
               o.dropoff_location,
               o.dispatch_status,
               o.execution_status,
               d.name AS driver_name,
               v.plate_number
        FROM incidents i
        LEFT JOIN orders o ON o.id = i.order_id AND o.tenant_id = i.tenant_id
        LEFT JOIN assignments a ON a.id = i.assignment_id AND a.tenant_id = i.tenant_id
        LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = i.tenant_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = i.tenant_id
        WHERE i.tenant_id = ?
        """
    ]
    params: list[Any] = [get_current_tenant_id()]

    for field in ("status", "incident_type", "severity", "order_id", "assignment_id"):
        value = filters.get(field)
        if value:
            sql.append(f"AND i.{field} = ?")
            params.append(value)

    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        sql.append(
            """
            AND (
                i.title LIKE ?
                OR i.description LIKE ?
                OR i.owner LIKE ?
                OR i.resolution LIKE ?
                OR o.oid LIKE ?
                OR o.pickup_location LIKE ?
                OR o.dropoff_location LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like])

    sql.append("ORDER BY CASE i.status WHEN 'open' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END, i.created_at DESC, i.id DESC")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def create_incident(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_create(payload)
    tenant_id = get_current_tenant_id()
    data["tenant_id"] = tenant_id

    with get_connection() as conn:
        if data.get("order_id") and not _order_exists(conn, data["order_id"], tenant_id):
            raise ValueError("order_not_found")
        if data.get("assignment_id") and not _assignment_exists(conn, data["assignment_id"], tenant_id):
            raise ValueError("assignment_not_found")

        fields = list(data)
        cursor = conn.execute(
            f"INSERT INTO incidents ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})",
            [data[field] for field in fields],
        )
        incident_id = cursor.lastrowid
        if data.get("order_id"):
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'exception',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (data["order_id"], tenant_id),
            )
        conn.commit()

    incident = get_incident(str(incident_id))
    if not incident:
        raise ValueError("incident_create_failed")
    from backend.services.notification_service import notify_incident

    notify_incident(incident)
    return incident


def close_incident(incident_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ? AND tenant_id = ?",
            (_numeric_id(incident_id), tenant_id),
        ).fetchone()
        if not row:
            return None

        conn.execute(
            """
            UPDATE incidents
            SET status = 'closed',
                resolution = COALESCE(NULLIF(?, ''), resolution),
                closed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (payload.get("resolution"), row["id"], tenant_id),
        )
        if row["order_id"]:
            _restore_order_dispatch_status(conn, row["order_id"], tenant_id)
        conn.commit()
    return get_incident(str(incident_id))


def get_incident(incident_id: str) -> dict[str, Any] | None:
    rows = list_incidents({"keyword": ""})
    numeric = _numeric_id(incident_id)
    for row in rows:
        if row["id"] == numeric:
            return row
    return None


def get_incident_summary() -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    today = date.today().isoformat()
    with get_connection() as conn:
        open_total = _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ? AND status IN ('open', 'processing')", (tenant_id,))
        delay_total = _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ? AND incident_type = 'delay' AND status IN ('open', 'processing')", (tenant_id,))
        complaint_total = _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ? AND incident_type = 'complaint' AND status IN ('open', 'processing')", (tenant_id,))
        accident_total = _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ? AND incident_type = 'accident' AND status IN ('open', 'processing')", (tenant_id,))
        closed_today = _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ? AND status = 'closed' AND date(closed_at) = ?", (tenant_id, today))
        high_priority = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM incidents
            WHERE tenant_id = ?
              AND status IN ('open', 'processing')
              AND severity IN ('high', 'critical')
            """,
            (tenant_id,),
        )
    return {
        "open_incidents": open_total,
        "delay_incidents": delay_total,
        "complaint_incidents": complaint_total,
        "accident_incidents": accident_total,
        "closed_incidents_today": closed_today,
        "high_priority_incidents": high_priority,
        "recent_incidents": list_incidents({"status": "open"})[:5],
    }


def _normalize_create(payload: dict[str, Any]) -> dict[str, Any]:
    incident_type = str(payload.get("incident_type") or "exception").strip()
    severity = str(payload.get("severity") or "medium").strip()
    status = str(payload.get("status") or "open").strip()
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    if incident_type not in INCIDENT_TYPES:
        raise ValueError("invalid_incident_type")
    if severity not in SEVERITIES:
        raise ValueError("invalid_severity")
    if status not in {"open", "processing", "closed"}:
        raise ValueError("invalid_incident_status")
    if not title:
        raise ValueError("missing_required_fields:title")

    return {
        "order_id": _optional_int(payload.get("order_id")),
        "assignment_id": _optional_int(payload.get("assignment_id")),
        "incident_type": incident_type,
        "severity": severity,
        "status": status,
        "title": title,
        "description": description,
        "owner": _text(payload.get("owner")),
        "delay_minutes": _optional_int(payload.get("delay_minutes")),
        "complaint_contact": _text(payload.get("complaint_contact")),
        "accident_location": _text(payload.get("accident_location")),
        "resolution": _text(payload.get("resolution")),
    }


def _restore_order_dispatch_status(conn, order_id: int, tenant_id: int) -> None:
    active = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM incidents
        WHERE order_id = ?
          AND tenant_id = ?
          AND status IN ('open', 'processing')
        """,
        (order_id, tenant_id),
    ).fetchone()["total"]
    if active:
        return
    assignment = conn.execute(
        """
        SELECT 1
        FROM assignments
        WHERE order_id = ?
          AND tenant_id = ?
          AND status = 'active'
        LIMIT 1
        """,
        (order_id, tenant_id),
    ).fetchone()
    conn.execute(
        """
        UPDATE orders
        SET dispatch_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND tenant_id = ?
        """,
        ("assigned" if assignment else "unassigned", order_id, tenant_id),
    )


def _order_exists(conn, order_id: int, tenant_id: int) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM orders WHERE id = ? AND tenant_id = ? AND COALESCE(is_deleted, 0) = 0 LIMIT 1",
            (order_id, tenant_id),
        ).fetchone()
    )


def _assignment_exists(conn, assignment_id: int, tenant_id: int) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM assignments WHERE id = ? AND tenant_id = ? LIMIT 1",
            (assignment_id, tenant_id),
        ).fetchone()
    )


def _optional_int(value: Any) -> int | None:
    if value in ("", None):
        return None
    return int(value)


def _numeric_id(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _text(value: Any) -> str | None:
    if value in ("", None):
        return None
    return str(value).strip()


def _count(conn, sql: str, params: tuple[Any, ...]) -> int:
    return int(conn.execute(sql, params).fetchone()["total"])

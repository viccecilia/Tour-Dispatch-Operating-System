from __future__ import annotations

from typing import Any

from backend.db.database import get_connection
from backend.services.permission_service import account_scope


def resolve_tenant_filter(user: dict[str, Any], requested_tenant_id: Any = None) -> int | None:
    if account_scope(user) == "platform":
        requested = str(requested_tenant_id or "").strip()
        if not requested or requested.lower() == "all":
            return None
        return _to_int(requested)
    return _to_int(user.get("tenant_id"))


def resolve_write_tenant(user: dict[str, Any], requested_tenant_id: Any = None) -> int:
    if account_scope(user) == "platform":
        requested = _to_int(requested_tenant_id)
        if not requested:
            raise ValueError("target_tenant_required")
        return requested
    return _to_int(user.get("tenant_id")) or 1


def list_carrier_tenants() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, slug, status
            FROM tenants
            WHERE COALESCE(status, 'active') != 'deleted'
            ORDER BY CASE WHEN id = 1 THEN 0 ELSE 1 END, name, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

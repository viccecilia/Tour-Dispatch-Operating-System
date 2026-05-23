from __future__ import annotations

import json
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


def record_dispatch_mobile_audit(
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    entity_type: str | None = None,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
    summary: str | None = None,
    source_path: str | None = None,
) -> None:
    payload = payload or {}
    dispatcher_id = _to_int(payload.get("dispatcher_id"))
    dispatcher_code = _text(payload.get("dispatcher_code"))
    dispatcher_name = _text(payload.get("dispatcher_name"))
    if not dispatcher_id and not dispatcher_code and not dispatcher_name:
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO dispatch_mobile_audit_logs (
                tenant_id, dispatcher_id, dispatcher_code, dispatcher_name,
                action, entity_type, entity_id, before_json, after_json,
                summary, source_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                get_current_tenant_id(),
                dispatcher_id,
                dispatcher_code,
                dispatcher_name,
                action,
                entity_type,
                str(entity_id) if entity_id is not None else None,
                _json(before),
                _json(after),
                summary,
                source_path,
            ),
        )
        conn.commit()


def list_dispatch_mobile_audit_logs(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    sql = ["SELECT * FROM dispatch_mobile_audit_logs WHERE tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    if params.get("dispatcher_id"):
        sql.append("AND dispatcher_id = ?")
        values.append(_to_int(params.get("dispatcher_id")))
    sql.append("ORDER BY id DESC LIMIT ?")
    values.append(_limit(params.get("limit")))
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 50
    return max(1, min(parsed, 200))

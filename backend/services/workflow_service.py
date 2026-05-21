from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from backend.db.database import get_connection
from backend.services.dispatch_brain_service import recommend_dispatch
from backend.services.incident_service import create_incident
from backend.services.notification_service import create_notification
from backend.services.tenant_context import get_current_tenant_id


DEFAULT_RULES = [
    {
        "code": "unassigned_due_soon",
        "name": "Unassigned orders due soon",
        "trigger_type": "schedule_check",
        "condition_json": {"window_hours": 24},
        "action_type": "notify",
        "action_json": {"priority": "high", "link": "#dispatch"},
        "enabled": 1,
    },
    {
        "code": "missing_price",
        "name": "Missing price reminder",
        "trigger_type": "data_check",
        "condition_json": {},
        "action_type": "notify",
        "action_json": {"priority": "normal", "link": "#orders"},
        "enabled": 1,
    },
    {
        "code": "overdue_unassigned_exception",
        "name": "Overdue unassigned auto exception",
        "trigger_type": "schedule_check",
        "condition_json": {},
        "action_type": "mark_exception",
        "action_json": {"severity": "high", "incident_type": "exception"},
        "enabled": 1,
    },
    {
        "code": "dispatch_suggestion",
        "name": "Dispatch suggestion for unassigned pool",
        "trigger_type": "manual",
        "condition_json": {"limit": 5},
        "action_type": "dispatch_suggestion",
        "action_json": {"priority": "normal", "link": "#dispatch"},
        "enabled": 1,
    },
]


def list_rules() -> list[dict[str, Any]]:
    ensure_workflow_schema()
    seed_default_rules()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM workflow_rules
            WHERE tenant_id = ?
            ORDER BY enabled DESC, id ASC
            """,
            (get_current_tenant_id(),),
        ).fetchall()
    return [_decode_rule(dict(row)) for row in rows]


def create_rule(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_workflow_schema()
    code = str(payload.get("code") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not code or not name:
        raise ValueError("workflow_rule_code_name_required")
    action_type = str(payload.get("action_type") or "notify").strip()
    if action_type not in {"notify", "mark_exception", "dispatch_suggestion"}:
        raise ValueError("invalid_workflow_action_type")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workflow_rules (
                tenant_id, code, name, trigger_type, condition_json, action_type, action_json, enabled, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                code,
                name,
                payload.get("trigger_type") or "manual",
                _json(payload.get("condition_json") or {}),
                action_type,
                _json(payload.get("action_json") or {}),
                1 if payload.get("enabled", True) else 0,
            ),
        )
        conn.commit()
        rule_id = cursor.lastrowid
    return get_rule(rule_id) or {}


def update_rule(rule_id: int | str, payload: dict[str, Any]) -> dict[str, Any] | None:
    ensure_workflow_schema()
    existing = get_rule(rule_id)
    if not existing:
        return None
    allowed = {
        "name": payload.get("name"),
        "trigger_type": payload.get("trigger_type"),
        "condition_json": _json(payload.get("condition_json")) if "condition_json" in payload else None,
        "action_type": payload.get("action_type"),
        "action_json": _json(payload.get("action_json")) if "action_json" in payload else None,
        "enabled": 1 if payload.get("enabled") else 0 if "enabled" in payload else None,
    }
    updates = []
    values = []
    for field, value in allowed.items():
        if value is not None:
            updates.append(f"{field} = ?")
            values.append(value)
    if not updates:
        return existing
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE workflow_rules
            SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            [*values, _to_int(rule_id), get_current_tenant_id()],
        )
        conn.commit()
    return get_rule(rule_id)


def get_rule(rule_id: int | str) -> dict[str, Any] | None:
    ensure_workflow_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_rules WHERE tenant_id = ? AND id = ?",
            (get_current_tenant_id(), _to_int(rule_id)),
        ).fetchone()
    return _decode_rule(dict(row)) if row else None


def run_workflows(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_workflow_schema()
    seed_default_rules()
    payload = payload or {}
    requested_code = payload.get("code")
    rules = [rule for rule in list_rules() if rule.get("enabled")]
    if requested_code:
        rules = [rule for rule in rules if rule["code"] == requested_code]
    results = [_execute_rule(rule) for rule in rules]
    return {
        "success": True,
        "executed_rules": len(results),
        "results": results,
        "total_actions": sum(item.get("action_count", 0) for item in results),
    }


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    ensure_workflow_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, wr.code, wr.name
            FROM workflow_runs r
            LEFT JOIN workflow_rules wr ON wr.id = r.rule_id AND wr.tenant_id = r.tenant_id
            WHERE r.tenant_id = ?
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            (get_current_tenant_id(), max(1, min(int(limit or 50), 200))),
        ).fetchall()
    return [dict(row) | {"result": _loads(row["result_json"])} for row in rows]


def _execute_rule(rule: dict[str, Any]) -> dict[str, Any]:
    code = rule["code"]
    if code == "unassigned_due_soon":
        result = _rule_unassigned_due_soon(rule)
    elif code == "missing_price":
        result = _rule_missing_price(rule)
    elif code == "overdue_unassigned_exception":
        result = _rule_overdue_unassigned_exception(rule)
    elif code == "dispatch_suggestion":
        result = _rule_dispatch_suggestion(rule)
    else:
        result = {"rule_code": code, "action_count": 0, "items": [], "message": "no_executor"}
    _record_run(rule["id"], result)
    return result


def _rule_unassigned_due_soon(rule: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, oid, order_date, start_time, pickup_location, dropoff_location
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND dispatch_status = 'unassigned'
              AND order_date <= date(?, '+1 day')
            ORDER BY order_date ASC, start_time ASC
            LIMIT 30
            """,
            (get_current_tenant_id(), today),
        ).fetchall()
    items = []
    for row in rows:
        order = dict(row)
        notification = create_notification(
            {
                "notification_type": "workflow_reminder",
                "title": f"未派车订单即将执行: {order.get('oid') or order['id']}",
                "body": f"{order.get('order_date')} {order.get('start_time') or ''} {order.get('pickup_location')} -> {order.get('dropoff_location')}",
                "priority": rule["action_json"].get("priority", "high"),
                "link": rule["action_json"].get("link", "#dispatch"),
                "source_type": "workflow",
                "source_id": f"{rule['code']}:{order['id']}",
            }
        )
        items.append({"order_id": order["id"], "notification_id": notification.get("id")})
    return {"rule_code": rule["code"], "action_type": rule["action_type"], "action_count": len(items), "items": items}


def _rule_missing_price(rule: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, oid, order_date, pickup_location, dropoff_location
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND (price IS NULL OR price = 0)
            ORDER BY order_date DESC, id DESC
            LIMIT 30
            """,
            (get_current_tenant_id(),),
        ).fetchall()
    items = []
    for row in rows:
        order = dict(row)
        notification = create_notification(
            {
                "notification_type": "workflow_reminder",
                "title": f"订单缺少价格: {order.get('oid') or order['id']}",
                "body": f"{order.get('order_date')} {order.get('pickup_location')} -> {order.get('dropoff_location')}",
                "priority": rule["action_json"].get("priority", "normal"),
                "link": rule["action_json"].get("link", "#orders"),
                "source_type": "workflow",
                "source_id": f"{rule['code']}:{order['id']}",
            }
        )
        items.append({"order_id": order["id"], "notification_id": notification.get("id")})
    return {"rule_code": rule["code"], "action_type": rule["action_type"], "action_count": len(items), "items": items}


def _rule_overdue_unassigned_exception(rule: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    now_time = datetime.now().strftime("%H:%M")
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, oid, order_date, start_time
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND dispatch_status = 'unassigned'
              AND (order_date < ? OR (order_date = ? AND COALESCE(start_time, '23:59') < ?))
            ORDER BY order_date ASC, start_time ASC
            LIMIT 20
            """,
            (get_current_tenant_id(), today, today, now_time),
        ).fetchall()
    items = []
    for row in rows:
        order = dict(row)
        if _incident_exists(order["id"], rule["code"]):
            continue
        incident = create_incident(
            {
                "order_id": order["id"],
                "incident_type": rule["action_json"].get("incident_type", "exception"),
                "severity": rule["action_json"].get("severity", "high"),
                "title": f"Workflow overdue unassigned: {order.get('oid') or order['id']}",
                "description": f"Rule {rule['code']} marked this order because it is overdue and still unassigned.",
                "owner": "workflow",
            }
        )
        items.append({"order_id": order["id"], "incident_id": incident.get("id")})
    return {"rule_code": rule["code"], "action_type": rule["action_type"], "action_count": len(items), "items": items}


def _rule_dispatch_suggestion(rule: dict[str, Any]) -> dict[str, Any]:
    limit = int(rule["condition_json"].get("limit") or 5)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND dispatch_status = 'unassigned'
            ORDER BY order_date ASC, start_time ASC, id ASC
            LIMIT ?
            """,
            (get_current_tenant_id(), max(1, min(limit, 20))),
        ).fetchall()
    order_ids = [row["id"] for row in rows]
    if not order_ids:
        return {"rule_code": rule["code"], "action_type": rule["action_type"], "action_count": 0, "items": []}
    suggestion = recommend_dispatch(order_ids)
    top = (suggestion.get("recommendations") or [])[:1]
    notification = create_notification(
        {
            "notification_type": "workflow_suggestion",
            "title": f"派车建议已生成: {len(order_ids)} 单",
            "body": "; ".join((top[0].get("reasons") or [])[:2]) if top else "可打开派车工作台查看建议。",
            "priority": rule["action_json"].get("priority", "normal"),
            "link": rule["action_json"].get("link", "#dispatch"),
            "source_type": "workflow",
            "source_id": f"{rule['code']}:{','.join(str(item) for item in order_ids)}",
        }
    )
    return {
        "rule_code": rule["code"],
        "action_type": rule["action_type"],
        "action_count": 1,
        "items": [{"order_ids": order_ids, "notification_id": notification.get("id"), "recommendation_count": len(suggestion.get("recommendations") or [])}],
    }


def ensure_workflow_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL DEFAULT 'manual',
                condition_json TEXT NOT NULL DEFAULT '{}',
                action_type TEXT NOT NULL DEFAULT 'notify',
                action_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                rule_id INTEGER,
                result_json TEXT NOT NULL DEFAULT '{}',
                action_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def seed_default_rules() -> None:
    ensure_workflow_schema()
    with get_connection() as conn:
        for rule in DEFAULT_RULES:
            conn.execute(
                """
                INSERT INTO workflow_rules (
                    tenant_id, code, name, trigger_type, condition_json, action_type, action_json, enabled, updated_at
                )
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                    SELECT 1 FROM workflow_rules WHERE tenant_id = ? AND code = ?
                )
                """,
                (
                    get_current_tenant_id(),
                    rule["code"],
                    rule["name"],
                    rule["trigger_type"],
                    _json(rule["condition_json"]),
                    rule["action_type"],
                    _json(rule["action_json"]),
                    rule["enabled"],
                    get_current_tenant_id(),
                    rule["code"],
                ),
            )
        conn.commit()


def _record_run(rule_id: int, result: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO workflow_runs (tenant_id, rule_id, result_json, action_count)
            VALUES (?, ?, ?, ?)
            """,
            (get_current_tenant_id(), rule_id, _json(result), int(result.get("action_count") or 0)),
        )
        conn.commit()


def _incident_exists(order_id: int, rule_code: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM incidents
            WHERE tenant_id = ?
              AND order_id = ?
              AND owner = 'workflow'
              AND title LIKE ?
              AND status IN ('open', 'processing')
            LIMIT 1
            """,
            (get_current_tenant_id(), order_id, f"%{rule_code}%"),
        ).fetchone()
    return bool(row)


def _decode_rule(row: dict[str, Any]) -> dict[str, Any]:
    row["condition_json"] = _loads(row.get("condition_json"))
    row["action_json"] = _loads(row.get("action_json"))
    row["enabled"] = bool(row.get("enabled"))
    return row


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _loads(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1

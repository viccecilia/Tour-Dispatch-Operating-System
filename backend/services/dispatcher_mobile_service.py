from __future__ import annotations

from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.auth_service import authenticate, authenticate_phone
from backend.services.dispatch_mobile_audit_service import record_dispatch_mobile_audit
from backend.services.parser_service import get_draft, parse_batch_text_to_drafts, parse_text_to_draft, update_draft
from backend.services.tenant_context import get_current_tenant_id


def login_dispatcher(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("phone"):
        result = authenticate_phone(
            payload.get("phone", ""),
            payload.get("password", ""),
            payload.get("wx_openid"),
            payload.get("wx_unionid"),
            payload.get("client_type", "dispatch_miniapp"),
        )
    else:
        result = authenticate(payload.get("username", ""), payload.get("password", ""))
    if not result:
        return None
    if result.get("error"):
        return result

    user = result["user"]
    if user.get("role") not in {"admin", "dispatcher", "operations_manager"}:
        return None

    dispatcher = _dispatcher_from_user(user)
    return {
        "token": result["token"],
        "dispatcher": dispatcher,
        "dispatcher_session": {
            "dispatcher_id": dispatcher["dispatcher_id"],
            "dispatcher_code": dispatcher["dispatcher_code"],
            "dispatcher_name": dispatcher["dispatcher_name"],
            "dispatcher_role": dispatcher["dispatcher_role"],
            "tenant_id": dispatcher["tenant_id"],
        },
    }


def get_dispatcher_context(params: dict[str, str]) -> dict[str, Any]:
    dispatcher_id = _to_int(params.get("dispatcher_id")) or 1
    dispatcher = _load_dispatcher(dispatcher_id)
    return {
        "ok": True,
        "dispatcher_context": dispatcher,
        "dispatcher_session": {
            "dispatcher_id": dispatcher["dispatcher_id"],
            "dispatcher_code": dispatcher["dispatcher_code"],
            "dispatcher_name": dispatcher["dispatcher_name"],
            "dispatcher_role": dispatcher["dispatcher_role"],
            "tenant_id": dispatcher["tenant_id"],
        },
    }


def get_dispatcher_dashboard(params: dict[str, str]) -> dict[str, Any]:
    dispatcher_id = _to_int(params.get("dispatcher_id")) or 1
    today = date.today().isoformat()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        counts = {
            "today_orders": _count(conn, "orders", "tenant_id = ? AND COALESCE(is_deleted, 0) = 0 AND order_date = ? AND created_by_dispatcher_id = ?", [tenant_id, today, dispatcher_id]),
            "unassigned_orders": _count(conn, "orders", "tenant_id = ? AND COALESCE(is_deleted, 0) = 0 AND dispatch_status = 'unassigned' AND created_by_dispatcher_id = ?", [tenant_id, dispatcher_id]),
            "drafts_pending": _count(conn, "order_drafts", "tenant_id = ? AND parse_status != 'confirmed' AND created_by_dispatcher_id = ?", [tenant_id, dispatcher_id]),
            "active_assignments": _count(conn, "assignments", "tenant_id = ? AND status = 'active'", [tenant_id]),
            "notifications_unread": _count(conn, "notifications", "tenant_id = ? AND status = 'unread'", [tenant_id]),
            "online_drivers": _count(conn, "location_logs", "tenant_id = ? AND reported_at >= DATETIME('now', '-30 minutes')", [tenant_id]),
            "exception_orders": _count(conn, "incidents", "tenant_id = ? AND status != 'closed'", [tenant_id]),
            "pending_confirmations": _count(conn, "assignments", "tenant_id = ? AND status = 'active' AND COALESCE(execution_status, 'assigned') = 'assigned'", [tenant_id]),
        }
        fleet_status = _fleet_status(conn, tenant_id)
        latest_orders = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, oid, order_date, start_time, pickup_location, dropoff_location, dispatch_status,
                       created_by_dispatcher, created_by_dispatcher_code
                FROM orders
                WHERE tenant_id = ? AND COALESCE(is_deleted, 0) = 0
                  AND created_by_dispatcher_id = ?
                ORDER BY id DESC
                LIMIT 5
                """,
                (tenant_id, dispatcher_id),
            ).fetchall()
        ]
    return {
        "ok": True,
        "dispatcher_id": dispatcher_id,
        "date": today,
        "counts": counts,
        "fleet_status": fleet_status,
        "latest_orders": latest_orders,
    }


def list_dispatcher_unassigned_orders(params: dict[str, str]) -> list[dict[str, Any]]:
    dispatcher_id = _to_int(params.get("dispatcher_id")) or 1
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM orders
                WHERE tenant_id = ?
                  AND COALESCE(is_deleted, 0) = 0
                  AND dispatch_status = 'unassigned'
                  AND created_by_dispatcher_id = ?
                ORDER BY order_date ASC, start_time ASC, id ASC
                """,
                (tenant_id, dispatcher_id),
            ).fetchall()
        ]


def get_dispatcher_notifications(params: dict[str, str]) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM notifications
                WHERE tenant_id = ?
                  AND target_role IN ('dispatcher', 'finance', 'driver')
                ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                         created_at DESC, id DESC
                LIMIT 100
                """,
                (tenant_id,),
            ).fetchall()
        ]
    return {"notifications": rows}


def get_shared_runtime_state(params: dict[str, str] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        counts = {
            "orders": _count(conn, "orders", "tenant_id = ? AND COALESCE(is_deleted, 0) = 0", [tenant_id]),
            "drafts": _count(conn, "order_drafts", "tenant_id = ?", [tenant_id]),
            "assignments": _count(conn, "assignments", "tenant_id = ?", [tenant_id]),
            "notifications": _count(conn, "notifications", "tenant_id = ?", [tenant_id]),
        }
        samples = {
            "latest_order": _one(conn, "SELECT id, oid, dispatch_status, updated_at FROM orders WHERE tenant_id = ? ORDER BY id DESC LIMIT 1", [tenant_id]),
            "latest_draft": _one(conn, "SELECT id, oid, parse_status, updated_at FROM order_drafts WHERE tenant_id = ? ORDER BY id DESC LIMIT 1", [tenant_id]),
            "latest_assignment": _one(conn, "SELECT id, order_id, driver_id, vehicle_id, status, updated_at FROM assignments WHERE tenant_id = ? ORDER BY id DESC LIMIT 1", [tenant_id]),
            "latest_notification": _one(conn, "SELECT id, title, status, updated_at FROM notifications WHERE tenant_id = ? ORDER BY id DESC LIMIT 1", [tenant_id]),
        }
    return {"ok": True, "shared_database": "sqlite", "tables": counts, "samples": samples}


def parse_dispatcher_text(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text", "")
    dispatcher = _payload_dispatcher(payload)
    if payload.get("batch", True):
        drafts = parse_batch_text_to_drafts(text, "text")
    else:
        drafts = [parse_text_to_draft(text, "text")]
    _mark_drafts_dispatcher([draft["id"] for draft in drafts if draft.get("id")], dispatcher)
    _mark_drafts_source([draft["id"] for draft in drafts if draft.get("id")], "mobile_dispatch")
    refreshed = _load_drafts([draft["id"] for draft in drafts if draft.get("id")])
    record_dispatch_mobile_audit(
        "mobile_parse",
        dispatcher,
        entity_type="order_draft",
        entity_id=",".join(str(draft.get("id")) for draft in refreshed),
        after={"count": len(refreshed)},
        summary=f"Mobile parsed {len(refreshed)} draft(s)",
        source_path="/api/dispatch-mobile/parser/text",
    )
    return {"ok": True, "count": len(refreshed), "drafts": refreshed, "dispatcher_context": dispatcher}


def update_dispatcher_draft(draft_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not get_draft(draft_id):
        return None
    dispatcher = _payload_dispatcher(payload)
    editable = dict(payload)
    editable["source_channel"] = payload.get("source_channel") or "mobile_dispatch"
    draft = update_draft(draft_id, editable)
    if not draft:
        return None
    _mark_drafts_dispatcher([int(draft["id"])], dispatcher)
    _mark_drafts_source([int(draft["id"])], "mobile_dispatch")
    refreshed = _load_drafts([int(draft["id"])])
    updated = refreshed[0] if refreshed else draft
    record_dispatch_mobile_audit(
        "mobile_draft_update",
        dispatcher,
        entity_type="order_draft",
        entity_id=draft_id,
        after=updated,
        summary=f"Mobile updated draft {draft_id}",
        source_path=f"/api/dispatch-mobile/drafts/{draft_id}",
    )
    return updated


def mark_order_dispatcher_context(order_id: int | str, payload: dict[str, Any], update_only: bool = False) -> dict[str, Any] | None:
    dispatcher = _payload_dispatcher(payload)
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM orders WHERE id = ? AND tenant_id = ?", (_to_int(order_id), get_current_tenant_id())).fetchone()
        if not row:
            return None
        if update_only:
            conn.execute(
                """
                UPDATE orders
                SET updated_by_dispatcher = ?,
                    updated_by_dispatcher_id = ?,
                    updated_by_dispatcher_code = ?,
                    source_channel = COALESCE(source_channel, 'mobile_dispatch'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    dispatcher["dispatcher_name"],
                    dispatcher["dispatcher_id"],
                    dispatcher["dispatcher_code"],
                    row["id"],
                    get_current_tenant_id(),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE orders
                SET created_by_dispatcher = COALESCE(created_by_dispatcher, ?),
                    created_by_dispatcher_id = COALESCE(created_by_dispatcher_id, ?),
                    created_by_dispatcher_code = COALESCE(created_by_dispatcher_code, ?),
                    updated_by_dispatcher = ?,
                    updated_by_dispatcher_id = ?,
                    updated_by_dispatcher_code = ?,
                    source_channel = COALESCE(source_channel, 'mobile_dispatch'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    dispatcher["dispatcher_name"],
                    dispatcher["dispatcher_id"],
                    dispatcher["dispatcher_code"],
                    dispatcher["dispatcher_name"],
                    dispatcher["dispatcher_id"],
                    dispatcher["dispatcher_code"],
                    row["id"],
                    get_current_tenant_id(),
                ),
            )
        conn.commit()
        order = conn.execute("SELECT * FROM orders WHERE id = ? AND tenant_id = ?", (row["id"], get_current_tenant_id())).fetchone()
    return dict(order) if order else None


def _fleet_status(conn, tenant_id: int) -> dict[str, int]:
    active_rows = conn.execute(
        """
        SELECT d.id, a.execution_status, o.end_time, o.order_date
        FROM drivers d
        LEFT JOIN assignments a ON a.driver_id = d.id AND a.status = 'active' AND a.tenant_id = ?
        LEFT JOIN orders o ON o.id = a.order_id AND o.tenant_id = ?
        WHERE d.tenant_id = ?
        """,
        (tenant_id, tenant_id, tenant_id),
    ).fetchall()
    latest_locations = {
        row["driver_id"]
        for row in conn.execute(
            """
            SELECT driver_id
            FROM location_logs
            WHERE tenant_id = ?
              AND driver_id IS NOT NULL
              AND reported_at >= DATETIME('now', '-30 minutes')
            """,
            (tenant_id,),
        ).fetchall()
    }
    working_status = {"confirmed", "departed", "arrived", "in_service"}
    working = {row["id"] for row in active_rows if (row["execution_status"] or "assigned") in working_status}
    assigned = {row["id"] for row in active_rows if (row["execution_status"] or "assigned") == "assigned"}
    online = latest_locations
    all_driver_ids = {row["id"] for row in active_rows}
    return {
        "online": len(online),
        "working": len(working),
        "ending_soon": 0,
        "offline": max(0, len(all_driver_ids - online)),
        "pending_confirmation": len(assigned),
    }


def _dispatcher_from_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "dispatcher_id": int(user.get("id") or 1),
        "dispatcher_code": f"D{int(user.get('id') or 1):03d}",
        "dispatcher_name": user.get("display_name") or user.get("username") or "调度员",
        "dispatcher_role": user.get("role") or "dispatcher",
        "tenant_id": int(user.get("tenant_id") or 1),
    }


def _load_dispatcher(dispatcher_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, tenant_id, username, role, display_name
            FROM users
            WHERE id = ? AND is_active = 1
            """,
            (dispatcher_id,),
        ).fetchone()
    if user:
        return _dispatcher_from_user(dict(user))
    return {
        "dispatcher_id": dispatcher_id,
        "dispatcher_code": f"D{dispatcher_id:03d}",
        "dispatcher_name": "移动调度",
        "dispatcher_role": "dispatcher",
        "tenant_id": get_current_tenant_id(),
    }


def _payload_dispatcher(payload: dict[str, Any]) -> dict[str, Any]:
    dispatcher_id = _to_int(payload.get("dispatcher_id")) or 1
    loaded = _load_dispatcher(dispatcher_id)
    return {
        "dispatcher_id": dispatcher_id,
        "dispatcher_code": payload.get("dispatcher_code") or loaded["dispatcher_code"],
        "dispatcher_name": payload.get("dispatcher_name") or loaded["dispatcher_name"],
        "dispatcher_role": payload.get("dispatcher_role") or loaded["dispatcher_role"],
        "tenant_id": _to_int(payload.get("tenant_id")) or loaded["tenant_id"],
    }


def _mark_drafts_dispatcher(draft_ids: list[int], dispatcher: dict[str, Any]) -> None:
    if not draft_ids:
        return
    placeholders = ",".join(["?"] * len(draft_ids))
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE order_drafts
            SET created_by_dispatcher = COALESCE(created_by_dispatcher, ?),
                created_by_dispatcher_id = COALESCE(created_by_dispatcher_id, ?),
                created_by_dispatcher_code = COALESCE(created_by_dispatcher_code, ?),
                updated_by_dispatcher = ?,
                updated_by_dispatcher_id = ?,
                updated_by_dispatcher_code = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
              AND tenant_id = ?
            """,
            [
                dispatcher["dispatcher_name"],
                dispatcher["dispatcher_id"],
                dispatcher["dispatcher_code"],
                dispatcher["dispatcher_name"],
                dispatcher["dispatcher_id"],
                dispatcher["dispatcher_code"],
                *draft_ids,
                get_current_tenant_id(),
            ],
        )
        conn.commit()


def _mark_drafts_source(draft_ids: list[int], source_channel: str) -> None:
    if not draft_ids:
        return
    placeholders = ",".join(["?"] * len(draft_ids))
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE order_drafts
            SET source_channel = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
              AND tenant_id = ?
            """,
            [source_channel, *draft_ids, get_current_tenant_id()],
        )
        conn.commit()


def _load_drafts(draft_ids: list[int]) -> list[dict[str, Any]]:
    if not draft_ids:
        return []
    placeholders = ",".join(["?"] * len(draft_ids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM order_drafts WHERE id IN ({placeholders}) AND tenant_id = ? ORDER BY id",
            [*draft_ids, get_current_tenant_id()],
        ).fetchall()
    return [dict(row) for row in rows]


def _count(conn, table: str, where: str, params: list[Any]) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params).fetchone()["c"])


def _one(conn, sql: str, params: list[Any]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

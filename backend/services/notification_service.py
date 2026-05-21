from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


PRIORITIES = {"low", "normal", "high", "critical"}
STATUSES = {"unread", "read"}


def create_notification(payload: dict[str, Any]) -> dict[str, Any]:
    notification_type = str(payload.get("notification_type") or payload.get("type") or "system").strip()
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("notification_title_required")
    priority = str(payload.get("priority") or "normal").strip()
    if priority not in PRIORITIES:
        priority = "normal"
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        source_type = _text(payload.get("source_type"))
        source_id = _text(payload.get("source_id"))
        if source_type and source_id:
            existing = conn.execute(
                """
                SELECT id
                FROM notifications
                WHERE tenant_id = ?
                  AND source_type = ?
                  AND source_id = ?
                LIMIT 1
                """,
                (tenant_id, source_type, source_id),
            ).fetchone()
            if existing:
                return get_notification(existing["id"]) or {}
        cursor = conn.execute(
            """
            INSERT INTO notifications (
                tenant_id, notification_type, title, body, priority, status,
                target_role, link, source_type, source_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'unread', ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                tenant_id,
                notification_type,
                title,
                _text(payload.get("body")),
                priority,
                _text(payload.get("target_role")),
                _text(payload.get("link")),
                source_type,
                source_id,
            ),
        )
        conn.commit()
        notification_id = cursor.lastrowid
    return get_notification(notification_id) or {}


def list_notifications(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    sync_resource_notifications()
    sql = [
        """
        SELECT *
        FROM notifications
        WHERE tenant_id = ?
        """
    ]
    values: list[Any] = [get_current_tenant_id()]
    if params.get("status") in STATUSES:
        sql.append("AND status = ?")
        values.append(params["status"])
    if params.get("notification_type"):
        sql.append("AND notification_type = ?")
        values.append(params["notification_type"])
    sql.append("ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, created_at DESC, id DESC LIMIT ?")
    values.append(_limit(params.get("limit")))
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def get_notification(notification_id: int | str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE tenant_id = ? AND id = ?",
            (get_current_tenant_id(), _to_int(notification_id)),
        ).fetchone()
    return dict(row) if row else None


def mark_notification_read(notification_id: int | str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM notifications WHERE tenant_id = ? AND id = ?",
            (get_current_tenant_id(), _to_int(notification_id)),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE notifications
            SET status = 'read',
                read_at = COALESCE(read_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (get_current_tenant_id(), row["id"]),
        )
        conn.commit()
    return get_notification(notification_id)


def mark_all_notifications_read() -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE notifications
            SET status = 'read',
                read_at = COALESCE(read_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND status = 'unread'
            """,
            (get_current_tenant_id(),),
        )
        conn.commit()
    return {"updated": cursor.rowcount}


def list_driver_notifications(driver_id: Any, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    driver_id_int = _to_int(driver_id)
    if driver_id_int <= 0:
        return []
    sync_driver_task_notifications(driver_id_int)
    sql = [
        """
        SELECT *
        FROM notifications
        WHERE tenant_id = ?
          AND target_role = 'driver'
          AND source_id LIKE ?
        """
    ]
    values: list[Any] = [get_current_tenant_id(), f"{driver_id_int}:%"]
    if params.get("status") in STATUSES:
        sql.append("AND status = ?")
        values.append(params["status"])
    sql.append("ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, created_at DESC, id DESC LIMIT ?")
    values.append(_limit(params.get("limit")))
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), values).fetchall()]


def mark_driver_notification_read(driver_id: Any, notification_id: Any) -> dict[str, Any] | None:
    driver_id_int = _to_int(driver_id)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM notifications
            WHERE tenant_id = ?
              AND id = ?
              AND target_role = 'driver'
              AND source_id LIKE ?
            """,
            (get_current_tenant_id(), _to_int(notification_id), f"{driver_id_int}:%"),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE notifications
            SET status = 'read',
                read_at = COALESCE(read_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (get_current_tenant_id(), row["id"]),
        )
        conn.commit()
    return get_notification(notification_id)


def sync_driver_task_notifications(driver_id: int) -> None:
    today = date.today().isoformat()
    now = datetime.now()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.id AS assignment_id,
                a.driver_id,
                a.execution_status,
                o.oid,
                o.order_date,
                o.start_time,
                o.end_time,
                o.pickup_location,
                o.dropoff_location
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            WHERE a.tenant_id = ?
              AND o.tenant_id = ?
              AND a.status = 'active'
              AND a.driver_id = ?
              AND COALESCE(o.is_deleted, 0) = 0
              AND o.order_date = ?
            """,
            (get_current_tenant_id(), get_current_tenant_id(), driver_id, today),
        ).fetchall()
    for row in rows:
        item = dict(row)
        start_dt = _assignment_start_datetime(item)
        if not start_dt:
            continue
        minutes_to_start = int((start_dt - now).total_seconds() // 60)
        if 0 <= minutes_to_start <= 60:
            create_notification(
                {
                    "notification_type": "upcoming_start",
                    "title": "订单即将开始",
                    "body": f"{item.get('start_time')} {item.get('pickup_location')} -> {item.get('dropoff_location')}",
                    "priority": "high" if minutes_to_start <= 20 else "normal",
                    "target_role": "driver",
                    "link": "#driver",
                    "source_type": "driver_upcoming_start",
                    "source_id": f"{driver_id}:upcoming:{item.get('assignment_id')}",
                }
            )
        if item.get("execution_status") in {"assigned", "confirmed"} and now > start_dt + timedelta(minutes=15):
            create_notification(
                {
                    "notification_type": "delay_risk",
                    "title": "订单可能延误",
                    "body": f"{item.get('oid') or item.get('assignment_id')} 已到开始时间，请尽快更新状态。",
                    "priority": "high",
                    "target_role": "driver",
                    "link": "#driver",
                    "source_type": "driver_delay_risk",
                    "source_id": f"{driver_id}:delay:{item.get('assignment_id')}",
                }
            )


def get_notification_summary() -> dict[str, Any]:
    sync_resource_notifications()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'unread' THEN 1 ELSE 0 END) AS unread,
                   SUM(CASE WHEN status = 'unread' AND priority IN ('high', 'critical') THEN 1 ELSE 0 END) AS urgent
            FROM notifications
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "unread": int(row["unread"] or 0),
        "urgent": int(row["urgent"] or 0),
        "latest": list_notifications({"limit": 8}),
    }


def sync_resource_notifications() -> None:
    from backend.services.resource_service import get_resource_reminders

    reminders = get_resource_reminders()
    for alert in reminders.get("alerts", []):
        status = alert.get("status")
        priority = "critical" if status == "expired" else "high" if status in {"upcoming", "maintenance", "invalid"} else "normal"
        source_id = f"{alert.get('type')}:{alert.get('id')}:{alert.get('field')}:{alert.get('date') or alert.get('status')}"
        create_notification(
            {
                "notification_type": "resource_reminder",
                "title": f"{alert.get('label') or '资源提醒'}：{alert.get('name')}",
                "body": alert.get("message"),
                "priority": priority,
                "target_role": "admin",
                "link": "#vehicles",
                "source_type": "resource_alert",
                "source_id": source_id,
            }
        )


def notify_dispatch_assigned(assignment_ids: list[int], order_ids: list[int], driver_id: int | None = None, driver_name: str | None = None, plate_number: str | None = None) -> None:
    if not assignment_ids:
        return
    create_notification(
        {
            "notification_type": "dispatch_assigned",
            "title": f"已派车 {len(order_ids)} 单",
            "body": f"司机 {driver_name or '-'} / 车辆 {plate_number or '-'}",
            "priority": "normal",
            "target_role": "dispatcher",
            "link": "#dispatch",
            "source_type": "assignment_batch",
            "source_id": ",".join(str(item) for item in assignment_ids),
        }
    )
    if driver_id:
        create_notification(
            {
                "notification_type": "new_order",
                "title": f"你有 {len(order_ids)} 个新任务",
                "body": f"车辆 {plate_number or '-'}，请打开今日任务确认。",
                "priority": "high",
                "target_role": "driver",
                "link": "#driver",
                "source_type": "driver_assignment",
                "source_id": f"{driver_id}:assigned:{','.join(str(item) for item in assignment_ids)}",
            }
        )


def notify_driver_report(report_id: int, report_type: str, assignment_id: int, driver_id: int) -> None:
    create_notification(
        {
            "notification_type": "driver_report",
            "title": f"司机报备：{report_type}",
            "body": f"派车记录 #{assignment_id}，司机 #{driver_id}",
            "priority": "normal",
            "target_role": "dispatcher",
            "link": "#driver-monitor",
            "source_type": "driver_report",
            "source_id": str(report_id),
        }
    )


def notify_incident(incident: dict[str, Any]) -> None:
    create_notification(
        {
            "notification_type": "incident",
            "title": f"异常：{incident.get('title')}",
            "body": incident.get("description") or incident.get("incident_type"),
            "priority": "critical" if incident.get("severity") == "critical" else "high",
            "target_role": "dispatcher",
            "link": "#incidents",
            "source_type": "incident",
            "source_id": str(incident.get("id")),
        }
    )


def _limit(value: Any) -> int:
    try:
        return max(1, min(int(value or 50), 200))
    except (TypeError, ValueError):
        return 50


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _text(value: Any) -> str | None:
    if value in ("", None):
        return None
    return str(value).strip()


def _assignment_start_datetime(item: dict[str, Any]) -> datetime | None:
    try:
        raw = f"{item.get('order_date')} {item.get('start_time') or '00:00'}"
        return datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None

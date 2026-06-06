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
    sync_operation_notifications()
    target_role = str(params.get("target_role") or "").strip()
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
    if target_role:
        sql.append("AND target_role = ?")
        values.append(target_role)
    else:
        sql.append("AND COALESCE(target_role, '') != 'driver'")
        sql.append("AND notification_type != 'dispatch_assigned'")
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
            WHERE tenant_id = ?
              AND status = 'unread'
              AND COALESCE(target_role, '') != 'driver'
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
    sync_dispatch_runtime_notifications()
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
        return [_normalize_driver_notification(dict(row)) for row in conn.execute(" ".join(sql), values).fetchall()]


def _normalize_driver_notification(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("notification_type") == "new_order" and row.get("source_type") == "driver_assignment":
        source_id = str(row.get("source_id") or "")
        assignment_part = source_id.rsplit(":", 1)[-1] if ":" in source_id else ""
        count = len([item for item in assignment_part.split(",") if item.strip()]) or 1
        row["title"] = f"你有 {count} 个待确认派单"
        row["body"] = row.get("body") or "请在司机首页确认接单。"
    return row


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
    sync_operation_notifications()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'unread' THEN 1 ELSE 0 END) AS unread,
                   SUM(CASE WHEN status = 'unread' AND priority IN ('high', 'critical') THEN 1 ELSE 0 END) AS urgent
            FROM notifications
            WHERE tenant_id = ?
              AND COALESCE(target_role, '') != 'driver'
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


def sync_operation_notifications() -> None:
    sync_resource_notifications()
    sync_dispatch_runtime_notifications()


def sync_dispatch_runtime_notifications() -> None:
    today = date.today().isoformat()
    now = datetime.now()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    a.id AS assignment_id,
                    a.driver_id,
                    a.vehicle_id,
                    a.execution_status,
                    a.status AS assignment_status,
                    o.id AS order_id,
                    o.oid,
                    o.order_date,
                    o.start_time,
                    o.end_time,
                    o.pickup_location,
                    o.dropoff_location,
                    d.name AS driver_name,
                    v.plate_number,
                    COALESCE(ev.photo_count, 0) AS photo_count,
                    COALESCE(ex.pending_expense_count, 0) AS pending_expense_count,
                    COALESCE(ex.pending_expense_amount, 0) AS pending_expense_amount
                FROM assignments a
                JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
                LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
                LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
                LEFT JOIN (
                    SELECT assignment_id, tenant_id, COUNT(*) AS photo_count
                    FROM driver_evidence_uploads
                    GROUP BY assignment_id, tenant_id
                ) ev ON ev.assignment_id = a.id AND ev.tenant_id = a.tenant_id
                LEFT JOIN (
                    SELECT assignment_id, tenant_id, COUNT(*) AS pending_expense_count, SUM(amount) AS pending_expense_amount
                    FROM driver_expense_reports
                    WHERE submit_status IN ('unsubmitted', 'in_hand', 'submitted')
                    GROUP BY assignment_id, tenant_id
                ) ex ON ex.assignment_id = a.id AND ex.tenant_id = a.tenant_id
                WHERE a.tenant_id = ?
                  AND a.status = 'active'
                  AND COALESCE(o.is_deleted, 0) = 0
                  AND o.order_date >= date(?, '-1 day')
                  AND o.order_date <= date(?, '+1 day')
                ORDER BY o.order_date ASC, o.start_time ASC, a.id ASC
                LIMIT 500
                """,
                (tenant_id, today, today),
            ).fetchall()
        ]
    for item in rows:
        start_dt = _assignment_start_datetime(item)
        end_dt = _assignment_end_datetime(item) or start_dt
        status = item.get("execution_status") or "assigned"
        route = f"{item.get('pickup_location') or '-'} -> {item.get('dropoff_location') or '-'}"
        order_label = item.get("oid") or f"#{item.get('assignment_id')}"
        driver_id = _to_int(item.get("driver_id"))

        if status == "assigned":
            _create_runtime_pair(
                driver_id,
                "unconfirmed_order",
                "订单未确认",
                f"{order_label} {item.get('order_date')} {item.get('start_time') or ''} {route}",
                "high" if _is_due(start_dt, now, minutes_before=720) else "normal",
                item,
                "unconfirmed",
            )

        if status in {"assigned", "confirmed"} and _is_due(start_dt, now, minutes_before=90):
            _create_runtime_pair(
                driver_id,
                "not_departed",
                "司机未出库",
                f"{order_label} 即将开始，司机 {item.get('driver_name') or '-'} 尚未出库。",
                "high",
                item,
                "not_departed",
            )

        if status == "departed" and _is_due(start_dt, now, minutes_after=15):
            _create_runtime_pair(
                driver_id,
                "not_arrived",
                "司机未到达上车点",
                f"{order_label} 已出库但未到达上车点：{item.get('pickup_location') or '-'}",
                "high",
                item,
                "not_arrived",
            )

        if status in {"arrived", "in_service", "completed", "returned"} and _to_int(item.get("photo_count")) == 0:
            _create_runtime_pair(
                driver_id,
                "missing_photo",
                "未上传执行照片",
                f"{order_label} 已进入执行流程，但还没有照片记录。",
                "normal",
                item,
                "missing_photo",
            )

        if _to_int(item.get("pending_expense_count")) > 0:
            _create_runtime_pair(
                driver_id,
                "pending_driver_expense",
                "有未提交费用",
                f"{order_label} 有 {item.get('pending_expense_count')} 笔费用待处理，合计 {item.get('pending_expense_amount') or 0} JPY。",
                "normal",
                item,
                "pending_expense",
            )

        if status in {"completed"} and _is_due(end_dt, now, minutes_after=60):
            _create_runtime_pair(
                driver_id,
                "not_returned",
                "司机未入库",
                f"{order_label} 行程已完成，车辆 {item.get('plate_number') or '-'} 尚未入库。",
                "high",
                item,
                "not_returned",
            )


def _create_runtime_pair(driver_id: int, notification_type: str, title: str, body: str, priority: str, item: dict[str, Any], code: str) -> None:
    assignment_id = item.get("assignment_id")
    order_date = item.get("order_date") or date.today().isoformat()
    source_id = f"{order_date}:{code}:{assignment_id}"
    create_notification(
        {
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "priority": priority,
            "target_role": "dispatcher",
            "link": "#driver-monitor",
            "source_type": "operation_runtime",
            "source_id": source_id,
        }
    )
    if driver_id > 0:
        create_notification(
            {
                "notification_type": notification_type,
                "title": title,
                "body": body,
                "priority": priority,
                "target_role": "driver",
                "link": "#driver",
                "source_type": "driver_operation_runtime",
                "source_id": f"{driver_id}:{source_id}",
            }
        )


def notify_dispatch_assigned(assignment_ids: list[int], order_ids: list[int], driver_id: int | None = None, driver_name: str | None = None, plate_number: str | None = None) -> None:
    if not assignment_ids:
        return
    if driver_id:
        create_notification(
            {
                "notification_type": "new_order",
                "title": f"你有 {len(order_ids)} 个待确认派单",
                "body": f"车辆 {plate_number or '-'}，请在今日任务中确认接单。",
                "priority": "high",
                "target_role": "driver",
                "link": "#driver",
                "source_type": "driver_assignment",
                "source_id": f"{driver_id}:assigned:{','.join(str(item) for item in assignment_ids)}",
            }
        )


def notify_order_changed_for_driver(before: dict[str, Any], after: dict[str, Any], actor: str | None = None) -> None:
    """Notify the assigned driver when an already assigned/running order is edited."""
    order_id = _to_int(after.get("id") or before.get("id"))
    if order_id <= 0:
        return
    changed = _describe_order_changes(before, after)
    if not changed:
        return
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT a.id AS assignment_id,
                   a.driver_id,
                   a.execution_status,
                   d.name AS driver_name,
                   v.plate_number
            FROM assignments a
            LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
              AND a.order_id = ?
              AND a.status = 'active'
              AND COALESCE(a.driver_id, 0) > 0
            ORDER BY a.id DESC
            LIMIT 1
            """,
            (tenant_id, order_id),
        ).fetchone()
    if not row:
        return
    driver_id = _to_int(row["driver_id"])
    if driver_id <= 0:
        return
    order_label = after.get("oid") or before.get("oid") or f"#{order_id}"
    body = "；".join(changed[:6])
    if len(changed) > 6:
        body = f"{body}；另有 {len(changed) - 6} 项变更"
    if actor:
        body = f"{body}。操作人：{actor}"
    create_notification(
        {
            "notification_type": "order_changed",
            "title": f"订单内容已变更：{order_label}",
            "body": body,
            "priority": "high" if row["execution_status"] in {"confirmed", "departed", "arrived", "in_service"} else "normal",
            "target_role": "driver",
            "link": "#driver",
            "source_type": "driver_order_changed",
            "source_id": f"{driver_id}:order_changed:{order_id}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        }
    )


def _describe_order_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    labels = {
        "order_date": "日期",
        "start_time": "开始时间",
        "end_time": "结束时间",
        "pickup_location": "起点",
        "dropoff_location": "终点",
        "order_type": "类型",
        "vehicle_type": "车型",
        "passenger_count": "人数",
        "luggage_count": "行李数",
        "guest_name": "客人姓名",
        "guest_contact": "客人联系方式",
        "guide_name": "导游姓名",
        "guide_phone": "导游电话",
        "remark": "备注",
        "fee_remark": "费用/路线备注",
    }
    changes: list[str] = []
    for field, label in labels.items():
        old = _display_change_value(before.get(field))
        new = _display_change_value(after.get(field))
        if old != new:
            changes.append(f"{label}：{old} -> {new}")
    return changes


def _display_change_value(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "-"


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


def _assignment_end_datetime(item: dict[str, Any]) -> datetime | None:
    try:
        raw = f"{item.get('order_date')} {item.get('end_time') or item.get('start_time') or '00:00'}"
        end_dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        start_dt = _assignment_start_datetime(item)
        if start_dt and end_dt < start_dt:
            return end_dt + timedelta(days=1)
        return end_dt
    except (TypeError, ValueError):
        return None


def _is_due(target: datetime | None, now: datetime, minutes_before: int = 0, minutes_after: int = 0) -> bool:
    if not target:
        return False
    return now >= target - timedelta(minutes=minutes_before) + timedelta(minutes=minutes_after)

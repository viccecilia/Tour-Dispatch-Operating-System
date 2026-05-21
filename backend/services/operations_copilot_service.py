from __future__ import annotations

from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


def get_copilot_summary(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    target_date = str(params.get("date") or date.today().isoformat())
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        metrics = _today_metrics(conn, tenant_id, target_date)
        risk_orders = _risk_orders(conn, tenant_id, target_date)
        unassigned = _unassigned_orders(conn, tenant_id, target_date)
        driver_exceptions = _driver_exception_summary(conn, tenant_id, target_date)
        open_incidents = _open_incidents(conn, tenant_id)
        urgent_notifications = _urgent_notifications(conn, tenant_id)

    suggestions = _suggestions(metrics, risk_orders, unassigned, driver_exceptions, open_incidents, urgent_notifications)
    return {
        "date": target_date,
        "operations_summary": _operations_summary_text(metrics),
        "metrics": metrics,
        "risk_orders": risk_orders,
        "unassigned_reminders": unassigned,
        "driver_exception_summary": driver_exceptions,
        "open_incidents": open_incidents,
        "urgent_notifications": urgent_notifications,
        "suggestions": suggestions,
        "explainability": [
            "All suggestions are generated from current orders, assignments, driver reports, incidents, and notifications.",
            "The copilot only explains risks and suggests next actions; it does not dispatch orders or change finance records.",
        ],
    }


def _today_metrics(conn, tenant_id: int, target_date: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS today_orders,
               SUM(CASE WHEN dispatch_status = 'unassigned' THEN 1 ELSE 0 END) AS unassigned_orders,
               SUM(CASE WHEN dispatch_status = 'assigned' THEN 1 ELSE 0 END) AS assigned_orders,
               SUM(CASE WHEN execution_status IN ('in_service', 'departed', 'arrived') THEN 1 ELSE 0 END) AS active_execution,
               SUM(CASE WHEN execution_status IN ('completed', 'returned') THEN 1 ELSE 0 END) AS completed_orders,
               SUM(CASE WHEN settlement_status IN ('pending', 'unsettled') THEN 1 ELSE 0 END) AS unsettled_orders,
               SUM(CASE WHEN price IS NULL OR price = 0 THEN 1 ELSE 0 END) AS missing_price_orders
        FROM orders
        WHERE tenant_id = ?
          AND COALESCE(is_deleted, 0) = 0
          AND order_date = ?
        """,
        (tenant_id, target_date),
    ).fetchone()
    incident_row = conn.execute(
        """
        SELECT COUNT(*) AS open_incidents
        FROM incidents
        WHERE tenant_id = ? AND status IN ('open', 'processing')
        """,
        (tenant_id,),
    ).fetchone()
    total = int(row["today_orders"] or 0)
    completed = int(row["completed_orders"] or 0)
    return {
        "today_orders": total,
        "unassigned_orders": int(row["unassigned_orders"] or 0),
        "assigned_orders": int(row["assigned_orders"] or 0),
        "active_execution": int(row["active_execution"] or 0),
        "completed_orders": completed,
        "completion_rate": round(completed / total * 100, 1) if total else 0,
        "unsettled_orders": int(row["unsettled_orders"] or 0),
        "missing_price_orders": int(row["missing_price_orders"] or 0),
        "open_incidents": int(incident_row["open_incidents"] or 0),
    }


def _risk_orders(conn, tenant_id: int, target_date: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT o.id, o.oid, o.order_date, o.start_time, o.end_time,
               o.pickup_location, o.dropoff_location, o.dispatch_status,
               o.execution_status, o.settlement_status, o.price,
               COUNT(i.id) AS incident_count
        FROM orders o
        LEFT JOIN incidents i ON i.order_id = o.id AND i.tenant_id = o.tenant_id AND i.status IN ('open', 'processing')
        WHERE o.tenant_id = ?
          AND COALESCE(o.is_deleted, 0) = 0
          AND (o.order_date = ? OR i.id IS NOT NULL)
        GROUP BY o.id
        ORDER BY incident_count DESC,
                 CASE o.dispatch_status WHEN 'unassigned' THEN 0 WHEN 'exception' THEN 1 ELSE 2 END,
                 o.order_date ASC,
                 o.start_time ASC
        LIMIT 12
        """,
        (tenant_id, target_date),
    ).fetchall()
    risks = []
    for row in rows:
        reasons = []
        if row["dispatch_status"] == "unassigned":
            reasons.append("未派车")
        if row["dispatch_status"] == "exception":
            reasons.append("异常状态")
        if int(row["incident_count"] or 0):
            reasons.append(f"{row['incident_count']} 个未关闭异常")
        if row["price"] in (None, 0):
            reasons.append("价格缺失")
        if row["settlement_status"] in {"pending", "unsettled"}:
            reasons.append("未结算")
        if not reasons:
            continue
        risk_level = "high" if row["dispatch_status"] in {"unassigned", "exception"} or int(row["incident_count"] or 0) else "medium"
        risks.append({**dict(row), "risk_level": risk_level, "reasons": reasons})
    return risks


def _unassigned_orders(conn, tenant_id: int, target_date: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, oid, order_date, start_time, end_time, pickup_location, dropoff_location, vehicle_type, price
        FROM orders
        WHERE tenant_id = ?
          AND COALESCE(is_deleted, 0) = 0
          AND dispatch_status = 'unassigned'
          AND order_date >= ?
        ORDER BY order_date ASC, start_time ASC, id ASC
        LIMIT 12
        """,
        (tenant_id, target_date),
    ).fetchall()
    return [
        dict(row)
        | {
            "suggested_action": "打开 Dispatch，按时间和地点接龙选择司机/车辆。",
            "reason": "订单未分配司机车辆，司机端不会收到任务。",
        }
        for row in rows
    ]


def _driver_exception_summary(conn, tenant_id: int, target_date: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.id AS driver_id,
               d.name AS driver_name,
               COUNT(DISTINCT a.id) AS active_assignments,
               SUM(CASE WHEN r.id IS NULL THEN 1 ELSE 0 END) AS no_report_assignments,
               SUM(CASE WHEN i.id IS NOT NULL THEN 1 ELSE 0 END) AS incident_count,
               MAX(r.report_time) AS latest_report_time
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
        LEFT JOIN (
            SELECT rr.*
            FROM driver_reports rr
            JOIN (
                SELECT assignment_id, MAX(id) AS max_id
                FROM driver_reports
                WHERE tenant_id = ?
                GROUP BY assignment_id
            ) latest ON latest.max_id = rr.id
        ) r ON r.assignment_id = a.id
        LEFT JOIN incidents i ON i.assignment_id = a.id AND i.tenant_id = a.tenant_id AND i.status IN ('open', 'processing')
        WHERE a.tenant_id = ?
          AND a.status = 'active'
          AND o.order_date = ?
        GROUP BY d.id, d.name
        HAVING no_report_assignments > 0 OR incident_count > 0
        ORDER BY incident_count DESC, no_report_assignments DESC
        LIMIT 10
        """,
        (tenant_id, tenant_id, target_date),
    ).fetchall()
    return [dict(row) for row in rows]


def _open_incidents(conn, tenant_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT i.id, i.title, i.incident_type, i.severity, i.status, i.created_at,
               o.oid, o.order_date, o.start_time, o.pickup_location, o.dropoff_location
        FROM incidents i
        LEFT JOIN orders o ON o.id = i.order_id AND o.tenant_id = i.tenant_id
        WHERE i.tenant_id = ?
          AND i.status IN ('open', 'processing')
        ORDER BY CASE i.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                 i.created_at DESC
        LIMIT 10
        """,
        (tenant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _urgent_notifications(conn, tenant_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, notification_type, title, body, priority, link, created_at
        FROM notifications
        WHERE tenant_id = ?
          AND status = 'unread'
          AND priority IN ('high', 'critical')
        ORDER BY created_at DESC, id DESC
        LIMIT 8
        """,
        (tenant_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _operations_summary_text(metrics: dict[str, Any]) -> str:
    return (
        f"今日 {metrics['today_orders']} 单，已派车 {metrics['assigned_orders']} 单，"
        f"执行中 {metrics['active_execution']} 单，已完成 {metrics['completed_orders']} 单。"
        f"当前未派车 {metrics['unassigned_orders']} 单，未关闭异常 {metrics['open_incidents']} 个。"
    )


def _suggestions(
    metrics: dict[str, Any],
    risk_orders: list[dict[str, Any]],
    unassigned: list[dict[str, Any]],
    driver_exceptions: list[dict[str, Any]],
    open_incidents: list[dict[str, Any]],
    urgent_notifications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    suggestions = []
    if metrics["unassigned_orders"]:
        suggestions.append(
            {
                "priority": "high",
                "title": "优先处理未派车订单",
                "text": f"还有 {metrics['unassigned_orders']} 单未派车，建议先打开 Dispatch 用接龙排序生成派车建议。",
                "reason": "未派车订单不会同步到司机端，且会影响日历可视化。",
                "link": "#dispatch",
            }
        )
    if risk_orders:
        suggestions.append(
            {
                "priority": "high",
                "title": "复核风险订单",
                "text": f"识别到 {len(risk_orders)} 条风险订单，最高风险来自：{', '.join(risk_orders[0]['reasons'])}。",
                "reason": "风险依据来自派车状态、异常、价格缺失和结算状态。",
                "link": "#orders",
            }
        )
    if driver_exceptions:
        suggestions.append(
            {
                "priority": "medium",
                "title": "跟进司机报备",
                "text": f"{len(driver_exceptions)} 名司机存在未报备或异常关联，建议查看 Driver Monitor。",
                "reason": "司机端报备是执行闭环的关键证据。",
                "link": "#driver-monitor",
            }
        )
    if open_incidents:
        suggestions.append(
            {
                "priority": "high",
                "title": "关闭或推进异常",
                "text": f"当前有 {len(open_incidents)} 条开放异常，最高优先级：{open_incidents[0]['title']}。",
                "reason": "异常未关闭会影响 dashboard、BI 和订单状态判断。",
                "link": "#incidents",
            }
        )
    if metrics["missing_price_orders"]:
        suggestions.append(
            {
                "priority": "medium",
                "title": "补齐价格",
                "text": f"今日有 {metrics['missing_price_orders']} 单缺少价格，建议在 Orders 或 Finance 中补齐。",
                "reason": "价格缺失会影响收入统计和后续结算。",
                "link": "#finance",
            }
        )
    if urgent_notifications:
        suggestions.append(
            {
                "priority": "medium",
                "title": "处理紧急通知",
                "text": f"有 {len(urgent_notifications)} 条高优先级未读通知。",
                "reason": "通知来自工作流、到期提醒、异常或派车状态变化。",
                "link": "#notifications",
            }
        )
    if not suggestions:
        suggestions.append(
            {
                "priority": "low",
                "title": "运营状态稳定",
                "text": "当前没有明显阻塞项，建议继续关注未结算和后续预约订单。",
                "reason": "今日未派车、异常、缺价和司机报备风险均未达到提醒阈值。",
                "link": "#dashboard",
            }
        )
    return suggestions

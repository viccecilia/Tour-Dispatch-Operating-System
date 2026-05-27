import base64
import math
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


REPORT_STATUS_MAP = {
    "confirm_order": "confirmed",
    "depart_yard": "departed",
    "arrive_pickup": "arrived",
    "start_service": "in_service",
    "complete_order": "completed",
    "return_yard": "returned",
}
GEOFENCE_RADIUS_METERS = 800

STATUS_ORDER = ["assigned", "confirmed", "departed", "arrived", "in_service", "completed", "returned"]
VEHICLE_RUNTIME_STATUS = {
    "departed": "outbound",
    "arrived": "outbound",
    "in_service": "in_service",
    "completed": "in_service",
    "returned": "returned",
}
WORKFLOW_VEHICLE_STATUS = {
    "roll_call_out": "outbound",
    "depart_yard": "outbound",
    "vehicle_check_out": "outbound",
    "roll_call_in": "returned",
    "return_yard": "returned",
    "vehicle_check_in": "returned",
}
EVIDENCE_TYPES = {
    "pickup",
    "completion",
    "vehicle_condition",
    "arrive_waiting_photo",
    "pickup_photo",
    "waypoint_photo",
    "dropoff_photo",
    "vehicle_check_photo",
    "cleaning_photo",
    "expense_receipt_photo",
}
EVIDENCE_STATUS_RULES = {
    "arrive_waiting_photo": {"arrived", "in_service", "completed", "returned"},
    "pickup_photo": {"arrived", "in_service", "completed", "returned"},
    "waypoint_photo": {"in_service", "completed", "returned"},
    "dropoff_photo": {"in_service", "completed", "returned"},
}
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "uploads" / "driver_evidence"

WORKFLOW_LABELS = {
    "accept_orders": "确认接单",
    "vehicle_check_out": "车辆点检",
    "alcohol_test_out": "出库前酒精测试",
    "roll_call_out": "点呼出库",
    "depart_yard": "出库",
    "arrive_pickup": "到达上车点",
    "arrive_waiting_photo": "拍照等待客人",
    "pickup_customer": "接到客人 / 开始行程",
    "waypoint_photo": "行程途中拍照",
    "arrive_dropoff": "到达目的地",
    "dropoff_photo": "送达照片",
    "complete_order": "行程结束",
    "vehicle_cleaning": "车辆清扫",
    "vehicle_check_in": "入库点检",
    "alcohol_test_in": "入库酒精测试",
    "roll_call_in": "点呼入库",
    "return_yard": "车辆入库 / 今日收工",
}


def list_driver_assignments(driver_id: Any) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                {DRIVER_ASSIGNMENT_SELECT}
                WHERE a.status = 'active'
                  AND a.tenant_id = ?
                  AND o.tenant_id = ?
                  AND a.driver_id = ?
                  AND COALESCE(o.is_deleted, 0) = 0
                ORDER BY o.order_date ASC, o.start_time ASC, a.id ASC
                """,
                (get_current_tenant_id(), get_current_tenant_id(), _to_int(driver_id)),
            ).fetchall()
        ]


def get_driver_assignment(driver_id: Any, assignment_id: Any) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            {DRIVER_ASSIGNMENT_SELECT}
            WHERE a.status = 'active'
              AND a.tenant_id = ?
              AND o.tenant_id = ?
              AND a.driver_id = ?
              AND a.id = ?
              AND COALESCE(o.is_deleted, 0) = 0
            """,
            (get_current_tenant_id(), get_current_tenant_id(), _to_int(driver_id), _to_int(assignment_id)),
        ).fetchone()
    return dict(row) if row else None


def submit_driver_report(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    report_type = str(payload.get("report_type") or "").strip()
    if not driver_id or not assignment_id or report_type not in REPORT_STATUS_MAP:
        return {"success": False, "error": "invalid_report_request"}

    assignment = get_driver_assignment(driver_id, assignment_id)
    if not assignment:
        return {"success": False, "error": "assignment_not_found_for_driver"}

    new_status = REPORT_STATUS_MAP[report_type]
    current_status = assignment.get("execution_status") or "assigned"
    current_index = STATUS_ORDER.index(current_status)
    new_index = STATUS_ORDER.index(new_status)
    if new_index <= current_index:
        return {"success": False, "error": "execution_status_duplicate_or_regression_not_allowed"}
    if new_index != current_index + 1:
        return {"success": False, "error": "execution_status_skip_not_allowed", "current_status": current_status}
    location_check = _validate_report_geofence(report_type, assignment, payload)
    if not location_check.get("ok"):
        return {"success": False, "error": "location_out_of_range", "location_check": location_check}

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO driver_reports (
                tenant_id, assignment_id, order_id, driver_id, report_type, report_status,
                report_time, latitude, longitude, location_text, note, photo_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'submitted', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                assignment_id,
                assignment["order_id"],
                driver_id,
                report_type,
                _optional_float(payload.get("latitude")),
                _optional_float(payload.get("longitude")),
                payload.get("location_text"),
                payload.get("note"),
                payload.get("photo_url"),
            ),
        )
        report_id = cursor.lastrowid
        _insert_location_log(
            conn,
            {
                "driver_id": driver_id,
                "assignment_id": assignment_id,
                "order_id": assignment["order_id"],
                "vehicle_id": assignment.get("vehicle_id"),
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "location_text": payload.get("location_text"),
                "source": f"report:{report_type}",
            },
        )
        conn.execute(
            """
            UPDATE assignments
            SET execution_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (new_status, assignment_id, get_current_tenant_id()),
        )
        conn.execute(
            """
            UPDATE orders
            SET execution_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (new_status, assignment["order_id"], get_current_tenant_id()),
        )
        _update_vehicle_runtime_status(conn, assignment.get("vehicle_id"), VEHICLE_RUNTIME_STATUS.get(new_status))
        conn.commit()
    from backend.services.notification_service import notify_driver_report

    notify_driver_report(report_id, report_type, assignment_id, driver_id)
    return {"success": True, "report_id": report_id, "new_execution_status": new_status, "location_check": location_check}


def submit_driver_location(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    if not driver_id:
        return {"success": False, "error": "missing_driver_id"}

    assignment: dict[str, Any] | None = None
    if assignment_id:
        assignment = get_driver_assignment(driver_id, assignment_id)
        if not assignment:
            return {"success": False, "error": "assignment_not_found_for_driver"}
    else:
        assignments = list_driver_assignments(driver_id)
        assignment = assignments[0] if assignments else None

    with get_connection() as conn:
        location_id = _insert_location_log(
            conn,
            {
                "driver_id": driver_id,
                "assignment_id": assignment.get("assignment_id") if assignment else None,
                "order_id": assignment.get("order_id") if assignment else None,
                "vehicle_id": assignment.get("vehicle_id") if assignment else payload.get("vehicle_id"),
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "location_text": payload.get("location_text"),
                "source": payload.get("source") or "driver_manual",
            },
        )
        conn.commit()
    return {"success": True, "location_id": location_id}


def submit_driver_incident(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    incident_kind = str(payload.get("incident_kind") or "exception").strip()
    if not driver_id or not assignment_id:
        return {"success": False, "error": "invalid_incident_request"}

    assignment = get_driver_assignment(driver_id, assignment_id)
    if not assignment:
        return {"success": False, "error": "assignment_not_found_for_driver"}

    kind_map = {
        "sos": ("accident", "critical", "司机 SOS"),
        "delay": ("delay", "high", "司机延误报备"),
        "vehicle_issue": ("exception", "high", "车辆异常"),
        "guest_issue": ("complaint", "high", "客人异常"),
        "exception": ("exception", "high", "司机异常报备"),
    }
    incident_type, severity, title = kind_map.get(incident_kind, kind_map["exception"])
    description_parts = [
        str(payload.get("description") or payload.get("note") or "").strip(),
        f"司机：{assignment.get('driver_name') or driver_id}",
        f"车辆：{assignment.get('plate_number') or '-'}",
        f"路线：{assignment.get('pickup_location') or '-'} -> {assignment.get('dropoff_location') or '-'}",
    ]
    location_text = payload.get("location_text")
    if location_text:
        description_parts.append(f"位置：{location_text}")
    from backend.services.incident_service import create_incident

    incident = create_incident(
        {
            "order_id": assignment.get("order_id"),
            "assignment_id": assignment_id,
            "incident_type": incident_type,
            "severity": severity,
            "status": "open",
            "title": title,
            "description": "\n".join(part for part in description_parts if part),
            "owner": "dispatcher",
            "delay_minutes": _to_int(payload.get("delay_minutes")) or None,
            "accident_location": location_text,
        }
    )
    if payload.get("latitude") or payload.get("longitude") or location_text:
        submit_driver_location(
            {
                "driver_id": driver_id,
                "assignment_id": assignment_id,
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "location_text": location_text,
                "source": f"driver_incident:{incident_kind}",
            }
        )
    return {"success": True, "incident": incident}


def list_driver_safety_alerts() -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        incident_rows = conn.execute(
            """
            SELECT
                'incident' AS alert_type,
                i.id AS incident_id,
                i.assignment_id,
                i.order_id,
                i.incident_type,
                i.severity,
                i.title,
                i.description,
                i.created_at,
                d.id AS driver_id,
                d.name AS driver_name,
                v.plate_number,
                o.oid,
                o.pickup_location,
                o.dropoff_location,
                a.execution_status
            FROM incidents i
            LEFT JOIN assignments a ON a.id = i.assignment_id AND a.tenant_id = i.tenant_id
            LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = i.tenant_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = i.tenant_id
            LEFT JOIN orders o ON o.id = i.order_id AND o.tenant_id = i.tenant_id
            WHERE i.tenant_id = ?
              AND i.status IN ('open', 'processing')
              AND i.severity IN ('high', 'critical')
            ORDER BY CASE i.severity WHEN 'critical' THEN 0 ELSE 1 END, i.created_at DESC
            LIMIT 20
            """,
            (tenant_id,),
        ).fetchall()
        stale_rows = conn.execute(
            """
            SELECT
                'stale_location' AS alert_type,
                a.id AS assignment_id,
                a.order_id,
                a.driver_id,
                d.name AS driver_name,
                v.plate_number,
                o.oid,
                o.pickup_location,
                o.dropoff_location,
                a.execution_status,
                latest.reported_at,
                latest.location_text,
                latest.latitude,
                latest.longitude
            FROM assignments a
            JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
            LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
            LEFT JOIN (
                SELECT ll.*
                FROM location_logs ll
                JOIN (
                    SELECT driver_id, MAX(id) AS max_id
                    FROM location_logs
                    WHERE tenant_id = ?
                    GROUP BY driver_id
                ) m ON m.max_id = ll.id
            ) latest ON latest.driver_id = a.driver_id
            WHERE a.tenant_id = ?
              AND a.status = 'active'
              AND a.execution_status IN ('departed', 'arrived', 'in_service')
              AND COALESCE(o.is_deleted, 0) = 0
              AND (
                latest.reported_at IS NULL
                OR datetime(latest.reported_at) <= datetime('now', '-30 minutes')
              )
            ORDER BY o.order_date ASC, o.start_time ASC
            LIMIT 20
            """,
            (tenant_id, tenant_id),
        ).fetchall()
    alerts = [dict(row) for row in incident_rows]
    for row in stale_rows:
        item = dict(row)
        item["severity"] = "high"
        item["title"] = "司机位置超过 30 分钟未更新"
        item["description"] = item.get("location_text") or "暂无最新位置"
        alerts.append(item)
    return alerts


def list_driver_reports(driver_id: Any) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM driver_reports
                WHERE driver_id = ? AND tenant_id = ?
                ORDER BY report_time DESC, id DESC
                """,
                (_to_int(driver_id), get_current_tenant_id()),
            ).fetchall()
        ]


def submit_driver_workflow_event(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    event_type = str(payload.get("event_type") or "").strip()
    if not driver_id or not event_type:
        return {"success": False, "error": "invalid_workflow_event"}

    assignment = None
    if assignment_id:
        assignment = get_driver_assignment(driver_id, assignment_id)
        if not assignment:
            return {"success": False, "error": "assignment_not_found_for_driver"}
    elif list_driver_assignments(driver_id):
        assignment = list_driver_assignments(driver_id)[0]

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO driver_workflow_events (
                tenant_id, driver_id, assignment_id, order_id, event_type, event_status,
                latitude, longitude, location_text, note, event_time, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                driver_id,
                assignment.get("assignment_id") if assignment else assignment_id or None,
                assignment.get("order_id") if assignment else _to_int(payload.get("order_id")) or None,
                event_type,
                _optional_float(payload.get("latitude")),
                _optional_float(payload.get("longitude")),
                payload.get("location_text"),
                payload.get("note"),
            ),
        )
        event_id = cursor.lastrowid
        _insert_location_log(
            conn,
            {
                "driver_id": driver_id,
                "assignment_id": assignment.get("assignment_id") if assignment else assignment_id,
                "order_id": assignment.get("order_id") if assignment else payload.get("order_id"),
                "vehicle_id": assignment.get("vehicle_id") if assignment else payload.get("vehicle_id"),
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "location_text": payload.get("location_text"),
                "source": f"workflow:{event_type}",
            },
        )
        _update_vehicle_runtime_status(
            conn,
            assignment.get("vehicle_id") if assignment else payload.get("vehicle_id"),
            WORKFLOW_VEHICLE_STATUS.get(event_type),
        )
        conn.commit()
    return {"success": True, "event_id": event_id, "event_type": event_type, "label": WORKFLOW_LABELS.get(event_type, event_type)}


def list_driver_workflow_events(driver_id: Any, day: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [get_current_tenant_id(), _to_int(driver_id)]
    where = ["tenant_id = ?", "driver_id = ?"]
    if day:
        where.append("date(event_time) = date(?)")
        params.append(day)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM driver_workflow_events
            WHERE {" AND ".join(where)}
            ORDER BY event_time DESC, id DESC
            """,
            params,
        ).fetchall()
    return [_with_workflow_label(dict(row)) for row in rows]


def submit_driver_expense(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    expense_kind = str(payload.get("expense_kind") or "advance").strip()
    category = str(payload.get("category") or "").strip()
    amount = _optional_float(payload.get("amount")) or 0.0
    if not driver_id or not category:
        return {"success": False, "error": "invalid_expense_request"}
    if expense_kind not in {"advance", "collect"}:
        return {"success": False, "error": "invalid_expense_kind"}

    assignment = None
    if assignment_id:
        assignment = get_driver_assignment(driver_id, assignment_id)
        if not assignment:
            return {"success": False, "error": "assignment_not_found_for_driver"}

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO driver_expense_reports (
                tenant_id, driver_id, assignment_id, order_id, expense_kind, category,
                amount, currency, submit_status, receipt_photo_url, note, submitted_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                driver_id,
                assignment_id or None,
                assignment.get("order_id") if assignment else _to_int(payload.get("order_id")) or None,
                expense_kind,
                category,
                amount,
                payload.get("currency") or "JPY",
                payload.get("submit_status") or ("in_hand" if expense_kind == "collect" else "submitted"),
                payload.get("receipt_photo_url"),
                payload.get("note"),
            ),
        )
        expense_id = cursor.lastrowid
        conn.commit()
    return {"success": True, "expense_id": expense_id}


def list_driver_expenses(driver_id: Any, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    sql_params: list[Any] = [get_current_tenant_id(), _to_int(driver_id)]
    where = ["e.tenant_id = ?", "e.driver_id = ?"]
    if params.get("submit_status"):
        where.append("e.submit_status = ?")
        sql_params.append(params["submit_status"])
    if params.get("start_date"):
        where.append("date(e.created_at) >= date(?)")
        sql_params.append(params["start_date"])
    if params.get("end_date"):
        where.append("date(e.created_at) <= date(?)")
        sql_params.append(params["end_date"])
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT e.*, o.oid, o.pickup_location, o.dropoff_location, o.order_date, o.start_time
            FROM driver_expense_reports e
            LEFT JOIN orders o ON o.id = e.order_id AND o.tenant_id = e.tenant_id
            WHERE {" AND ".join(where)}
            ORDER BY e.created_at DESC, e.id DESC
            """,
            sql_params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_driver_history(driver_id: Any, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    sql_params: list[Any] = [get_current_tenant_id(), get_current_tenant_id(), _to_int(driver_id)]
    where = ["a.tenant_id = ?", "o.tenant_id = ?", "a.driver_id = ?", "COALESCE(o.is_deleted, 0) = 0"]
    if params.get("start_date"):
        where.append("date(o.order_date) >= date(?)")
        sql_params.append(params["start_date"])
    if params.get("end_date"):
        where.append("date(o.order_date) <= date(?)")
        sql_params.append(params["end_date"])
    if params.get("order_type"):
        where.append("o.order_type LIKE ?")
        sql_params.append(f"%{params['order_type']}%")
    if params.get("keyword"):
        kw = f"%{params['keyword']}%"
        where.append("(o.oid LIKE ? OR o.pickup_location LIKE ? OR o.dropoff_location LIKE ? OR o.remark LIKE ?)")
        sql_params.extend([kw, kw, kw, kw])
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                a.id AS assignment_id,
                a.execution_status,
                o.id AS order_id,
                o.oid,
                o.order_date,
                o.start_time,
                o.end_time,
                o.pickup_location,
                o.dropoff_location,
                o.order_type,
                o.vehicle_type,
                o.settlement_status,
                v.plate_number,
                COUNT(DISTINCT ev.id) AS photo_count,
                COALESCE(SUM(DISTINCT ex.amount), 0) AS expense_amount
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            LEFT JOIN driver_evidence_uploads ev ON ev.assignment_id = a.id AND ev.tenant_id = a.tenant_id
            LEFT JOIN driver_expense_reports ex ON ex.assignment_id = a.id AND ex.tenant_id = a.tenant_id
            WHERE {" AND ".join(where)}
            GROUP BY a.id, o.id
            ORDER BY o.order_date DESC, o.start_time DESC, a.id DESC
            LIMIT 300
            """,
            sql_params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_driver_workbench(driver_id: Any) -> dict[str, Any]:
    driver_id_int = _to_int(driver_id)
    today = date.today().isoformat()
    assignments = list_driver_assignments(driver_id_int)
    today_assignments = [item for item in assignments if item.get("order_date") == today]
    completed_today = [item for item in today_assignments if item.get("execution_status") in {"completed", "returned"}]
    active_today = [item for item in today_assignments if item.get("execution_status") not in {"completed", "returned"}]
    current_assignment = _pick_current_assignment(today_assignments) or _pick_current_assignment(assignments)
    workflow_events = list_driver_workflow_events(driver_id_int, today)
    latest_event = workflow_events[0] if workflow_events else None
    expenses = list_driver_expenses(driver_id_int, {"start_date": today, "end_date": today})
    pending_expenses = [
        item for item in expenses
        if item.get("submit_status") in {"unsubmitted", "in_hand", "submitted"}
    ]
    month_stats = _driver_month_stats(driver_id_int)
    next_step = _derive_next_step(current_assignment, latest_event, active_today)
    return {
        "driver_id": driver_id_int,
        "date": today,
        "today_order_count": len(today_assignments),
        "next_start_time": current_assignment.get("start_time") if current_assignment else None,
        "month_completed_count": month_stats["completed_count"],
        "month_airport_count": month_stats["airport_count"],
        "month_charter_count": month_stats["charter_count"],
        "month_incident_count": month_stats["incident_count"],
        "today_pending_reports": _pending_report_count(today_assignments),
        "today_pending_expenses": len(pending_expenses),
        "vehicle_status": _vehicle_status_from_events(workflow_events),
        "cleaning_status": "已清扫" if _has_event(workflow_events, "vehicle_cleaning") else "未清扫",
        "alcohol_status": _alcohol_status(workflow_events),
        "current_assignment": current_assignment,
        "next_step": next_step,
        "workflow_events": workflow_events[:20],
        "expenses": expenses[:20],
    }


def get_driver_profile(driver_id: Any) -> dict[str, Any]:
    driver_id_int = _to_int(driver_id)
    if not driver_id_int:
        return {"driver": None}
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, driver_code, driver_language, office, phone, email,
                   wechat, line, whatsapp, kakao,
                   license_due_date, health_check_due_date, driver_status, status
            FROM drivers
            WHERE tenant_id = ? AND id = ?
            """,
            (get_current_tenant_id(), driver_id_int),
        ).fetchone()
    return {"driver": dict(row) if row else None}


def update_driver_profile(driver_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    driver_id_int = _to_int(driver_id or payload.get("driver_id"))
    if not driver_id_int:
        return {"success": False, "error": "missing_driver_id"}
    allowed = ("phone", "wechat", "line", "whatsapp", "kakao")
    data = {key: str(payload.get(key) or "").strip() for key in allowed if key in payload}
    if not data:
        return {"success": False, "error": "empty_profile_update"}
    assignments = ", ".join(f"{key} = ?" for key in data)
    with get_connection() as conn:
        cursor = conn.execute(
            f"""
            UPDATE drivers
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            [*data.values(), get_current_tenant_id(), driver_id_int],
        )
        conn.commit()
    if cursor.rowcount <= 0:
        return {"success": False, "error": "driver_not_found"}
    profile = get_driver_profile(driver_id_int).get("driver")
    return {"success": True, "driver": profile}


def upload_driver_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = _to_int(payload.get("driver_id"))
    assignment_id = _to_int(payload.get("assignment_id"))
    evidence_type = str(payload.get("evidence_type") or "").strip()
    image_data = str(payload.get("image_base64") or "").strip()
    if not driver_id or not assignment_id or evidence_type not in EVIDENCE_TYPES or not image_data:
        return {"success": False, "error": "invalid_evidence_request"}

    assignment = get_driver_assignment(driver_id, assignment_id)
    if not assignment:
        return {"success": False, "error": "assignment_not_found_for_driver"}
    allowed_statuses = EVIDENCE_STATUS_RULES.get(evidence_type)
    if allowed_statuses and (assignment.get("execution_status") or "assigned") not in allowed_statuses:
        return {
            "success": False,
            "error": "evidence_status_not_allowed",
            "current_status": assignment.get("execution_status") or "assigned",
            "allowed_statuses": sorted(allowed_statuses),
        }

    try:
        suffix, raw = _decode_image_payload(image_data)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    file_name = f"driver{driver_id}_assignment{assignment_id}_{evidence_type}_{uuid.uuid4().hex[:10]}.{suffix}"
    file_path = UPLOAD_ROOT / file_name
    file_path.write_bytes(raw)
    file_url = f"/uploads/driver_evidence/{file_name}"

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO driver_evidence_uploads (
                tenant_id, assignment_id, order_id, driver_id, evidence_type,
                file_name, file_url, note, uploaded_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                assignment_id,
                assignment.get("order_id"),
                driver_id,
                evidence_type,
                file_name,
                file_url,
                payload.get("note"),
            ),
        )
        evidence_id = cursor.lastrowid
        conn.execute(
            """
            UPDATE driver_reports
            SET photo_url = COALESCE(NULLIF(photo_url, ''), ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM driver_reports
                WHERE tenant_id = ?
                  AND driver_id = ?
                  AND assignment_id = ?
                  AND report_type IN ('arrive_pickup', 'complete_order', 'return_yard')
                ORDER BY id DESC
                LIMIT 1
            )
            """,
            (file_url, get_current_tenant_id(), driver_id, assignment_id),
        )
        conn.commit()
    return {
        "success": True,
        "evidence": {
            "id": evidence_id,
            "assignment_id": assignment_id,
            "order_id": assignment.get("order_id"),
            "driver_id": driver_id,
            "evidence_type": evidence_type,
            "file_name": file_name,
            "file_url": file_url,
            "note": payload.get("note"),
        },
    }


def list_driver_evidence(driver_id: Any, assignment_id: Any = None) -> list[dict[str, Any]]:
    params: list[Any] = [get_current_tenant_id(), _to_int(driver_id)]
    where = ["tenant_id = ?", "driver_id = ?"]
    if assignment_id not in ("", None):
        where.append("assignment_id = ?")
        params.append(_to_int(assignment_id))
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM driver_evidence_uploads
            WHERE {" AND ".join(where)}
            ORDER BY uploaded_at DESC, id DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_assignment_evidence_chain(assignment_id: Any) -> dict[str, Any] | None:
    assignment_id_int = _to_int(assignment_id)
    if not assignment_id_int:
        return None
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        assignment_row = conn.execute(
            """
            SELECT
                a.id AS assignment_id,
                a.order_id,
                a.driver_id,
                a.vehicle_id,
                a.status AS assignment_status,
                a.execution_status,
                a.assigned_at,
                o.oid,
                o.order_date,
                o.start_time,
                o.end_time,
                o.pickup_location,
                o.dropoff_location,
                o.order_type,
                o.vehicle_type,
                o.guest_name,
                o.guest_contact,
                o.remark,
                d.name AS driver_name,
                d.phone AS driver_phone,
                v.plate_number,
                v.vehicle_type AS assigned_vehicle_type
            FROM assignments a
            JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
            LEFT JOIN drivers d ON d.id = a.driver_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            WHERE a.tenant_id = ? AND a.id = ?
            """,
            (tenant_id, assignment_id_int),
        ).fetchone()
        if not assignment_row:
            return None
        assignment = dict(assignment_row)
        evidence = [
            _decorate_evidence(dict(row))
            for row in conn.execute(
                """
                SELECT *
                FROM driver_evidence_uploads
                WHERE tenant_id = ? AND assignment_id = ?
                ORDER BY uploaded_at ASC, id ASC
                """,
                (tenant_id, assignment_id_int),
            ).fetchall()
        ]
        reports = [
            _decorate_report_event(dict(row))
            for row in conn.execute(
                """
                SELECT *
                FROM driver_reports
                WHERE tenant_id = ? AND assignment_id = ?
                ORDER BY report_time ASC, id ASC
                """,
                (tenant_id, assignment_id_int),
            ).fetchall()
        ]
        workflow_events = [
            _decorate_workflow_timeline_event(dict(row))
            for row in conn.execute(
                """
                SELECT *
                FROM driver_workflow_events
                WHERE tenant_id = ? AND assignment_id = ?
                ORDER BY event_time ASC, id ASC
                """,
                (tenant_id, assignment_id_int),
            ).fetchall()
        ]
        expenses = [
            _decorate_expense_event(dict(row))
            for row in conn.execute(
                """
                SELECT *
                FROM driver_expense_reports
                WHERE tenant_id = ? AND assignment_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (tenant_id, assignment_id_int),
            ).fetchall()
        ]

    timeline = sorted(
        [
            *[_timeline_item("report", item) for item in reports],
            *[_timeline_item("workflow", item) for item in workflow_events],
            *[_timeline_item("photo", item) for item in evidence],
            *[_timeline_item("expense", item) for item in expenses],
        ],
        key=lambda item: (item.get("event_time") or "", item.get("id") or 0),
    )
    download_files = [
        {
            "id": item.get("id"),
            "kind": "photo",
            "label": item.get("label"),
            "url": item.get("file_url"),
            "file_name": item.get("file_name"),
        }
        for item in evidence
        if item.get("file_url")
    ] + [
        {
            "id": item.get("id"),
            "kind": "receipt",
            "label": item.get("label"),
            "url": item.get("receipt_photo_url"),
            "file_name": f"expense-{item.get('id')}",
        }
        for item in expenses
        if item.get("receipt_photo_url")
    ]
    return {
        "assignment": assignment,
        "timeline": timeline,
        "reports": reports,
        "workflow_events": workflow_events,
        "evidence": evidence,
        "expenses": expenses,
        "download_files": download_files,
        "summary": {
            "photo_count": len(evidence),
            "report_count": len(reports),
            "workflow_event_count": len(workflow_events),
            "expense_count": len(expenses),
            "download_count": len(download_files),
        },
    }


def get_order_evidence_chain(order_id: Any) -> dict[str, Any] | None:
    order_id_int = _to_int(order_id)
    if not order_id_int:
        return None
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        assignment = conn.execute(
            """
            SELECT id
            FROM assignments
            WHERE tenant_id = ? AND order_id = ?
            ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, id DESC
            LIMIT 1
            """,
            (tenant_id, order_id_int),
        ).fetchone()
        order = conn.execute(
            """
            SELECT id AS order_id, oid, order_date, start_time, end_time, pickup_location, dropoff_location,
                   order_type, vehicle_type, guest_name, guest_contact, remark
            FROM orders
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant_id, order_id_int),
        ).fetchone()
    if assignment:
        return get_assignment_evidence_chain(assignment["id"])
    if not order:
        return None
    return {
        "assignment": dict(order),
        "timeline": [],
        "reports": [],
        "workflow_events": [],
        "evidence": [],
        "expenses": [],
        "download_files": [],
        "summary": {"photo_count": 0, "report_count": 0, "workflow_event_count": 0, "expense_count": 0, "download_count": 0},
    }


def get_driver_dashboard(driver_id: Any) -> dict[str, Any]:
    assignments = list_driver_assignments(driver_id)
    reports = list_driver_reports(driver_id)
    latest_location = get_latest_locations(driver_id=driver_id, limit=1)
    today = date.today().isoformat()
    today_assignments = [item for item in assignments if item.get("order_date") == today]
    completed = [item for item in today_assignments if item.get("execution_status") in {"completed", "returned"}]
    today_estimated_amount = _driver_today_salary(driver_id, today)
    return {
        "driver_id": _to_int(driver_id),
        "active_assignment_count": len(assignments),
        "report_count": len(reports),
        "latest_location": latest_location[0] if latest_location else None,
        "next_assignment": assignments[0] if assignments else None,
        "assignments": assignments,
        "today_order_count": len(today_assignments),
        "today_completed_count": len(completed),
        "today_estimated_amount": today_estimated_amount,
    }


def _driver_today_salary(driver_id: Any, today: str) -> float:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(COALESCE(o.driver_salary_jpy, 0)), 0) AS total
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            WHERE a.status = 'active'
              AND a.tenant_id = ?
              AND o.tenant_id = ?
              AND a.driver_id = ?
              AND o.order_date = ?
              AND COALESCE(o.is_deleted, 0) = 0
            """,
            (get_current_tenant_id(), get_current_tenant_id(), _to_int(driver_id), today),
        ).fetchone()
    return float(row["total"] or 0) if row else 0.0


def _driver_month_stats(driver_id: int) -> dict[str, int]:
    month_start = date.today().replace(day=1).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.order_type, a.execution_status
            FROM assignments a
            JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
              AND a.driver_id = ?
              AND date(o.order_date) >= date(?)
              AND COALESCE(o.is_deleted, 0) = 0
            """,
            (get_current_tenant_id(), driver_id, month_start),
        ).fetchall()
        incident_count = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM incidents i
            JOIN assignments a ON a.id = i.assignment_id AND a.tenant_id = i.tenant_id
            WHERE i.tenant_id = ?
              AND a.driver_id = ?
              AND date(i.created_at) >= date(?)
            """,
            (get_current_tenant_id(), driver_id, month_start),
        ).fetchone()
    order_rows = [dict(row) for row in rows]
    return {
        "completed_count": sum(1 for row in order_rows if row.get("execution_status") in {"completed", "returned"}),
        "airport_count": sum(1 for row in order_rows if any(token in str(row.get("order_type") or "") for token in ["接机", "送机", "送迎", "单送", "往返"])),
        "charter_count": sum(1 for row in order_rows if "包车" in str(row.get("order_type") or "")),
        "incident_count": int(incident_count["total"] or 0) if incident_count else 0,
    }


def _pick_current_assignment(assignments: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not assignments:
        return None
    in_progress = {"confirmed", "departed", "arrived", "in_service"}
    return (
        next((item for item in assignments if item.get("execution_status") in in_progress), None)
        or next((item for item in assignments if item.get("execution_status") not in {"completed", "returned"}), None)
        or assignments[0]
    )


def _derive_next_step(current_assignment: dict[str, Any] | None, latest_event: dict[str, Any] | None, active_today: list[dict[str, Any]]) -> dict[str, Any]:
    if not current_assignment:
        if latest_event and latest_event.get("event_type") == "vehicle_cleaning":
            return {"event_type": "vehicle_check_in", "label": WORKFLOW_LABELS["vehicle_check_in"], "kind": "workflow"}
        return {"event_type": "accept_orders", "label": "今日暂无待执行订单", "kind": "idle"}
    status = current_assignment.get("execution_status") or "assigned"
    if status == "assigned":
        return {"event_type": "confirm_order", "label": "确认接单", "kind": "report"}
    if status == "confirmed" and not _has_active_event("vehicle_check_out", current_assignment):
        return {"event_type": "vehicle_check_out", "label": WORKFLOW_LABELS["vehicle_check_out"], "kind": "workflow"}
    if status == "confirmed":
        return {"event_type": "depart_yard", "label": "出库", "kind": "report"}
    if status == "departed":
        return {"event_type": "arrive_pickup", "label": "到达上车点", "kind": "report"}
    if status == "arrived":
        return {"event_type": "pickup_photo", "label": "拍照等待客人", "kind": "photo"}
    if status == "in_service":
        return {"event_type": "dropoff_photo", "label": "送达照片", "kind": "photo"}
    if status == "completed" and active_today:
        return {"event_type": "start_next_order", "label": "开启下一单", "kind": "workflow"}
    if status == "completed":
        return {"event_type": "return_yard", "label": "车辆入库 / 今日收工", "kind": "report"}
    return {"event_type": "complete_order", "label": "行程结束", "kind": "report"}


def _has_active_event(event_type: str, assignment: dict[str, Any]) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM driver_workflow_events
            WHERE tenant_id = ? AND assignment_id = ? AND event_type = ?
            LIMIT 1
            """,
            (get_current_tenant_id(), assignment.get("assignment_id"), event_type),
        ).fetchone()
    return row is not None


def _pending_report_count(assignments: list[dict[str, Any]]) -> int:
    return sum(1 for item in assignments if item.get("execution_status") not in {"returned"})


def _has_event(events: list[dict[str, Any]], event_type: str) -> bool:
    return any(item.get("event_type") == event_type for item in events)


def _vehicle_status_from_events(events: list[dict[str, Any]]) -> str:
    if _has_event(events, "return_yard") or _has_event(events, "roll_call_in") or _has_event(events, "vehicle_check_in"):
        return "已入库"
    if _has_event(events, "depart_yard") or _has_event(events, "roll_call_out"):
        return "已出库"
    return "未出库"


def _alcohol_status(events: list[dict[str, Any]]) -> str:
    if _has_event(events, "alcohol_test_in"):
        return "入库后已测"
    if _has_event(events, "return_yard"):
        return "入库后未测"
    if _has_event(events, "alcohol_test_out"):
        return "出库前已测"
    return "出库前未测"


def _with_workflow_label(row: dict[str, Any]) -> dict[str, Any]:
    row["label"] = WORKFLOW_LABELS.get(str(row.get("event_type") or ""), row.get("event_type"))
    return row


def get_latest_locations(driver_id: Any = None, limit: int = 50) -> list[dict[str, Any]]:
    params: list[Any] = [get_current_tenant_id()]
    where = ["ll.tenant_id = ?"]
    if driver_id not in ("", None):
        where.append("ll.driver_id = ?")
        params.append(_to_int(driver_id))
    params.append(max(1, min(int(limit or 50), 200)))
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM (
                SELECT
                    ll.*,
                    d.name AS driver_name,
                    v.plate_number,
                    v.vehicle_type,
                    o.oid,
                    o.pickup_location,
                    o.dropoff_location,
                    o.order_date,
                    o.start_time,
                    o.end_time,
                    a.execution_status,
                    ROW_NUMBER() OVER (PARTITION BY ll.driver_id ORDER BY ll.reported_at DESC, ll.id DESC) AS rn
                FROM location_logs ll
                LEFT JOIN drivers d ON d.id = ll.driver_id
                LEFT JOIN vehicles v ON v.id = ll.vehicle_id
                LEFT JOIN assignments a ON a.id = ll.assignment_id
                LEFT JOIN orders o ON o.id = ll.order_id
                WHERE {" AND ".join(where)}
            )
            WHERE rn = 1
            ORDER BY reported_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_with_online_status(dict(row)) for row in rows]


def list_location_logs(driver_id: Any = None, limit: int = 100) -> list[dict[str, Any]]:
    params: list[Any] = [get_current_tenant_id()]
    where = ["ll.tenant_id = ?"]
    if driver_id not in ("", None):
        where.append("ll.driver_id = ?")
        params.append(_to_int(driver_id))
    params.append(max(1, min(int(limit or 100), 300)))
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT ll.*, d.name AS driver_name, v.plate_number, o.oid
            FROM location_logs ll
            LEFT JOIN drivers d ON d.id = ll.driver_id
            LEFT JOIN vehicles v ON v.id = ll.vehicle_id
            LEFT JOIN orders o ON o.id = ll.order_id
            WHERE {" AND ".join(where)}
            ORDER BY ll.reported_at DESC, ll.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_with_online_status(dict(row)) for row in rows]


def latest_reports_by_assignment() -> dict[int, dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*
            FROM driver_reports r
            JOIN (
                SELECT assignment_id, MAX(id) AS max_id
                FROM driver_reports
                WHERE tenant_id = ?
                GROUP BY assignment_id
            ) latest ON latest.max_id = r.id
            WHERE r.tenant_id = ?
            """
            ,
            (get_current_tenant_id(), get_current_tenant_id()),
        ).fetchall()
    return {row["assignment_id"]: dict(row) for row in rows}


def _insert_location_log(conn, payload: dict[str, Any]) -> int | None:
    latitude = _optional_float(payload.get("latitude"))
    longitude = _optional_float(payload.get("longitude"))
    location_text = payload.get("location_text")
    if latitude is None and longitude is None and not location_text:
        return None
    cursor = conn.execute(
        """
        INSERT INTO location_logs (
            tenant_id, driver_id, vehicle_id, assignment_id, order_id,
            latitude, longitude, location_text, source, reported_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            get_current_tenant_id(),
            _to_int(payload.get("driver_id")),
            _to_int(payload.get("vehicle_id")) or None,
            _to_int(payload.get("assignment_id")) or None,
            _to_int(payload.get("order_id")) or None,
            latitude,
            longitude,
            location_text,
            payload.get("source") or "driver",
        ),
    )
    return cursor.lastrowid


def _validate_report_geofence(report_type: str, assignment: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    target_map = {
        "arrive_pickup": ("pickup_latitude", "pickup_longitude", "上车点"),
        "complete_order": ("dropoff_latitude", "dropoff_longitude", "终点"),
    }
    if report_type not in target_map:
        return {"ok": True, "required": False}

    lat_key, lng_key, label = target_map[report_type]
    target_lat = _optional_float(assignment.get(lat_key))
    target_lng = _optional_float(assignment.get(lng_key))
    if target_lat is None or target_lng is None:
        return {"ok": True, "required": False, "skipped_reason": "target_coordinate_missing", "target_label": label}

    driver_lat = _optional_float(payload.get("latitude"))
    driver_lng = _optional_float(payload.get("longitude"))
    if driver_lat is None or driver_lng is None:
        return {
            "ok": False,
            "required": True,
            "target_label": label,
            "reason": "driver_coordinate_missing",
            "allowed_radius_meters": GEOFENCE_RADIUS_METERS,
        }

    distance = _distance_meters(driver_lat, driver_lng, target_lat, target_lng)
    return {
        "ok": distance <= GEOFENCE_RADIUS_METERS,
        "required": True,
        "target_label": label,
        "distance_meters": round(distance),
        "allowed_radius_meters": GEOFENCE_RADIUS_METERS,
        "reason": "ok" if distance <= GEOFENCE_RADIUS_METERS else "out_of_range",
    }


def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _with_online_status(row: dict[str, Any]) -> dict[str, Any]:
    try:
        reported_at = datetime.fromisoformat(str(row.get("reported_at")).replace("Z", ""))
        row["online_status"] = "online" if datetime.utcnow() - reported_at <= timedelta(minutes=15) else "stale"
    except (TypeError, ValueError):
        row["online_status"] = "unknown"
    return row


def _update_vehicle_runtime_status(conn, vehicle_id: Any, status: str | None) -> None:
    vehicle_id_int = _to_int(vehicle_id)
    if not vehicle_id_int or not status:
        return
    conn.execute(
        """
        UPDATE vehicles
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND tenant_id = ?
        """,
        (status, vehicle_id_int, get_current_tenant_id()),
    )


def _decorate_evidence(row: dict[str, Any]) -> dict[str, Any]:
    labels = {
        "pickup": "接客照片",
        "completion": "完成照片",
        "vehicle_condition": "车况照片",
        "arrive_waiting_photo": "到达等待照片",
        "pickup_photo": "接到客人照片",
        "waypoint_photo": "中途地点照片",
        "dropoff_photo": "送达照片",
        "vehicle_check_photo": "车辆点检照片",
        "cleaning_photo": "车辆清扫照片",
        "expense_receipt_photo": "费用小票照片",
    }
    row["label"] = labels.get(row.get("evidence_type"), row.get("evidence_type") or "照片")
    row["event_time"] = row.get("uploaded_at") or row.get("created_at")
    return row


def _decorate_report_event(row: dict[str, Any]) -> dict[str, Any]:
    row["label"] = WORKFLOW_LABELS.get(row.get("report_type"), row.get("report_type") or "司机报备")
    row["event_time"] = row.get("report_time") or row.get("created_at")
    return row


def _decorate_workflow_timeline_event(row: dict[str, Any]) -> dict[str, Any]:
    row["label"] = WORKFLOW_LABELS.get(row.get("event_type"), row.get("event_type") or "工作流事件")
    row["event_time"] = row.get("event_time") or row.get("created_at")
    return row


def _decorate_expense_event(row: dict[str, Any]) -> dict[str, Any]:
    kind_label = "司机垫付" if row.get("expense_kind") == "advance" else "司机代收"
    row["label"] = f"{kind_label}：{row.get('category') or '-'}"
    row["event_time"] = row.get("submitted_at") or row.get("created_at")
    return row


def _timeline_item(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": row.get("id"),
        "assignment_id": row.get("assignment_id"),
        "order_id": row.get("order_id"),
        "driver_id": row.get("driver_id"),
        "label": row.get("label"),
        "event_time": row.get("event_time"),
        "status": row.get("report_status") or row.get("event_status") or row.get("submit_status"),
        "location_text": row.get("location_text"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "note": row.get("note"),
        "file_url": row.get("file_url") or row.get("photo_url") or row.get("receipt_photo_url"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "raw": row,
    }


DRIVER_ASSIGNMENT_SELECT = """
SELECT
    a.id AS assignment_id,
    a.order_id,
    a.driver_id,
    a.vehicle_id,
    a.status AS assignment_status,
    a.execution_status,
    a.assigned_at,
    o.oid,
    o.order_date,
    o.end_date,
    o.start_time,
    o.end_time,
    o.pickup_location,
    o.dropoff_location,
    o.pickup_latitude,
    o.pickup_longitude,
    o.dropoff_latitude,
    o.dropoff_longitude,
    o.order_type,
    o.vehicle_type,
    o.passenger_count,
    o.luggage_count,
    o.guest_name,
    o.guest_contact,
    o.agency_name,
    o.remark,
    o.dispatch_status,
    o.settlement_status,
    d.name AS driver_name,
    d.phone AS driver_phone,
    v.plate_number,
    v.vehicle_type AS assigned_vehicle_type,
    v.status AS vehicle_status
FROM assignments a
JOIN orders o ON o.id = a.order_id
LEFT JOIN drivers d ON d.id = a.driver_id
LEFT JOIN vehicles v ON v.id = a.vehicle_id
"""


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decode_image_payload(image_data: str) -> tuple[str, bytes]:
    suffix = "jpg"
    data = image_data
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", image_data, re.IGNORECASE | re.DOTALL)
    if match:
        suffix = "jpg" if match.group(1).lower() == "jpeg" else match.group(1).lower()
        data = match.group(2)
    try:
        raw = base64.b64decode(data, validate=True)
    except Exception as exc:  # noqa: BLE001 - input validation boundary.
        raise ValueError("invalid_image_base64") from exc
    if not raw:
        raise ValueError("empty_image")
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("image_too_large")
    return suffix, raw

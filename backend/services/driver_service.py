from typing import Any

from backend.db.database import get_connection


REPORT_STATUS_MAP = {
    "confirm_order": "confirmed",
    "depart_yard": "departed",
    "arrive_pickup": "arrived",
    "start_service": "in_service",
    "complete_order": "completed",
    "return_yard": "returned",
}

STATUS_ORDER = ["assigned", "confirmed", "departed", "arrived", "in_service", "completed", "returned"]


def list_driver_assignments(driver_id: Any) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"""
                {DRIVER_ASSIGNMENT_SELECT}
                WHERE a.status = 'active'
                  AND a.driver_id = ?
                  AND COALESCE(o.is_deleted, 0) = 0
                ORDER BY o.order_date ASC, o.start_time ASC, a.id ASC
                """,
                (_to_int(driver_id),),
            ).fetchall()
        ]


def get_driver_assignment(driver_id: Any, assignment_id: Any) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            {DRIVER_ASSIGNMENT_SELECT}
            WHERE a.status = 'active'
              AND a.driver_id = ?
              AND a.id = ?
              AND COALESCE(o.is_deleted, 0) = 0
            """,
            (_to_int(driver_id), _to_int(assignment_id)),
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
    if STATUS_ORDER.index(new_status) < STATUS_ORDER.index(current_status):
        return {"success": False, "error": "execution_status_regression_not_allowed"}

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO driver_reports (
                assignment_id, order_id, driver_id, report_type, report_status,
                report_time, latitude, longitude, location_text, note, photo_url, updated_at
            )
            VALUES (?, ?, ?, ?, 'submitted', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
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
        conn.execute(
            """
            UPDATE assignments
            SET execution_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, assignment_id),
        )
        conn.execute(
            """
            UPDATE orders
            SET execution_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, assignment["order_id"]),
        )
        conn.commit()
    return {"success": True, "report_id": report_id, "new_execution_status": new_status}


def list_driver_reports(driver_id: Any) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM driver_reports
                WHERE driver_id = ?
                ORDER BY report_time DESC, id DESC
                """,
                (_to_int(driver_id),),
            ).fetchall()
        ]


def get_driver_dashboard(driver_id: Any) -> dict[str, Any]:
    assignments = list_driver_assignments(driver_id)
    reports = list_driver_reports(driver_id)
    return {
        "driver_id": _to_int(driver_id),
        "active_assignment_count": len(assignments),
        "report_count": len(reports),
        "next_assignment": assignments[0] if assignments else None,
        "assignments": assignments,
    }


def latest_reports_by_assignment() -> dict[int, dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*
            FROM driver_reports r
            JOIN (
                SELECT assignment_id, MAX(id) AS max_id
                FROM driver_reports
                GROUP BY assignment_id
            ) latest ON latest.max_id = r.id
            """
        ).fetchall()
    return {row["assignment_id"]: dict(row) for row in rows}


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
    o.start_time,
    o.end_time,
    o.pickup_location,
    o.dropoff_location,
    o.order_type,
    o.vehicle_type,
    o.passenger_count,
    o.luggage_count,
    o.guest_name,
    o.guest_contact,
    o.agency_name,
    o.price,
    o.remark,
    o.dispatch_status,
    o.settlement_status,
    d.name AS driver_name,
    d.phone AS driver_phone,
    v.plate_number,
    v.vehicle_type AS assigned_vehicle_type
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

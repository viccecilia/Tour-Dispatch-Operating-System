from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


DEPART_EVENTS = {"depart_yard", "roll_call_out"}
RETURN_EVENTS = {"return_yard", "roll_call_in"}


def get_driver_attendance_daily(target_date: str | None = None) -> dict[str, Any]:
    day = _parse_date(target_date) or date.today()
    tenant_id = get_current_tenant_id()
    rows: list[dict[str, Any]] = []
    with get_connection() as conn:
        drivers = conn.execute(
            """
            SELECT id, name, driver_code, phone
            FROM drivers
            WHERE tenant_id = ?
              AND COALESCE(status, 'available') != 'deleted'
            ORDER BY id
            """,
            (tenant_id,),
        ).fetchall()
        for driver in drivers:
            row = _build_driver_row(conn, dict(driver), day, tenant_id)
            if row:
                rows.append(row)

    summary = {
        "total_drivers": len(rows),
        "departed": sum(1 for row in rows if row.get("depart_time")),
        "returned": sum(1 for row in rows if row.get("return_time")),
        "sleep_risk": sum(1 for row in rows if row.get("sleep_risk_level") == "danger"),
        "missing_report": sum(1 for row in rows if row.get("report_status") == "missing"),
        "average_constraint_hours": _average([row.get("constraint_hours") for row in rows]),
    }
    return {"date": day.isoformat(), "summary": summary, "rows": rows}


def _build_driver_row(conn: Any, driver: dict[str, Any], day: date, tenant_id: int) -> dict[str, Any] | None:
    driver_id = int(driver["id"])
    assignments = _list_driver_assignments_for_day(conn, driver_id, day, tenant_id)
    reports = _list_driver_events_for_day(conn, driver_id, day, tenant_id)
    if not assignments and not reports:
        return None

    vehicle = _pick_vehicle(assignments)
    depart_dt = _first_event_time(reports, DEPART_EVENTS)
    return_dt = _last_event_time(reports, RETURN_EVENTS)
    inferred = False

    if not depart_dt:
        first_assignment = _first_assignment(assignments)
        if first_assignment:
            depart_dt = _combine(day, first_assignment.get("start_time"), minutes_delta=-60)
            inferred = True
    if not return_dt:
        last_assignment = _last_assignment(assignments)
        if last_assignment:
            end_date = _parse_date(last_assignment.get("end_date")) or day
            return_dt = _combine(end_date, last_assignment.get("end_time"), minutes_delta=30)
            inferred = True

    sleep_hours = _reported_number(reports, "sleep_hours")
    rest_hours = _reported_number(reports, "rest_hours")
    if rest_hours is None:
        rest_hours = _estimated_rest_hours(assignments)

    depart_call_dt = depart_dt - timedelta(minutes=_stable_offset(driver_id, day, "depart")) if depart_dt else None
    return_call_dt = return_dt + timedelta(minutes=_stable_offset(driver_id, day, "return")) if return_dt else None
    previous_return_dt = _previous_return_time(conn, driver_id, depart_dt, tenant_id) if depart_dt else None
    rest_interval_hours = _hours_between(previous_return_dt, depart_dt)
    constraint_hours = _constraint_hours(depart_dt, return_dt, rest_hours)
    sleep_assessment = _assess_sleep(sleep_hours, rest_interval_hours, depart_dt, previous_return_dt)

    return {
        "date": day.isoformat(),
        "driver_id": driver_id,
        "driver_name": driver.get("name"),
        "driver_code": driver.get("driver_code"),
        "driver_phone": driver.get("phone"),
        "vehicle_id": vehicle.get("vehicle_id"),
        "vehicle_plate": vehicle.get("plate_number") or vehicle.get("vehicle_plate") or "-",
        "sleep_hours_reported": sleep_hours,
        "depart_call_time": _format_time(depart_call_dt),
        "depart_time": _format_time(depart_dt),
        "return_time": _format_time(return_dt),
        "rest_hours_reported": rest_hours,
        "return_call_time": _format_time(return_call_dt),
        "constraint_hours": constraint_hours,
        "previous_return_time": _format_datetime(previous_return_dt),
        "rest_interval_hours": rest_interval_hours,
        "sleep_risk_level": sleep_assessment["level"],
        "sleep_risk_message": sleep_assessment["message"],
        "report_status": "inferred" if inferred else "reported",
        "assignment_count": len(assignments),
    }


def _list_driver_assignments_for_day(conn: Any, driver_id: int, day: date, tenant_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            a.id AS assignment_id,
            a.driver_id,
            a.vehicle_id,
            o.id AS order_id,
            o.order_date,
            COALESCE(o.end_date, o.order_date) AS end_date,
            o.start_time,
            o.end_time,
            o.pickup_location,
            o.dropoff_location,
            v.plate_number,
            v.plate_no AS vehicle_plate
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
        WHERE a.tenant_id = ?
          AND a.driver_id = ?
          AND a.status = 'active'
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date <= ?
          AND COALESCE(o.end_date, o.order_date) >= ?
        ORDER BY o.order_date, COALESCE(o.start_time, '00:00'), a.id
        """,
        (tenant_id, driver_id, day.isoformat(), day.isoformat()),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_driver_events_for_day(conn: Any, driver_id: int, day: date, tenant_id: int) -> list[dict[str, Any]]:
    start = datetime.combine(day, time.min).isoformat(sep=" ")
    end = datetime.combine(day + timedelta(days=1), time.min).isoformat(sep=" ")
    report_rows = conn.execute(
        """
        SELECT report_type AS event_type, report_time AS event_time, note
        FROM driver_reports
        WHERE tenant_id = ? AND driver_id = ? AND report_time >= ? AND report_time < ?
        """,
        (tenant_id, driver_id, start, end),
    ).fetchall()
    workflow_rows = conn.execute(
        """
        SELECT event_type, event_time, note
        FROM driver_workflow_events
        WHERE tenant_id = ? AND driver_id = ? AND event_time >= ? AND event_time < ?
        """,
        (tenant_id, driver_id, start, end),
    ).fetchall()
    events = [dict(row) for row in report_rows] + [dict(row) for row in workflow_rows]
    return sorted(events, key=lambda item: item.get("event_time") or "")


def _previous_return_time(conn: Any, driver_id: int, before_dt: datetime | None, tenant_id: int) -> datetime | None:
    if not before_dt:
        return None
    before = before_dt.isoformat(sep=" ")
    row = conn.execute(
        """
        SELECT MAX(event_time) AS event_time
        FROM (
            SELECT report_time AS event_time
            FROM driver_reports
            WHERE tenant_id = ? AND driver_id = ? AND report_type IN ('return_yard')
              AND report_time < ?
            UNION ALL
            SELECT event_time
            FROM driver_workflow_events
            WHERE tenant_id = ? AND driver_id = ? AND event_type IN ('return_yard', 'roll_call_in')
              AND event_time < ?
        )
        """,
        (tenant_id, driver_id, before, tenant_id, driver_id, before),
    ).fetchone()
    return _parse_datetime(row["event_time"]) if row and row["event_time"] else None


def _first_event_time(events: list[dict[str, Any]], names: set[str]) -> datetime | None:
    for event in events:
        if event.get("event_type") in names:
            parsed = _parse_datetime(event.get("event_time"))
            if parsed:
                return parsed
    return None


def _last_event_time(events: list[dict[str, Any]], names: set[str]) -> datetime | None:
    for event in reversed(events):
        if event.get("event_type") in names:
            parsed = _parse_datetime(event.get("event_time"))
            if parsed:
                return parsed
    return None


def _reported_number(events: list[dict[str, Any]], key: str) -> float | None:
    for event in reversed(events):
        note = event.get("note")
        if not note:
            continue
        try:
            payload = json_loads(note)
        except ValueError:
            continue
        value = payload.get(key)
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


def json_loads(value: str) -> dict[str, Any]:
    import json

    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("note_payload_not_object")
    return payload


def _estimated_rest_hours(assignments: list[dict[str, Any]]) -> float | None:
    if not assignments:
        return None
    if len(assignments) == 1:
        return 1.0
    total_gap = 0.0
    previous_end: datetime | None = None
    for item in assignments:
        start = _combine(_parse_date(item.get("order_date")) or date.today(), item.get("start_time"))
        end = _combine(_parse_date(item.get("end_date")) or _parse_date(item.get("order_date")) or date.today(), item.get("end_time"))
        if previous_end and start:
            gap = max(0.0, (start - previous_end).total_seconds() / 3600)
            total_gap += min(gap, 2.0)
        if end:
            previous_end = end
    return round(max(1.0, min(total_gap, 3.0)), 2)


def _constraint_hours(depart_dt: datetime | None, return_dt: datetime | None, rest_hours: float | None) -> float | None:
    if not depart_dt or not return_dt:
        return None
    if return_dt < depart_dt:
        return_dt += timedelta(days=1)
    hours = (return_dt - depart_dt).total_seconds() / 3600 - float(rest_hours or 0)
    return round(max(hours, 0), 2)


def _assess_sleep(
    sleep_hours: float | None,
    rest_interval_hours: float | None,
    depart_dt: datetime | None,
    previous_return_dt: datetime | None,
) -> dict[str, str]:
    if sleep_hours is None:
        return {"level": "warning", "message": "睡眠时间未申报"}
    if sleep_hours < 6.5:
        return {"level": "danger", "message": f"申报睡眠 {sleep_hours:g}h，低于公司 6.5h 要求"}
    if previous_return_dt and depart_dt and rest_interval_hours is not None and rest_interval_hours < 8:
        return {
            "level": "danger",
            "message": f"前日入库到今日出库间隔 {rest_interval_hours:g}h，不足 8h，6.5h 睡眠申报不可信",
        }
    return {"level": "ok", "message": "睡眠与前后出入库间隔正常"}


def _pick_vehicle(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    for item in assignments:
        if item.get("vehicle_id") or item.get("plate_number") or item.get("vehicle_plate"):
            return item
    return {}


def _first_assignment(assignments: list[dict[str, Any]]) -> dict[str, Any] | None:
    return assignments[0] if assignments else None


def _last_assignment(assignments: list[dict[str, Any]]) -> dict[str, Any] | None:
    return assignments[-1] if assignments else None


def _stable_offset(driver_id: int, day: date, kind: str) -> int:
    digest = hashlib.sha1(f"{driver_id}:{day.isoformat()}:{kind}".encode("utf-8")).hexdigest()
    return 15 + int(digest[:2], 16) % 6


def _combine(day: date, value: Any, minutes_delta: int = 0) -> datetime | None:
    parsed_time = _parse_time(value)
    if not parsed_time:
        return None
    return datetime.combine(day, parsed_time) + timedelta(minutes=minutes_delta)


def _parse_time(value: Any) -> time | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt, length in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M", 16),
    ):
        try:
            return datetime.strptime(text[:length], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_time(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M") if value else None


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return round(max(0, (end - start).total_seconds() / 3600), 2)


def _average(values: list[Any]) -> float:
    numeric = [float(value) for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 2) if numeric else 0

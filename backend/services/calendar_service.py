from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Any

from backend.db.database import get_connection


LEGEND = [
    {"key": "airport_pickup", "label": "接机", "color": "#2563eb"},
    {"key": "airport_dropoff", "label": "送机", "color": "#16a34a"},
    {"key": "charter", "label": "包车", "color": "#7c3aed"},
    {"key": "exception", "label": "异常", "color": "#dc2626"},
    {"key": "completed", "label": "完结", "color": "#6b7280"},
    {"key": "pending_settlement", "label": "未结算", "color": "#f97316"},
]


def get_dispatch_calendar(filters: dict[str, str]) -> dict[str, Any]:
    view = filters.get("view") if filters.get("view") in {"day", "week", "month"} else "day"
    base_date = _parse_date(filters.get("date"))
    start_date, end_date = _date_range(view, base_date)
    items = _query_calendar_items(filters, start_date, end_date)
    return {
        "ok": True,
        "view": view,
        "date": base_date.isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
        "vehicles": _list_vehicles(),
        "drivers": _list_drivers(),
        "legend": LEGEND,
        "month_summary": _month_summary(items) if view == "month" else [],
    }


def get_dispatch_detail(assignment_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                a.id AS assignment_id,
                a.order_id,
                a.driver_id,
                a.vehicle_id,
                a.status AS assignment_status,
                a.assigned_at,
                a.cancelled_at,
                o.oid,
                o.order_date,
                o.end_date,
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
                o.agency_id,
                o.agency_name,
                o.price,
                o.remark,
                o.dispatch_status,
                o.settlement_status,
                d.name AS driver_name,
                d.phone AS driver_phone,
                v.plate_number,
                v.vehicle_type AS assigned_vehicle_type,
                v.seat_count
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            LEFT JOIN drivers d ON d.id = a.driver_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id
            WHERE a.id = ?
              AND a.status = 'active'
              AND COALESCE(o.is_deleted, 0) = 0
            """,
            (_to_int(assignment_id),),
        ).fetchone()
    if not row:
        return None
    detail = dict(row)
    detail["calendar_color"] = _calendar_color(detail)
    detail["display_title"] = _display_title(detail)
    detail["display_subtitle"] = _display_subtitle(detail)
    return detail


def _query_calendar_items(filters: dict[str, str], start_date: date_cls, end_date: date_cls) -> list[dict[str, Any]]:
    sql = [
        """
        SELECT
            a.id AS assignment_id,
            a.order_id,
            a.driver_id,
            a.vehicle_id,
            a.status AS assignment_status,
            o.order_date,
            o.end_date,
            o.start_time,
            o.end_time,
            o.pickup_location,
            o.dropoff_location,
            o.order_type,
            o.vehicle_type,
            o.dispatch_status,
            o.execution_status,
            o.settlement_status,
            o.oid,
            o.price,
            d.name AS driver_name,
            v.plate_number
        FROM assignments a
        JOIN orders o ON o.id = a.order_id
        LEFT JOIN drivers d ON d.id = a.driver_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id
        WHERE a.status = 'active'
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date <= ?
          AND COALESCE(o.end_date, o.order_date) >= ?
        """
    ]
    params: list[Any] = [end_date.isoformat(), start_date.isoformat()]
    for field, column in (
        ("vehicle_id", "a.vehicle_id"),
        ("driver_id", "a.driver_id"),
        ("order_type", "o.order_type"),
        ("dispatch_status", "o.dispatch_status"),
        ("settlement_status", "o.settlement_status"),
    ):
        value = filters.get(field)
        if value:
            sql.append(f"AND {column} = ?")
            params.append(value)
    sql.append("ORDER BY o.order_date ASC, v.plate_number ASC, o.start_time ASC, a.id ASC")
    with get_connection() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["calendar_color"] = _calendar_color(item)
        item["display_title"] = _display_title(item)
        item["display_subtitle"] = _display_subtitle(item)
        item["start_minute"] = _time_to_minutes(item.get("start_time"))
        item["end_minute"] = _time_to_minutes(item.get("end_time"))
        items.append(item)
    return items


def _list_vehicles() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, plate_number, vehicle_type, seat_count, status
                FROM vehicles
                ORDER BY plate_number ASC, id ASC
                """
            ).fetchall()
        ]


def _list_drivers() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name, phone, status
                FROM drivers
                ORDER BY id ASC
                """
            ).fetchall()
        ]


def _month_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        day = item["order_date"]
        bucket = grouped.setdefault(
            day,
            {"date": day, "order_count": 0, "exception_count": 0, "pending_settlement_count": 0},
        )
        bucket["order_count"] += 1
        if item.get("dispatch_status") == "exception":
            bucket["exception_count"] += 1
        if item.get("settlement_status") == "pending":
            bucket["pending_settlement_count"] += 1
    return [grouped[key] for key in sorted(grouped)]


def _calendar_color(item: dict[str, Any]) -> str:
    if item.get("dispatch_status") == "exception":
        return "#dc2626"
    if item.get("dispatch_status") == "completed":
        return "#6b7280"
    if item.get("settlement_status") == "pending":
        return "#f97316"
    order_type = str(item.get("order_type") or "").lower()
    if order_type in {"接机", "airport_pickup"}:
        return "#2563eb"
    if order_type in {"送机", "airport_dropoff"}:
        return "#16a34a"
    if order_type in {"包车", "charter"}:
        return "#7c3aed"
    return "#334155"


def _display_title(item: dict[str, Any]) -> str:
    start = item.get("start_time") or "--:--"
    end = item.get("end_time") or "--:--"
    return f"{start}-{end} {item.get('pickup_location') or ''} -> {item.get('dropoff_location') or ''}"


def _display_subtitle(item: dict[str, Any]) -> str:
    return f"{item.get('driver_name') or '-'} / {item.get('plate_number') or '-'} / {item.get('dispatch_status') or '-'}"


def _date_range(view: str, base_date: date_cls) -> tuple[date_cls, date_cls]:
    if view == "week":
        start = base_date - timedelta(days=base_date.weekday())
        return start, start + timedelta(days=6)
    if view == "month":
        start = base_date.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    return base_date, base_date


def _parse_date(value: str | None) -> date_cls:
    if not value:
        return date_cls.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date_cls.today()


def _time_to_minutes(value: Any) -> int | None:
    if not value or ":" not in str(value):
        return None
    hour, minute = str(value).split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

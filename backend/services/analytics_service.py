from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


def get_analytics_summary(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    today = date.today()
    date_to = _parse_date(params.get("date_to")) or today
    date_from = _parse_date(params.get("date_from")) or (date_to - timedelta(days=29))
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS order_count,
                   COALESCE(SUM(price), 0) AS revenue,
                   SUM(CASE WHEN dispatch_status = 'assigned' THEN 1 ELSE 0 END) AS assigned_count,
                   SUM(CASE WHEN execution_status IN ('completed', 'returned') THEN 1 ELSE 0 END) AS completed_count,
                   SUM(CASE WHEN settlement_status IN ('pending', 'unsettled') THEN 1 ELSE 0 END) AS unsettled_count,
                   SUM(CASE WHEN price IS NULL OR price = 0 THEN 1 ELSE 0 END) AS missing_price_count
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND order_date BETWEEN ? AND ?
            """,
            (tenant_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchone()
        incident_totals = conn.execute(
            """
            SELECT COUNT(*) AS incident_count,
                   SUM(CASE WHEN status != 'closed' THEN 1 ELSE 0 END) AS open_incident_count
            FROM incidents
            WHERE tenant_id = ?
              AND date(created_at) BETWEEN ? AND ?
            """,
            (tenant_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchone()
        trend = _order_trend(conn, tenant_id, date_from, date_to)
        agency_revenue = _agency_revenue(conn, tenant_id, date_from, date_to)
        driver_performance = _driver_performance(conn, tenant_id, date_from, date_to)
        vehicle_utilization = _vehicle_utilization(conn, tenant_id, date_from, date_to)

    order_count = int(totals["order_count"] or 0)
    completed_count = int(totals["completed_count"] or 0)
    incident_count = int(incident_totals["incident_count"] or 0)
    driver_count = len(driver_performance)
    avg_driver_completion = round(
        sum(float(item.get("completion_rate") or 0) for item in driver_performance) / driver_count,
        1,
    ) if driver_count else 0
    avg_driver_ontime = round(
        sum(float(item.get("ontime_rate") or 0) for item in driver_performance) / driver_count,
        1,
    ) if driver_count else 0
    completion_rate = round(completed_count / order_count * 100, 1) if order_count else 0
    incident_rate = round(incident_count / order_count * 100, 1) if order_count else 0
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "kpis": {
            "order_count": order_count,
            "revenue": float(totals["revenue"] or 0),
            "assigned_count": int(totals["assigned_count"] or 0),
            "completed_count": completed_count,
            "completion_rate": completion_rate,
            "incident_count": incident_count,
            "open_incident_count": int(incident_totals["open_incident_count"] or 0),
            "incident_rate": incident_rate,
            "driver_count": driver_count,
            "avg_driver_completion_rate": avg_driver_completion,
            "avg_driver_ontime_rate": avg_driver_ontime,
            "unsettled_count": int(totals["unsettled_count"] or 0),
            "missing_price_count": int(totals["missing_price_count"] or 0),
        },
        "trend": trend,
        "agency_revenue": agency_revenue,
        "driver_performance": driver_performance,
        "vehicle_utilization": vehicle_utilization,
    }


def _order_trend(conn, tenant_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    rows = {
        row["order_date"]: dict(row)
        for row in conn.execute(
            """
            SELECT order_date,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(price), 0) AS revenue,
                   SUM(CASE WHEN dispatch_status = 'assigned' THEN 1 ELSE 0 END) AS assigned_count,
                   SUM(CASE WHEN execution_status IN ('completed', 'returned') THEN 1 ELSE 0 END) AS completed_count
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND order_date BETWEEN ? AND ?
            GROUP BY order_date
            ORDER BY order_date ASC
            """,
            (tenant_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    }
    items = []
    current = date_from
    while current <= date_to:
        key = current.isoformat()
        row = rows.get(key, {})
        items.append(
            {
                "date": key,
                "order_count": int(row.get("order_count") or 0),
                "revenue": float(row.get("revenue") or 0),
                "assigned_count": int(row.get("assigned_count") or 0),
                "completed_count": int(row.get("completed_count") or 0),
            }
        )
        current += timedelta(days=1)
    return items


def _agency_revenue(conn, tenant_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT COALESCE(NULLIF(agency_name, ''), 'Direct / Unknown') AS agency_name,
                   COUNT(*) AS order_count,
                   COALESCE(SUM(price), 0) AS revenue,
                   COALESCE(SUM(CASE WHEN settlement_status IN ('pending', 'unsettled') THEN price ELSE 0 END), 0) AS pending_amount,
                   SUM(CASE WHEN dispatch_status = 'assigned' THEN 1 ELSE 0 END) AS assigned_count
            FROM orders
            WHERE tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
              AND order_date BETWEEN ? AND ?
            GROUP BY COALESCE(NULLIF(agency_name, ''), 'Direct / Unknown')
            ORDER BY revenue DESC, order_count DESC
            LIMIT 15
            """,
            (tenant_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    ]


def _driver_performance(conn, tenant_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        WITH first_arrival AS (
            SELECT assignment_id, MIN(report_time) AS arrival_time
            FROM driver_reports
            WHERE tenant_id = ?
              AND report_type IN ('arrive_pickup', 'start_service')
            GROUP BY assignment_id
        ),
        incident_by_assignment AS (
            SELECT assignment_id,
                   COUNT(*) AS incident_count,
                   SUM(CASE WHEN incident_type = 'complaint' THEN 1 ELSE 0 END) AS complaint_count
            FROM incidents
            WHERE tenant_id = ?
            GROUP BY assignment_id
        )
        SELECT d.id AS driver_id,
               d.name AS driver_name,
               d.driver_code,
               COUNT(DISTINCT o.id) AS order_count,
               COALESCE(SUM(o.price), 0) AS revenue,
               COALESCE(SUM(COALESCE(o.driver_salary_jpy, 0)), 0) AS driver_income,
               COUNT(DISTINCT CASE WHEN a.execution_status IN ('completed', 'returned') OR o.execution_status IN ('completed', 'returned') THEN o.id END) AS completed_count,
               COUNT(DISTINCT CASE WHEN fa.arrival_time IS NOT NULL
                    AND o.order_date IS NOT NULL
                    AND o.start_time IS NOT NULL
                    AND datetime(fa.arrival_time) <= datetime(o.order_date || ' ' || substr(o.start_time, 1, 5), '+15 minutes')
                    THEN a.id END) AS ontime_count,
               COALESCE(SUM(iba.incident_count), 0) AS incident_count,
               COALESCE(SUM(iba.complaint_count), 0) AS complaint_count
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
        LEFT JOIN incident_by_assignment iba ON iba.assignment_id = a.id
        LEFT JOIN first_arrival fa ON fa.assignment_id = a.id
        WHERE a.tenant_id = ?
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date BETWEEN ? AND ?
          AND a.status IN ('active', 'completed')
        GROUP BY d.id, d.name, d.driver_code
        ORDER BY driver_income DESC, completed_count DESC, order_count DESC
        LIMIT 20
        """,
        (tenant_id, tenant_id, tenant_id, date_from.isoformat(), date_to.isoformat()),
    ).fetchall()
    result = []
    for index, row in enumerate(rows, start=1):
        order_count = int(row["order_count"] or 0)
        completed_count = int(row["completed_count"] or 0)
        ontime_count = int(row["ontime_count"] or 0)
        incident_count = int(row["incident_count"] or 0)
        complaint_count = int(row["complaint_count"] or 0)
        driver_income = float(row["driver_income"] or 0)
        result.append(
            {
                **dict(row),
                "rank": index,
                "driver_income": driver_income,
                "completion_rate": round(completed_count / order_count * 100, 1) if order_count else 0,
                "ontime_count": ontime_count,
                "ontime_rate": round(ontime_count / order_count * 100, 1) if order_count else 0,
                "incident_rate": round(incident_count / order_count * 100, 1) if order_count else 0,
                "complaint_rate": round(complaint_count / order_count * 100, 1) if order_count else 0,
            }
        )
    return result


def _vehicle_utilization(conn, tenant_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT v.id AS vehicle_id,
               v.plate_number,
               v.vehicle_type,
               COUNT(DISTINCT o.id) AS order_count,
               COALESCE(SUM(o.price), 0) AS revenue,
               GROUP_CONCAT(o.start_time || '-' || o.end_time) AS time_ranges
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
        WHERE a.tenant_id = ?
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date BETWEEN ? AND ?
          AND a.status IN ('active', 'completed')
        GROUP BY v.id, v.plate_number, v.vehicle_type
        ORDER BY order_count DESC, revenue DESC
        LIMIT 20
        """,
        (tenant_id, date_from.isoformat(), date_to.isoformat()),
    ).fetchall()
    days = max((date_to - date_from).days + 1, 1)
    capacity_hours = days * 10
    result = []
    for row in rows:
        busy_hours = _busy_hours(row["time_ranges"] or "")
        result.append(
            {
                **dict(row),
                "busy_hours": round(busy_hours, 1),
                "utilization_rate": round(min(busy_hours / capacity_hours * 100, 100), 1) if capacity_hours else 0,
            }
        )
    return result


def _busy_hours(value: str) -> float:
    total = 0.0
    for item in value.split(","):
        if "-" not in item:
            continue
        start, end = item.split("-", 1)
        start_minutes = _minutes(start)
        end_minutes = _minutes(end)
        if start_minutes is None or end_minutes is None:
            continue
        if end_minutes <= start_minutes:
            end_minutes += 24 * 60
        total += max(end_minutes - start_minutes, 0) / 60
    return total


def _minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    try:
        parsed = datetime.strptime(value[:5], "%H:%M")
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None

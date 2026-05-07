import re
from typing import Any

from backend.db.database import get_connection


def list_available_drivers() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name, phone, status, created_at, updated_at
                FROM drivers
                WHERE status = 'available'
                ORDER BY id
                """
            ).fetchall()
        ]


def list_available_vehicles() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, plate_number, vehicle_type, seat_count, status, created_at, updated_at
                FROM vehicles
                WHERE status = 'available'
                ORDER BY id
                """
            ).fetchall()
        ]


def list_unassigned_orders() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM orders
                WHERE COALESCE(is_deleted, 0) = 0
                  AND dispatch_status = 'unassigned'
                ORDER BY order_date ASC, start_time ASC, id ASC
                """
            ).fetchall()
        ]


def list_assignments(status: str | None = "active") -> list[dict[str, Any]]:
    sql = [
        """
        SELECT
            a.id,
            a.order_id,
            a.driver_id,
            a.vehicle_id,
            a.status,
            a.execution_status,
            a.assigned_at,
            a.cancelled_at,
            a.created_at,
            a.updated_at,
            o.oid,
            o.order_date,
            o.end_date,
            o.start_time,
            o.end_time,
            o.pickup_location,
            o.dropoff_location,
            o.order_type,
            o.vehicle_type AS order_vehicle_type,
            o.agency_name,
            o.price,
            o.dispatch_status,
            d.name AS driver_name,
            d.phone AS driver_phone,
            v.plate_number,
            v.vehicle_type AS assigned_vehicle_type,
            r.report_type AS latest_report_type,
            r.report_time AS latest_report_time,
            r.location_text AS latest_location_text
        FROM assignments a
        JOIN orders o ON o.id = a.order_id
        LEFT JOIN drivers d ON d.id = a.driver_id
        LEFT JOIN vehicles v ON v.id = a.vehicle_id
        LEFT JOIN (
            SELECT rr.*
            FROM driver_reports rr
            JOIN (
                SELECT assignment_id, MAX(id) AS max_id
                FROM driver_reports
                GROUP BY assignment_id
            ) latest ON latest.max_id = rr.id
        ) r ON r.assignment_id = a.id
        WHERE COALESCE(o.is_deleted, 0) = 0
        """
    ]
    params: list[Any] = []
    if status:
        sql.append("AND a.status = ?")
        params.append(status)
    sql.append("ORDER BY o.order_date ASC, o.start_time ASC, a.id DESC")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def assign_orders(order_ids: list[Any], driver_id: Any, vehicle_id: Any) -> dict[str, Any]:
    normalized_order_ids = _normalize_ids(order_ids)
    driver_id_int = _to_int(driver_id)
    vehicle_id_int = _to_int(vehicle_id)
    if not normalized_order_ids or not driver_id_int or not vehicle_id_int:
        raise ValueError("missing_order_driver_or_vehicle")

    with get_connection() as conn:
        orders = _fetch_orders(conn, normalized_order_ids)
        if len(orders) != len(normalized_order_ids):
            raise ValueError("order_not_found")
        driver = _fetch_driver(conn, driver_id_int)
        vehicle = _fetch_vehicle(conn, vehicle_id_int)
        if not driver or not vehicle:
            raise ValueError("driver_or_vehicle_not_found")
        conflicts = _find_conflicts(conn, orders, driver_id_int, vehicle_id_int)
        if conflicts:
            return {
                "success": False,
                "assignment_ids": [],
                "updated_order_ids": [],
                "conflicts": conflicts,
            }

        assignment_ids: list[int] = []
        for order in orders:
            cursor = conn.execute(
                """
                INSERT INTO assignments (order_id, driver_id, vehicle_id, status, execution_status, assigned_at, updated_at)
                VALUES (?, ?, ?, 'active', 'assigned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (order["id"], driver_id_int, vehicle_id_int),
            )
            assignment_ids.append(cursor.lastrowid)
            conn.execute(
                """
                UPDATE orders
                SET oid = ?,
                    dispatch_status = 'assigned',
                    execution_status = 'assigned',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_build_assigned_oid(order.get("oid"), vehicle["plate_number"], driver["name"]), order["id"]),
            )
        conn.commit()

    return {
        "success": True,
        "assignment_ids": assignment_ids,
        "updated_order_ids": [order["id"] for order in orders],
        "conflicts": [],
    }


def cancel_assignment(assignment_id: Any = None, order_id: Any = None) -> dict[str, Any]:
    with get_connection() as conn:
        row = None
        if assignment_id:
            row = conn.execute(
                """
                SELECT *
                FROM assignments
                WHERE id = ? AND status = 'active'
                """,
                (_to_int(assignment_id),),
            ).fetchone()
        elif order_id:
            row = conn.execute(
                """
                SELECT *
                FROM assignments
                WHERE order_id = ? AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (_to_int(order_id),),
            ).fetchone()
        if not row:
            return {"success": False, "error": "active_assignment_not_found"}

        conn.execute(
            """
            UPDATE assignments
            SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["id"],),
        )
        conn.execute(
            """
            UPDATE orders
            SET dispatch_status = 'unassigned', execution_status = 'assigned', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["order_id"],),
        )
        conn.commit()
    return {
        "success": True,
        "cancelled_assignment_id": row["id"],
        "updated_order_id": row["order_id"],
        "dispatch_status": "unassigned",
    }


def reassign_orders(order_ids: list[Any], new_driver_id: Any, new_vehicle_id: Any) -> dict[str, Any]:
    normalized_order_ids = _normalize_ids(order_ids)
    cancelled_ids: list[int] = []
    with get_connection() as conn:
        for order_id in normalized_order_ids:
            rows = conn.execute(
                """
                SELECT id
                FROM assignments
                WHERE order_id = ? AND status = 'active'
                """,
                (order_id,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE assignments
                    SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (row["id"],),
                )
                cancelled_ids.append(row["id"])
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'unassigned', execution_status = 'assigned', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (order_id,),
            )
        conn.commit()

    assigned = assign_orders(normalized_order_ids, new_driver_id, new_vehicle_id)
    return {
        "success": assigned["success"],
        "new_assignment_ids": assigned["assignment_ids"],
        "cancelled_old_assignment_ids": cancelled_ids,
        "updated_order_ids": assigned["updated_order_ids"],
        "conflicts": assigned["conflicts"],
    }


def route_suggestion(order_ids: list[Any]) -> dict[str, Any]:
    normalized_order_ids = _normalize_ids(order_ids)
    with get_connection() as conn:
        orders = _fetch_orders(conn, normalized_order_ids)
    ordered = sorted(
        [dict(order) for order in orders],
        key=lambda order: (order.get("order_date") or "", order.get("start_time") or "", order.get("id") or 0),
    )
    links = []
    for index in range(1, len(ordered)):
        previous = ordered[index - 1]
        current = ordered[index]
        links.append(
            {
                "from_order_id": previous["id"],
                "to_order_id": current["id"],
                "handoff": f"{previous.get('dropoff_location') or ''} -> {current.get('pickup_location') or ''}",
            }
        )
    return {"orders": ordered, "links": links}


def _fetch_orders(conn, order_ids: list[int]) -> list[dict[str, Any]]:
    if not order_ids:
        return []
    placeholders = ", ".join(["?"] * len(order_ids))
    rows = conn.execute(
        f"""
        SELECT *
        FROM orders
        WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 0
        """,
        order_ids,
    ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[order_id] for order_id in order_ids if order_id in by_id]


def _find_conflicts(conn, orders: list[dict[str, Any]], driver_id: int, vehicle_id: int) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for index, order in enumerate(orders):
        if order.get("dispatch_status") == "assigned":
            conflicts.append({"order_id": order["id"], "type": "order_already_assigned"})

        for other in orders[index + 1:]:
            if _orders_overlap(order, other):
                conflicts.append(
                    {
                        "order_id": order["id"],
                        "conflict_order_id": other["id"],
                        "type": "selected_orders_time_overlap",
                    }
                )

        rows = conn.execute(
            """
            SELECT a.id AS assignment_id, a.driver_id, a.vehicle_id, o.*
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            WHERE a.status = 'active'
              AND COALESCE(o.is_deleted, 0) = 0
              AND o.id != ?
              AND (a.driver_id = ? OR a.vehicle_id = ?)
            """,
            (order["id"], driver_id, vehicle_id),
        ).fetchall()
        for row in rows:
            active_order = dict(row)
            if not _orders_overlap(order, active_order):
                continue
            if active_order["driver_id"] == driver_id:
                conflicts.append(
                    {
                        "order_id": order["id"],
                        "conflict_order_id": active_order["id"],
                        "assignment_id": active_order["assignment_id"],
                        "type": "driver_time_overlap",
                    }
                )
            if active_order["vehicle_id"] == vehicle_id:
                conflicts.append(
                    {
                        "order_id": order["id"],
                        "conflict_order_id": active_order["id"],
                        "assignment_id": active_order["assignment_id"],
                        "type": "vehicle_time_overlap",
                    }
                )
    return conflicts


def _fetch_driver(conn, driver_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT id, name FROM drivers WHERE id = ?", (driver_id,)).fetchone()
    return dict(row) if row else None


def _fetch_vehicle(conn, vehicle_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT id, plate_number FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    return dict(row) if row else None


def _build_assigned_oid(current_oid: Any, plate_number: Any, driver_name: Any) -> str:
    base = str(current_oid or "").strip() or "ORDER"
    parts = base.split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        base = "-".join(parts[:2])
    plate_code = _plate_code(plate_number)
    driver_code = _driver_code(driver_name)
    return f"{base}-{plate_code}-{driver_code}"


def _plate_code(value: Any) -> str:
    chars = re.sub(r"[^0-9A-Za-z]", "", str(value or ""))
    return (chars[-4:] or "CAR0").upper()


def _driver_code(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    ascii_chars = "".join(ch for ch in text.upper() if "A" <= ch <= "Z")
    if ascii_chars:
        return ascii_chars[:3]
    return (text[:2] or "DR")


def _orders_overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if first.get("order_date") != second.get("order_date"):
        return False
    first_start = _time_to_minutes(first.get("start_time"))
    first_end = _time_to_minutes(first.get("end_time"))
    second_start = _time_to_minutes(second.get("start_time"))
    second_end = _time_to_minutes(second.get("end_time"))
    if None in (first_start, first_end, second_start, second_end):
        return False
    return first_start < second_end and second_start < first_end


def _time_to_minutes(value: Any) -> int | None:
    if not value or ":" not in str(value):
        return None
    hour, minute = str(value).split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def _normalize_ids(values: list[Any]) -> list[int]:
    normalized = []
    for value in values or []:
        parsed = _to_int(value)
        if parsed:
            normalized.append(parsed)
    return normalized


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

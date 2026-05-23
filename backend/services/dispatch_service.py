import re
from typing import Any

from backend.db.database import get_connection
from backend.services.order_number_service import build_order_oid, normalize_vehicle_type_code, plate_short_code
from backend.services.tenant_context import get_current_tenant_id


def list_available_drivers() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name, phone, status, driver_code, driver_language, office, created_at, updated_at
                FROM drivers
                WHERE status = 'available' AND tenant_id = ?
                ORDER BY id
                """
                ,
                (get_current_tenant_id(),),
            ).fetchall()
        ]


def list_available_vehicles() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, plate_number, vehicle_type, seat_count, status, plate_short_code, vehicle_type_code, vehicle_color, snow_tire, created_at, updated_at
                FROM vehicles
                WHERE status = 'available' AND tenant_id = ?
                ORDER BY id
                """
                ,
                (get_current_tenant_id(),),
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
                  AND tenant_id = ?
                ORDER BY order_date ASC, start_time ASC, id ASC
                """
                ,
                (get_current_tenant_id(),),
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
            v.status AS vehicle_status,
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
          AND a.tenant_id = ?
          AND o.tenant_id = ?
        """
    ]
    params: list[Any] = [get_current_tenant_id(), get_current_tenant_id()]
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
                INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status, execution_status, assigned_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', 'assigned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (get_current_tenant_id(), order["id"], driver_id_int, vehicle_id_int),
            )
            assignment_ids.append(cursor.lastrowid)
            assigned_oid = _build_assigned_oid(conn, order, vehicle, driver)
            conn.execute(
                """
                UPDATE orders
                SET oid = ?,
                    plate_short_code = ?,
                    driver_code = COALESCE(NULLIF(driver_code, ''), ?),
                    vehicle_type_code = COALESCE(NULLIF(vehicle_type_code, ''), ?),
                    dispatch_status = 'assigned',
                    execution_status = 'assigned',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    assigned_oid,
                    vehicle.get("plate_short_code") or plate_short_code(vehicle["plate_number"]),
                    driver.get("driver_code") or _driver_code(driver.get("name")),
                    vehicle.get("vehicle_type_code") or normalize_vehicle_type_code(order.get("vehicle_type"), vehicle.get("vehicle_type")),
                    order["id"],
                    get_current_tenant_id(),
                ),
            )
        conn.commit()

    from backend.services.notification_service import notify_dispatch_assigned

    notify_dispatch_assigned(
        assignment_ids,
        [order["id"] for order in orders],
        driver_id=driver_id_int,
        driver_name=driver.get("name"),
        plate_number=vehicle.get("plate_number"),
    )
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
                WHERE id = ? AND status = 'active' AND tenant_id = ?
                """,
                (_to_int(assignment_id), get_current_tenant_id()),
            ).fetchone()
        elif order_id:
            row = conn.execute(
                """
                SELECT *
                FROM assignments
                WHERE order_id = ? AND status = 'active' AND tenant_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (_to_int(order_id), get_current_tenant_id()),
            ).fetchone()
        if not row:
            return {"success": False, "error": "active_assignment_not_found"}

        conn.execute(
            """
            UPDATE assignments
            SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (row["id"], get_current_tenant_id()),
        )
        conn.execute(
            """
            UPDATE orders
            SET dispatch_status = 'unassigned', execution_status = 'assigned', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (row["order_id"], get_current_tenant_id()),
        )
        _mark_vehicle_available_if_idle(conn, row["vehicle_id"])
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
                WHERE order_id = ? AND status = 'active' AND tenant_id = ?
                """,
                (order_id, get_current_tenant_id()),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE assignments
                    SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (row["id"], get_current_tenant_id()),
                )
                old_assignment = conn.execute(
                    "SELECT vehicle_id FROM assignments WHERE id = ? AND tenant_id = ?",
                    (row["id"], get_current_tenant_id()),
                ).fetchone()
                if old_assignment:
                    _mark_vehicle_available_if_idle(conn, old_assignment["vehicle_id"])
                cancelled_ids.append(row["id"])
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'unassigned', execution_status = 'assigned', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (order_id, get_current_tenant_id()),
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
    ordered = _optimized_order_sequence([dict(order) for order in orders])
    links = []
    risk_count = 0
    total_score = 0
    for index in range(1, len(ordered)):
        previous = ordered[index - 1]
        current = ordered[index]
        score, risk, reasons = _handoff_metrics(previous, current)
        if risk != "low":
            risk_count += 1
        total_score += score
        links.append(
            {
                "from_order_id": previous["id"],
                "to_order_id": current["id"],
                "handoff": f"{previous.get('dropoff_location') or ''} -> {current.get('pickup_location') or ''}",
                "score": score,
                "risk": risk,
                "reasons": reasons,
                "time_gap_minutes": _time_gap_minutes(previous, current),
            }
        )
    average_score = round(total_score / len(links), 1) if links else 100
    return {
        "orders": ordered,
        "links": links,
        "summary": {
            "order_count": len(ordered),
            "link_count": len(links),
            "average_score": average_score,
            "risk_count": risk_count,
            "same_vehicle_suggestion": len(ordered) > 1 and risk_count == 0,
            "message": _route_summary_message(len(ordered), average_score, risk_count),
        },
    }


def _optimized_order_sequence(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Dispatch safety rule: never move a later order ahead of an earlier one.
    # The optimization output is chronological first; adjacent links carry the route score.
    return sorted(orders, key=_route_sort_key)


def _route_sort_key(order: dict[str, Any]) -> tuple:
    return (order.get("order_date") or "", order.get("start_time") or "", order.get("pickup_location") or "", order.get("id") or 0)


def _candidate_score(previous: dict[str, Any], current: dict[str, Any]) -> int:
    score, risk, _ = _handoff_metrics(previous, current)
    if risk == "high":
        score -= 30
    if _time_gap_minutes(previous, current) is not None and _time_gap_minutes(previous, current) < 0:
        score -= 40
    return score


def _handoff_metrics(previous: dict[str, Any], current: dict[str, Any]) -> tuple[int, str, list[str]]:
    reasons: list[str] = []
    score = 50
    gap = _time_gap_minutes(previous, current)
    if gap is None:
        reasons.append("时间不完整，无法判断间隔。")
        score -= 15
    elif gap < 0:
        reasons.append(f"时间重叠 {abs(gap)} 分钟，不能作为同车连续单。")
        score -= 60
    elif gap < 30:
        reasons.append(f"间隔 {gap} 分钟，接单时间偏紧。")
        score -= 15
    elif gap <= 180:
        reasons.append(f"间隔 {gap} 分钟，适合同车接龙。")
        score += 20
    else:
        reasons.append(f"间隔 {gap} 分钟，车辆等待时间较长。")
        score -= 5

    location_score = _location_similarity(previous.get("dropoff_location"), current.get("pickup_location"))
    score += int(location_score * 0.35)
    if location_score >= 80:
        reasons.append("上一单终点和下一单起点高度匹配。")
    elif location_score >= 45:
        reasons.append("上一单终点和下一单起点有部分地点重合。")
    else:
        reasons.append("上一单终点和下一单起点差异较大，可能空驶。")

    score = max(0, min(100, score))
    if score < 45 or (gap is not None and gap < 0):
        risk = "high"
    elif score < 70:
        risk = "medium"
    else:
        risk = "low"
    return score, risk, reasons


def _time_gap_minutes(previous: dict[str, Any], current: dict[str, Any]) -> int | None:
    if previous.get("order_date") != current.get("order_date"):
        return None
    previous_end = _time_to_minutes(previous.get("end_time"))
    current_start = _time_to_minutes(current.get("start_time"))
    if previous_end is None or current_start is None:
        return None
    return current_start - previous_end


def _location_similarity(left: Any, right: Any) -> int:
    left_text = _normalize_location(left)
    right_text = _normalize_location(right)
    if not left_text or not right_text:
        return 0
    if left_text == right_text:
        return 100
    if left_text in right_text or right_text in left_text:
        return 85
    left_tokens = _location_tokens(left_text)
    right_tokens = _location_tokens(right_text)
    if not left_tokens or not right_tokens:
        return 0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return int((overlap / union) * 100) if union else 0


def _normalize_location(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "").lower())
    aliases = {
        "关空": "关西机场",
        "kix": "关西机场",
        "关西": "关西机场",
        "大阪市内": "大阪",
        "osaka": "大阪",
        "京都市内": "京都",
        "tokyo": "东京",
    }
    for source, target in aliases.items():
        text = text.replace(source, target)
    return re.sub(r"[-→>到至往返/、,，.。()（）]", "", text)


def _location_tokens(text: str) -> set[str]:
    tokens = {text[index : index + 2] for index in range(max(0, len(text) - 1))}
    known = {"大阪", "京都", "奈良", "关西机场", "神户", "名古屋", "东京", "酒店", "机场", "车站", "环球", "美山"}
    return tokens | {item for item in known if item in text}


def _route_summary_message(order_count: int, average_score: float, risk_count: int) -> str:
    if order_count <= 1:
        return "单订单无需接龙优化。"
    if risk_count == 0 and average_score >= 70:
        return "接龙顺序较顺，可以考虑同车多单。"
    if risk_count:
        return f"发现 {risk_count} 段空驶或时间风险，请人工确认后再派车。"
    return "已生成时间优先的接龙顺序，建议人工复核地点衔接。"


def _fetch_orders(conn, order_ids: list[int]) -> list[dict[str, Any]]:
    if not order_ids:
        return []
    placeholders = ", ".join(["?"] * len(order_ids))
    rows = conn.execute(
        f"""
        SELECT *
        FROM orders
        WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 0 AND tenant_id = ?
        """,
        [*order_ids, get_current_tenant_id()],
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
              AND a.tenant_id = ?
              AND o.tenant_id = ?
              AND o.id != ?
              AND (a.driver_id = ? OR a.vehicle_id = ?)
            """,
            (get_current_tenant_id(), get_current_tenant_id(), order["id"], driver_id, vehicle_id),
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
    row = conn.execute("SELECT id, name, driver_code, driver_language FROM drivers WHERE id = ? AND tenant_id = ?", (driver_id, get_current_tenant_id())).fetchone()
    return dict(row) if row else None


def _fetch_vehicle(conn, vehicle_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT id, plate_number, vehicle_type, plate_short_code, vehicle_type_code, vehicle_color, snow_tire FROM vehicles WHERE id = ? AND tenant_id = ?", (vehicle_id, get_current_tenant_id())).fetchone()
    return dict(row) if row else None


def _mark_vehicle_available_if_idle(conn, vehicle_id: Any) -> None:
    vehicle_id_int = _to_int(vehicle_id)
    if not vehicle_id_int:
        return
    active = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM assignments
        WHERE vehicle_id = ?
          AND tenant_id = ?
          AND status = 'active'
          AND COALESCE(execution_status, 'assigned') NOT IN ('completed', 'returned')
        """,
        (vehicle_id_int, get_current_tenant_id()),
    ).fetchone()
    if active and int(active["total"] or 0) > 0:
        return
    conn.execute(
        """
        UPDATE vehicles
        SET status = 'available', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND tenant_id = ? AND status IN ('outbound', 'in_service', 'returned')
        """,
        (vehicle_id_int, get_current_tenant_id()),
    )


def _build_assigned_oid(conn, order: dict[str, Any], vehicle: dict[str, Any], driver: dict[str, Any]) -> str:
    serial = _serial_for_order(conn, order)
    vehicle_code = vehicle.get("vehicle_type_code") or normalize_vehicle_type_code(order.get("vehicle_type_code"), order.get("vehicle_type"), vehicle.get("vehicle_type"))
    return build_order_oid(
        order_note_code=order.get("order_note_code"),
        order_source=order.get("order_source"),
        order_date=order.get("order_date"),
        serial=serial,
        plate_code=vehicle.get("plate_short_code") or plate_short_code(vehicle.get("plate_number")),
        driver_code=order.get("driver_code") or driver.get("driver_code"),
        driver_name=driver.get("name"),
        vehicle_type_code=vehicle_code,
        temporary=False,
    )


def _serial_for_order(conn, order: dict[str, Any]) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE order_date = ? AND id <= ? AND COALESCE(is_deleted, 0) = 0 AND tenant_id = ?
        """,
        (order.get("order_date"), order.get("id"), get_current_tenant_id()),
    ).fetchone()
    return int(row["count"] if row else 0) or int(order.get("id") or 1)


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

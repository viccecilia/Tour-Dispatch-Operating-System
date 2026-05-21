from typing import Any

from backend.db.database import get_connection
from backend.services.dispatch_service import _find_conflicts, _normalize_ids
from backend.services.tenant_context import get_current_tenant_id


def recommend_dispatch(order_ids: list[Any]) -> dict[str, Any]:
    normalized_order_ids = _normalize_ids(order_ids)
    if not normalized_order_ids:
        return {"success": False, "error": "missing_order_ids", "recommendations": []}

    with get_connection() as conn:
        orders = _fetch_orders(conn, normalized_order_ids)
        drivers = _fetch_available_drivers(conn)
        vehicles = _fetch_available_vehicles(conn)
        recommendations = []
        for driver in drivers:
            for vehicle in vehicles:
                score, reasons, conflicts = _score_pair(conn, orders, driver, vehicle)
                recommendations.append(
                    {
                        "driver": driver,
                        "vehicle": vehicle,
                        "score": score,
                        "reasons": reasons,
                        "conflicts": conflicts,
                    }
                )

    recommendations.sort(key=lambda item: (item["score"], -len(item["conflicts"])), reverse=True)
    return {
        "success": True,
        "order_ids": normalized_order_ids,
        "recommendations": recommendations[:5],
    }


def _score_pair(conn, orders: list[dict[str, Any]], driver: dict[str, Any], vehicle: dict[str, Any]) -> tuple[int, list[str], list[dict[str, Any]]]:
    score = 60
    reasons: list[str] = []
    conflicts = _find_conflicts(conn, orders, driver["id"], vehicle["id"])
    if conflicts:
        score -= 70
        reasons.append(f"发现 {len(conflicts)} 个时间冲突，不建议直接派给该司机/车辆。")
    else:
        score += 25
        reasons.append("未发现司机或车辆时间重叠。")

    if _vehicle_matches_orders(vehicle, orders):
        score += 15
        reasons.append("车辆类型与订单车型要求匹配。")
    else:
        score -= 10
        reasons.append("车型匹配度一般，需要人工确认。")

    handoff_score, handoff_reason = _handoff_score(orders)
    score += handoff_score
    reasons.append(handoff_reason)

    if driver.get("driver_language"):
        score += 5
        reasons.append(f"司机语言信息明确：{driver['driver_language']}。")
    if vehicle.get("snow_tire"):
        reasons.append(f"车辆雪胎标记：{vehicle['snow_tire']}。")
    return max(0, min(100, score)), reasons, conflicts


def _vehicle_matches_orders(vehicle: dict[str, Any], orders: list[dict[str, Any]]) -> bool:
    vehicle_text = f"{vehicle.get('vehicle_type') or ''} {vehicle.get('vehicle_type_code') or ''}".lower()
    if not vehicle_text.strip():
        return False
    matched = 0
    for order in orders:
        want = f"{order.get('vehicle_type') or ''} {order.get('vehicle_type_code') or ''}".lower()
        if not want.strip() or want in vehicle_text or vehicle_text in want:
            matched += 1
    return matched == len(orders)


def _handoff_score(orders: list[dict[str, Any]]) -> tuple[int, str]:
    ordered = sorted(orders, key=lambda item: (item.get("order_date") or "", item.get("start_time") or "", item.get("id") or 0))
    if len(ordered) < 2:
        return 5, "单订单派车，无需接龙。"
    good_handoffs = 0
    links = []
    for previous, current in zip(ordered, ordered[1:]):
        prev_drop = str(previous.get("dropoff_location") or "")
        next_pick = str(current.get("pickup_location") or "")
        if prev_drop and next_pick and (prev_drop in next_pick or next_pick in prev_drop):
            good_handoffs += 1
        links.append(f"{prev_drop or '-'} -> {next_pick or '-'}")
    if good_handoffs:
        return 10 + good_handoffs * 5, f"地点接龙较顺：{' / '.join(links[:3])}。"
    return 0, f"地点接龙需人工判断：{' / '.join(links[:3])}。"


def _fetch_orders(conn, order_ids: list[int]) -> list[dict[str, Any]]:
    placeholders = ", ".join(["?"] * len(order_ids))
    rows = conn.execute(
        f"""
        SELECT *
        FROM orders
        WHERE id IN ({placeholders})
          AND tenant_id = ?
          AND COALESCE(is_deleted, 0) = 0
        """,
        [*order_ids, get_current_tenant_id()],
    ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[order_id] for order_id in order_ids if order_id in by_id]


def _fetch_available_drivers(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, name, phone, status, driver_code, driver_language, office
            FROM drivers
            WHERE tenant_id = ? AND status = 'available'
            ORDER BY id
            """,
            (get_current_tenant_id(),),
        ).fetchall()
    ]


def _fetch_available_vehicles(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, plate_number, vehicle_type, seat_count, status, plate_short_code, vehicle_type_code, vehicle_color, snow_tire
            FROM vehicles
            WHERE tenant_id = ? AND status = 'available'
            ORDER BY id
            """,
            (get_current_tenant_id(),),
        ).fetchall()
    ]

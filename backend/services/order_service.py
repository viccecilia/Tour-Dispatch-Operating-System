from typing import Any, Optional

from backend.db.database import get_connection


ORDER_FIELDS = [
    "oid",
    "order_date",
    "end_date",
    "start_time",
    "end_time",
    "pickup_location",
    "dropoff_location",
    "order_type",
    "vehicle_type",
    "passenger_count",
    "luggage_count",
    "guest_name",
    "guest_contact",
    "agency_id",
    "agency_name",
    "price",
    "remark",
    "dispatch_status",
    "settlement_status",
]

REQUIRED_FIELDS = ["order_date", "pickup_location", "dropoff_location"]


def list_orders(filters: dict[str, str]) -> list[dict[str, Any]]:
    sql = ["SELECT * FROM orders WHERE COALESCE(is_deleted, 0) = 0"]
    params: list[Any] = []

    for field in ("order_date", "agency_id", "dispatch_status", "settlement_status"):
        value = filters.get(field)
        if value:
            sql.append(f"AND {field} = ?")
            params.append(value)

    agency_name = filters.get("agency_name")
    if agency_name:
        sql.append("AND agency_name LIKE ?")
        params.append(f"%{agency_name}%")

    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        sql.append(
            """
            AND (
                oid LIKE ?
                OR pickup_location LIKE ?
                OR dropoff_location LIKE ?
                OR guest_name LIKE ?
                OR guest_contact LIKE ?
                OR agency_name LIKE ?
                OR remark LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like])

    sql.append("ORDER BY order_date DESC, start_time DESC, id DESC")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE (id = ? OR oid = ?) AND COALESCE(is_deleted, 0) = 0
            """,
            (_numeric_id(order_id), order_id),
        ).fetchone()
    return dict(row) if row else None


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_payload(payload, partial=False)
    fields = list(data.keys())
    placeholders = ", ".join(["?"] * len(fields))
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO orders ({', '.join(fields)}) VALUES ({placeholders})",
            [data[field] for field in fields],
        )
        order_id = cursor.lastrowid
        oid = data.get("oid") or _build_order_oid(conn, order_id, data.get("order_date"))
        conn.execute(
            "UPDATE orders SET oid = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (oid, order_id),
        )
        conn.commit()
    created = get_order(str(order_id))
    if not created:
        raise ValueError("order_create_failed")
    return created


def update_order(order_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not get_order(order_id):
        return None

    data = _normalize_payload(payload, partial=True)
    if not data:
        return get_order(order_id)

    assignments = ", ".join(f"{field} = ?" for field in data)
    params = [data[field] for field in data]
    params.extend([_numeric_id(order_id), order_id])
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE orders
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE (id = ? OR oid = ?) AND COALESCE(is_deleted, 0) = 0
            """,
            params,
        )
        conn.commit()
    return get_order(order_id)


def soft_delete_order(order_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE orders
            SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP
            WHERE (id = ? OR oid = ?) AND COALESCE(is_deleted, 0) = 0
            """,
            (_numeric_id(order_id), order_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def _normalize_payload(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    data = {field: payload.get(field) for field in ORDER_FIELDS if field in payload}
    if not partial:
        missing = [field for field in REQUIRED_FIELDS if not str(data.get(field, "")).strip()]
        if missing:
            raise ValueError(f"missing_required_fields:{','.join(missing)}")
        data.setdefault("dispatch_status", "unassigned")
        data.setdefault("settlement_status", "pending")
        data.setdefault("passenger_count", 0)
        data.setdefault("luggage_count", 0)

    for count_field in ("passenger_count", "luggage_count", "agency_id"):
        if count_field in data and data[count_field] in ("", None):
            data[count_field] = None if count_field == "agency_id" else 0
        elif count_field in data:
            data[count_field] = int(data[count_field])

    if "price" in data:
        data["price"] = None if data["price"] in ("", None) else float(data["price"])

    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()
    return data


def _numeric_id(order_id: str) -> int:
    try:
        return int(order_id)
    except (TypeError, ValueError):
        return -1


def _build_order_oid(conn, order_id: int, order_date: Any) -> str:
    date_text = str(order_date or "").replace("-", "")
    if len(date_text) != 8 or not date_text.isdigit():
        return f"WXO{order_id:06d}"
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE order_date = ?
          AND id <= ?
          AND COALESCE(is_deleted, 0) = 0
        """,
        (str(order_date), order_id),
    ).fetchone()
    serial = int(row["count"] if row else 0) or order_id
    return f"{date_text}-{serial:03d}"

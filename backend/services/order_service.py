from typing import Any, Optional

from backend.db.database import get_connection
from backend.services.order_number_service import build_order_oid, normalize_source_code, normalize_vehicle_type_code
from backend.services.tenant_context import get_current_tenant_id


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
    "order_note_code",
    "order_source",
    "vehicle_class",
    "vehicle_type_code",
    "plate_short_code",
    "driver_code",
    "driver_language",
    "vehicle_color",
    "snow_tire",
    "passenger_count",
    "luggage_count",
    "flight_number",
    "flight_date",
    "flight_airline",
    "flight_origin",
    "flight_destination",
    "flight_terminal",
    "flight_gate",
    "flight_status",
    "flight_scheduled_departure",
    "flight_scheduled_arrival",
    "flight_estimated_departure",
    "flight_estimated_arrival",
    "flight_actual_departure",
    "flight_actual_arrival",
    "flight_provider",
    "flight_last_checked_at",
    "flight_manual_note",
    "guest_name",
    "guest_contact",
    "guide_name",
    "guide_phone",
    "guide_wechat",
    "guide_line",
    "guide_whatsapp",
    "itinerary_pdf_url",
    "itinerary_pdf_name",
    "agency_id",
    "agency_name",
    "price",
    "price_rmb",
    "price_jpy",
    "fee_remark",
    "collection_amount_jpy",
    "parking_fee_jpy",
    "other_fee_jpy",
    "driver_salary_jpy",
    "remark",
    "dispatch_status",
    "settlement_status",
    "source_channel",
    "created_by_dispatcher",
    "created_by_dispatcher_id",
    "created_by_dispatcher_code",
    "updated_by_dispatcher",
    "updated_by_dispatcher_id",
    "updated_by_dispatcher_code",
]

REQUIRED_FIELDS = ["order_date", "pickup_location", "dropoff_location"]


def list_orders(filters: dict[str, str]) -> list[dict[str, Any]]:
    sql = ["SELECT * FROM orders WHERE tenant_id = ? AND COALESCE(is_deleted, 0) = 0"]
    params: list[Any] = [get_current_tenant_id()]

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
                OR order_source LIKE ?
                OR order_note_code LIKE ?
                OR remark LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like])

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
              AND tenant_id = ?
            """,
            (_numeric_id(order_id), order_id, get_current_tenant_id()),
        ).fetchone()
    return dict(row) if row else None


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_payload(payload, partial=False)
    data["tenant_id"] = get_current_tenant_id()
    with get_connection() as conn:
        if data.get("oid"):
            exists = conn.execute("SELECT 1 FROM orders WHERE oid = ? LIMIT 1", (data["oid"],)).fetchone()
            if exists:
                data["oid"] = None
        fields = list(data.keys())
        placeholders = ", ".join(["?"] * len(fields))
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
              AND tenant_id = ?
            """,
            [*params[:-2], params[-2], params[-1], get_current_tenant_id()],
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
              AND tenant_id = ?
            """,
            (_numeric_id(order_id), order_id, get_current_tenant_id()),
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
        data.setdefault("order_note_code", normalize_source_code(data.get("order_note_code") or data.get("order_source")))
        data.setdefault("order_source", data.get("order_source") or data.get("agency_name"))
        data.setdefault("vehicle_type_code", normalize_vehicle_type_code(data.get("vehicle_type_code"), data.get("vehicle_type"), data.get("vehicle_class")))

    for count_field in ("passenger_count", "luggage_count", "agency_id", "created_by_dispatcher_id", "updated_by_dispatcher_id"):
        if count_field in data and data[count_field] in ("", None):
            data[count_field] = None if count_field == "agency_id" else 0
        elif count_field in data:
            data[count_field] = int(data[count_field])

    for money_field in (
        "price",
        "price_rmb",
        "price_jpy",
        "collection_amount_jpy",
        "parking_fee_jpy",
        "other_fee_jpy",
        "driver_salary_jpy",
    ):
        if money_field in data:
            data[money_field] = None if data[money_field] in ("", None) else float(data[money_field])

    if "price" in data and "price_rmb" not in data and data.get("price") is not None:
        data["price_rmb"] = data["price"]
    if "vehicle_type_code" in data and not data.get("vehicle_type_code"):
        data["vehicle_type_code"] = normalize_vehicle_type_code(data.get("vehicle_type"), data.get("vehicle_class"))
    if "order_note_code" in data:
        data["order_note_code"] = normalize_source_code(data.get("order_note_code") or data.get("order_source"))

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
    row_data = conn.execute(
        """
        SELECT order_note_code, order_source, vehicle_type, vehicle_type_code
        FROM orders
        WHERE id = ?
        """,
        (order_id,),
    ).fetchone()
    date_text = str(order_date or "").replace("-", "")
    if len(date_text) != 8 or not date_text.isdigit():
        return f"D000000-{order_id:04d}-TMP"
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE order_date = ?
          AND id <= ?
          AND tenant_id = ?
        """,
        (str(order_date), order_id, get_current_tenant_id()),
    ).fetchone()
    serial = int(row["count"] if row else 0) or order_id
    while True:
        oid = build_order_oid(
            order_note_code=row_data["order_note_code"] if row_data else None,
            order_source=row_data["order_source"] if row_data else None,
            order_date=order_date,
            serial=serial,
            vehicle_type_code=row_data["vehicle_type_code"] if row_data else None,
            vehicle_type=row_data["vehicle_type"] if row_data else None,
            temporary=True,
        )
        exists = conn.execute("SELECT 1 FROM orders WHERE oid = ? LIMIT 1", (oid,)).fetchone()
        if not exists:
            return oid
        serial += 1

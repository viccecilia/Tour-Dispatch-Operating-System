from typing import Any, Optional

from backend.db.database import get_connection


DRIVER_FIELDS = ["name", "phone", "status"]
VEHICLE_FIELDS = ["plate_number", "vehicle_type", "seat_count", "status"]


def list_drivers(status: str | None = None) -> list[dict[str, Any]]:
    sql = ["SELECT id, name, phone, status, created_at, updated_at FROM drivers WHERE 1 = 1"]
    params: list[Any] = []
    if status:
        sql.append("AND status = ?")
        params.append(status)
    sql.append("ORDER BY CASE status WHEN 'available' THEN 0 WHEN 'resting' THEN 1 ELSE 2 END, id")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def create_driver(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_driver(payload, partial=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO drivers (name, phone, status, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (data["name"], data.get("phone"), data["status"]),
        )
        conn.commit()
        driver_id = cursor.lastrowid
    created = get_driver(str(driver_id))
    if not created:
        raise ValueError("driver_create_failed")
    return created


def get_driver(driver_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, phone, status, created_at, updated_at
            FROM drivers
            WHERE id = ?
            """,
            (_to_int(driver_id),),
        ).fetchone()
    return dict(row) if row else None


def update_driver(driver_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not get_driver(driver_id):
        return None
    data = _normalize_driver(payload, partial=True)
    if not data:
        return get_driver(driver_id)
    assignments = ", ".join(f"{field} = ?" for field in data)
    params = [data[field] for field in data]
    params.append(_to_int(driver_id))
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE drivers
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            params,
        )
        conn.commit()
    return get_driver(driver_id)


def list_vehicles(status: str | None = None) -> list[dict[str, Any]]:
    sql = [
        """
        SELECT id, plate_number, vehicle_type, seat_count, status, created_at, updated_at
        FROM vehicles
        WHERE 1 = 1
        """
    ]
    params: list[Any] = []
    if status:
        sql.append("AND status = ?")
        params.append(status)
    sql.append("ORDER BY CASE status WHEN 'available' THEN 0 WHEN 'maintenance' THEN 1 ELSE 2 END, id")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def create_vehicle(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_vehicle(payload, partial=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO vehicles (plate_no, plate_number, vehicle_type, seats, seat_count, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                data["plate_number"],
                data["plate_number"],
                data.get("vehicle_type"),
                data.get("seat_count"),
                data.get("seat_count"),
                data["status"],
            ),
        )
        conn.commit()
        vehicle_id = cursor.lastrowid
    created = get_vehicle(str(vehicle_id))
    if not created:
        raise ValueError("vehicle_create_failed")
    return created


def get_vehicle(vehicle_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, plate_number, vehicle_type, seat_count, status, created_at, updated_at
            FROM vehicles
            WHERE id = ?
            """,
            (_to_int(vehicle_id),),
        ).fetchone()
    return dict(row) if row else None


def update_vehicle(vehicle_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not get_vehicle(vehicle_id):
        return None
    data = _normalize_vehicle(payload, partial=True)
    if not data:
        return get_vehicle(vehicle_id)

    assignments = []
    params: list[Any] = []
    for field, value in data.items():
        assignments.append(f"{field} = ?")
        params.append(value)
        if field == "plate_number":
            assignments.append("plate_no = ?")
            params.append(value)
        if field == "seat_count":
            assignments.append("seats = ?")
            params.append(value)
    params.append(_to_int(vehicle_id))
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE vehicles
            SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            params,
        )
        conn.commit()
    return get_vehicle(vehicle_id)


def _normalize_driver(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    data = {field: payload.get(field) for field in DRIVER_FIELDS if field in payload}
    if not partial and not str(data.get("name", "")).strip():
        raise ValueError("missing_driver_name")
    data.setdefault("status", "available")
    return _strip_strings(data)


def _normalize_vehicle(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    data = {field: payload.get(field) for field in VEHICLE_FIELDS if field in payload}
    if not partial and not str(data.get("plate_number", "")).strip():
        raise ValueError("missing_plate_number")
    data.setdefault("status", "available")
    if "seat_count" in data:
        data["seat_count"] = 0 if data["seat_count"] in ("", None) else int(data["seat_count"])
    return _strip_strings(data)


def _strip_strings(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()
    return data


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1

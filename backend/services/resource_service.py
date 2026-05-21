from datetime import date, datetime
from typing import Any, Optional

from backend.db.database import get_connection
from backend.services.settings_service import get_reminder_settings
from backend.services.tenant_context import get_current_tenant_id


DRIVER_FIELDS = [
    "name",
    "phone",
    "status",
    "driver_status",
    "driver_code",
    "driver_language",
    "office",
    "driver_external_id",
    "license_number",
    "residence_status",
    "residence_due_date",
    "health_check_remaining_days",
    "wechat",
    "line",
    "whatsapp",
    "email",
    "license_due_date",
    "health_check_due_date",
    "license_expires_at",
    "medical_check_expires_at",
]
VEHICLE_FIELDS = [
    "plate_number",
    "vehicle_type",
    "seat_count",
    "status",
    "plate_short_code",
    "vehicle_type_code",
    "vehicle_color",
    "snow_tire",
    "vehicle_group",
    "first_registration_date",
    "company_registration_date",
    "last_inspection_date",
    "next_inspection_due_date",
    "shaken_due_date",
    "insurance_due_date",
    "inspection_expires_at",
    "insurance_expires_at",
    "maintenance_status",
]

RESOURCE_COLUMNS = {
    "drivers": {
        "driver_status": "TEXT",
        "license_due_date": "TEXT",
        "health_check_due_date": "TEXT",
        "license_expires_at": "TEXT",
        "medical_check_expires_at": "TEXT",
        "driver_external_id": "TEXT",
        "license_number": "TEXT",
        "residence_status": "TEXT",
        "residence_due_date": "TEXT",
        "health_check_remaining_days": "INTEGER",
        "wechat": "TEXT",
        "line": "TEXT",
        "whatsapp": "TEXT",
        "email": "TEXT",
    },
    "vehicles": {
        "last_inspection_date": "TEXT",
        "next_inspection_due_date": "TEXT",
        "shaken_due_date": "TEXT",
        "insurance_due_date": "TEXT",
        "inspection_expires_at": "TEXT",
        "insurance_expires_at": "TEXT",
        "maintenance_status": "TEXT",
        "vehicle_group": "TEXT",
        "first_registration_date": "TEXT",
        "company_registration_date": "TEXT",
    },
}


def list_drivers(status: str | None = None) -> list[dict[str, Any]]:
    _ensure_resource_columns()
    sql = [
        """
        SELECT id, name, phone, status, driver_status, driver_code, driver_language, office,
               driver_external_id, license_number, residence_status, residence_due_date,
               health_check_remaining_days, wechat, line, whatsapp, email,
               license_due_date, health_check_due_date, license_expires_at, medical_check_expires_at,
               created_at, updated_at
        FROM drivers
        WHERE tenant_id = ?
        """
    ]
    params: list[Any] = [get_current_tenant_id()]
    if status:
        sql.append("AND status = ?")
        params.append(status)
    sql.append("ORDER BY CASE status WHEN 'available' THEN 0 WHEN 'busy' THEN 1 WHEN 'resting' THEN 2 ELSE 3 END, id")
    with get_connection() as conn:
        return [_with_resource_alert(dict(row), "driver") for row in conn.execute(" ".join(sql), params).fetchall()]


def create_driver(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_resource_columns()
    data = _normalize_driver(payload, partial=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO drivers (
                tenant_id, name, phone, status, driver_status, driver_code, driver_language, office,
                driver_external_id, license_number, residence_status, residence_due_date,
                health_check_remaining_days, wechat, line, whatsapp, email,
                license_due_date, health_check_due_date, license_expires_at, medical_check_expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                data["name"],
                data.get("phone"),
                data["status"],
                data.get("driver_status"),
                data.get("driver_code"),
                data.get("driver_language"),
                data.get("office"),
                data.get("driver_external_id"),
                data.get("license_number"),
                data.get("residence_status"),
                data.get("residence_due_date"),
                data.get("health_check_remaining_days"),
                data.get("wechat"),
                data.get("line"),
                data.get("whatsapp"),
                data.get("email"),
                data.get("license_due_date"),
                data.get("health_check_due_date"),
                data.get("license_expires_at"),
                data.get("medical_check_expires_at"),
            ),
        )
        conn.commit()
        driver_id = cursor.lastrowid
    created = get_driver(str(driver_id))
    if not created:
        raise ValueError("driver_create_failed")
    return created


def get_driver(driver_id: str) -> Optional[dict[str, Any]]:
    _ensure_resource_columns()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, phone, status, driver_status, driver_code, driver_language, office,
                   driver_external_id, license_number, residence_status, residence_due_date,
                   health_check_remaining_days, wechat, line, whatsapp, email,
                   license_due_date, health_check_due_date, license_expires_at, medical_check_expires_at,
                   created_at, updated_at
            FROM drivers
            WHERE id = ? AND tenant_id = ?
            """,
            (_to_int(driver_id), get_current_tenant_id()),
        ).fetchone()
    return _with_resource_alert(dict(row), "driver") if row else None


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
            WHERE id = ? AND tenant_id = ?
            """,
            [*params, get_current_tenant_id()],
        )
        conn.commit()
    return get_driver(driver_id)


def list_vehicles(status: str | None = None) -> list[dict[str, Any]]:
    _ensure_resource_columns()
    sql = [
        """
        SELECT id, plate_number, vehicle_type, seat_count, status, plate_short_code, vehicle_type_code,
               vehicle_color, snow_tire, vehicle_group, first_registration_date, company_registration_date,
               last_inspection_date, next_inspection_due_date, shaken_due_date,
               insurance_due_date, inspection_expires_at, insurance_expires_at, maintenance_status,
               created_at, updated_at
        FROM vehicles
        WHERE tenant_id = ?
        """
    ]
    params: list[Any] = [get_current_tenant_id()]
    if status:
        sql.append("AND status = ?")
        params.append(status)
    sql.append("ORDER BY CASE status WHEN 'available' THEN 0 WHEN 'busy' THEN 1 WHEN 'maintenance' THEN 2 ELSE 3 END, id")
    with get_connection() as conn:
        return [_with_resource_alert(dict(row), "vehicle") for row in conn.execute(" ".join(sql), params).fetchall()]


def create_vehicle(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_resource_columns()
    data = _normalize_vehicle(payload, partial=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO vehicles (
                tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status,
                plate_short_code, vehicle_type_code, vehicle_color, snow_tire,
                vehicle_group, first_registration_date, company_registration_date,
                last_inspection_date, next_inspection_due_date, shaken_due_date, insurance_due_date,
                inspection_expires_at, insurance_expires_at, maintenance_status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                get_current_tenant_id(),
                data["plate_number"],
                data["plate_number"],
                data.get("vehicle_type"),
                data.get("seat_count"),
                data.get("seat_count"),
                data["status"],
                data.get("plate_short_code"),
                data.get("vehicle_type_code"),
                data.get("vehicle_color"),
                data.get("snow_tire"),
                data.get("vehicle_group"),
                data.get("first_registration_date"),
                data.get("company_registration_date"),
                data.get("last_inspection_date"),
                data.get("next_inspection_due_date"),
                data.get("shaken_due_date"),
                data.get("insurance_due_date"),
                data.get("inspection_expires_at"),
                data.get("insurance_expires_at"),
                data.get("maintenance_status"),
            ),
        )
        conn.commit()
        vehicle_id = cursor.lastrowid
    created = get_vehicle(str(vehicle_id))
    _replace_vehicle_records(vehicle_id, data.get("inspection_records"))
    if not created:
        raise ValueError("vehicle_create_failed")
    return get_vehicle(str(vehicle_id)) or created


def get_vehicle(vehicle_id: str) -> Optional[dict[str, Any]]:
    _ensure_resource_columns()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, plate_number, vehicle_type, seat_count, status, plate_short_code, vehicle_type_code,
                   vehicle_color, snow_tire, vehicle_group, first_registration_date, company_registration_date,
                   last_inspection_date, next_inspection_due_date, shaken_due_date,
                   insurance_due_date, inspection_expires_at, insurance_expires_at, maintenance_status,
                   created_at, updated_at
            FROM vehicles
            WHERE id = ? AND tenant_id = ?
            """,
            (_to_int(vehicle_id), get_current_tenant_id()),
        ).fetchone()
    return _with_resource_alert(dict(row), "vehicle") if row else None


def update_vehicle(vehicle_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not get_vehicle(vehicle_id):
        return None
    data = _normalize_vehicle(payload, partial=True)
    if not data:
        return get_vehicle(vehicle_id)
    inspection_records = data.pop("inspection_records", None)

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
            WHERE id = ? AND tenant_id = ?
            """,
            [*params, get_current_tenant_id()],
        )
        conn.commit()
    if inspection_records is not None:
        _replace_vehicle_records(_to_int(vehicle_id), inspection_records)
    return get_vehicle(vehicle_id)


def get_resource_reminders() -> dict[str, Any]:
    settings = get_reminder_settings()
    drivers = list_drivers()
    vehicles = list_vehicles()
    alerts = []
    for driver in drivers:
        for field, label, days_key in (
            ("license_due_date", "驾照到期", "driver_license_days"),
            ("health_check_due_date", "健康体检到期", "driver_health_check_days"),
        ):
            alert = _expiry_alert(driver.get(field), int(settings[days_key]))
            if alert:
                alerts.append({"type": "driver", "id": driver["id"], "name": driver["name"], "field": field, "label": label, **alert})
    for vehicle in vehicles:
        for field, label, days_key in (
            ("next_inspection_due_date", "三个月点检到期", "vehicle_inspection_days"),
            ("shaken_due_date", "一年车检到期", "vehicle_shaken_days"),
        ):
            alert = _expiry_alert(vehicle.get(field), int(settings[days_key]))
            if alert:
                alerts.append({"type": "vehicle", "id": vehicle["id"], "name": vehicle["plate_number"], "field": field, "label": label, **alert})
        if vehicle.get("maintenance_status") or vehicle.get("status") == "maintenance":
            alerts.append(
                {
                    "type": "vehicle",
                    "id": vehicle["id"],
                    "name": vehicle["plate_number"],
                    "field": "maintenance_status",
                    "label": "维修状态",
                    "status": "maintenance",
                    "message": vehicle.get("maintenance_status") or "车辆处于维修状态",
                    "days_left": None,
                }
            )
    alerts.sort(key=lambda item: (9999 if item.get("days_left") is None else item["days_left"], item["type"], item["name"]))
    return {
        "settings": settings,
        "alerts": alerts,
        "total": len(alerts),
        "expired": sum(1 for item in alerts if item.get("status") == "expired"),
        "upcoming": sum(1 for item in alerts if item.get("status") == "upcoming"),
        "maintenance": sum(1 for item in alerts if item.get("status") == "maintenance"),
    }


def _normalize_driver(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    mapped = dict(payload)
    if "license_due_date" not in mapped and mapped.get("license_expires_at"):
        mapped["license_due_date"] = mapped["license_expires_at"]
    if "health_check_due_date" not in mapped and mapped.get("medical_check_expires_at"):
        mapped["health_check_due_date"] = mapped["medical_check_expires_at"]
    if "driver_status" not in mapped and mapped.get("status"):
        mapped["driver_status"] = mapped["status"]
    if "status" not in mapped and mapped.get("driver_status"):
        mapped["status"] = mapped["driver_status"]

    data = {field: mapped.get(field) for field in DRIVER_FIELDS if field in mapped}
    if not partial and not str(data.get("name", "")).strip():
        raise ValueError("missing_driver_name")
    data.setdefault("status", "available")
    data.setdefault("driver_status", data.get("status", "available"))
    for field in ("license_due_date", "health_check_due_date", "license_expires_at", "medical_check_expires_at", "residence_due_date"):
        if field in data:
            data[field] = _normalize_date(data[field])
    if data.get("health_check_due_date"):
        due = _parse_iso_date(data.get("health_check_due_date"))
        data["health_check_remaining_days"] = (due - date.today()).days if due else data.get("health_check_remaining_days")
    data["license_expires_at"] = data.get("license_expires_at") or data.get("license_due_date")
    data["medical_check_expires_at"] = data.get("medical_check_expires_at") or data.get("health_check_due_date")
    return _strip_strings(data)


def _normalize_vehicle(payload: dict[str, Any], partial: bool) -> dict[str, Any]:
    mapped = dict(payload)
    records = _normalize_inspection_records(mapped.get("inspection_records"))
    derived = _derive_vehicle_dates(mapped, records)
    if records is not None:
        mapped.update({key: value for key, value in derived.items() if value})
    else:
        mapped.update({key: value for key, value in derived.items() if value and not mapped.get(key)})
    if "next_inspection_due_date" not in mapped and mapped.get("inspection_expires_at"):
        mapped["next_inspection_due_date"] = mapped["inspection_expires_at"]
    if "inspection_expires_at" not in mapped and mapped.get("next_inspection_due_date"):
        mapped["inspection_expires_at"] = mapped["next_inspection_due_date"]
    if "insurance_due_date" not in mapped and mapped.get("insurance_expires_at"):
        mapped["insurance_due_date"] = mapped["insurance_expires_at"]
    if "insurance_expires_at" not in mapped and mapped.get("insurance_due_date"):
        mapped["insurance_expires_at"] = mapped["insurance_due_date"]

    data = {field: mapped.get(field) for field in VEHICLE_FIELDS if field in mapped}
    if not partial and not str(data.get("plate_number", "")).strip():
        raise ValueError("missing_plate_number")
    data.setdefault("status", "available")
    if "seat_count" in data:
        data["seat_count"] = 0 if data["seat_count"] in ("", None) else int(data["seat_count"])
    for field in (
        "last_inspection_date",
        "next_inspection_due_date",
        "shaken_due_date",
        "insurance_due_date",
        "inspection_expires_at",
        "insurance_expires_at",
        "first_registration_date",
        "company_registration_date",
    ):
        if field in data:
            data[field] = _normalize_date(data[field])
    if records is not None:
        data["inspection_records"] = records
    data["inspection_expires_at"] = data.get("inspection_expires_at") or data.get("next_inspection_due_date")
    data["insurance_expires_at"] = data.get("insurance_expires_at") or data.get("insurance_due_date")
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


def _ensure_resource_columns() -> None:
    with get_connection() as conn:
        for table, columns in RESOURCE_COLUMNS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicle_inspection_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                vehicle_id INTEGER NOT NULL,
                inspection_type TEXT NOT NULL DEFAULT 'inspection',
                inspection_date TEXT NOT NULL,
                source TEXT,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
            """
        )
        conn.commit()


def _normalize_inspection_records(records: Any) -> list[dict[str, Any]] | None:
    if records is None:
        return None
    normalized = []
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        inspection_date = _normalize_date(record.get("inspection_date") or record.get("date"))
        if not inspection_date:
            continue
        inspection_type = str(record.get("inspection_type") or record.get("type") or "inspection").strip()
        normalized.append(
            {
                "inspection_date": inspection_date,
                "inspection_type": "shaken" if inspection_type in {"shaken", "车检", "車検"} else "inspection",
                "source": record.get("source") or "manual",
                "note": record.get("note"),
            }
        )
    return normalized


def _derive_vehicle_dates(mapped: dict[str, Any], records: list[dict[str, Any]] | None) -> dict[str, str | None]:
    valid_records = records or []
    dates = []
    for record in valid_records:
        parsed = _parse_iso_date(record.get("inspection_date"))
        if parsed:
            dates.append((parsed, record.get("inspection_type")))
    for field, inspection_type in (("last_inspection_date", "inspection"), ("shaken_due_date", "shaken")):
        parsed = _parse_iso_date(mapped.get(field))
        if parsed:
            dates.append((parsed, inspection_type))
    if not dates:
        return {}
    latest_any = max(date_value for date_value, _ in dates)
    latest_shaken = max((date_value for date_value, kind in dates if kind == "shaken"), default=None)
    # 车检本身也算一次点检，所以最近一次记录不区分点检/车检。
    return {
        "last_inspection_date": latest_any.isoformat(),
        "next_inspection_due_date": _add_months(latest_any, 3).isoformat(),
        "shaken_due_date": _add_years(latest_shaken, 1).isoformat() if latest_shaken else mapped.get("shaken_due_date"),
    }


def _replace_vehicle_records(vehicle_id: int, records: list[dict[str, Any]] | None) -> None:
    if records is None:
        return
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM vehicle_inspection_records WHERE tenant_id = ? AND vehicle_id = ?",
            (get_current_tenant_id(), vehicle_id),
        )
        for record in records:
            conn.execute(
                """
                INSERT INTO vehicle_inspection_records (
                    tenant_id, vehicle_id, inspection_type, inspection_date, source, note, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    get_current_tenant_id(),
                    vehicle_id,
                    record["inspection_type"],
                    record["inspection_date"],
                    record.get("source"),
                    record.get("note"),
                ),
            )
        conn.commit()


def _vehicle_records(vehicle_id: int) -> list[dict[str, Any]]:
    _ensure_resource_columns()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, vehicle_id, inspection_type, inspection_date, source, note, created_at
            FROM vehicle_inspection_records
            WHERE tenant_id = ? AND vehicle_id = ?
            ORDER BY inspection_date DESC, id DESC
            """,
            (get_current_tenant_id(), vehicle_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _normalize_date(value: Any) -> str | None:
    if value in ("", None):
        return None
    text = str(value).strip().replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return text


def _parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return value.replace(year=year, month=month, day=min(value.day, days[month - 1]))


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _with_resource_alert(row: dict[str, Any], resource_type: str) -> dict[str, Any]:
    settings = get_reminder_settings()
    if resource_type == "driver":
        row["license_due_date"] = row.get("license_due_date") or row.get("license_expires_at")
        row["health_check_due_date"] = row.get("health_check_due_date") or row.get("medical_check_expires_at")
        row["driver_status"] = row.get("driver_status") or row.get("status")
        alerts = [
            _named_alert("license_due_date", "驾照到期", row.get("license_due_date"), int(settings["driver_license_days"])),
            _named_alert("health_check_due_date", "健康体检到期", row.get("health_check_due_date"), int(settings["driver_health_check_days"])),
        ]
    else:
        row["next_inspection_due_date"] = row.get("next_inspection_due_date") or row.get("inspection_expires_at")
        row["insurance_due_date"] = row.get("insurance_due_date") or row.get("insurance_expires_at")
        row["inspection_records"] = _vehicle_records(int(row["id"]))
        alerts = [
            _named_alert("next_inspection_due_date", "三个月点检到期", row.get("next_inspection_due_date"), int(settings["vehicle_inspection_days"])),
            _named_alert("shaken_due_date", "一年车检到期", row.get("shaken_due_date"), int(settings["vehicle_shaken_days"])),
        ]
        if row.get("maintenance_status") or row.get("status") == "maintenance":
            alerts.append(
                {
                    "field": "maintenance_status",
                    "label": "维修状态",
                    "status": "maintenance",
                    "message": row.get("maintenance_status") or "车辆处于维修状态",
                    "days_left": None,
                }
            )
    row["alerts"] = [alert for alert in alerts if alert]
    row["alert_level"] = _alert_level(row["alerts"])
    return row


def _named_alert(field: str, label: str, value: Any, days: int) -> dict[str, Any] | None:
    alert = _expiry_alert(value, days)
    if not alert:
        return None
    return {"field": field, "label": label, **alert}


def _expiry_alert(value: Any, days: int) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        expiry = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return {"status": "invalid", "date": str(value), "days_left": None, "message": f"日期格式异常：{value}"}
    days_left = (expiry - date.today()).days
    if days_left < 0:
        return {"status": "expired", "date": expiry.isoformat(), "days_left": days_left, "message": f"已过期 {abs(days_left)} 天"}
    if days_left <= days:
        return {"status": "upcoming", "date": expiry.isoformat(), "days_left": days_left, "message": f"{days_left} 天后到期"}
    return None


def _alert_level(alerts: list[dict[str, Any]]) -> str:
    statuses = {alert.get("status") for alert in alerts}
    if "expired" in statuses or "invalid" in statuses:
        return "danger"
    if "upcoming" in statuses or "maintenance" in statuses:
        return "warning"
    return "ok"

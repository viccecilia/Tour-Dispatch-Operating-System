import json
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


REMINDER_SETTING_KEY = "resource_reminder_rules"
PLATFORM_AUTH_SETTING_KEY = "platform_auth"
DEFAULT_REMINDER_SETTINGS = {
    "vehicle_inspection_days": 20,
    "vehicle_shaken_days": 20,
    "driver_health_check_days": 30,
    "driver_license_days": 30,
}
DEFAULT_PLATFORM_AUTH_SETTINGS = {
    "wechat_auto_login_enabled": False,
    "wechat_binding_required": False,
}


def get_reminder_settings() -> dict[str, int]:
    _ensure_settings_table()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT value_json
            FROM settings
            WHERE tenant_id = ? AND key = ?
            """,
            (get_current_tenant_id(), REMINDER_SETTING_KEY),
        ).fetchone()
    stored = _parse_json(row["value_json"]) if row else {}
    return _normalize_settings({**DEFAULT_REMINDER_SETTINGS, **stored})


def update_reminder_settings(payload: dict[str, Any]) -> dict[str, int]:
    _ensure_settings_table()
    settings = _normalize_settings({**get_reminder_settings(), **payload})
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (tenant_id, key, value_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id, key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (get_current_tenant_id(), REMINDER_SETTING_KEY, json.dumps(settings, ensure_ascii=False)),
        )
        conn.commit()
    return settings


def get_platform_auth_settings() -> dict[str, bool]:
    _ensure_settings_table()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT value_json
            FROM settings
            WHERE tenant_id = ? AND key = ?
            """,
            (get_current_tenant_id(), PLATFORM_AUTH_SETTING_KEY),
        ).fetchone()
    stored = _parse_json(row["value_json"]) if row else {}
    return _normalize_platform_auth_settings({**DEFAULT_PLATFORM_AUTH_SETTINGS, **stored})


def update_platform_auth_settings(payload: dict[str, Any]) -> dict[str, bool]:
    _ensure_settings_table()
    settings = _normalize_platform_auth_settings({**get_platform_auth_settings(), **payload})
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (tenant_id, key, value_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id, key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (get_current_tenant_id(), PLATFORM_AUTH_SETTING_KEY, json.dumps(settings, ensure_ascii=False)),
        )
        conn.commit()
    return settings


def is_wechat_auto_login_enabled() -> bool:
    return bool(get_platform_auth_settings().get("wechat_auto_login_enabled"))


def is_wechat_binding_required() -> bool:
    return bool(get_platform_auth_settings().get("wechat_binding_required"))


def _ensure_settings_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL DEFAULT 1,
                key TEXT NOT NULL,
                value_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, key)
            )
            """
        )
        conn.commit()


def _normalize_settings(payload: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, default in DEFAULT_REMINDER_SETTINGS.items():
        try:
            result[key] = max(0, min(365, int(payload.get(key, default))))
        except (TypeError, ValueError):
            result[key] = default
    return result


def _normalize_platform_auth_settings(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        key: _bool_value(payload.get(key), default)
        for key, default in DEFAULT_PLATFORM_AUTH_SETTINGS.items()
    }


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}

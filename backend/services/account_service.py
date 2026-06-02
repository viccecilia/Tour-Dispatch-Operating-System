import sqlite3
import re
from typing import Any

from backend.db.database import get_connection, hash_password
from backend.services.audit_service import record_audit
from backend.services.auth_service import company_login_name, normalize_phone, phone_password_tail, reset_user_password_to_phone_tail, unbind_user_wechat
from backend.services.tenant_context import get_current_tenant_id


ROLES = {"admin", "dispatcher", "operations_manager", "driver"}
MANAGEMENT_ROLES = {"admin", "dispatcher", "operations_manager"}

ROLE_LABELS = {
    "admin": "管理账号",
    "dispatcher": "调度",
    "operations_manager": "运行管理",
    "driver": "司机",
}


def get_account_overview() -> dict[str, Any]:
    ensure_driver_accounts()
    accounts = [
        account
        for account in list_accounts()
        if not _is_synthetic_account(account)
        and (
            account.get("role") != "driver"
            or (
                _looks_like_driver_phone(account.get("phone"))
                and account.get("driver_record_status") != "deleted"
            )
        )
    ]
    grouped: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    for account in accounts:
        grouped.setdefault(account["role"], []).append(account)
    roles = []
    for role in ("admin", "dispatcher", "operations_manager", "driver"):
        items = grouped.get(role, [])
        roles.append(
            {
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "total": len(items),
                "active": len([item for item in items if item.get("is_active")]),
                "disabled": len([item for item in items if not item.get("is_active")]),
                "wechat_bound": len([item for item in items if item.get("wx_bind_status") == "bound"]),
                "wechat_unbound": len([item for item in items if item.get("wx_bind_status") != "bound"]),
                "accounts": items,
            }
        )
    return {"roles": roles, "accounts": accounts}


def list_accounts() -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.tenant_id,
                u.username,
                u.role,
                u.display_name,
                u.phone,
                u.profile_type,
                u.profile_id,
                u.wx_bind_status,
                u.wx_bound_at,
                u.last_login_at,
                u.password_changed_at,
                u.must_change_password,
                u.is_active,
                u.created_at,
                u.updated_at,
                d.name AS driver_name,
                d.phone AS driver_phone,
                d.driver_code,
                d.status AS driver_record_status,
                p.operator_code,
                p.title AS operator_title,
                p.phone AS operator_phone,
                p.invite_status,
                p.disabled_at,
                t.slug AS tenant_slug,
                t.name AS tenant_name
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            LEFT JOIN drivers d ON d.tenant_id = u.tenant_id AND u.profile_type = 'driver' AND d.id = u.profile_id
            LEFT JOIN operator_profiles p ON p.tenant_id = u.tenant_id AND u.profile_type = 'operator' AND p.id = u.profile_id
            WHERE u.tenant_id = ?
            ORDER BY
                CASE u.role
                    WHEN 'admin' THEN 1
                    WHEN 'dispatcher' THEN 2
                    WHEN 'operations_manager' THEN 3
                    WHEN 'driver' THEN 4
                    ELSE 9
                END,
                u.is_active DESC,
                u.id ASC
            """,
            (tenant_id,),
        ).fetchall()
    return [_public_account(dict(row)) for row in rows]


def ensure_driver_accounts(actor: str = "system") -> int:
    """Create login accounts for preloaded drivers that have a phone number."""
    tenant_id = get_current_tenant_id()
    created = 0
    with get_connection() as conn:
        tenant_slug, tenant_name = _tenant_identity(conn, tenant_id)
        drivers = conn.execute(
            """
            SELECT id, name, phone, driver_code, user_id
            FROM drivers
            WHERE tenant_id = ?
              AND COALESCE(TRIM(phone), '') != ''
              AND COALESCE(status, '') != 'deleted'
              AND COALESCE(driver_status, '') != 'deleted'
            ORDER BY id ASC
            """,
            (tenant_id,),
        ).fetchall()
        for driver in drivers:
            if _is_synthetic_name(driver["name"]) or _is_synthetic_name(driver["phone"]):
                continue
            normalized = normalize_phone(driver["phone"])
            if not _looks_like_driver_phone(driver["phone"]):
                continue
            existing = _find_user_by_phone(conn, tenant_id, normalized)
            if existing:
                if not driver["user_id"] and existing["profile_type"] == "driver":
                    conn.execute(
                        "UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
                        (existing["id"], tenant_id, driver["id"]),
                    )
                continue
            username = _unique_username(conn, tenant_id, company_login_name(normalized, tenant_slug, tenant_name))
            password = phone_password_tail(driver["phone"])
            if not password:
                continue
            display_name = driver["name"] or driver["driver_code"] or driver["phone"]
            conn.execute(
                """
                INSERT INTO users (
                    tenant_id, username, password_hash, role, display_name, phone,
                    profile_type, profile_id, wx_bind_status, is_active,
                    password_changed_at, must_change_password, updated_at
                )
                VALUES (?, ?, ?, 'driver', ?, ?, 'driver', ?, 'unbound', 1, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
                """,
                (tenant_id, username, hash_password(password), display_name, driver["phone"], driver["id"]),
            )
            user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute(
                "UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
                (user_id, tenant_id, driver["id"]),
            )
            created += 1
        conn.commit()
    if created:
        record_audit(
            "driver_accounts_sync",
            "user",
            "driver",
            after={"created": created},
            actor=actor,
            source_path="/api/accounts/overview",
            summary=f"Created {created} driver accounts from driver phones",
        )
    return created


def create_account(payload: dict[str, Any], actor: str = "system") -> dict[str, Any]:
    role = str(payload.get("role") or "").strip()
    display_name = str(payload.get("display_name") or payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    operator_code = str(payload.get("operator_code") or payload.get("code") or "").strip().upper()
    if role not in ROLES:
        raise ValueError("invalid_role")
    if not phone:
        raise ValueError("phone_required")
    normalized = normalize_phone(phone)
    if len(normalized) < 6:
        raise ValueError("phone_tail_unavailable")
    password = phone_password_tail(phone)
    if not display_name:
        display_name = phone
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        tenant_slug, tenant_name = _tenant_identity(conn, tenant_id)
        existing = _find_user_by_phone(conn, tenant_id, normalized)
        if existing:
            raise ValueError("account_phone_exists")
        if role == "driver":
            profile = _find_driver_profile(conn, tenant_id, normalized)
            if not profile:
                raise ValueError("driver_phone_not_preloaded")
            if profile["user_id"]:
                linked = conn.execute("SELECT id, is_active FROM users WHERE id = ? AND tenant_id = ?", (profile["user_id"], tenant_id)).fetchone()
                if linked:
                    raise ValueError("driver_profile_already_bound")
            profile_type = "driver"
            profile_id = profile["id"]
            display_name = display_name or profile["name"]
        else:
            profile_type = "operator"
            profile_id = None
        username = _unique_username(conn, tenant_id, company_login_name(normalized or phone, tenant_slug, tenant_name))
        conn.execute(
            """
            INSERT INTO users (
                tenant_id, username, password_hash, role, display_name, phone,
                profile_type, profile_id, wx_bind_status, is_active,
                password_changed_at, must_change_password, created_by_user_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unbound', 1, CURRENT_TIMESTAMP, 1, ?, CURRENT_TIMESTAMP)
            """,
            (tenant_id, username, hash_password(password), role, display_name, phone, profile_type, profile_id, _actor_user_id(conn, tenant_id, actor)),
        )
        user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        if role == "driver":
            conn.execute("UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (user_id, tenant_id, profile_id))
        else:
            profile_id = _create_operator_profile_shell(conn, tenant_id, user_id, phone, role, operator_code)
            conn.execute("UPDATE users SET profile_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (profile_id, tenant_id, user_id))
        conn.commit()
    account = get_account(user_id)
    record_audit("account_create", "user", user_id, after=account, actor=actor, source_path="/api/accounts", summary=f"Created {role} account {display_name}")
    return account or {}


def update_account(user_id: int | str, payload: dict[str, Any], actor: str = "system") -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        tenant_slug, tenant_name = _tenant_identity(conn, tenant_id)
        before = _get_account_row(conn, tenant_id, user_id)
        if not before:
            return None
        new_role = payload.get("role")
        if new_role is not None:
            new_role = str(new_role).strip()
            if new_role not in ROLES:
                raise ValueError("invalid_role")
            if before["role"] == "driver" and new_role in MANAGEMENT_ROLES and not payload.get("confirm_driver_role_change"):
                raise ValueError("driver_role_change_requires_confirmation")
        display_name = payload.get("display_name", payload.get("name"))
        phone = payload.get("phone")
        operator_code = payload.get("operator_code", payload.get("code"))
        updates: list[str] = []
        values: list[Any] = []
        if display_name is not None:
            updates.append("display_name = ?")
            values.append(str(display_name).strip())
        if phone is not None:
            phone_value = str(phone).strip()
            if phone_value:
                normalized = normalize_phone(phone_value)
                if len(normalized) < 6:
                    raise ValueError("phone_tail_unavailable")
                existing = _find_user_by_phone(conn, tenant_id, normalized)
                if existing and str(existing["id"]) != str(user_id):
                    raise ValueError("account_phone_exists")
                username = _unique_username(conn, tenant_id, company_login_name(normalized, tenant_slug, tenant_name), user_id)
            else:
                username = _unique_username(conn, tenant_id, f"account-{user_id}", user_id)
            updates.append("phone = ?")
            values.append(phone_value)
            updates.append("username = ?")
            values.append(username)
        if new_role is not None and new_role != before["role"]:
            profile_type, profile_id = _resolve_profile_for_role_change(conn, tenant_id, before, new_role, phone)
            updates.extend(["role = ?", "profile_type = ?", "profile_id = ?"])
            values.extend([new_role, profile_type, profile_id])
        if "is_active" in payload:
            updates.append("is_active = ?")
            values.append(1 if payload.get("is_active") else 0)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE tenant_id = ? AND id = ?", (*values, tenant_id, user_id))
        _sync_profile_after_user_update(conn, tenant_id, user_id)
        if operator_code is not None:
            conn.execute(
                """
                UPDATE operator_profiles
                SET operator_code = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND user_id = ?
                """,
                (str(operator_code).strip().upper(), tenant_id, user_id),
            )
        conn.commit()
    after = get_account(user_id)
    record_audit("account_update", "user", user_id, before=_public_account(dict(before)), after=after, actor=actor, source_path=f"/api/accounts/{user_id}", summary=f"Updated account {user_id}")
    return after


def disable_account(user_id: int | str, actor: str = "system") -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        before = _get_account_row(conn, tenant_id, user_id)
        if not before:
            return None
        conn.execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (tenant_id, user_id))
        conn.execute(
            """
            UPDATE operator_profiles
            SET invite_status = 'disabled', disabled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND user_id = ?
            """,
            (tenant_id, user_id),
        )
        conn.commit()
    after = get_account(user_id)
    record_audit("account_disable", "user", user_id, before=_public_account(dict(before)), after=after, actor=actor, source_path=f"/api/accounts/{user_id}/disable", summary=f"Disabled account {user_id}")
    return after


def enable_account(user_id: int | str, actor: str = "system") -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        before = _get_account_row(conn, tenant_id, user_id)
        if not before:
            return None
        conn.execute("UPDATE users SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (tenant_id, user_id))
        conn.execute(
            """
            UPDATE operator_profiles
            SET invite_status = 'active', disabled_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND user_id = ?
            """,
            (tenant_id, user_id),
        )
        conn.commit()
    after = get_account(user_id)
    record_audit("account_enable", "user", user_id, before=_public_account(dict(before)), after=after, actor=actor, source_path=f"/api/accounts/{user_id}/enable", summary=f"Enabled account {user_id}")
    return after


def reset_account_password(user_id: int | str, actor: str = "system") -> dict[str, Any] | None:
    return reset_user_password_to_phone_tail(user_id, actor)


def unbind_account_wechat(user_id: int | str, actor: str = "system") -> dict[str, Any] | None:
    return unbind_user_wechat(user_id, actor)


def get_account(user_id: int | str) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = _get_account_row(conn, tenant_id, user_id)
    return _public_account(dict(row)) if row else None


def _resolve_profile_for_role_change(conn: sqlite3.Connection, tenant_id: int, before: sqlite3.Row, new_role: str, new_phone: Any = None) -> tuple[str, int]:
    phone = str(new_phone if new_phone is not None else before["phone"] or before["username"])
    normalized = normalize_phone(phone)
    if new_role == "driver":
        driver = _find_driver_profile(conn, tenant_id, normalized)
        if not driver:
            raise ValueError("driver_phone_not_preloaded")
        if driver["user_id"] and str(driver["user_id"]) != str(before["id"]):
            raise ValueError("driver_profile_already_bound")
        conn.execute("UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (before["id"], tenant_id, driver["id"]))
        return "driver", int(driver["id"])
    profile_id = before["profile_id"] if before["profile_type"] == "operator" and before["profile_id"] else None
    if not profile_id:
        profile_id = _create_operator_profile_shell(conn, tenant_id, before["id"], phone, new_role)
    else:
        conn.execute(
            """
            UPDATE operator_profiles
            SET user_id = ?, phone = ?, title = ?, invite_status = 'active', disabled_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (before["id"], phone, ROLE_LABELS.get(new_role, new_role), tenant_id, profile_id),
        )
    return "operator", int(profile_id)


def _sync_profile_after_user_update(conn: sqlite3.Connection, tenant_id: int, user_id: int | str) -> None:
    user = conn.execute("SELECT * FROM users WHERE tenant_id = ? AND id = ?", (tenant_id, user_id)).fetchone()
    if not user:
        return
    if user["profile_type"] == "driver" and user["profile_id"]:
        conn.execute(
            """
            UPDATE drivers
            SET user_id = ?, name = COALESCE(NULLIF(?, ''), name), phone = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (user_id, user["display_name"], user["phone"] or "", tenant_id, user["profile_id"]),
        )
    elif user["profile_type"] == "operator" and user["profile_id"]:
        conn.execute(
            """
            UPDATE operator_profiles
            SET user_id = ?, phone = ?, title = ?, invite_status = CASE WHEN ? = 0 THEN 'disabled' ELSE COALESCE(NULLIF(invite_status, ''), 'active') END, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (user_id, user["phone"] or "", ROLE_LABELS.get(user["role"], user["role"]), user["is_active"], tenant_id, user["profile_id"]),
        )


def _create_operator_profile_shell(conn: sqlite3.Connection, tenant_id: int, user_id: int | str, phone: str, role: str, operator_code: str = "") -> int:
    conn.execute(
        """
        INSERT INTO operator_profiles (tenant_id, user_id, operator_code, title, phone, invite_status, invited_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (tenant_id, user_id, operator_code, ROLE_LABELS.get(role, role), phone),
    )
    return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])


def _find_user_by_phone(conn: sqlite3.Connection, tenant_id: int, normalized: str):
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE tenant_id = ?
          AND (
              REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
              OR REPLACE(REPLACE(REPLACE(COALESCE(username, ''), '-', ''), ' ', ''), '+', '') = ?
          )
        ORDER BY is_active DESC, id ASC
        LIMIT 1
        """,
        (tenant_id, normalized, normalized),
    ).fetchone()


def _find_driver_profile(conn: sqlite3.Connection, tenant_id: int, normalized: str):
    return conn.execute(
        """
        SELECT *
        FROM drivers
        WHERE tenant_id = ?
          AND REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (tenant_id, normalized),
    ).fetchone()


def _unique_username(conn: sqlite3.Connection, tenant_id: int, base: str, exclude_user_id: int | str | None = None) -> str:
    username = base
    suffix = 1
    while True:
        row = conn.execute("SELECT id FROM users WHERE tenant_id = ? AND username = ?", (tenant_id, username)).fetchone()
        if not row or (exclude_user_id is not None and str(row["id"]) == str(exclude_user_id)):
            return username
        suffix += 1
        username = f"{base}-{suffix}"


def _tenant_identity(conn: sqlite3.Connection, tenant_id: int) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT slug, name FROM tenants WHERE id = ? LIMIT 1", (tenant_id,)).fetchone()
    if not row:
        return None, None
    return row["slug"], row["name"]


def _actor_user_id(conn: sqlite3.Connection, tenant_id: int, actor: str) -> int | None:
    text = str(actor or "")
    if ":" not in text:
        return None
    role, username = text.split(":", 1)
    row = conn.execute(
        "SELECT id FROM users WHERE tenant_id = ? AND role = ? AND username = ? LIMIT 1",
        (tenant_id, role, username),
    ).fetchone()
    return int(row["id"]) if row else None


def _get_account_row(conn: sqlite3.Connection, tenant_id: int, user_id: int | str):
    return conn.execute(
        """
        SELECT
            u.id,
            u.tenant_id,
            u.username,
            u.role,
            u.display_name,
            u.phone,
            u.profile_type,
            u.profile_id,
            u.wx_bind_status,
            u.wx_bound_at,
            u.last_login_at,
            u.password_changed_at,
            u.must_change_password,
            u.is_active,
            u.created_at,
            u.updated_at,
            d.name AS driver_name,
            d.phone AS driver_phone,
            d.driver_code,
            d.status AS driver_record_status,
                p.operator_code,
                p.title AS operator_title,
                p.phone AS operator_phone,
                p.invite_status,
                p.disabled_at,
                t.slug AS tenant_slug,
                t.name AS tenant_name
        FROM users u
        LEFT JOIN tenants t ON t.id = u.tenant_id
        LEFT JOIN drivers d ON d.tenant_id = u.tenant_id AND u.profile_type = 'driver' AND d.id = u.profile_id
        LEFT JOIN operator_profiles p ON p.tenant_id = u.tenant_id AND u.profile_type = 'operator' AND p.id = u.profile_id
        WHERE u.tenant_id = ? AND u.id = ?
        """,
        (tenant_id, user_id),
    ).fetchone()


def _public_account(row: dict[str, Any]) -> dict[str, Any]:
    phone = row.get("phone") or ""
    tenant_slug = row.get("tenant_slug")
    tenant_name = row.get("tenant_name")
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "username": row.get("username"),
        "account_login": company_login_name(phone or row.get("username"), tenant_slug, tenant_name),
        "display_name": row.get("display_name") or row.get("driver_name") or row.get("username"),
        "phone": phone,
        "role": row.get("role"),
        "role_label": ROLE_LABELS.get(row.get("role"), row.get("role")),
        "profile_type": row.get("profile_type"),
        "profile_id": row.get("profile_id"),
        "profile_label": row.get("driver_name") or row.get("operator_title") or "-",
        "driver_code": row.get("driver_code"),
        "driver_record_status": row.get("driver_record_status") or "",
        "operator_code": row.get("operator_code") or "",
        "is_active": bool(row.get("is_active")),
        "account_status": "active" if row.get("is_active") else "disabled",
        "wx_bind_status": row.get("wx_bind_status") or "unbound",
        "wx_bound_at": row.get("wx_bound_at"),
        "last_login_at": row.get("last_login_at"),
        "password_changed_at": row.get("password_changed_at"),
        "must_change_password": bool(row.get("must_change_password", 0)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _is_synthetic_name(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(re.match(r"^R\d{3}", text)) or text in {"driver_demo", "司机演示账号"}


def _is_synthetic_account(account: dict[str, Any]) -> bool:
    return any(
        _is_synthetic_name(account.get(key))
        for key in ("username", "display_name", "phone", "profile_label")
    )


def _looks_like_driver_phone(value: Any) -> bool:
    normalized = normalize_phone(str(value or ""))
    return len(normalized) in {10, 11} and normalized.startswith("0")

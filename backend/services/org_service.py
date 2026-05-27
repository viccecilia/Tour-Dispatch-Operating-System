import sqlite3
from typing import Any

from backend.db.database import get_connection, hash_password
from backend.services.tenant_context import get_current_tenant_id


ROLES = {"admin", "dispatcher", "operations_manager", "driver"}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "manage_org",
        "manage_billing",
        "manage_resources",
        "manage_orders",
        "manage_dispatch",
        "view_finance",
        "view_driver_monitor",
    ],
    "dispatcher": [
        "manage_orders",
        "manage_dispatch",
        "view_calendar",
        "view_driver_monitor",
    ],
    "operations_manager": [
        "manage_resources",
        "view_calendar",
        "view_driver_monitor",
        "view_fleet_map",
        "view_incidents",
    ],
    "driver": [
        "driver_app",
        "view_own_assignments",
        "submit_driver_reports",
    ],
}


def list_departments() -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.*,
                   COUNT(DISTINCT t.id) AS team_count,
                   COUNT(DISTINCT p.user_id) AS member_count
            FROM departments d
            LEFT JOIN teams t ON t.department_id = d.id AND t.tenant_id = d.tenant_id
            LEFT JOIN operator_profiles p ON p.department_id = d.id AND p.tenant_id = d.tenant_id
            WHERE d.tenant_id = ?
            GROUP BY d.id
            ORDER BY d.id ASC
            """,
            (tenant_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_department(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("department_name_required")
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO departments (tenant_id, name, description, status, updated_at)
            VALUES (?, ?, ?, COALESCE(NULLIF(?, ''), 'active'), CURRENT_TIMESTAMP)
            """,
            (tenant_id, name, payload.get("description"), payload.get("status")),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return get_department(row_id) or {}


def get_department(department_id: int | str) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM departments WHERE tenant_id = ? AND id = ?",
            (tenant_id, department_id),
        ).fetchone()
    return dict(row) if row else None


def list_teams() -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.*, d.name AS department_name, COUNT(DISTINCT p.user_id) AS member_count
            FROM teams t
            LEFT JOIN departments d ON d.id = t.department_id AND d.tenant_id = t.tenant_id
            LEFT JOIN operator_profiles p ON p.team_id = t.id AND p.tenant_id = t.tenant_id
            WHERE t.tenant_id = ?
            GROUP BY t.id
            ORDER BY t.id ASC
            """,
            (tenant_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_team(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("team_name_required")
    tenant_id = get_current_tenant_id()
    department_id = _optional_int(payload.get("department_id"))
    with get_connection() as conn:
        if department_id and not _department_exists(conn, tenant_id, department_id):
            raise ValueError("department_not_found")
        conn.execute(
            """
            INSERT INTO teams (tenant_id, department_id, name, description, status, updated_at)
            VALUES (?, ?, ?, ?, COALESCE(NULLIF(?, ''), 'active'), CURRENT_TIMESTAMP)
            """,
            (tenant_id, department_id, name, payload.get("description"), payload.get("status")),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return get_team(row_id) or {}


def get_team(team_id: int | str) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT t.*, d.name AS department_name
            FROM teams t
            LEFT JOIN departments d ON d.id = t.department_id AND d.tenant_id = t.tenant_id
            WHERE t.tenant_id = ? AND t.id = ?
            """,
            (tenant_id, team_id),
        ).fetchone()
    return dict(row) if row else None


def list_members() -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id,
                   u.tenant_id,
                   u.username,
                   u.role,
                   u.display_name,
                   u.is_active,
                   u.created_at,
                   u.updated_at,
                   p.id AS profile_id,
                   p.department_id,
                   p.team_id,
                   p.title,
                   p.phone,
                   p.invite_status,
                   p.invited_at,
                   p.disabled_at,
                   d.name AS department_name,
                   t.name AS team_name
            FROM users u
            LEFT JOIN operator_profiles p ON p.user_id = u.id AND p.tenant_id = u.tenant_id
            LEFT JOIN departments d ON d.id = p.department_id AND d.tenant_id = u.tenant_id
            LEFT JOIN teams t ON t.id = p.team_id AND t.tenant_id = u.tenant_id
            WHERE u.tenant_id = ?
            ORDER BY u.is_active DESC, u.id ASC
            """,
            (tenant_id,),
        ).fetchall()
    return [dict(row) | {"permissions": ROLE_PERMISSIONS.get(row["role"], [])} for row in rows]


def invite_member(payload: dict[str, Any]) -> dict[str, Any]:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    role = str(payload.get("role") or "dispatcher").strip()
    display_name = str(payload.get("display_name") or username).strip()
    if not username:
        raise ValueError("username_required")
    if not password:
        raise ValueError("password_required")
    if role not in ROLES:
        raise ValueError("invalid_role")
    tenant_id = get_current_tenant_id()
    department_id = _optional_int(payload.get("department_id"))
    team_id = _optional_int(payload.get("team_id"))
    with get_connection() as conn:
        _validate_profile_targets(conn, tenant_id, department_id, team_id)
        try:
            conn.execute(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, display_name, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (tenant_id, username, hash_password(password), role, display_name),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("username_exists") from exc
        user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO operator_profiles (
                tenant_id, user_id, department_id, team_id, title, phone, invite_status, invited_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (tenant_id, user_id, department_id, team_id, payload.get("title"), payload.get("phone")),
        )
        conn.commit()
    return get_member(user_id) or {}


def update_member(user_id: int | str, payload: dict[str, Any]) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    role = payload.get("role")
    if role is not None and role not in ROLES:
        raise ValueError("invalid_role")
    department_id = _optional_int(payload.get("department_id"))
    team_id = _optional_int(payload.get("team_id"))
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE tenant_id = ? AND id = ?",
            (tenant_id, user_id),
        ).fetchone()
        if not existing:
            return None
        _validate_profile_targets(conn, tenant_id, department_id, team_id)
        updates: list[str] = []
        values: list[Any] = []
        for field in ["display_name", "role"]:
            if field in payload:
                updates.append(f"{field} = ?")
                values.append(payload.get(field))
        if "is_active" in payload:
            updates.append("is_active = ?")
            values.append(1 if payload.get("is_active") else 0)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE tenant_id = ? AND id = ?",
                (*values, tenant_id, user_id),
            )
        _ensure_profile(conn, tenant_id, int(user_id))
        conn.execute(
            """
            UPDATE operator_profiles
            SET department_id = COALESCE(?, department_id),
                team_id = COALESCE(?, team_id),
                title = COALESCE(?, title),
                phone = COALESCE(?, phone),
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND user_id = ?
            """,
            (
                department_id,
                team_id,
                payload.get("title"),
                payload.get("phone"),
                tenant_id,
                user_id,
            ),
        )
        conn.commit()
    return get_member(user_id)


def disable_member(user_id: int | str) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE tenant_id = ? AND id = ?",
            (tenant_id, user_id),
        ).fetchone()
        if not existing:
            return None
        _ensure_profile(conn, tenant_id, int(user_id))
        conn.execute(
            """
            UPDATE users
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant_id, user_id),
        )
        conn.execute(
            """
            UPDATE operator_profiles
            SET invite_status = 'disabled',
                disabled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND user_id = ?
            """,
            (tenant_id, user_id),
        )
        conn.commit()
    return get_member(user_id)


def get_member(user_id: int | str) -> dict[str, Any] | None:
    return next((member for member in list_members() if str(member["id"]) == str(user_id)), None)


def get_role_permissions() -> dict[str, list[str]]:
    return ROLE_PERMISSIONS


def get_org_overview() -> dict[str, Any]:
    members = list_members()
    departments = list_departments()
    teams = list_teams()
    return {
        "departments": departments,
        "teams": teams,
        "members": members,
        "role_permissions": get_role_permissions(),
        "summary": {
            "departments": len(departments),
            "teams": len(teams),
            "members": len(members),
            "active_members": len([member for member in members if member.get("is_active")]),
            "disabled_members": len([member for member in members if not member.get("is_active")]),
        },
    }


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_id") from exc


def _department_exists(conn: sqlite3.Connection, tenant_id: int, department_id: int) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM departments WHERE tenant_id = ? AND id = ?",
            (tenant_id, department_id),
        ).fetchone()
    )


def _team_exists(conn: sqlite3.Connection, tenant_id: int, team_id: int) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM teams WHERE tenant_id = ? AND id = ?",
            (tenant_id, team_id),
        ).fetchone()
    )


def _validate_profile_targets(conn: sqlite3.Connection, tenant_id: int, department_id: int | None, team_id: int | None) -> None:
    if department_id and not _department_exists(conn, tenant_id, department_id):
        raise ValueError("department_not_found")
    if team_id and not _team_exists(conn, tenant_id, team_id):
        raise ValueError("team_not_found")


def _ensure_profile(conn: sqlite3.Connection, tenant_id: int, user_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM operator_profiles WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, user_id),
    ).fetchone()
    if row:
        return
    conn.execute(
        """
        INSERT INTO operator_profiles (tenant_id, user_id, invite_status, invited_at, updated_at)
        VALUES (?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (tenant_id, user_id),
    )

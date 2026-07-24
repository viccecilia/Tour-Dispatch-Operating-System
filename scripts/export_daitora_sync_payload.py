from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "runtime" / "wx_dispatch.sqlite3"
OUT_PATH = ROOT / "runtime" / "deploy" / "daitora_sync_payload.json"
TENANT_ID = 529


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        tenant = rows(conn, "SELECT * FROM tenants WHERE id = ?", (TENANT_ID,))
        registration = rows(conn, "SELECT * FROM company_registrations WHERE tenant_id = ?", (TENANT_ID,))
        admin_users = rows(
            conn,
            """
            SELECT id, tenant_id, username, display_name, role, phone, is_active, profile_type, profile_id
            FROM users
            WHERE tenant_id = ? AND role = 'admin'
            ORDER BY is_active DESC, id ASC
            """,
            (TENANT_ID,),
        )
        drivers = rows(
            conn,
            """
            SELECT d.*, u.username, u.display_name AS user_display_name, u.is_active AS user_is_active
            FROM drivers d
            LEFT JOIN users u ON u.id = d.user_id
            WHERE d.tenant_id = ?
            ORDER BY d.id
            """,
            (TENANT_ID,),
        )
        vehicles = rows(
            conn,
            "SELECT * FROM vehicles WHERE tenant_id = ? ORDER BY id",
            (TENANT_ID,),
        )
    finally:
        conn.close()

    payload = {
        "tenant": tenant[0] if tenant else None,
        "registration": registration[0] if registration else None,
        "admin_user": admin_users[0] if admin_users else None,
        "drivers": drivers,
        "vehicles": vehicles,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PATH)
    print(f"drivers={len(drivers)} vehicles={len(vehicles)}")


if __name__ == "__main__":
    main()

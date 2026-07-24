from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import hash_password  # noqa: E402
from backend.services.auth_service import normalize_phone, phone_password_tail  # noqa: E402


def migrate(db_path: Path, reset_passwords: bool = False, tenant_slug: str | None = None) -> dict[str, int]:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    stats = {"seen": 0, "renamed": 0, "passwords_reset": 0, "skipped": 0}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT u.id, u.tenant_id, u.username, u.phone, u.password_hash, t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE COALESCE(u.phone, '') <> ''
              AND (? IS NULL OR UPPER(COALESCE(t.slug, '')) = UPPER(?))
            ORDER BY u.id ASC
            """,
            (tenant_slug, tenant_slug),
        ).fetchall()
        for row in rows:
            stats["seen"] += 1
            phone = str(row["phone"] or "").strip()
            digits = normalize_phone(phone)
            if len(digits) < 6:
                stats["skipped"] += 1
                continue
            username = _unique_username(conn, digits, row["id"])
            updates = []
            values = []
            if row["username"] != username:
                updates.append("username = ?")
                values.append(username)
                stats["renamed"] += 1
            if reset_passwords:
                tail = phone_password_tail(phone)
                if tail:
                    updates.extend(["password_hash = ?", "password_changed_at = CURRENT_TIMESTAMP", "must_change_password = 1"])
                    values.append(hash_password(tail))
                    stats["passwords_reset"] += 1
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", (*values, row["id"]))
        conn.commit()
    return stats


def _unique_username(conn: sqlite3.Connection, base: str, user_id: int) -> str:
    username = base
    suffix = 2
    while True:
        row = conn.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (username,)).fetchone()
        if not row or int(row["id"]) == int(user_id):
            return username
        username = f"{base}-{suffix}"
        suffix += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate phone-based TourFlow accounts to pure phone usernames.")
    parser.add_argument("--db", default=str(ROOT / "runtime" / "wx_dispatch.sqlite3"), help="SQLite database path")
    parser.add_argument("--reset-passwords", action="store_true", help="Reset migrated accounts to phone last 6 digits")
    parser.add_argument("--tenant-slug", help="Limit migration to one tenant slug, e.g. DAITORA")
    args = parser.parse_args()
    stats = migrate(Path(args.db), reset_passwords=args.reset_passwords, tenant_slug=args.tenant_slug)
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan and migrate local account identities to Supabase Auth")
    parser.add_argument("--db", type=Path, default=ROOT / "runtime" / "wx_dispatch.sqlite3")
    parser.add_argument("--report", type=Path, default=ROOT / "runtime" / "reports" / "supabase_auth_migration.json")
    parser.add_argument("--backup-dir", type=Path, default=ROOT / "runtime" / "backups")
    parser.add_argument("--platform-admin-email", default=os.environ.get("SUPABASE_PLATFORM_ADMIN_EMAIL", ""))
    parser.add_argument("--apply", action="store_true", help="Create Supabase users and link identities after a clean scan")
    return parser.parse_args()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _phone_key(value: Any) -> str:
    digits = _digits(value)
    if digits.startswith("81"):
        return "0" + digits[2:]
    return digits


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def scan(conn: sqlite3.Connection, platform_admin_email: str = "") -> dict[str, Any]:
    tables = _tables(conn)
    issues: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if "users" not in tables:
        return {"candidates": [], "issues": [{"code": "users_table_missing", "severity": "blocking"}]}

    user_columns = _columns(conn, "users")
    required_user_columns = {"tenant_id", "phone", "profile_type", "profile_id", "account_scope", "supabase_user_id"}
    missing_user_columns = sorted(required_user_columns - user_columns)
    if missing_user_columns:
        issues.append({"code": "auth_identity_schema_not_applied", "severity": "blocking", "columns": missing_user_columns})
    else:
        for row in conn.execute(
            "SELECT id, tenant_id, username, role, display_name, phone, profile_type, profile_id, account_scope, supabase_user_id, is_active FROM users ORDER BY id"
        ).fetchall():
            item = _row(row)
            item.update({"source": "users", "local_id": item.pop("id"), "migration_blockers": []})
            candidates.append(item)

    if "travel_agency_accounts" in tables:
        agency_columns = _columns(conn, "travel_agency_accounts")
        if "supabase_user_id" not in agency_columns:
            issues.append({"code": "agency_auth_identity_schema_not_applied", "severity": "blocking"})
        else:
            for row in conn.execute(
                "SELECT id, tenant_id, company_id, role, display_name, phone, supabase_user_id, status FROM travel_agency_accounts ORDER BY id"
            ).fetchall():
                item = _row(row)
                item.update({"source": "travel_agency_accounts", "local_id": item.pop("id"), "account_scope": "agency", "migration_blockers": []})
                candidates.append(item)

    by_phone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        is_active = item.get("is_active") if item["source"] == "users" else str(item.get("status") or "").lower() == "active"
        if not is_active:
            item["migration_blockers"].append("inactive_account")
            issues.append(
                {
                    "code": "inactive_account",
                    "severity": "blocking",
                    "source": item["source"],
                    "local_id": item["local_id"],
                }
            )
        key = _phone_key(item.get("phone"))
        if key:
            if len(key) not in {10, 11}:
                item["migration_blockers"].append("invalid_phone")
                issues.append(
                    {
                        "code": "invalid_phone",
                        "severity": "blocking",
                        "source": item["source"],
                        "local_id": item["local_id"],
                    }
                )
            else:
                by_phone[key].append(item)
        elif item.get("account_scope") == "platform" and item.get("role") == "admin" and platform_admin_email:
            item["auth_email"] = platform_admin_email.strip().lower()
        elif item.get("account_scope") == "platform" and item.get("role") == "admin":
            item["migration_blockers"].append("platform_admin_auth_identifier_required")
            issues.append({"code": "platform_admin_auth_identifier_required", "severity": "blocking", "source": item["source"], "local_id": item["local_id"]})
        else:
            item["migration_blockers"].append("phone_required")
            issues.append({"code": "phone_required", "severity": "blocking", "source": item["source"], "local_id": item["local_id"], "display_name": item.get("display_name")})
    for phone, rows in sorted(by_phone.items()):
        if len(rows) > 1:
            for item in rows:
                item["migration_blockers"].append("duplicate_phone")
            issues.append({"code": "duplicate_phone", "severity": "blocking", "phone": phone, "accounts": [{"source": r["source"], "local_id": r["local_id"], "display_name": r.get("display_name")} for r in rows]})

    if "drivers" in tables and required_user_columns.issubset(user_columns):
        driver_columns = _columns(conn, "drivers")
        if {"tenant_id", "user_id", "phone", "status"}.issubset(driver_columns):
            rows = conn.execute(
                """
                SELECT d.id AS driver_id, d.tenant_id, d.name, d.phone, d.user_id, d.status,
                       u.id AS account_id, u.role, u.profile_type, u.profile_id, u.tenant_id AS account_tenant_id, u.is_active
                FROM drivers d LEFT JOIN users u ON u.id = d.user_id ORDER BY d.id
                """
            ).fetchall()
            account_drivers: Counter[int] = Counter(int(row["user_id"]) for row in rows if row["user_id"])
            user_candidates = {int(item["local_id"]): item for item in candidates if item["source"] == "users"}
            for row in rows:
                item = _row(row)
                account_candidate = user_candidates.get(int(item.get("account_id") or 0))
                def block_account(code: str) -> None:
                    if account_candidate is not None and code not in account_candidate["migration_blockers"]:
                        account_candidate["migration_blockers"].append(code)
                if not _phone_key(item.get("phone")):
                    block_account("driver_phone_required")
                    issues.append({"code": "driver_phone_required", "severity": "blocking", "driver_id": item["driver_id"], "driver_name": item["name"]})
                if item.get("user_id") and not item.get("account_id"):
                    issues.append({"code": "driver_user_missing", "severity": "blocking", "driver_id": item["driver_id"], "user_id": item["user_id"]})
                if item.get("account_id") and (item.get("role") != "driver" or item.get("profile_type") != "driver"):
                    block_account("driver_role_mismatch")
                    issues.append({"code": "driver_role_mismatch", "severity": "blocking", "driver_id": item["driver_id"], "account_id": item["account_id"]})
                if item.get("account_id") and int(item.get("profile_id") or 0) != int(item["driver_id"]):
                    block_account("driver_profile_mismatch")
                    issues.append({"code": "driver_profile_mismatch", "severity": "blocking", "driver_id": item["driver_id"], "account_id": item["account_id"], "profile_id": item.get("profile_id")})
                if item.get("account_id") and int(item.get("account_tenant_id") or 0) != int(item["tenant_id"]):
                    block_account("driver_cross_tenant_binding")
                    issues.append({"code": "driver_cross_tenant_binding", "severity": "blocking", "driver_id": item["driver_id"], "account_id": item["account_id"]})
                if item.get("user_id") and account_drivers[int(item["user_id"])] > 1:
                    block_account("user_multiple_drivers")
                    issues.append({"code": "user_multiple_drivers", "severity": "blocking", "account_id": item["user_id"]})
                if str(item.get("status") or "").lower() in {"deleted", "retired"} and item.get("is_active"):
                    block_account("deleted_driver_active_account")
                    issues.append({"code": "deleted_driver_active_account", "severity": "blocking", "driver_id": item["driver_id"], "account_id": item.get("account_id")})

    return {
        "candidates": candidates,
        "issues": issues,
        "summary": {
            "candidate_count": len(candidates),
            "already_linked": sum(bool(item.get("supabase_user_id")) for item in candidates),
            "pending": sum(not bool(item.get("supabase_user_id")) for item in candidates),
            "blocked_account_count": sum(bool(item.get("migration_blockers")) for item in candidates),
            "migratable_account_count": sum(not item.get("supabase_user_id") and not item.get("migration_blockers") for item in candidates),
            "blocking_issue_count": sum(item.get("severity") == "blocking" for item in issues),
        },
    }


def _backup(db: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{db.stem}_pre_supabase_auth_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db.suffix}"
    shutil.copy2(db, target)
    return target


def apply_migration(db: Path, candidates: list[dict[str, Any]], platform_password: str = "") -> dict[str, Any]:
    # Imports happen only for --apply so a read-only scan never needs Supabase secrets.
    from backend.db import database
    from backend.services.auth_account_service import (
        SupabaseAuthError,
        account_login_email,
        create_supabase_account,
        delete_supabase_account,
        link_identity,
        update_supabase_account,
    )
    from backend.services.travel_agency_service import ensure_travel_agency_schema

    database.DB_PATH = db.resolve()
    database.init_db(seed=False)
    ensure_travel_agency_schema()
    created = []
    updated = []
    failed = []
    for item in candidates:
        email = str(item.get("auth_email") or account_login_email(item["source"], int(item["local_id"])))
        if item.get("supabase_user_id"):
            try:
                update_supabase_account(
                    str(item["supabase_user_id"]),
                    {"email": email, "email_confirm": True},
                )
                updated.append({"source": item["source"], "local_id": item["local_id"]})
            except SupabaseAuthError as exc:
                failed.append({"source": item["source"], "local_id": item["local_id"], "error": str(exc)})
            continue
        if item.get("migration_blockers"):
            continue
        phone = _phone_key(item.get("phone"))
        if phone:
            password = phone[-6:]
        elif email and platform_password:
            password = platform_password
        else:
            continue
        auth_user_id = ""
        try:
            result = create_supabase_account(
                str(item.get("phone") or ""),
                password,
                app_metadata={"migration": "trial", "account_scope": item.get("account_scope"), "role": item.get("role")},
                email=email,
            )
            auth_user_id = str(result.get("id") or "")
            if not auth_user_id:
                raise RuntimeError("supabase_user_create_missing_id")
            kwargs = {"auth_user_id": auth_user_id, "actor": "supabase-auth-migration"}
            if item["source"] == "users":
                kwargs["local_user_id"] = int(item["local_id"])
            else:
                kwargs["agency_account_id"] = int(item["local_id"])
            link_identity(**kwargs)
            created.append({"source": item["source"], "local_id": item["local_id"], "auth_user_id": auth_user_id})
        except (SupabaseAuthError, RuntimeError, ValueError) as exc:
            if auth_user_id:
                try:
                    delete_supabase_account(auth_user_id)
                except SupabaseAuthError:
                    pass
            failed.append({"source": item["source"], "local_id": item["local_id"], "error": str(exc)})
    return {
        "created": created,
        "created_count": len(created),
        "updated": updated,
        "updated_count": len(updated),
        "failed": failed,
        "failed_count": len(failed),
    }


def main() -> int:
    args = _args()
    db = args.db.resolve()
    if not db.is_file():
        raise SystemExit(f"database_not_found:{db}")
    platform_admin_email = str(args.platform_admin_email or "").strip().lower()
    if not platform_admin_email:
        try:
            from backend.config import SUPABASE_PLATFORM_ADMIN_EMAIL

            platform_admin_email = str(SUPABASE_PLATFORM_ADMIN_EMAIL or "").strip().lower()
        except (ImportError, RuntimeError):
            platform_admin_email = ""
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        result = scan(conn, platform_admin_email)
    result.update({"database": str(db), "scanned_at": datetime.now(timezone.utc).isoformat(), "apply_requested": bool(args.apply)})
    if args.apply:
        structural_codes = {"users_table_missing", "auth_identity_schema_not_applied", "agency_auth_identity_schema_not_applied"}
        if any(issue.get("code") in structural_codes for issue in result.get("issues", [])):
            result["apply_error"] = "auth_identity_schema_not_applied"
        else:
            result["backup"] = str(_backup(db, args.backup_dir.resolve()))
            needs_platform_password = any(item.get("auth_email") and not item.get("supabase_user_id") and not item.get("migration_blockers") for item in result["candidates"])
            platform_password = getpass.getpass("Existing Trial platform admin password: ") if needs_platform_password else ""
            result["migration"] = apply_migration(db, result["candidates"], platform_password)
    result["candidates"] = [{k: v for k, v in item.items() if k not in {"phone", "auth_email"}} for item in result.get("candidates", [])]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report.resolve()), "summary": result.get("summary", {}), "apply_error": result.get("apply_error")}, ensure_ascii=False))
    return 2 if result.get("apply_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())

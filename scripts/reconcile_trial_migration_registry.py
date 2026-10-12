from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRIAL_DB = Path("/home/ubuntu/tourflow/runtime/trial/wx_dispatch_trial.sqlite3")
ALLOWED_MIGRATIONS = {
    "20261009_document_model_phase2a.sql": "76b6b2d6a14291315f3603e2f1ef25d2cc9b0e2c38b6cd71f52e5b08f9a079d6",
    "20261010_document_model_phase2b.sql": "5346100e0df3aff06a69f6c0bb994a4d89c401e6940e54ae83a42cc8f2a0d000",
    "20261010_phase2c2r1_daily_import_batches.sql": "0178cd18150adfb1710cfd9926774eca68bae4cc9c765e50e14799ec432302b5",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_sql(value: str) -> str:
    value = re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", value, flags=re.I)
    value = value.replace('"', "").replace("`", "").strip().rstrip(";")
    return re.sub(r"\s+", " ", value).strip().lower()


def migration_statements(sql: str, prefix: str) -> list[str]:
    pattern = re.compile(
        rf"({prefix}\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\s+IF\s+NOT\s+EXISTS\s+\w+.*?;)",
        flags=re.I | re.S,
    )
    return [match.group(1).strip() for match in pattern.finditer(sql)]


def object_name(statement: str) -> tuple[str, str]:
    match = re.search(
        r"CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX)\s+IF\s+NOT\s+EXISTS\s+(\w+)",
        statement,
        flags=re.I,
    )
    if not match:
        raise ValueError(f"unsupported_create_statement:{statement[:80]}")
    return match.group(1).lower(), match.group(2)


def alter_columns(sql: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(
        r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(.*?);",
        flags=re.I | re.S,
    )
    result = []
    for table, definition in pattern.findall(sql):
        column = definition.strip().split(None, 1)[0].strip('"`[]')
        result.append((table, column, definition.strip()))
    return result


def expected_column(definition: str) -> dict[str, Any]:
    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    try:
        memory.execute("CREATE TABLE target (__seed INTEGER)")
        memory.execute(f"ALTER TABLE target ADD COLUMN {definition}")
        row = memory.execute("PRAGMA table_info(target)").fetchall()[-1]
        return {
            "name": row["name"],
            "type": (row["type"] or "").upper(),
            "notnull": int(row["notnull"]),
            "default": row["dflt_value"],
            "pk": int(row["pk"]),
        }
    finally:
        memory.close()


def actual_column(connection: sqlite3.Connection, table: str, column: str) -> dict[str, Any] | None:
    for row in connection.execute(f'PRAGMA table_info("{table}")'):
        if row["name"] == column:
            return {
                "name": row["name"],
                "type": (row["type"] or "").upper(),
                "notnull": int(row["notnull"]),
                "default": row["dflt_value"],
                "pk": int(row["pk"]),
            }
    return None


def effect_report(connection: sqlite3.Connection, migration: Path) -> dict[str, Any]:
    sql = migration.read_text(encoding="utf-8")
    checks: list[dict[str, Any]] = []
    for table, column, definition in alter_columns(sql):
        expected = expected_column(definition)
        actual = actual_column(connection, table, column)
        checks.append(
            {
                "kind": "column",
                "object": f"{table}.{column}",
                "ok": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )

    for statement in migration_statements(sql, "CREATE"):
        kind, name = object_name(statement)
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = ? AND name = ?", (kind, name)
        ).fetchone()
        expected = normalize_sql(statement)
        actual = normalize_sql(row["sql"]) if row and row["sql"] else None
        checks.append(
            {
                "kind": kind,
                "object": name,
                "ok": actual == expected,
                "expected_sql": expected,
                "actual_sql": actual,
            }
        )

    if migration.name == "20261009_document_model_phase2a.sql":
        required = {
            "document_id",
            "document_version_id",
            "run_group_id",
            "lifecycle_status",
            "source_hash",
            "source_sha256",
            "status",
        }
        available = {
            row["name"] for row in connection.execute("PRAGMA table_info(driver_run_documents)")
        }
        if required <= available:
            rows = connection.execute(
                """
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN document_id IS NULL OR document_version_id IS NULL OR run_group_id IS NULL THEN 1 ELSE 0 END) AS missing_identity,
                  SUM(CASE WHEN status = 'stale' AND lifecycle_status <> 'superseded' THEN 1 ELSE 0 END) AS stale_not_superseded,
                  SUM(CASE WHEN source_hash IS NOT NULL AND source_sha256 IS NULL THEN 1 ELSE 0 END) AS missing_source_sha256
                FROM driver_run_documents
                """
            ).fetchone()
            actual = {key: int(rows[key] or 0) for key in rows.keys()}
        else:
            actual = {"missing_columns": sorted(required - available)}
        checks.append(
            {
                "kind": "data_backfill",
                "object": "driver_run_documents",
                "ok": "missing_columns" not in actual
                and actual["missing_identity"] == 0
                and actual["stale_not_superseded"] == 0
                and actual["missing_source_sha256"] == 0,
                "actual": actual,
            }
        )

    return {
        "name": migration.name,
        "sha256": sha256(migration),
        "checks": checks,
        "equivalent": bool(checks) and all(item["ok"] for item in checks),
    }


def open_database(path: Path, *, writable: bool) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"database_not_found:{path}")
    mode = "rw" if writable else "ro"
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode={mode}", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def validate_backup(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise SystemExit(f"backup_not_found:{path}")
    with open_database(path, writable=False) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"backup_integrity_failed:{integrity}")
    return {"path": str(path), "sha256": sha256(path), "integrity": integrity}


def business_fingerprint(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = ("orders", "assignments", "drivers", "vehicles", "driver_run_documents", "fixed_tour_charter_drafts")
    result: dict[str, Any] = {}
    for table in tables:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            result[table] = {"exists": False}
            continue
        row = connection.execute(
            f'SELECT COUNT(*) AS count, COALESCE(SUM(id), 0) AS id_sum, COALESCE(MAX(id), 0) AS max_id FROM "{table}"'
        ).fetchone()
        logical_digest = hashlib.sha256()
        for data_row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id'):
            logical_digest.update(
                json.dumps(list(data_row), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            )
            logical_digest.update(b"\n")
        result[table] = {
            "exists": True,
            **{key: int(row[key] or 0) for key in row.keys()},
            "content_sha256": logical_digest.hexdigest(),
        }
    return result


def inspect(
    connection: sqlite3.Connection,
    migrations_dir: Path,
) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"database_integrity_failed:{integrity}")
    registry_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not registry_sql_row:
        raise SystemExit("schema_migrations_missing")
    registered = {
        row["name"]: row["applied_at"]
        for row in connection.execute("SELECT name, applied_at FROM schema_migrations")
    }
    effects = []
    for name, expected_hash in ALLOWED_MIGRATIONS.items():
        path = migrations_dir / name
        if not path.is_file():
            raise SystemExit(f"migration_file_missing:{path}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise SystemExit(
                f"migration_hash_mismatch:{name}:expected={expected_hash}:actual={actual_hash}"
            )
        result = effect_report(connection, path)
        result["registered"] = name in registered
        result["registered_at"] = registered.get(name)
        effects.append(result)
    return {
        "integrity": integrity,
        "schema_migrations_sql": normalize_sql(registry_sql_row["sql"]),
        "effects": effects,
        "business_fingerprint": business_fingerprint(connection),
        "eligible": all(item["equivalent"] for item in effects),
        "missing_registration": [item["name"] for item in effects if not item["registered"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile the three verified DAITORA Trial migration registry rows"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--migrations-dir", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--audit-file", type=Path)
    parser.add_argument("--operator", default=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    parser.add_argument("--reason", default="R1 applied verified SQL without schema_migrations registration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--isolated-copy", action="store_true")
    args = parser.parse_args()

    db_path = args.db.resolve()
    trial_path = TRIAL_DB.resolve()
    if args.isolated_copy:
        if db_path == trial_path:
            raise SystemExit("isolated_copy_must_not_be_trial_db")
    elif db_path != trial_path:
        raise SystemExit(f"unexpected_trial_db:{db_path}")
    if args.apply and (args.backup is None or args.audit_file is None):
        raise SystemExit("apply_requires_backup_and_audit_file")

    backup = validate_backup(args.backup)
    before_mtime_ns = db_path.stat().st_mtime_ns
    with open_database(db_path, writable=args.apply) as connection:
        before = inspect(connection, args.migrations_dir)
        result: dict[str, Any] = {
            "schema_version": 1,
            "mode": "apply" if args.apply else "dry-run",
            "target": "isolated-copy" if args.isolated_copy else "trial",
            "database": str(db_path),
            "database_sha256_before": sha256(db_path),
            "database_mtime_ns_before": before_mtime_ns,
            "backup": backup,
            "operator": args.operator,
            "reason": args.reason,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "before": before,
        }
        if not before["eligible"]:
            result["status"] = "blocked_effect_mismatch"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise SystemExit(3)

        if args.apply:
            connection.execute("BEGIN IMMEDIATE")
            try:
                locked = inspect(connection, args.migrations_dir)
                if not locked["eligible"] or locked["business_fingerprint"] != before["business_fingerprint"]:
                    raise RuntimeError("database_changed_during_reconciliation")
                for name in locked["missing_registration"]:
                    connection.execute("INSERT INTO schema_migrations(name) VALUES (?)", (name,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            after = inspect(connection, args.migrations_dir)
            if after["business_fingerprint"] != before["business_fingerprint"]:
                raise RuntimeError("business_fingerprint_changed")
            result["after"] = after
            result["status"] = "applied" if before["missing_registration"] else "already_reconciled"
            result["applied_at"] = datetime.now(timezone.utc).isoformat()
            result["database_sha256_after"] = sha256(db_path)
            args.audit_file.parent.mkdir(parents=True, exist_ok=True)
            temporary_audit = args.audit_file.with_suffix(args.audit_file.suffix + ".tmp")
            temporary_audit.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary_audit.replace(args.audit_file)
        else:
            result["status"] = "ready_to_reconcile" if before["missing_registration"] else "already_reconciled"
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.db import database


MIGRATION_NAME = "20261015_driver_route_node_actuals_phase2a.sql"


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table_fingerprint(conn, table):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    rows = [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    return hashlib.sha256(
        json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


class DriverPhase2AMigrationTest(unittest.TestCase):
    def test_additive_migration_rehearsal_repeat_start_and_recoverable_backup(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            db_path = Path(temp) / "pre-phase2a.sqlite3"
            backup_path = Path(temp) / "pre-phase2a.backup.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            for migration in sorted(database.MIGRATIONS_PATH.glob("*.sql")):
                if migration.name == MIGRATION_NAME:
                    continue
                conn.executescript(migration.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (migration.name,))
            conn.execute("INSERT INTO drivers (tenant_id, name) VALUES (1, '迁移演练司机')")
            driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute("INSERT INTO vehicles (tenant_id, plate_number) VALUES (1, '大阪500あ9900')")
            vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """INSERT INTO orders (tenant_id, oid, order_date, pickup_location, dropoff_location)
                   VALUES (1, 'P2A-MIG-1', '2026-10-20', 'A', 'B')"""
            )
            order_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, published_at)
                   VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (order_id, driver_id, vehicle_id),
            )
            conn.execute(
                """INSERT INTO dispatch_route_node_actuals
                   (tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date,
                    actual_location, entered_by)
                   VALUES (1, 'node-pre', 'run-pre', ?, ?, '2026-10-20', '保留地点', 'driver:test')""",
                (driver_id, vehicle_id),
            )
            conn.commit()
            conn.close()

            shutil.copy2(db_path, backup_path)
            backup_sha = file_sha256(backup_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            before = {
                table: table_fingerprint(conn, table)
                for table in ("orders", "assignments", "driver_run_documents", "dispatch_route_nodes")
            }
            actual_rows_before = [dict(row) for row in conn.execute(
                "SELECT tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date, actual_location, entered_by FROM dispatch_route_node_actuals ORDER BY id"
            )]
            conn.executescript((database.MIGRATIONS_PATH / MIGRATION_NAME).read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (MIGRATION_NAME,))
            conn.commit()
            after = {
                table: table_fingerprint(conn, table)
                for table in ("orders", "assignments", "driver_run_documents", "dispatch_route_nodes")
            }
            actual_rows_after = [dict(row) for row in conn.execute(
                "SELECT tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date, actual_location, entered_by FROM dispatch_route_node_actuals ORDER BY id"
            )]
            self.assertEqual(before, after)
            self.assertEqual(actual_rows_before, actual_rows_after)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(dispatch_route_node_actuals)")}
            self.assertTrue({"revision", "source_document_version_id", "source_sha256"}.issubset(columns))
            request_columns = {row["name"] for row in conn.execute("PRAGMA table_info(driver_route_node_actual_requests)")}
            self.assertTrue({"actor_user_id", "actor_role", "before_json", "after_json", "response_json", "received_at"}.issubset(request_columns))

            database.apply_migrations(conn)
            database.apply_migrations(conn)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE name = ?", (MIGRATION_NAME,)
            ).fetchone()[0], 1)
            conn.close()

            restored = sqlite3.connect(backup_path)
            restored.row_factory = sqlite3.Row
            self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(restored.execute(
                "SELECT actual_location FROM dispatch_route_node_actuals WHERE route_node_id = 'node-pre'"
            ).fetchone()[0], "保留地点")
            restored.close()
            self.assertEqual(file_sha256(backup_path), backup_sha)

            artifact_root = os.environ.get("DAITORA_PHASE2A_ARTIFACT_DIR")
            if artifact_root:
                destination = Path(artifact_root)
                destination.mkdir(parents=True, exist_ok=True)
                pre_copy = destination / "phase2a-migration-pre.sqlite3"
                post_copy = destination / "phase2a-migration-post.sqlite3"
                shutil.copy2(backup_path, pre_copy)
                shutil.copy2(db_path, post_copy)
                evidence = {
                    "migration": MIGRATION_NAME,
                    "pre_database": str(pre_copy.resolve()),
                    "pre_sha256": file_sha256(pre_copy),
                    "post_database": str(post_copy.resolve()),
                    "post_sha256": file_sha256(post_copy),
                    "integrity_check": "ok",
                    "business_fingerprints_before": before,
                    "business_fingerprints_after": after,
                    "existing_actual_rows_unchanged": actual_rows_before == actual_rows_after,
                    "migration_registration_count_after_two_restarts": 1,
                    "rollback_backup_integrity": "ok",
                }
                (destination / "phase2a-migration-rehearsal.json").write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
                )


if __name__ == "__main__":
    unittest.main()

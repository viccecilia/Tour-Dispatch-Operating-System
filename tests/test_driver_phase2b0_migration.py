import hashlib
import json
import os
import shutil
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database


MIGRATION_NAME = "20261015_driver_provisional_tasks_phase2b0a.sql"
DEPENDENT_MIGRATIONS = {"20261015_m1_driver_provisional_dual_odometers.sql"}


class DriverPhase2B0MigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        self.original_db = database.DB_PATH
        self.original_migrations = database.MIGRATIONS_PATH
        database.DB_PATH = self.root / "phase2b0a-rehearsal.sqlite3"

    def tearDown(self):
        database.DB_PATH = self.original_db
        database.MIGRATIONS_PATH = self.original_migrations
        self.temp.cleanup()

    def _fingerprint(self, conn):
        projections = {
            "users": "id, tenant_id, username, role, display_name, is_active",
            "drivers": "id, tenant_id, user_id, name, status, driver_status",
            "vehicles": "id, tenant_id, plate_number, status",
            # OIDs are intentionally excluded: the existing compatibility startup refreshes
            # legacy temporary OIDs independently of this migration. Business/manual values
            # are the non-regression gate here.
            "orders": "id, tenant_id, order_date, end_date, start_time, end_time, pickup_location, dropoff_location, order_type, price, price_jpy, dispatch_status, execution_status, settlement_status, is_deleted",
            "assignments": "id, tenant_id, order_id, driver_id, vehicle_id, status, execution_status, published_at",
            "dispatch_route_node_actuals": "id, tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date, actual_arrival_at, actual_departure_at, odometer_km, actual_location, revision, source_document_version_id, source_sha256",
        }
        result = {}
        for table, projection in projections.items():
            rows = [list(row) for row in conn.execute(f"SELECT {projection} FROM {table} ORDER BY id").fetchall()]
            result[table] = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return result

    def test_preflight_apply_repeat_startup_and_restore(self):
        pre_migrations = self.root / "pre-migrations"
        pre_migrations.mkdir()
        for source in self.original_migrations.glob("*.sql"):
            if source.name != MIGRATION_NAME and source.name not in DEPENDENT_MIGRATIONS:
                shutil.copy2(source, pre_migrations / source.name)
        database.MIGRATIONS_PATH = pre_migrations
        database.init_db(seed=True)
        with closing(database.get_connection()) as conn:
            driver = int(conn.execute(
                "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, 'B0 Rehearsal Driver', 'available', 'available')"
            ).lastrowid)
            vehicle = int(conn.execute(
                "INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (1, '大阪500あ8999', 'available')"
            ).lastrowid)
            order = int(conn.execute(
                """INSERT INTO orders
                   (tenant_id, oid, order_date, pickup_location, dropoff_location, order_type,
                    price, price_jpy, dispatch_status, execution_status)
                   VALUES (1, 'B0-REHEARSAL-LEGACY', '2026-10-14', 'Before', 'After',
                           'airport_transfer', 19500, 19500, 'assigned', 'completed')"""
            ).lastrowid)
            assignment = int(conn.execute(
                """INSERT INTO assignments
                   (tenant_id, order_id, driver_id, vehicle_id, status, execution_status, published_at)
                   VALUES (1, ?, ?, ?, 'active', 'completed', CURRENT_TIMESTAMP)""",
                (order, driver, vehicle),
            ).lastrowid)
            conn.execute(
                """INSERT INTO dispatch_route_node_actuals
                   (tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date,
                    actual_arrival_at, actual_departure_at, odometer_km, actual_location,
                    revision, source_document_version_id, source_sha256)
                   VALUES (1, 'b0-node', 'b0-run', ?, ?, '2026-10-14',
                           '2026-10-14T13:20:00+09:00', '2026-10-14T14:20:00+09:00',
                           128.4, 'legacy actual', 1, 'b0-docv', 'b0-source')""",
                (driver, vehicle),
            )
            conn.commit()

        # Establish the fully normalized pre-B0 startup baseline first.  This
        # separates existing compatibility repairs from the new migration.
        database.init_db(seed=False)
        with closing(database.get_connection()) as conn:
            pre_fingerprint = self._fingerprint(conn)
            pre_integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            pre_migration_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            self.assertNotIn("origin_kind", [row[1] for row in conn.execute("PRAGMA table_info(orders)")])
            self.assertIsNone(conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'driver_provisional_tasks'"
            ).fetchone())

        backup = self.root / "phase2b0a-before.sqlite3"
        shutil.copy2(database.DB_PATH, backup)
        backup_sha = hashlib.sha256(backup.read_bytes()).hexdigest()

        database.MIGRATIONS_PATH = self.original_migrations
        database.init_db(seed=False)
        with closing(database.get_connection()) as conn:
            post_fingerprint = self._fingerprint(conn)
            post_integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            registration_count = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE name = ?", (MIGRATION_NAME,)
            ).fetchone()[0]
            order_columns = [row[1] for row in conn.execute("PRAGMA table_info(orders)")]
            task_columns = [row[1] for row in conn.execute("PRAGMA table_info(driver_provisional_tasks)")]
            event_columns = [row[1] for row in conn.execute("PRAGMA table_info(driver_provisional_task_events)")]
            if pre_fingerprint != post_fingerprint:
                changed = {key: (pre_fingerprint[key], post_fingerprint[key]) for key in pre_fingerprint if pre_fingerprint[key] != post_fingerprint[key]}
                current_orders = [dict(row) for row in conn.execute("SELECT id, oid, order_date, end_date, start_time, end_time, pickup_location, dropoff_location, order_type, price, price_rmb, price_jpy, dispatch_status, execution_status, settlement_status, is_deleted FROM orders ORDER BY id")]
                self.fail(f"legacy_fingerprint_changed:{changed}; orders={current_orders}")
            self.assertEqual((pre_integrity, post_integrity), ("ok", "ok"))
            self.assertEqual(registration_count, 1)
            self.assertIn("origin_kind", order_columns)
            self.assertIn("origin_provisional_task_id", order_columns)
            self.assertIn("original_snapshot_json", task_columns)
            self.assertIn("client_request_id", event_columns)

        database.init_db(seed=False)
        with closing(database.get_connection()) as conn:
            repeat_fingerprint = self._fingerprint(conn)
            repeat_registration_count = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE name = ?", (MIGRATION_NAME,)
            ).fetchone()[0]
            self.assertEqual(repeat_fingerprint, pre_fingerprint)
            self.assertEqual(repeat_registration_count, 1)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

        rollback = self.root / "phase2b0a-rollback.sqlite3"
        shutil.copy2(backup, rollback)
        original_live = database.DB_PATH
        database.DB_PATH = rollback
        try:
            with closing(database.get_connection()) as conn:
                self.assertEqual(self._fingerprint(conn), pre_fingerprint)
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertNotIn("origin_kind", [row[1] for row in conn.execute("PRAGMA table_info(orders)")])
                self.assertIsNone(conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'driver_provisional_tasks'"
                ).fetchone())
        finally:
            database.DB_PATH = original_live

        artifact_root = os.environ.get("DAITORA_PHASE2B0_ARTIFACT_DIR")
        if artifact_root:
            destination = Path(artifact_root)
            destination.mkdir(parents=True, exist_ok=True)
            for source in (backup, rollback, database.DB_PATH):
                shutil.copy2(source, destination / source.name)
            evidence = {
                "migration": MIGRATION_NAME,
                "migration_sha256": hashlib.sha256((self.original_migrations / MIGRATION_NAME).read_bytes()).hexdigest(),
                "pre_migration_count": pre_migration_count,
                "registration_count": 1,
                "backup_sha256": backup_sha,
                "pre_integrity": pre_integrity,
                "post_integrity": post_integrity,
                "legacy_fingerprints_unchanged": pre_fingerprint == post_fingerprint == repeat_fingerprint,
                "rollback_verified": True,
            }
            (destination / "phase2b0a-migration-rehearsal.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    unittest.main()

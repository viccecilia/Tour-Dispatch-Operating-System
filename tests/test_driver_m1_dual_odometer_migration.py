import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database


MIGRATION_NAME = "20261015_m1_driver_provisional_dual_odometers.sql"


class DriverM1DualOdometerMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        self.original_db = database.DB_PATH
        self.original_migrations = database.MIGRATIONS_PATH
        database.DB_PATH = self.root / "m1-dual-odometer.sqlite3"

    def tearDown(self):
        database.DB_PATH = self.original_db
        database.MIGRATIONS_PATH = self.original_migrations
        self.temp.cleanup()

    @staticmethod
    def _fingerprint(conn):
        projections = {
            "orders": "id, tenant_id, oid, price, price_jpy, execution_status",
            "assignments": "id, tenant_id, order_id, driver_id, vehicle_id, status",
            "driver_provisional_tasks": "id, tenant_id, provisional_task_id, display_number, odometer_km, status, revision, original_snapshot_json",
            "driver_provisional_task_events": "id, tenant_id, provisional_task_id, event_type, request_sha256",
        }
        result = {}
        for table, projection in projections.items():
            rows = [list(row) for row in conn.execute(f"SELECT {projection} FROM {table} ORDER BY id")]
            result[table] = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return result

    def test_additive_apply_repeat_and_restore(self):
        pre_migrations = self.root / "pre-migrations"
        pre_migrations.mkdir()
        for source in self.original_migrations.glob("*.sql"):
            if source.name != MIGRATION_NAME:
                shutil.copy2(source, pre_migrations / source.name)
        database.MIGRATIONS_PATH = pre_migrations
        database.init_db(seed=True)

        with closing(database.get_connection()) as conn:
            driver_id = conn.execute("INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, 'M1 Driver', 'available', 'available')").lastrowid
            vehicle_id = conn.execute("INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (1, '大阪500あM101', 'available')").lastrowid
            user_id = conn.execute("SELECT id FROM users WHERE tenant_id = 1 ORDER BY id LIMIT 1").fetchone()[0]
            conn.execute(
                """INSERT INTO driver_provisional_tasks
                   (tenant_id, provisional_task_id, display_number, driver_id, vehicle_id,
                    business_date, odometer_km, status, original_snapshot_json, created_by_user_id)
                   VALUES (1, 'pt-m1-legacy', 'TMP-M1-LEGACY', ?, ?, '2026-10-15', 88.8,
                           'draft', '{"legacy":true}', ?)""",
                (driver_id, vehicle_id, user_id),
            )
            conn.commit()
            before = self._fingerprint(conn)
            self.assertNotIn("pickup_odometer_km", [row[1] for row in conn.execute("PRAGMA table_info(driver_provisional_tasks)")])

        backup = self.root / "before-m1-dual-odometer.sqlite3"
        shutil.copy2(database.DB_PATH, backup)
        database.MIGRATIONS_PATH = self.original_migrations
        database.init_db(seed=False)
        with closing(database.get_connection()) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(driver_provisional_tasks)")]
            self.assertIn("pickup_odometer_km", columns)
            self.assertIn("dropoff_odometer_km", columns)
            self.assertEqual(self._fingerprint(conn), before)
            legacy = conn.execute("SELECT odometer_km, pickup_odometer_km, dropoff_odometer_km FROM driver_provisional_tasks WHERE provisional_task_id = 'pt-m1-legacy'").fetchone()
            self.assertEqual((legacy[0], legacy[1], legacy[2]), (88.8, None, None))
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE name = ?", (MIGRATION_NAME,)).fetchone()[0], 1)

        database.init_db(seed=False)
        with closing(database.get_connection()) as conn:
            self.assertEqual(self._fingerprint(conn), before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE name = ?", (MIGRATION_NAME,)).fetchone()[0], 1)

        rollback = self.root / "rollback-m1-dual-odometer.sqlite3"
        shutil.copy2(backup, rollback)
        database.DB_PATH = rollback
        try:
            with closing(database.get_connection()) as conn:
                self.assertEqual(self._fingerprint(conn), before)
                self.assertNotIn("pickup_odometer_km", [row[1] for row in conn.execute("PRAGMA table_info(driver_provisional_tasks)")])
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            database.DB_PATH = self.root / "m1-dual-odometer.sqlite3"


if __name__ == "__main__":
    unittest.main()

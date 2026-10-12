import tempfile
import unittest
from copy import deepcopy
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend.db import database
from backend.services import dispatch_service, parser_service
from backend.services.tenant_context import set_current_tenant_id


class DailyImportTransactionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "daily-import.sqlite3"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, '柚子旅行', 'yuzu-test')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, status, driver_status) VALUES (10, 1, '姚博', 'available', 'available')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_number, plate_no, status) VALUES (20, 1, '大阪7007', '大阪7007', 'available')")
            conn.commit()
        self.actor = {"id": 99, "display_name": "运行管理"}

    def tearDown(self):
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def payload(self):
        return {
            "driver_id": 10,
            "vehicle_id": 20,
            "orders": [
                {
                    "order_date": "2026-10-05",
                    "end_date": "2026-10-05",
                    "start_time": "07:45",
                    "end_time": "09:45",
                    "order_type": "单送",
                    "pickup_location": "大阪ホテル",
                    "dropoff_location": "新大阪駅",
                    "remark": "公司单",
                },
                {
                    "order_date": "2026-10-05",
                    "end_date": "2026-10-05",
                    "start_time": "10:15",
                    "end_time": "12:15",
                    "order_type": "单送",
                    "pickup_location": "大阪ホテル",
                    "dropoff_location": "りんくうタウン",
                    "source_channel": "WeChat",
                },
            ],
        }

    def counts(self):
        with closing(database.get_connection()) as conn:
            orders = conn.execute("SELECT COUNT(*) AS n FROM orders WHERE COALESCE(is_deleted, 0) = 0").fetchone()["n"]
            assignments = conn.execute("SELECT COUNT(*) AS n FROM assignments WHERE status = 'active'").fetchone()["n"]
        return orders, assignments

    def test_same_batch_twice_is_idempotent(self):
        first = dispatch_service.import_daily_assignment_group(self.payload(), self.actor)
        second = dispatch_service.import_daily_assignment_group(self.payload(), self.actor)
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["order_ids"], second["order_ids"])
        self.assertEqual(self.counts(), (2, 2))

    def test_arrival_provenance_survives_daily_import(self):
        payload = self.payload()
        payload["orders"][0].update({
            "end_time": "08:45",
            "end_time_source": "suggested_60m",
            "end_time_confirmed": 0,
        })
        result = dispatch_service.import_daily_assignment_group(payload, self.actor)
        with closing(database.get_connection()) as conn:
            row = conn.execute(
                "SELECT end_time, end_time_source, end_time_confirmed FROM orders WHERE id = ?",
                (result["order_ids"][0],),
            ).fetchone()
        self.assertEqual((row["end_time"], row["end_time_source"], row["end_time_confirmed"]), ("08:45", "suggested_60m", 0))

    def test_city_hotel_candidate_provenance_survives_raw_parse_and_import(self):
        raw = "10/9 姚博 7007\n09:30 大阪送机关西 微信"
        parsed = parser_service.parse_daily_assignment_text(raw, base_year=2026)["groups"][0]["orders"][0]["parsed"]
        payload = {
            "driver_id": 10,
            "vehicle_id": 20,
            "orders": [parsed],
        }
        result = dispatch_service.import_daily_assignment_group(payload, self.actor)
        with closing(database.get_connection()) as conn:
            row = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (result["order_ids"][0],)).fetchone())
        self.assertEqual(row["pickup_source_text"], "大阪")
        self.assertEqual(row["pickup_parsed_location"], "大阪")
        self.assertEqual(row["pickup_suggested_location"], parsed["pickup_location"])
        self.assertEqual(row["pickup_location"], parsed["pickup_location"])
        self.assertEqual(row["pickup_location_confirmed"], 0)

    def test_mid_transaction_failure_rolls_back_everything(self):
        original = dispatch_service._insert_daily_import_order
        calls = {"count": 0}

        def fail_on_second(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("injected failure")
            return original(*args, **kwargs)

        with patch.object(dispatch_service, "_insert_daily_import_order", side_effect=fail_on_second):
            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                dispatch_service.import_daily_assignment_group(self.payload(), self.actor)
        self.assertEqual(self.counts(), (0, 0))

    def test_published_assignment_remains_a_real_conflict(self):
        with closing(database.get_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (tenant_id, order_date, end_date, start_time, end_time,
                                    pickup_location, dropoff_location, dispatch_status, execution_status)
                VALUES (1, '2026-10-05', '2026-10-05', '07:30', '08:30',
                        '大阪', '京都', 'assigned', 'assigned')
                """
            )
            conn.execute(
                """
                INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status,
                                         execution_status, published_at)
                VALUES (1, ?, 10, 20, 'active', 'assigned', CURRENT_TIMESTAMP)
                """,
                (cursor.lastrowid,),
            )
            conn.commit()
        result = dispatch_service.import_daily_assignment_group(self.payload(), self.actor)
        self.assertFalse(result["success"])
        self.assertTrue(any(item["type"] == "published_assignment" for item in result["conflicts"]))
        self.assertEqual(self.counts(), (1, 1))

    def test_corrected_unpublished_group_updates_in_place(self):
        first = dispatch_service.import_daily_assignment_group(self.payload(), self.actor)
        changed = self.payload()
        changed["orders"][1]["dropoff_location"] = "関西国際空港"
        second = dispatch_service.import_daily_assignment_group(changed, self.actor)
        self.assertTrue(second["success"])
        self.assertTrue(second["updated_existing"])
        self.assertEqual(first["order_ids"], second["order_ids"])
        self.assertEqual(self.counts(), (2, 2))
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT dropoff_location FROM orders WHERE id = ?", (first["order_ids"][1],)).fetchone()
        self.assertEqual(row["dropoff_location"], "関西国際空港")

    def test_multi_group_failure_rolls_back_earlier_group(self):
        second_group = self.payload()
        second_group["driver_id"] = 11
        second_group["vehicle_id"] = 21
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO drivers (id, tenant_id, name, status, driver_status) VALUES (11, 1, '备用司机', 'available', 'available')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_number, plate_no, status) VALUES (21, 1, '大阪7011', '大阪7011', 'available')")
            conn.commit()
        original = dispatch_service._insert_daily_import_order
        calls = {"count": 0}

        def fail_in_second_group(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 3:
                raise RuntimeError("second group failed")
            return original(*args, **kwargs)

        with patch.object(dispatch_service, "_insert_daily_import_order", side_effect=fail_in_second_group):
            with self.assertRaisesRegex(RuntimeError, "second group failed"):
                dispatch_service.import_daily_assignment_batch(
                    {"groups": [self.payload(), second_group]},
                    self.actor,
                )
        self.assertEqual(self.counts(), (0, 0))

    def test_same_resources_on_different_dates_have_unique_oids(self):
        first = self.payload()
        first["orders"] = [deepcopy(first["orders"][0])]
        first["orders"][0]["order_date"] = "2026-10-09"
        first["orders"][0]["end_date"] = "2026-10-09"
        second = deepcopy(first)
        second["orders"][0]["order_date"] = "2026-10-12"
        second["orders"][0]["end_date"] = "2026-10-12"
        one = dispatch_service.import_daily_assignment_group(first, self.actor)
        two = dispatch_service.import_daily_assignment_group(second, self.actor)
        self.assertTrue(one["success"])
        self.assertTrue(two["success"])
        with closing(database.get_connection()) as conn:
            rows = conn.execute("SELECT oid, order_date FROM orders ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["oid"] for row in rows}), 2)
        self.assertIn("261009", rows[0]["oid"])
        self.assertIn("261012", rows[1]["oid"])

    def test_client_batch_id_replay_returns_same_business_result(self):
        request = {"client_batch_id": "daily-r1-idempotent", "groups": [self.payload()]}
        first = dispatch_service.import_daily_assignment_batch(request, self.actor)
        second = dispatch_service.import_daily_assignment_batch(request, self.actor)
        status = dispatch_service.get_daily_import_batch_status("daily-r1-idempotent")
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(first["order_ids"], second["order_ids"])
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(status["result"]["order_ids"], first["order_ids"])
        self.assertEqual(self.counts(), (2, 2))

    def test_failed_client_batch_records_rollback_status(self):
        original = dispatch_service._insert_daily_import_order
        calls = {"count": 0}

        def fail_on_second(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("injected batch failure")
            return original(*args, **kwargs)

        request = {"client_batch_id": "daily-r1-failed", "groups": [self.payload()]}
        with patch.object(dispatch_service, "_insert_daily_import_order", side_effect=fail_on_second):
            with self.assertRaisesRegex(RuntimeError, "injected batch failure"):
                dispatch_service.import_daily_assignment_batch(request, self.actor)
        status = dispatch_service.get_daily_import_batch_status("daily-r1-failed")
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error_code"], "daily_import_transaction_failed")
        self.assertEqual(self.counts(), (0, 0))


if __name__ == "__main__":
    unittest.main()

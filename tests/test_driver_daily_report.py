import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database
from backend.services import dispatch_service, driver_service, order_service
from backend.services.tenant_context import set_current_tenant_id


class DriverDailyReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "driver_daily_report.sqlite3"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, 'Tenant 1', 'tenant-1')")
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (2, 'Tenant 2', 'tenant-2')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, status, driver_status) VALUES (1, 1, '司机甲', 'available', 'available')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, status, driver_status) VALUES (2, 1, '司机乙', 'available', 'available')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, status, driver_status) VALUES (3, 2, '外部司机', 'available', 'available')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_number, vehicle_type, status) VALUES (1, 1, '大阪300あ7007', 'Alphard', 'available')")
            conn.commit()

    def tearDown(self):
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def create_published_assignment(self):
        order = order_service.create_order({
            "order_date": "2026-10-10",
            "start_time": "08:00",
            "end_time": "10:00",
            "pickup_location": "大阪市内酒店",
            "dropoff_location": "KIX",
            "order_type": "送机",
        })
        result = dispatch_service.assign_orders(
            [order["id"]], 1, 1,
            actor={"id": 9, "tenant_id": 1, "display_name": "调度", "role": "dispatcher"},
            notify_driver=False,
            publish_assignment=True,
        )
        self.assertTrue(result["success"])
        return order, result["assignment_ids"][0]

    def test_driver_only_sees_published_own_assignment_and_can_submit_daily_report(self):
        order, assignment_id = self.create_published_assignment()
        visible = driver_service.list_driver_assignments(1)
        self.assertEqual([item["order_id"] for item in visible], [order["id"]])
        self.assertEqual(driver_service.list_driver_assignments(2), [])

        prefill = driver_service.get_driver_daily_report(1, "2026-10-10")
        self.assertTrue(prefill["success"])
        self.assertEqual(prefill["report"]["assignment_count"], 1)

        for event_type in ("vehicle_check_out", "roll_call_out"):
            self.assertTrue(driver_service.submit_driver_workflow_event({
                "driver_id": 1, "assignment_id": assignment_id, "event_type": event_type,
                "location_text": "大阪车库",
            })["success"])
        for report_type in ("confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"):
            payload = {
                "driver_id": 1, "assignment_id": assignment_id, "report_type": report_type,
                "location_text": "司机端测试",
            }
            if report_type == "arrive_pickup":
                payload.update({"latitude": visible[0]["pickup_latitude"], "longitude": visible[0]["pickup_longitude"]})
            if report_type == "complete_order":
                payload.update({"latitude": visible[0]["dropoff_latitude"], "longitude": visible[0]["dropoff_longitude"]})
            result = driver_service.submit_driver_report(payload)
            self.assertTrue(result["success"], result)
        for event_type in ("vehicle_check_in", "roll_call_in"):
            self.assertTrue(driver_service.submit_driver_workflow_event({
                "driver_id": 1, "assignment_id": assignment_id, "event_type": event_type,
                "location_text": "大阪车库",
            })["success"])
        self.assertTrue(driver_service.submit_driver_location({
            "driver_id": 1, "assignment_id": assignment_id, "location_text": "大阪车库", "source": "test",
        })["success"])

        saved = driver_service.save_driver_daily_report({
            "driver_id": 1,
            "business_date": "2026-10-10",
            "summary": "已安全完成，代收已交接。",
            "rest_hours": "8.0",
            "submit": True,
        })
        self.assertTrue(saved["success"])
        self.assertEqual((saved["report"]["status"], saved["report"]["rest_hours"]), ("submitted", 8.0))
        self.assertEqual(saved["report"]["assignments"][0]["execution_status"], "returned")
        self.assertTrue(driver_service.list_driver_history(1))

    def test_daily_report_is_tenant_scoped(self):
        self.create_published_assignment()
        set_current_tenant_id(2)
        self.assertEqual(driver_service.list_driver_assignments(1), [])
        result = driver_service.get_driver_daily_report(1, "2026-10-10")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "driver_not_found")


if __name__ == "__main__":
    unittest.main()

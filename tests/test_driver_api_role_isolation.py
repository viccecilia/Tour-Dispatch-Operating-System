import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from backend.api.routes import ApiHandler
from backend.db import database
from backend.services import dispatch_service, order_service
from backend.services.tenant_context import set_current_tenant_id


class DriverApiRoleIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "driver-api-isolation.sqlite3"
        database.init_db(seed=True)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, '司机本人', 'available', 'available')")
            self.driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute("INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, '其他司机', 'available', 'available')")
            self.other_driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute("INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (1, '大阪500あ1234', 'available')")
            self.vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute("UPDATE users SET profile_type = 'driver', profile_id = ? WHERE username = 'driver_demo'", (self.driver_id,))
            conn.commit()

        self.own_order_id = self.create_published_assignment(self.driver_id, "本人任务")
        self.other_order_id = self.create_published_assignment(self.other_driver_id, "他人任务")
        with closing(database.get_connection()) as conn:
            self.own_assignment_id = int(conn.execute(
                "SELECT id FROM assignments WHERE order_id = ?", (self.own_order_id,)
            ).fetchone()[0])
            self.other_assignment_id = int(conn.execute(
                "SELECT id FROM assignments WHERE order_id = ?", (self.other_order_id,)
            ).fetchone()[0])

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.driver_token = self.login("driver_demo", "driver123")
        self.admin_token = self.login("admin", "admin123")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def create_published_assignment(self, driver_id, label):
        order = order_service.create_order({
            "order_date": date.today().isoformat(),
            "start_time": "08:00" if driver_id == self.driver_id else "10:00",
            "end_time": "09:00" if driver_id == self.driver_id else "11:00",
            "pickup_location": label,
            "dropoff_location": "KIX",
            "order_type": "送机",
        })
        result = dispatch_service.assign_orders(
            [order["id"]], driver_id, self.vehicle_id,
            actor={"id": 9, "tenant_id": 1, "display_name": "调度", "role": "dispatcher"},
            notify_driver=False,
            publish_assignment=True,
        )
        self.assertTrue(result["success"])
        return order["id"]

    def login(self, username, password):
        status, payload = self.request("POST", "/api/auth/login", {"username": username, "password": password})
        self.assertEqual(status, 200, payload)
        return payload["token"]

    def request(self, method, path, payload=None, token=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_driver_query_cannot_select_another_driver_and_admin_is_denied(self):
        query = urllib.parse.urlencode({"driver_id": self.other_driver_id})
        status, payload = self.request("GET", f"/api/driver/assignments?{query}", token=self.driver_token)
        self.assertEqual(status, 200)
        self.assertEqual([item["order_id"] for item in payload["assignments"]], [self.own_order_id])
        self.assertNotIn(self.other_order_id, [item["order_id"] for item in payload["assignments"]])

        status, payload = self.request("GET", "/api/driver/workbench", token=self.admin_token)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "forbidden")

    def test_driver_post_payload_is_overwritten_with_authenticated_profile(self):
        status, payload = self.request(
            "POST",
            "/api/driver/workflow-event",
            {"driver_id": self.other_driver_id, "event_type": "vehicle_cleaning", "note": "role isolation test"},
            token=self.driver_token,
        )
        self.assertEqual(status, 201, payload)
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT driver_id FROM driver_workflow_events WHERE id = ?", (payload["event_id"],)).fetchone()
        self.assertEqual(int(row["driver_id"]), self.driver_id)

    def test_driver_cannot_select_another_drivers_report_expense_document_or_notification(self):
        day = date.today().isoformat()
        with closing(database.get_connection()) as conn:
            for driver_id, assignment_id, order_id, marker in (
                (self.driver_id, self.own_assignment_id, self.own_order_id, "own"),
                (self.other_driver_id, self.other_assignment_id, self.other_order_id, "other"),
            ):
                conn.execute(
                    """INSERT INTO driver_daily_reports
                       (tenant_id, driver_id, business_date, status, assignment_snapshot_json, summary)
                       VALUES (1, ?, ?, 'draft', '[]', ?)""",
                    (driver_id, day, f"{marker}-report"),
                )
                conn.execute(
                    """INSERT INTO driver_expense_reports
                       (tenant_id, driver_id, assignment_id, order_id, expense_kind, category, amount, submit_status, note)
                       VALUES (1, ?, ?, ?, 'advance', 'parking', 100, 'submitted', ?)""",
                    (driver_id, assignment_id, order_id, f"{marker}-expense"),
                )
                conn.execute(
                    """INSERT INTO driver_run_documents
                       (tenant_id, business_date, driver_id, vehicle_id, version, status, source_hash,
                        file_name, file_path, file_url, published_at)
                       VALUES (1, ?, ?, ?, 1, 'published', ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        day, driver_id, self.vehicle_id, f"{marker}-hash", f"{marker}.pdf",
                        f"C:/isolated/{marker}.pdf", f"/isolated/{marker}.pdf",
                    ),
                )
                conn.execute(
                    """INSERT INTO notifications
                       (tenant_id, notification_type, title, body, target_role, source_type, source_id)
                       VALUES (1, 'run_document_published', ?, 'role isolation', 'driver',
                               'driver_run_document', ?)""",
                    (f"{marker}-notification", f"{driver_id}:document:{marker}"),
                )
            conn.commit()

        forged = urllib.parse.urlencode({"driver_id": self.other_driver_id, "date": day})

        status, payload = self.request("GET", f"/api/driver/daily-report?{forged}", token=self.driver_token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["report"]["driver_id"], self.driver_id)
        self.assertEqual(payload["report"]["summary"], "own-report")

        status, payload = self.request("GET", f"/api/driver/expenses?{forged}", token=self.driver_token)
        self.assertEqual(status, 200)
        self.assertEqual([item["note"] for item in payload["expenses"]], ["own-expense"])

        status, payload = self.request("GET", f"/api/driver/run-documents?{forged}", token=self.driver_token)
        self.assertEqual(status, 200)
        self.assertEqual([item["file_name"] for item in payload["documents"]], ["own.pdf"])

        status, payload = self.request("GET", f"/api/driver/notifications?{forged}", token=self.driver_token)
        self.assertEqual(status, 200)
        titles = [item["title"] for item in payload["notifications"]]
        self.assertIn("own-notification", titles)
        self.assertNotIn("other-notification", titles)


if __name__ == "__main__":
    unittest.main()

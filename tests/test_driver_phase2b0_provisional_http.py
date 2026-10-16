import concurrent.futures
import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from backend.api.routes import ApiHandler
from backend.db import database
from backend.services import driver_provisional_service
from backend.services.tenant_context import set_current_tenant_id


class DriverPhase2B0ProvisionalHttpTest(unittest.TestCase):
    BUSINESS_DATE = "2026-10-14"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "phase2b0a.sqlite3"
        database.init_db(seed=True)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            self.driver1, self.driver1_user, self.vehicle1, self.shift1 = self._create_driver_shift(
                conn, 1, "b0_driver_1", "B0 Driver One", "大阪500あ8101"
            )
            self.driver2, self.driver2_user, self.vehicle2, self.shift2 = self._create_driver_shift(
                conn, 1, "b0_driver_2", "B0 Driver Two", "大阪500あ8102"
            )
            self.tenant2_driver, self.tenant2_driver_user, self.tenant2_vehicle, self.tenant2_shift = self._create_driver_shift(
                conn, 2, "b0_t2_driver", "B0 Tenant Two Driver", "京都500あ8201"
            )
            self.admin1 = self._create_user(conn, 1, "b0_admin_1", "admin", "carrier", "Carrier Admin One")
            self.admin2 = self._create_user(conn, 1, "b0_admin_2", "admin", "carrier", "Carrier Admin Two")
            self.tenant2_admin = self._create_user(conn, 2, "b0_t2_admin", "admin", "carrier", "Tenant Two Admin")
            self.operations = self._create_user(conn, 1, "b0_operations", "operations_manager", "carrier", "Operations")
            self.dispatcher = self._create_user(conn, 1, "b0_dispatcher", "dispatcher", "carrier", "Dispatcher")
            self.existing_order, self.existing_assignment = self._create_existing_link_order(conn)
            conn.commit()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.http_records = []
        self.tokens = {
            "driver1": self.login("b0_driver_1", "test123"),
            "driver2": self.login("b0_driver_2", "test123"),
            "tenant2_driver": self.login("b0_t2_driver", "test123"),
            "admin1": self.login("b0_admin_1", "test123"),
            "admin2": self.login("b0_admin_2", "test123"),
            "tenant2_admin": self.login("b0_t2_admin", "test123"),
            "operations": self.login("b0_operations", "test123"),
            "dispatcher": self.login("b0_dispatcher", "test123"),
            "platform": self.login("admin", "admin123"),
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        artifact_root = os.environ.get("DAITORA_PHASE2B0_ARTIFACT_DIR")
        if artifact_root:
            destination = Path(artifact_root)
            destination.mkdir(parents=True, exist_ok=True)
            database_copy = destination / f"phase2b0a-http-{self._testMethodName}.sqlite3"
            shutil.copy2(database.DB_PATH, database_copy)
            with closing(database.get_connection()) as conn:
                evidence = {
                    "test": self._testMethodName,
                    "database": str(database_copy.resolve()),
                    "database_sha256": hashlib.sha256(database_copy.read_bytes()).hexdigest(),
                    "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
                    "provisional_tasks": conn.execute("SELECT COUNT(*) FROM driver_provisional_tasks").fetchone()[0],
                    "provisional_events": conn.execute("SELECT COUNT(*) FROM driver_provisional_task_events").fetchone()[0],
                    "formal_orders_from_provisional": conn.execute("SELECT COUNT(*) FROM orders WHERE origin_kind = 'driver_provisional'").fetchone()[0],
                    "published_formal_assignments_from_provisional": conn.execute(
                        """SELECT COUNT(*) FROM assignments a JOIN orders o ON o.id = a.order_id
                           WHERE o.origin_kind = 'driver_provisional' AND a.published_at IS NOT NULL"""
                    ).fetchone()[0],
                    "migration_registration_count": conn.execute(
                        "SELECT COUNT(*) FROM schema_migrations WHERE name = '20261015_driver_provisional_tasks_phase2b0a.sql'"
                    ).fetchone()[0],
                    "http_records": self.http_records,
                }
            (destination / f"phase2b0a-http-{self._testMethodName}.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def _create_user(self, conn, tenant_id, username, role, scope, display_name):
        cursor = conn.execute(
            """INSERT INTO users
               (tenant_id, username, password_hash, role, account_scope, display_name, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (tenant_id, username, database.hash_password("test123"), role, scope, display_name),
        )
        return int(cursor.lastrowid)

    def _create_driver_shift(self, conn, tenant_id, username, name, plate):
        driver = conn.execute(
            "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (?, ?, 'available', 'available')",
            (tenant_id, name),
        )
        driver_id = int(driver.lastrowid)
        user_id = self._create_user(conn, tenant_id, username, "driver", "driver", name)
        conn.execute("UPDATE users SET profile_type = 'driver', profile_id = ? WHERE id = ?", (driver_id, user_id))
        conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (user_id, driver_id))
        vehicle_id = int(conn.execute(
            "INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (?, ?, 'available')",
            (tenant_id, plate),
        ).lastrowid)
        order_id = int(conn.execute(
            """INSERT INTO orders
               (tenant_id, oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, dispatch_status, execution_status)
               VALUES (?, ?, ?, ?, '08:00', '09:00', 'Shift start', 'Shift end',
                       'airport_transfer', 'assigned', 'assigned')""",
            (tenant_id, f"B0-SHIFT-{tenant_id}-{driver_id}", self.BUSINESS_DATE, self.BUSINESS_DATE),
        ).lastrowid)
        assignment_id = int(conn.execute(
            """INSERT INTO assignments
               (tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
                assigned_at, published_at)
               VALUES (?, ?, ?, ?, 'active', 'assigned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (tenant_id, order_id, driver_id, vehicle_id),
        ).lastrowid)
        return driver_id, user_id, vehicle_id, assignment_id

    def _create_existing_link_order(self, conn):
        order_id = int(conn.execute(
            """INSERT INTO orders
               (tenant_id, oid, order_date, end_date, start_time, end_time,
                pickup_location, dropoff_location, order_type, dispatch_status, execution_status)
               VALUES (1, 'B0-EXISTING-LINK', ?, ?, '13:00', '14:00',
                       'Existing pickup', 'Existing dropoff', 'airport_transfer', 'assigned', 'completed')""",
            (self.BUSINESS_DATE, self.BUSINESS_DATE),
        ).lastrowid)
        assignment_id = int(conn.execute(
            """INSERT INTO assignments
               (tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
                assigned_at, published_at)
               VALUES (1, ?, ?, ?, 'active', 'completed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (order_id, self.driver1, self.vehicle1),
        ).lastrowid)
        return order_id, assignment_id

    def request(self, method, path, payload=None, token=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                if hasattr(self, "http_records"):
                    self.http_records.append({"method": method, "path": path.split("?")[0], "status": response.status, "error": result.get("error") if isinstance(result, dict) else None})
                return response.status, result
        except urllib.error.HTTPError as exc:
            result = json.loads(exc.read().decode("utf-8"))
            if hasattr(self, "http_records"):
                self.http_records.append({"method": method, "path": path.split("?")[0], "status": exc.code, "error": result.get("error") if isinstance(result, dict) else None})
            return exc.code, result

    def login(self, username, password):
        status, payload = self.request("POST", "/api/auth/login", {"username": username, "password": password})
        self.assertEqual(status, 200, payload)
        return payload["token"]

    def create_payload(self, request_id, complete=False):
        payload = {
            "client_request_id": request_id,
            "business_date": self.BUSINESS_DATE,
            "service_kind": "airport_transfer",
            "service_source": "company_admin_phone",
            "vehicle_id": self.vehicle2,
            "actual_pickup_location": "临时接客地点",
            "actual_pickup_at": f"{self.BUSINESS_DATE}T13:20:00+09:00",
        }
        if complete:
            payload.update({
                "authorization_source": "carrier_admin_phone",
                "authorization_evidence": "Call log reference B0-A",
                "actual_dropoff_location": "临时送达地点",
                "actual_dropoff_at": f"{self.BUSINESS_DATE}T14:20:00+09:00",
                "pickup_odometer_km": 120.1,
                "dropoff_odometer_km": 128.4,
            })
        return payload

    def create_task(self, request_id, complete=True):
        status, payload = self.request(
            "POST", "/api/driver/provisional-tasks", self.create_payload(request_id, complete), self.tokens["driver1"]
        )
        self.assertEqual(status, 201, payload)
        return payload["task"]

    def submit_task(self, task, request_id):
        status, payload = self.request(
            "POST", f"/api/driver/provisional-tasks/{task['provisional_task_id']}/submit",
            {"client_request_id": request_id, "expected_revision": task["revision"]}, self.tokens["driver1"],
        )
        self.assertEqual(status, 200, payload)
        return payload["task"]

    def test_driver_partial_save_idempotency_isolation_and_carrier_admin_approval(self):
        mixed_timezone = self.create_payload("mixed-timezone", True)
        mixed_timezone["actual_dropoff_at"] = f"{self.BUSINESS_DATE}T14:20:00"
        status, invalid = self.request(
            "POST", "/api/driver/provisional-tasks", mixed_timezone, self.tokens["driver1"]
        )
        self.assertEqual((status, invalid["error"]), (400, "actual_time_timezone_mismatch"))

        status, created = self.request(
            "POST", "/api/driver/provisional-tasks", self.create_payload("create-partial", False), self.tokens["driver1"]
        )
        self.assertEqual(status, 201, created)
        task = created["task"]
        self.assertEqual(task["vehicle_id"], self.vehicle1)
        self.assertEqual(task["original_snapshot"]["requested_vehicle_id"], self.vehicle2)
        self.assertEqual(task["status"], "draft")

        status, replay = self.request(
            "POST", "/api/driver/provisional-tasks", self.create_payload("create-partial", False), self.tokens["driver1"]
        )
        self.assertEqual(status, 201, replay)
        self.assertTrue(replay["idempotent_replay"])
        conflict_payload = self.create_payload("create-partial", False)
        conflict_payload["actual_pickup_location"] = "different"
        status, conflict = self.request("POST", "/api/driver/provisional-tasks", conflict_payload, self.tokens["driver1"])
        self.assertEqual((status, conflict["error"]), (409, "client_request_id_payload_conflict"))

        update = {
            "client_request_id": "complete-draft",
            "expected_revision": 1,
            "authorization_source": "carrier_admin_phone",
            "authorization_evidence": "immutable source evidence reference",
            "actual_dropoff_location": "临时送达地点",
            "actual_dropoff_at": f"{self.BUSINESS_DATE}T14:20:00+09:00",
            "pickup_odometer_km": 120.1,
            "dropoff_odometer_km": 128.4,
            "reason": "complete actual facts",
        }
        status, updated = self.request(
            "POST", f"/api/driver/provisional-tasks/{task['provisional_task_id']}/update",
            update, self.tokens["driver1"],
        )
        self.assertEqual(status, 200, updated)
        task = updated["task"]
        self.assertEqual(task["revision"], 2)
        self.assertEqual((task["pickup_odometer_km"], task["dropoff_odometer_km"]), (120.1, 128.4))
        self.assertIsNone(task["original_snapshot"].get("actual_dropoff_location"))

        stale = dict(update, client_request_id="stale-update", actual_dropoff_location="stale")
        status, payload = self.request(
            "POST", f"/api/driver/provisional-tasks/{task['provisional_task_id']}/update",
            stale, self.tokens["driver1"],
        )
        self.assertEqual((status, payload["error"]), (409, "provisional_revision_conflict"))

        quoted = urllib.parse.quote(task["provisional_task_id"])
        status, own = self.request("GET", f"/api/driver/provisional-tasks/{quoted}", token=self.tokens["driver1"])
        self.assertEqual(status, 200, own)
        self.assertEqual(len(own["task"]["events"]), 2)
        for actor in ("driver2", "tenant2_driver"):
            status, denied = self.request("GET", f"/api/driver/provisional-tasks/{quoted}", token=self.tokens[actor])
            self.assertEqual(status, 403, denied)

        task = self.submit_task(task, "submit-task")
        self.assertEqual(task["status"], "pending_company_confirmation")
        status, pending_edit = self.request(
            "POST", f"/api/driver/provisional-tasks/{task['provisional_task_id']}/update",
            {"client_request_id": "edit-while-pending", "expected_revision": task["revision"], "note": "must wait for company"},
            self.tokens["driver1"],
        )
        self.assertEqual((status, pending_edit["error"]), (409, "provisional_task_already_pending"))
        for actor in ("operations", "dispatcher", "platform"):
            status, denied = self.request("GET", "/api/company/provisional-tasks", token=self.tokens[actor])
            self.assertEqual((status, denied["error"]), (403, "carrier_admin_required"))
        status, denied = self.request("GET", f"/api/company/provisional-tasks/{quoted}", token=self.tokens["tenant2_admin"])
        self.assertEqual((status, denied["error"]), (403, "provisional_task_cross_tenant_forbidden"))

        with closing(database.get_connection()) as conn:
            before = {
                "notifications": conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
                "documents": conn.execute("SELECT COUNT(*) FROM driver_run_documents").fetchone()[0],
                "expenses": conn.execute("SELECT COUNT(*) FROM driver_expense_reports").fetchone()[0],
            }
        status, pricing_denied = self.request(
            "POST", f"/api/company/provisional-tasks/{quoted}/approve-create",
            {
                "client_request_id": "premature-price", "expected_revision": task["revision"],
                "reason": "must not price in B0-A", "price_jpy": 19500,
            },
            self.tokens["admin1"],
        )
        self.assertEqual((status, pricing_denied["error"]), (400, "provisional_pricing_not_available_in_phase2b0a"))
        review = {"client_request_id": "approve-new", "expected_revision": task["revision"], "reason": "verified by company admin"}
        status, approved = self.request(
            "POST", f"/api/company/provisional-tasks/{quoted}/approve-create", review, self.tokens["admin1"]
        )
        self.assertEqual(status, 200, approved)
        self.assertEqual(approved["task"]["status"], "approved_new_order")
        self.assertEqual(approved["side_effects"], {"pdf": False, "notifications": False, "finance": False})
        status, replay = self.request(
            "POST", f"/api/company/provisional-tasks/{quoted}/approve-create", review, self.tokens["admin1"]
        )
        self.assertEqual(status, 200, replay)
        self.assertTrue(replay["idempotent_replay"])

        with closing(database.get_connection()) as conn:
            formal = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (approved["formal_order"]["order_id"],)).fetchone())
            assignment = dict(conn.execute("SELECT * FROM assignments WHERE id = ?", (approved["formal_order"]["assignment_id"],)).fetchone())
            after = {
                "notifications": conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
                "documents": conn.execute("SELECT COUNT(*) FROM driver_run_documents").fetchone()[0],
                "expenses": conn.execute("SELECT COUNT(*) FROM driver_expense_reports").fetchone()[0],
            }
            event_count = conn.execute(
                "SELECT COUNT(*) FROM driver_provisional_task_events WHERE provisional_task_id = ?",
                (task["provisional_task_id"],),
            ).fetchone()[0]
        self.assertEqual(formal["origin_kind"], "driver_provisional")
        self.assertEqual(formal["origin_provisional_task_id"], task["provisional_task_id"])
        self.assertEqual(formal["order_type"], "airport_transfer")
        self.assertEqual(formal["order_date"], self.BUSINESS_DATE)
        self.assertIsNone(formal["price"])
        self.assertIsNone(formal["price_jpy"])
        self.assertIsNone(assignment["published_at"])
        self.assertEqual(before, after)
        self.assertEqual(event_count, 4)

        status, denied = self.request(
            "POST", "/api/orders", {"order_date": self.BUSINESS_DATE, "pickup_location": "x", "dropoff_location": "y"},
            self.tokens["driver1"],
        )
        self.assertEqual(status, 403, denied)

    def test_two_admin_concurrency_creates_exactly_one_formal_order(self):
        task = self.submit_task(self.create_task("concurrent-create"), "concurrent-submit")
        path = f"/api/company/provisional-tasks/{task['provisional_task_id']}/approve-create"

        def approve(actor, request_id):
            return self.request(
                "POST", path,
                {"client_request_id": request_id, "expected_revision": task["revision"], "reason": "concurrent check"},
                self.tokens[actor],
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda args: approve(*args), [("admin1", "concurrent-a"), ("admin2", "concurrent-b")]))
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertIn("provisional_revision_conflict", [body.get("error") for _, body in results])
        with closing(database.get_connection()) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE origin_kind = 'driver_provisional' AND origin_provisional_task_id = ?",
                (task["provisional_task_id"],),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_link_existing_reject_history_and_atomic_fault_rollback(self):
        link_task = self.submit_task(self.create_task("link-create"), "link-submit")
        status, linked = self.request(
            "POST", f"/api/company/provisional-tasks/{link_task['provisional_task_id']}/approve-link",
            {
                "client_request_id": "link-approve", "expected_revision": link_task["revision"],
                "linked_order_id": self.existing_order, "linked_assignment_id": self.existing_assignment,
                "reason": "matched existing formal order",
            },
            self.tokens["admin1"],
        )
        self.assertEqual(status, 200, linked)
        self.assertEqual(linked["task"]["status"], "approved_linked_order")
        with closing(database.get_connection()) as conn:
            existing = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (self.existing_order,)).fetchone())
        self.assertIsNone(existing["origin_kind"])
        self.assertIsNone(existing["origin_provisional_task_id"])

        reject_task = self.submit_task(self.create_task("reject-create"), "reject-submit")
        status, rejected = self.request(
            "POST", f"/api/company/provisional-tasks/{reject_task['provisional_task_id']}/reject",
            {"client_request_id": "reject-review", "expected_revision": reject_task["revision"], "reason": "not authorized by company"},
            self.tokens["admin1"],
        )
        self.assertEqual(status, 200, rejected)
        self.assertEqual(rejected["task"]["status"], "rejected")
        self.assertIsNone(rejected["formal_order"])

        rollback_task = self.submit_task(self.create_task("rollback-create"), "rollback-submit")
        with closing(database.get_connection()) as conn:
            admin = dict(conn.execute("SELECT * FROM users WHERE id = ?", (self.admin1,)).fetchone())
        with mock.patch.object(driver_provisional_service, "_insert_event", side_effect=RuntimeError("fault after order insert")):
            with self.assertRaises(RuntimeError):
                driver_provisional_service.review_company_provisional_task(
                    admin, rollback_task["provisional_task_id"], "approve-create",
                    {"client_request_id": "rollback-review", "expected_revision": rollback_task["revision"], "reason": "fault test"},
                )
        with closing(database.get_connection()) as conn:
            task_row = dict(conn.execute(
                "SELECT * FROM driver_provisional_tasks WHERE provisional_task_id = ?",
                (rollback_task["provisional_task_id"],),
            ).fetchone())
            order_count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE origin_provisional_task_id = ?",
                (rollback_task["provisional_task_id"],),
            ).fetchone()[0]
            with self.assertRaises(Exception):
                conn.execute("DELETE FROM driver_provisional_tasks WHERE provisional_task_id = ?", (reject_task["provisional_task_id"],))
            with self.assertRaises(Exception):
                conn.execute(
                    "UPDATE driver_provisional_task_events SET reason = 'tampered' WHERE provisional_task_id = ?",
                    (reject_task["provisional_task_id"],),
                )
        self.assertEqual(task_row["status"], "pending_company_confirmation")
        self.assertEqual(order_count, 0)

    def test_needs_information_resubmit_pricing_history_and_unique_finance(self):
        task = self.submit_task(self.create_task("needs-create"), "needs-submit")
        path = f"/api/company/provisional-tasks/{task['provisional_task_id']}"

        for actor in ("operations", "dispatcher", "platform", "tenant2_admin"):
            status, denied = self.request(
                "POST", f"{path}/needs-info",
                {"client_request_id": f"needs-denied-{actor}", "expected_revision": task["revision"], "reason": "more evidence"},
                self.tokens[actor],
            )
            self.assertEqual(status, 403, (actor, denied))

        status, needs = self.request(
            "POST", f"{path}/needs-info",
            {"client_request_id": "needs-info", "expected_revision": task["revision"], "reason": "attach call reference"},
            self.tokens["admin1"],
        )
        self.assertEqual(status, 200, needs)
        self.assertEqual(needs["task"]["status"], "needs_information")

        status, updated = self.request(
            "POST", f"/api/driver/provisional-tasks/{task['provisional_task_id']}/update",
            {
                "client_request_id": "driver-supplement",
                "expected_revision": needs["task"]["revision"],
                "authorization_evidence": "supplemented call reference",
                "reason": "company requested evidence",
            },
            self.tokens["driver1"],
        )
        self.assertEqual(status, 200, updated)
        task = self.submit_task(updated["task"], "driver-resubmit")
        status, approved = self.request(
            "POST", f"{path}/approve-create",
            {"client_request_id": "approve-after-info", "expected_revision": task["revision"], "reason": "verified"},
            self.tokens["admin1"],
        )
        self.assertEqual(status, 200, approved)
        task = approved["task"]
        order_id = approved["formal_order"]["order_id"]

        status, detail = self.request("GET", path, token=self.tokens["admin1"])
        self.assertEqual(status, 200, detail)
        self.assertIsNone(detail["formal_order"]["price_jpy"])
        self.assertEqual([event["event_type"] for event in detail["task"]["events"]][-3:], [
            "driver_updated", "driver_submitted", "carrier_admin_approve_create"
        ])

        status, invalid_null_settlement = self.request(
            "POST", f"{path}/pricing",
            {
                "client_request_id": "pricing-null-settlement",
                "expected_revision": task["revision"],
                "driver_settlement_amount": None,
            },
            self.tokens["admin1"],
        )
        self.assertEqual((status, invalid_null_settlement["error"]), (400, "driver_settlement_amount_omit_when_unknown"))

        pricing = {
            "client_request_id": "pricing-once",
            "expected_revision": task["revision"],
            "price_jpy": 19500,
            "driver_salary_jpy": 7500,
            "driver_settlement_amount": 7500,
            "driver_settlement_status": "pending",
            "reason": "carrier admin confirmed price",
        }
        for actor in ("operations", "dispatcher", "platform", "tenant2_admin"):
            status, denied = self.request("POST", f"{path}/pricing", pricing, self.tokens[actor])
            self.assertEqual(status, 403, (actor, denied))

        status, priced = self.request("POST", f"{path}/pricing", pricing, self.tokens["admin1"])
        self.assertEqual(status, 200, priced)
        self.assertEqual(priced["formal_order"]["price_jpy"], 19500)
        self.assertEqual(priced["formal_order"]["driver_salary_jpy"], 7500)
        self.assertFalse(priced["settlement_adjustment_required"])

        status, replay = self.request("POST", f"{path}/pricing", pricing, self.tokens["admin1"])
        self.assertEqual(status, 200, replay)
        self.assertTrue(replay["idempotent_replay"])
        changed = dict(pricing, price_jpy=20000)
        status, conflict = self.request("POST", f"{path}/pricing", changed, self.tokens["admin1"])
        self.assertEqual((status, conflict["error"]), (409, "client_request_id_payload_conflict"))

        mark_settled = {
            "client_request_id": "pricing-settled",
            "expected_revision": priced["task"]["revision"],
            "driver_settlement_status": "settled",
            "reason": "settlement confirmed",
        }
        status, settled = self.request("POST", f"{path}/pricing", mark_settled, self.tokens["admin1"])
        self.assertEqual(status, 200, settled)
        self.assertFalse(settled["settlement_adjustment_required"])
        status, adjusted = self.request(
            "POST", f"{path}/pricing",
            {
                "client_request_id": "pricing-after-settlement",
                "expected_revision": settled["task"]["revision"],
                "driver_settlement_amount": 8000,
                "reason": "audited post-settlement correction",
            },
            self.tokens["admin1"],
        )
        self.assertEqual(status, 200, adjusted)
        self.assertTrue(adjusted["settlement_adjustment_required"])
        self.assertEqual(adjusted["settled_delta_jpy"], 500)

        status, summary = self.request("GET", "/api/company/provisional-finance-summary", token=self.tokens["admin1"])
        self.assertEqual(status, 200, summary)
        self.assertGreaterEqual(summary["company"]["formal_order_count"], 1)
        self.assertEqual(summary["company"]["known_business_amount_jpy"], 19500)
        with closing(database.get_connection()) as conn:
            sourced_count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE origin_provisional_task_id = ?", (task["provisional_task_id"],)
            ).fetchone()[0]
            pricing_event_count = conn.execute(
                "SELECT COUNT(*) FROM driver_provisional_task_events WHERE provisional_task_id = ? AND event_type = 'carrier_admin_pricing_updated'",
                (task["provisional_task_id"],),
            ).fetchone()[0]
            stored = dict(conn.execute("SELECT price, price_jpy, driver_salary_jpy FROM orders WHERE id = ?", (order_id,)).fetchone())
        self.assertEqual(sourced_count, 1)
        self.assertEqual(pricing_event_count, 3)
        self.assertEqual((stored["price"], stored["price_jpy"], stored["driver_salary_jpy"]), (19500, 19500, 7500))


if __name__ == "__main__":
    unittest.main()

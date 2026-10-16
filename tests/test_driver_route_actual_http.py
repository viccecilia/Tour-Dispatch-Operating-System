import json
import hashlib
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
from backend.services import driver_route_actual_service
from backend.services.document_model_service import make_run_group_id, stable_id
from backend.services.tenant_context import set_current_tenant_id


class DriverRouteActualHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "phase2a.sqlite3"
        database.init_db(seed=True)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            self.driver1, self.driver1_user = self._create_driver(conn, 1, "phase2a_driver_1", "Driver One")
            self.driver2, self.driver2_user = self._create_driver(conn, 1, "phase2a_driver_2", "Driver Two")
            self.tenant2_driver1, self.tenant2_user1 = self._create_driver(conn, 2, "phase2a_t2_driver_1", "Tenant2 One")
            self.tenant2_driver2, self.tenant2_user2 = self._create_driver(conn, 2, "phase2a_t2_driver_2", "Tenant2 Two")
            self.plan6 = self._create_plan(conn, 1, self.driver1, "2026-10-20", 6, "6001")
            self.plan10 = self._create_plan(conn, 1, self.driver1, "2026-10-21", 10, "6010")
            self.plan11 = self._create_plan(conn, 1, self.driver1, "2026-10-22", 11, "6011")
            self.charter = self._create_charter_plan(conn, 1, self.driver1, "2026-10-23", "6023")
            self.other_plan = self._create_plan(conn, 1, self.driver2, "2026-10-20", 1, "7001")
            self.tenant2_plan = self._create_plan(conn, 2, self.tenant2_driver1, "2026-10-20", 1, "8001")
            conn.commit()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.token1 = self.login("phase2a_driver_1", "driver123")
        self.token2 = self.login("phase2a_driver_2", "driver123")
        self.tenant2_token = self.login("phase2a_t2_driver_1", "driver123")
        self.admin_token = self.login("admin", "admin123")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        artifact_root = os.environ.get("DAITORA_PHASE2A_ARTIFACT_DIR")
        if artifact_root and self._testMethodName == "test_partial_save_reload_idempotency_and_revision_conflicts":
            destination = Path(artifact_root)
            destination.mkdir(parents=True, exist_ok=True)
            database_copy = destination / "phase2a-http-acceptance.sqlite3"
            shutil.copy2(database.DB_PATH, database_copy)
            with closing(database.get_connection()) as conn:
                evidence = {
                    "database": str(database_copy.resolve()),
                    "sha256": hashlib.sha256(database_copy.read_bytes()).hexdigest(),
                    "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
                    "tenants": conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0],
                    "drivers": conn.execute("SELECT COUNT(*) FROM drivers WHERE name LIKE 'Driver %' OR name LIKE 'Tenant2 %'").fetchone()[0],
                    "published_documents": conn.execute("SELECT COUNT(*) FROM driver_run_documents WHERE status = 'published'").fetchone()[0],
                    "route_nodes": conn.execute("SELECT COUNT(*) FROM dispatch_route_nodes").fetchone()[0],
                    "actual_rows": conn.execute("SELECT COUNT(*) FROM dispatch_route_node_actuals").fetchone()[0],
                    "idempotency_audit_rows": conn.execute("SELECT COUNT(*) FROM driver_route_node_actual_requests").fetchone()[0],
                    "migration_registration_count": conn.execute(
                        "SELECT COUNT(*) FROM schema_migrations WHERE name = '20261015_driver_route_node_actuals_phase2a.sql'"
                    ).fetchone()[0],
                }
            (destination / "phase2a-http-acceptance.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def _create_driver(self, conn, tenant_id, username, name):
        conn.execute(
            "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (?, ?, 'available', 'available')",
            (tenant_id, name),
        )
        driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """INSERT INTO users
               (tenant_id, username, password_hash, role, display_name, profile_type, profile_id, account_scope)
               VALUES (?, ?, ?, 'driver', ?, 'driver', ?, 'driver')""",
            (tenant_id, username, database.hash_password("driver123"), name, driver_id),
        )
        user_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (user_id, driver_id))
        return driver_id, user_id

    def _create_plan(self, conn, tenant_id, driver_id, business_date, count, plate_suffix):
        conn.execute(
            "INSERT INTO vehicles (tenant_id, plate_number, status) VALUES (?, ?, 'available')",
            (tenant_id, f"大阪500あ{plate_suffix}"),
        )
        vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        run_group_id = make_run_group_id(tenant_id, business_date, driver_id, vehicle_id)
        version_id = f"docv-{tenant_id}-{driver_id}-{business_date}-{count}"
        source_sha = stable_id("source", run_group_id, count)
        conn.execute(
            """INSERT INTO driver_run_documents
               (tenant_id, business_date, driver_id, vehicle_id, version, status, source_hash,
                file_name, file_path, file_url, page_count, published_at, document_id,
                document_version_id, run_group_id, lifecycle_status, snapshot_json, source_sha256)
               VALUES (?, ?, ?, ?, 1, 'published', ?, ?, ?, ?, 2, CURRENT_TIMESTAMP,
                       ?, ?, ?, 'published', '{}', ?)""",
            (
                tenant_id, business_date, driver_id, vehicle_id, source_sha,
                f"{version_id}.pdf", f"C:/isolated/{version_id}.pdf", f"/isolated/{version_id}.pdf",
                stable_id("doc", run_group_id), version_id, run_group_id, source_sha,
            ),
        )
        sequence = 1
        self._insert_node(conn, tenant_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, None, "garage_out", "大阪車庫", None, f"{business_date}T07:00:00")
        sequence += 1
        orders = []
        for index in range(1, count + 1):
            conn.execute(
                """INSERT INTO orders
                   (tenant_id, oid, order_date, end_date, start_time, end_time,
                    pickup_location, dropoff_location, order_type, dispatch_status, execution_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'airport', 'assigned', 'assigned')""",
                (
                    tenant_id, f"P2A-{tenant_id}-{driver_id}-{business_date}-{index}", business_date, business_date,
                    f"{7 + index:02d}:00", f"{8 + index:02d}:00", f"Pickup {index}", f"Dropoff {index}",
                ),
            )
            order_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """INSERT INTO assignments
                   (tenant_id, order_id, driver_id, vehicle_id, status, execution_status, assigned_at, published_at)
                   VALUES (?, ?, ?, ?, 'active', 'assigned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (tenant_id, order_id, driver_id, vehicle_id),
            )
            assignment_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            pickup_id = stable_id("node", run_group_id, order_id, "pickup", 0)
            dropoff_id = stable_id("node", run_group_id, order_id, "dropoff", 0)
            self._insert_node(conn, tenant_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, order_id, "pickup", f"Pickup {index}", f"{business_date}T{7 + index:02d}:00:00", f"{business_date}T{7 + index:02d}:00:00", pickup_id)
            sequence += 1
            self._insert_node(conn, tenant_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, order_id, "dropoff", f"Dropoff {index}", f"{business_date}T{8 + index:02d}:00:00", f"{business_date}T{8 + index:02d}:00:00", dropoff_id)
            sequence += 1
            orders.append({"order_id": order_id, "assignment_id": assignment_id, "pickup_id": pickup_id, "dropoff_id": dropoff_id})
        self._insert_node(conn, tenant_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, None, "garage_in", "大阪車庫", f"{business_date}T23:00:00", None)
        return {
            "tenant_id": tenant_id, "driver_id": driver_id, "vehicle_id": vehicle_id,
            "business_date": business_date, "run_group_id": run_group_id,
            "version_id": version_id, "source_sha": source_sha, "orders": orders,
        }

    def _create_charter_plan(self, conn, tenant_id, driver_id, business_date, plate_suffix):
        plan = self._create_plan(conn, tenant_id, driver_id, business_date, 1, plate_suffix)
        order = plan["orders"][0]
        conn.execute(
            "UPDATE orders SET end_date = '2026-10-24', order_type = 'charter' WHERE id = ?",
            (order["order_id"],),
        )
        sequence = 3
        for day, location in (("2026-10-23", "京都一日目"), ("2026-10-24", "京都二日目")):
            node_id = stable_id("node", plan["run_group_id"], order["order_id"], "charter", day)
            self._insert_node(
                conn, tenant_id, plan["run_group_id"], plan["version_id"], driver_id,
                plan["vehicle_id"], day, sequence, order["order_id"], "via", location,
                f"{day}T12:00:00", f"{day}T13:00:00", node_id,
            )
            sequence += 1
        return plan

    def _insert_node(self, conn, tenant_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, order_id, node_type, location, arrival, departure, node_id=None):
        route_node_id = node_id or stable_id("node", run_group_id, order_id or 0, node_type, sequence)
        conn.execute(
            """INSERT INTO dispatch_route_nodes
               (tenant_id, route_node_id, run_group_id, document_version_id, driver_id,
                vehicle_id, business_date, sequence_number, order_id, node_type,
                planned_location, planned_arrival_at, planned_departure_at, load_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned')""",
            (tenant_id, route_node_id, run_group_id, version_id, driver_id, vehicle_id, business_date, sequence, order_id, node_type, location, arrival, departure),
        )
        return route_node_id

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

    def workbench(self, plan, token=None, extra_query=None):
        query = {"date": plan["business_date"]}
        if extra_query:
            query.update(extra_query)
        return self.request("GET", "/api/driver/day-workbench?" + urllib.parse.urlencode(query), token=token or self.token1)

    def save_payload(self, plan, order_index=0, node_kind="pickup", request_id="req-1", revision=0, **changes):
        order = plan["orders"][order_index]
        payload = {
            "client_request_id": request_id,
            "run_group_id": plan["run_group_id"],
            "route_node_id": order[f"{node_kind}_id"],
            "source_document_version_id": plan["version_id"],
            "source_sha256": plan["source_sha"],
            "assignment_id": order["assignment_id"],
            "order_id": order["order_id"],
            "expected_revision": revision,
        }
        payload.update(changes)
        return payload

    def test_real_http_workbench_counts_and_role_tenant_driver_isolation(self):
        for plan, expected in ((self.plan6, 14), (self.plan10, 22), (self.plan11, 24)):
            status, payload = self.workbench(plan)
            self.assertEqual(status, 200, payload)
            self.assertEqual(len(payload["nodes"]), expected)
            self.assertTrue(all(node["driver_id"] == self.driver1 for node in payload["nodes"]))

        status, payload = self.workbench(self.plan6, extra_query={"driver_id": self.driver2})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["driver_id"], self.driver1)
        self.assertNotIn(self.other_plan["run_group_id"], [item["run_group_id"] for item in payload["documents"]])

        status, payload = self.workbench(self.plan6, token=self.token2)
        self.assertEqual(status, 200, payload)
        self.assertNotIn(self.plan6["run_group_id"], [item["run_group_id"] for item in payload["documents"]])

        status, payload = self.workbench(self.plan6, token=self.tenant2_token)
        self.assertEqual(status, 200, payload)
        self.assertEqual([item["run_group_id"] for item in payload["documents"]], [self.tenant2_plan["run_group_id"]])

        status, payload = self.workbench(self.plan6, token=self.admin_token)
        self.assertEqual(status, 403, payload)
        self.assertEqual(payload["error"], "forbidden")

    def test_partial_save_reload_idempotency_and_revision_conflicts(self):
        order = self.plan6["orders"][0]
        with closing(database.get_connection()) as conn:
            untouched_before = {
                "order": dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order["order_id"],)).fetchone()),
                "assignment": dict(conn.execute("SELECT * FROM assignments WHERE id = ?", (order["assignment_id"],)).fetchone()),
                "document": dict(conn.execute("SELECT * FROM driver_run_documents WHERE document_version_id = ?", (self.plan6["version_id"],)).fetchone()),
                "notifications": conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
            }
        first = self.save_payload(self.plan6, request_id="partial-1", actual_location="手动地点")
        status, saved = self.request("POST", "/api/driver/route-node-actual", first, self.token1)
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["actual"]["revision"], 1)
        self.assertEqual(saved["actual"]["actual_location"], "手动地点")
        self.assertIsNone(saved["actual"]["actual_arrival_at"])

        second = self.save_payload(
            self.plan6, request_id="partial-2", revision=1,
            actual_arrival_at="2026-10-20T08:05:00", odometer_km=100.5,
            client_recorded_at="2026-10-20T08:06:00",
        )
        status, saved2 = self.request("POST", "/api/driver/route-node-actual", second, self.token1)
        self.assertEqual(status, 200, saved2)
        self.assertEqual(saved2["actual"]["revision"], 2)
        self.assertEqual(saved2["actual"]["actual_location"], "手动地点")

        status, replay = self.request("POST", "/api/driver/route-node-actual", second, self.token1)
        self.assertEqual(status, 200, replay)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["actual"]["revision"], 2)

        changed = dict(second, odometer_km=101)
        status, conflict = self.request("POST", "/api/driver/route-node-actual", changed, self.token1)
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict["error"], "client_request_id_payload_conflict")

        stale = self.save_payload(self.plan6, request_id="stale-1", revision=1, actual_location="覆盖")
        status, conflict = self.request("POST", "/api/driver/route-node-actual", stale, self.token1)
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict["current_actual"]["revision"], 2)

        status, loaded = self.workbench(self.plan6)
        self.assertEqual(status, 200, loaded)
        node = next(item for item in loaded["nodes"] if item["route_node_id"] == first["route_node_id"])
        self.assertEqual(node["actual"]["actual_location"], "手动地点")
        self.assertEqual(node["actual"]["odometer_km"], 100.5)
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM driver_route_node_actual_requests").fetchone()[0], 2)
            untouched_after = {
                "order": dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order["order_id"],)).fetchone()),
                "assignment": dict(conn.execute("SELECT * FROM assignments WHERE id = ?", (order["assignment_id"],)).fetchone()),
                "document": dict(conn.execute("SELECT * FROM driver_run_documents WHERE document_version_id = ?", (self.plan6["version_id"],)).fetchone()),
                "notifications": conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
            }
        self.assertEqual(untouched_before, untouched_after)

    def test_validation_cross_midnight_odometer_and_assignment_binding(self):
        cross_midnight = self.save_payload(
            self.plan6, request_id="midnight-1",
            actual_arrival_at="2026-10-20T23:55:00",
            actual_departure_at="2026-10-21T00:15:00",
            odometer_km=500,
        )
        status, payload = self.request("POST", "/api/driver/route-node-actual", cross_midnight, self.token1)
        self.assertEqual(status, 200, payload)

        invalid_time = self.save_payload(
            self.plan6, order_index=1, request_id="bad-time", actual_arrival_at="not-a-date",
        )
        status, payload = self.request("POST", "/api/driver/route-node-actual", invalid_time, self.token1)
        self.assertEqual(status, 400, payload)
        self.assertEqual(payload["error"], "invalid_actual_arrival_at")

        negative = self.save_payload(self.plan6, order_index=1, request_id="negative", odometer_km=-1)
        status, payload = self.request("POST", "/api/driver/route-node-actual", negative, self.token1)
        self.assertEqual(status, 400, payload)
        self.assertEqual(payload["error"], "odometer_km_negative")

        non_finite = self.save_payload(self.plan6, order_index=1, request_id="non-finite", odometer_km=float("nan"))
        status, payload = self.request("POST", "/api/driver/route-node-actual", non_finite, self.token1)
        self.assertEqual(status, 400, payload)
        self.assertEqual(payload["error"], "invalid_odometer_km")

        regression = self.save_payload(self.plan6, order_index=1, request_id="regression", odometer_km=499)
        status, payload = self.request("POST", "/api/driver/route-node-actual", regression, self.token1)
        self.assertEqual(status, 400, payload)
        self.assertEqual(payload["error"], "odometer_km_regression")

        forged = self.save_payload(self.plan6, request_id="forged", actual_location="越权")
        forged["assignment_id"] = self.other_plan["orders"][0]["assignment_id"]
        status, payload = self.request("POST", "/api/driver/route-node-actual", forged, self.token1)
        self.assertEqual(status, 403, payload)
        self.assertEqual(payload["error"], "assignment_id_mismatch")

        status, payload = self.request("POST", "/api/driver/route-node-actual", forged, self.token2)
        self.assertEqual(status, 404, payload)
        status, payload = self.request("POST", "/api/driver/route-node-actual", forged, self.tenant2_token)
        self.assertEqual(status, 404, payload)
        status, payload = self.request("POST", "/api/driver/route-node-actual", forged, self.admin_token)
        self.assertEqual(status, 403, payload)

    def test_stable_node_survives_new_version_new_node_is_empty_and_old_history_remains(self):
        first = self.save_payload(self.plan6, request_id="stable-1", actual_location="版本一实绩")
        status, saved = self.request("POST", "/api/driver/route-node-actual", first, self.token1)
        self.assertEqual(status, 200, saved)

        new_version = "docv-stable-v2"
        new_sha = stable_id("source", self.plan6["run_group_id"], "v2")
        with closing(database.get_connection()) as conn:
            conn.execute(
                """INSERT INTO driver_run_documents
                   (tenant_id, business_date, driver_id, vehicle_id, version, status, source_hash,
                    file_name, file_path, file_url, page_count, published_at, document_id,
                    document_version_id, run_group_id, lifecycle_status, snapshot_json, source_sha256)
                   SELECT tenant_id, business_date, driver_id, vehicle_id, 2, 'published', ?,
                          ?, ?, ?, page_count, CURRENT_TIMESTAMP, document_id,
                          ?, run_group_id, 'published', snapshot_json, ?
                   FROM driver_run_documents WHERE document_version_id = ?""",
                (new_sha, f"{new_version}.pdf", f"C:/isolated/{new_version}.pdf", f"/isolated/{new_version}.pdf", new_version, new_sha, self.plan6["version_id"]),
            )
            old_nodes = conn.execute(
                "SELECT * FROM dispatch_route_nodes WHERE document_version_id = ? ORDER BY sequence_number",
                (self.plan6["version_id"],),
            ).fetchall()
            for raw in old_nodes:
                node = dict(raw)
                conn.execute(
                    """INSERT INTO dispatch_route_nodes
                       (tenant_id, route_node_id, run_group_id, document_version_id, driver_id,
                        vehicle_id, business_date, sequence_number, order_id, node_type,
                        planned_location, planned_arrival_at, planned_departure_at, load_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        node["tenant_id"], node["route_node_id"], node["run_group_id"], new_version,
                        node["driver_id"], node["vehicle_id"], node["business_date"], node["sequence_number"],
                        node["order_id"], node["node_type"], node["planned_location"],
                        node["planned_arrival_at"], node["planned_departure_at"], node["load_status"],
                    ),
                )
            new_node_id = stable_id("node", self.plan6["run_group_id"], "new-v2")
            self._insert_node(
                conn, 1, self.plan6["run_group_id"], new_version, self.driver1, self.plan6["vehicle_id"],
                self.plan6["business_date"], 99, self.plan6["orders"][0]["order_id"], "via",
                "版本二新增节点", "2026-10-20T08:30:00", "2026-10-20T08:40:00", new_node_id,
            )
            conn.commit()
        self.plan6["version_id"] = new_version
        self.plan6["source_sha"] = new_sha

        status, workbench = self.workbench(self.plan6)
        self.assertEqual(status, 200, workbench)
        stable = next(item for item in workbench["nodes"] if item["route_node_id"] == first["route_node_id"])
        new_node = next(item for item in workbench["nodes"] if item["route_node_id"] == new_node_id)
        self.assertEqual(stable["actual"]["actual_location"], "版本一实绩")
        self.assertEqual(stable["actual"]["revision"], 1)
        self.assertIsNone(new_node["actual"]["actual_location"])
        self.assertEqual(new_node["actual"]["revision"], 0)
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM dispatch_route_node_actuals WHERE route_node_id = ?",
                (first["route_node_id"],),
            ).fetchone()[0], 1)

    def test_fault_injection_rolls_back_actual_and_ledger_atomically(self):
        payload = self.save_payload(self.plan6, request_id="fault-1", actual_location="不应落库")
        with mock.patch.object(driver_route_actual_service, "_insert_request_ledger", side_effect=RuntimeError("fault injection")):
            status, response = self.request("POST", "/api/driver/route-node-actual", payload, self.token1)
        self.assertEqual(status, 500, response)
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM dispatch_route_node_actuals WHERE route_node_id = ?",
                (payload["route_node_id"],),
            ).fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM driver_route_node_actual_requests WHERE client_request_id = 'fault-1'"
            ).fetchone()[0], 0)

    def test_charter_multiday_nodes_and_cancelled_or_deleted_sources_are_not_writable(self):
        status, payload = self.workbench(self.charter)
        self.assertEqual(status, 200, payload)
        node_dates = {node["business_date"] for node in payload["nodes"]}
        self.assertIn("2026-10-23", node_dates)
        self.assertIn("2026-10-24", node_dates)

        order = self.plan6["orders"][0]
        saved_payload = self.save_payload(self.plan6, request_id="before-cancel", actual_location="取消前实绩")
        status, response = self.request("POST", "/api/driver/route-node-actual", saved_payload, self.token1)
        self.assertEqual(status, 200, response)
        blocked = self.save_payload(self.plan6, request_id="cancelled-1", revision=1, actual_location="不可写")
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE assignments SET status = 'cancelled' WHERE id = ?", (order["assignment_id"],))
            conn.commit()
        status, response = self.request("POST", "/api/driver/route-node-actual", blocked, self.token1)
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"], "route_node_assignment_not_active")
        with closing(database.get_connection()) as conn:
            retained = conn.execute(
                "SELECT actual_location, revision FROM dispatch_route_node_actuals WHERE route_node_id = ?",
                (saved_payload["route_node_id"],),
            ).fetchone()
        self.assertEqual(dict(retained), {"actual_location": "取消前实绩", "revision": 1})

        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE assignments SET status = 'active' WHERE id = ?", (order["assignment_id"],))
            conn.execute("UPDATE orders SET is_deleted = 1 WHERE id = ?", (order["order_id"],))
            conn.commit()
        blocked["client_request_id"] = "deleted-1"
        status, response = self.request("POST", "/api/driver/route-node-actual", blocked, self.token1)
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"], "route_node_assignment_not_active")


if __name__ == "__main__":
    unittest.main()

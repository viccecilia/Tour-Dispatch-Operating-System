import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from pypdf import PdfReader

from backend.api.routes import ApiHandler
from backend.db import database
from backend.services import run_document_service
from backend.services.tenant_context import set_current_tenant_id


class RunDocumentHttpFlowTest(unittest.TestCase):
    BUSINESS_DATE = "2026-10-16"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        self.original_runtime = run_document_service.RUNTIME_DIR
        database.DB_PATH = Path(self.temp.name) / "run-document-http.sqlite3"
        run_document_service.RUNTIME_DIR = Path(self.temp.name) / "runtime"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            vehicle_columns = {row["name"] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
            if "office" not in vehicle_columns:
                conn.execute("ALTER TABLE vehicles ADD COLUMN office TEXT")
            if "permitted_business_area" not in vehicle_columns:
                conn.execute("ALTER TABLE vehicles ADD COLUMN permitted_business_area TEXT")
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, 'DAITORA HTTP FLOW', 'daitora-http-flow')")
            conn.execute(
                """INSERT INTO users
                   (tenant_id, username, password_hash, role, display_name, phone,
                    profile_type, account_scope, is_active)
                   VALUES (1, 'flow-ops', ?, 'operations_manager', '流程运管', '08000000010',
                           'operator', 'carrier', 1)""",
                (database.hash_password("flow123"),),
            )
            conn.execute(
                """INSERT INTO drivers
                   (tenant_id, name, driver_code, office, status, driver_status)
                   VALUES (1, 'HTTP验收司机', 'FLOW01', '大阪営業所', 'available', 'available')"""
            )
            self.driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """INSERT INTO users
                   (tenant_id, username, password_hash, role, display_name, phone,
                    profile_type, profile_id, account_scope, is_active)
                   VALUES (1, 'flow-driver', ?, 'driver', '流程司机', '08000000011',
                           'driver', ?, 'driver', 1)""",
                (database.hash_password("driver123"), self.driver_id),
            )
            driver_user_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute("UPDATE drivers SET user_id = ? WHERE id = ?", (driver_user_id, self.driver_id))
            conn.execute(
                """INSERT INTO vehicles
                   (tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status,
                    office, permitted_business_area)
                   VALUES (1, 'なにわ7007', 'なにわ300あ7007', 'Alphard', 7, 7, 'available',
                           '大阪営業所', '大阪市域交通圏')"""
            )
            self.vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """INSERT INTO company_registrations
                   (managing_tenant_id, company_type, tenant_id, company_code,
                    company_name, registered_name, address, contact_name,
                    contact_phone, contact_email, status)
                   VALUES (1, 'carrier', 1, 'FLOW', '株式会社大寅', '株式会社大寅',
                           '大阪府大阪市大正区', '流程运管', '06-0000-0000',
                           'flow@example.invalid', 'approved')"""
            )
            self.order_ids = []
            for index in range(6):
                start_hour = 8 + index * 2
                cursor = conn.execute(
                    """INSERT INTO orders
                       (tenant_id, oid, order_date, end_date, start_time, end_time,
                        pickup_location, dropoff_location, order_type, price,
                        agency_name, guest_contact, dispatch_status, execution_status,
                        operations_business_area, area_validation_status,
                        run_confirmation_status, fee_remark)
                       VALUES (1, ?, ?, ?, ?, ?, ?, ?, '送机', 18000,
                               'HTTP测试申请者', '06-0000-0000', 'assigned', 'draft',
                               '大阪市域交通圏', 'pending', 'pending',
                               '区域确认：大阪市内 → KIX')""",
                    (
                        f"HTTP-FLOW-{index + 1}", self.BUSINESS_DATE, self.BUSINESS_DATE,
                        f"{start_hour:02d}:00", f"{start_hour + 1:02d}:00",
                        f"大阪ホテル{index + 1}", "関西空港",
                    ),
                )
                order_id = int(cursor.lastrowid)
                self.order_ids.append(order_id)
                conn.execute(
                    """INSERT INTO assignments
                       (tenant_id, order_id, driver_id, vehicle_id, status, execution_status)
                       VALUES (1, ?, ?, ?, 'active', 'draft')""",
                    (order_id, self.driver_id, self.vehicle_id),
                )
            conn.commit()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.ops_token = self.login("flow-ops", "flow123")
        self.driver_token = self.login("flow-driver", "driver123")
        self.final_document = None
        self.flow_evidence = {}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        artifact_dir = os.environ.get("DAITORA_DOCUMENT_FLOW_ARTIFACT_DIR")
        if artifact_dir and self.final_document:
            destination = Path(artifact_dir)
            destination.mkdir(parents=True, exist_ok=True)
            with closing(database.get_connection()) as conn:
                stored_document = dict(conn.execute(
                    "SELECT * FROM driver_run_documents WHERE id = ?", (self.final_document["id"],)
                ).fetchone())
            source = Path(stored_document["file_path"])
            pdf_path = destination / "DAITORA_local_6orders_footer_date_only.pdf"
            shutil.copy2(source, pdf_path)
            shutil.copy2(source, destination / "DAITORA_daily_mode_v2_6orders.pdf")
            db_path = destination / "DAITORA_local_6orders_flow_review.sqlite3"
            shutil.copy2(database.DB_PATH, db_path)
            evidence = {
                "business_date": self.BUSINESS_DATE,
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "order_ids": self.order_ids,
                "document_id": self.final_document["document_id"],
                "document_version_id": self.final_document["document_version_id"],
                "version": self.final_document["version"],
                "renderer_version": run_document_service.DOCUMENT_RENDERER_VERSION,
                "source_sha256": stored_document["source_sha256"],
                "page_count": len(PdfReader(str(pdf_path)).pages),
                "pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                "database_sha256": hashlib.sha256(db_path.read_bytes()).hexdigest(),
                "flow": self.flow_evidence,
            }
            (destination / "DAITORA_local_6orders_flow_review_evidence.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        database.DB_PATH = self.original_db
        run_document_service.RUNTIME_DIR = self.original_runtime
        set_current_tenant_id(None)
        self.temp.cleanup()

    def request(self, method, path, payload=None, token=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def login(self, username, password):
        status, payload = self.request("POST", "/api/auth/login", {"username": username, "password": password})
        self.assertEqual(status, 200, payload)
        return payload["token"]

    def confirm_order(self, order_id, area_override=None):
        with closing(database.get_connection()) as conn:
            row = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        status, payload = self.request(
            "POST", "/api/dispatch-mobile/run-confirm",
            {
                "order_id": order_id,
                "order_date": row["order_date"],
                "start_time": row["start_time"],
                "operations_business_area": area_override or row["operations_business_area"],
                "order_type": row["order_type"],
                "pickup_location": row["pickup_location"],
                "dropoff_location": row["dropoff_location"],
                "price": row["price"],
                "pdf_edit": False,
            },
            self.ops_token,
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["order"]["run_confirmation_status"], "confirmed")
        return payload["order"]

    def test_daily_v2_confirm_publish_is_real_http_and_idempotent(self):
        group_key = run_document_service.group_key(self.BUSINESS_DATE, self.driver_id, self.vehicle_id)
        status, groups = self.request(
            "GET", f"/api/dispatch-mobile/run-groups?date={self.BUSINESS_DATE}", token=self.ops_token
        )
        self.assertEqual(status, 200, groups)
        group = groups["groups"][0]
        self.assertEqual(group["auto_checked_count"], 6)
        self.assertEqual(group["pending_check_count"], 0)
        status, published = self.request(
            "POST",
            "/api/dispatch-mobile/run-documents/confirm-publish",
            {"group_key": group_key},
            self.ops_token,
        )
        self.assertEqual(status, 200, published)
        self.assertEqual(published["document"]["status"], "published")
        self.assertFalse(published["idempotent"])
        self.final_document = published["document"]
        self.flow_evidence = {
            "flow": "daily_mode_v2_confirm_publish",
            "first_request_idempotent": False,
            "server_auto_checked_count": group["auto_checked_count"],
        }
        first_id = published["document"]["id"]
        status, repeated = self.request(
            "POST",
            "/api/dispatch-mobile/run-documents/confirm-publish",
            {"group_key": group_key},
            self.ops_token,
        )
        self.assertEqual(status, 200, repeated)
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(repeated["document"]["id"], first_id)
        self.flow_evidence["repeat_request_idempotent"] = True
        with closing(database.get_connection()) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM driver_run_documents").fetchone()[0],
                1,
            )

    def test_real_http_confirm_generate_review_stale_regenerate_publish(self):
        group_key = run_document_service.group_key(self.BUSINESS_DATE, self.driver_id, self.vehicle_id)
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET operations_business_area = '' WHERE id = ?",
                (self.order_ids[3],),
            )
            conn.commit()
        status, missing_area = self.request(
            "POST", "/api/dispatch-mobile/run-documents/preview", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, missing_area)
        self.assertIn("order_4_area_validation_required", missing_area["preview"]["validation_issues"])
        with closing(database.get_connection()) as conn:
            missing_row = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (self.order_ids[3],)).fetchone())
        status, rejected_confirmation = self.request(
            "POST", "/api/dispatch-mobile/run-confirm",
            {
                "order_id": self.order_ids[3],
                "order_date": missing_row["order_date"],
                "start_time": missing_row["start_time"],
                "operations_business_area": "",
                "order_type": missing_row["order_type"],
                "pickup_location": missing_row["pickup_location"],
                "dropoff_location": missing_row["dropoff_location"],
                "price": missing_row["price"],
                "pdf_edit": False,
            },
            self.ops_token,
        )
        self.assertEqual(status, 400, rejected_confirmation)
        self.assertIn("営業区域", rejected_confirmation["error"])

        for index, order_id in enumerate(self.order_ids):
            self.confirm_order(order_id, "大阪市域交通圏" if index == 3 else None)

        status, confirmed_preview = self.request(
            "POST", "/api/dispatch-mobile/run-documents/preview", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, confirmed_preview)
        self.assertFalse(any(item.endswith("_area_validation_required") for item in confirmed_preview["preview"]["validation_issues"]))

        status, generated = self.request(
            "POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, generated)
        self.assertEqual(generated["document"]["status"], "generated")
        self.assertEqual(generated["document"]["page_count"], 2)

        status, reviewed = self.request(
            "POST", "/api/dispatch-mobile/run-documents/review", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, reviewed)
        self.assertEqual(reviewed["document"]["status"], "reviewed")

        status, preview = self.request(
            "POST", "/api/dispatch-mobile/run-documents/preview", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, preview)
        order3 = self.order_ids[2]
        status, patched = self.request(
            "POST", "/api/dispatch-mobile/run-documents/draft-patch",
            {
                "group_key": group_key,
                "expected_source_hash": preview["preview"]["source_sha256"],
                "client_request_id": "http-flow-order3-location",
                "patches": [{"field_id": f"order:{order3}:applicant_contact", "value": "06-1234-5678"}],
            },
            self.ops_token,
        )
        self.assertEqual(status, 200, patched)
        self.assertTrue(any("order_3_run_confirmation_required" == item for item in patched["preview"]["validation_issues"]))

        status, blocked = self.request(
            "POST", "/api/dispatch-mobile/run-documents/publish", {"group_keys": [group_key]}, self.ops_token
        )
        self.assertEqual(status, 400, blocked)

        self.confirm_order(order3)
        status, regenerated = self.request(
            "POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, regenerated)
        self.assertEqual(regenerated["document"]["version"], generated["document"]["version"] + 1)
        status, rereviewed = self.request(
            "POST", "/api/dispatch-mobile/run-documents/review", {"group_key": group_key}, self.ops_token
        )
        self.assertEqual(status, 200, rereviewed)
        status, published = self.request(
            "POST", "/api/dispatch-mobile/run-documents/publish", {"group_keys": [group_key]}, self.ops_token
        )
        self.assertEqual(status, 200, published)
        self.assertEqual(published["documents"][0]["status"], "published")
        self.final_document = published["documents"][0]
        with closing(database.get_connection()) as conn:
            document_path = Path(conn.execute(
                "SELECT file_path FROM driver_run_documents WHERE id = ?", (self.final_document["id"],)
            ).fetchone()["file_path"])
        document_text = "\n".join(
            page.extract_text() or "" for page in PdfReader(str(document_path)).pages
        )
        self.assertIn(self.BUSINESS_DATE, document_text)
        self.assertIn("運賃：18,000円", document_text)
        self.assertIn("料金：立替", document_text)
        self.assertIn("料金内訳：P代・高速代", document_text)
        self.assertNotIn("流程司机", document_text)
        self.assertNotIn("予定版", document_text)

        status, assignments = self.request("GET", "/api/driver/assignments", token=self.driver_token)
        self.assertEqual(status, 200, assignments)
        self.assertEqual(len(assignments["assignments"]), 6)
        priced_group = run_document_service.list_run_groups(self.BUSINESS_DATE, tenant_id=1)[0]
        with closing(database.get_connection()) as conn:
            price_snapshots = [
                json.loads(row["price_snapshot_json"])
                for row in conn.execute(
                    "SELECT price_snapshot_json FROM orders WHERE id IN ({}) ORDER BY id".format(
                        ",".join("?" for _ in self.order_ids)
                    ),
                    self.order_ids,
                ).fetchall()
            ]
        self.flow_evidence = {
            "missing_area_issue": "order_4_area_validation_required",
            "missing_area_confirmation_http_status": 400,
            "old_area_note_cleared_after_confirmation": True,
            "confirmed_order_count": 6,
            "generated_version_1": generated["document"]["version"],
            "reviewed_version_1": reviewed["document"]["version"],
            "order_3_edit_invalidated_review": True,
            "publish_while_stale_http_status": 400,
            "generated_version_2": regenerated["document"]["version"],
            "reviewed_version_2": rereviewed["document"]["version"],
            "published_version": published["documents"][0]["version"],
            "driver_assignment_count": len(assignments["assignments"]),
            "vehicle_office": priced_group["vehicle_office"],
            "vehicle_permitted_business_area": priced_group["vehicle_permitted_business_area"],
            "vehicle_affiliation_status": priced_group["vehicle_affiliation"]["status"],
            "recommended_prices": [item["recommended_price"] for item in priced_group["orders"]],
            "effective_prices": [item["price"] for item in priced_group["orders"]],
            "price_snapshot_sources": [item["source"] for item in price_snapshots],
            "price_rule_versions": [item["rule_version"] for item in price_snapshots],
        }
        with closing(database.get_connection()) as conn:
            rows = conn.execute(
                "SELECT status, lifecycle_status FROM driver_run_documents ORDER BY version"
            ).fetchall()
        self.assertEqual(rows[0]["lifecycle_status"], "superseded")
        self.assertEqual(rows[-1]["status"], "published")


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import tempfile
import unittest
import warnings
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import fitz
from pypdf import PdfReader

from backend.db import database
from backend.services import dispatch_service, parser_service
from backend.services import run_document_service as service
from backend.services.hotel_pool_service import hotel_pool
from backend.services.v014_document_renderer import build_acceptance_view_model, build_dispatch_view_model
from backend.services.driver_service import list_driver_assignments
from backend.services.notification_service import list_driver_notifications
from backend.services.tenant_context import set_current_tenant_id

warnings.filterwarnings("ignore", category=ResourceWarning)


def pdf_pages_text(path):
    with fitz.open(str(path)) as document:
        return [page.get_text() for page in document]


def pdf_text(path):
    return "\n".join(pdf_pages_text(path))


class RunDocumentWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp.name)
        self.original_db = database.DB_PATH
        self.original_runtime = service.RUNTIME_DIR
        database.DB_PATH = root / "test.sqlite3"
        service.RUNTIME_DIR = root / "runtime"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        self.actor = {"id": 11, "tenant_id": 1, "username": "ops", "display_name": "运行管理", "role": "operations_manager"}
        with closing(database.get_connection()) as conn:
            vehicle_columns = {row["name"] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
            if "office" not in vehicle_columns:
                conn.execute("ALTER TABLE vehicles ADD COLUMN office TEXT")
            if "permitted_business_area" not in vehicle_columns:
                conn.execute("ALTER TABLE vehicles ADD COLUMN permitted_business_area TEXT")
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, '柚子旅行', 'yuzu-test')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (1, 1, '胡东锴', 'HDK', '大阪营业所', 'available', 'available')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (2, 1, '李成志', 'LCZ', '京都营业所', 'available', 'available')")
            conn.execute("INSERT INTO users (id, tenant_id, username, password_hash, role, display_name, phone, profile_type, profile_id, account_scope, is_active) VALUES (101, 1, 'driver-1', 'test', 'driver', '胡东锴', '08000000001', 'driver', 1, 'driver', 1)")
            conn.execute("INSERT INTO users (id, tenant_id, username, password_hash, role, display_name, phone, profile_type, profile_id, account_scope, is_active) VALUES (102, 1, 'driver-2', 'test', 'driver', '李成志', '08000000002', 'driver', 2, 'driver', 1)")
            conn.execute("UPDATE drivers SET user_id = 101 WHERE id = 1")
            conn.execute("UPDATE drivers SET user_id = 102 WHERE id = 2")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status, office, permitted_business_area) VALUES (1, 1, '大阪6832', '大阪 500 あ 6832', 'HiAce', 10, 10, 'available', '大阪営業所', '大阪市域交通圏')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status, office, permitted_business_area) VALUES (2, 1, '京都7011', '京都 300 い 7011', 'Alphard', 7, 7, 'available', '京都営業所', '京都市域交通圏')")
            conn.execute(
                """
                INSERT INTO company_registrations (
                    managing_tenant_id, company_type, tenant_id, company_code,
                    company_name, registered_name, address, contact_name,
                    contact_phone, contact_email, status
                ) VALUES (
                    1, 'carrier', 1, 'DAITORA', '株式会社大寅', '株式会社大寅',
                    '〒551-0013 大阪府大阪市大正区小林西2丁目10-3\n〒612-8448 京都府京都市伏見区竹田東小屋ノ内町95',
                    '運行管理', '06-6710-9861', 'dispatch@example.invalid', 'approved'
                )
                """
            )
            conn.commit()

    def tearDown(self):
        database.DB_PATH = self.original_db
        service.RUNTIME_DIR = self.original_runtime
        set_current_tenant_id(None)
        self.temp.cleanup()

    def add_order(self, driver_id=1, vehicle_id=1, minute=0, suffix="A", price=12460):
        with closing(database.get_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    tenant_id, oid, order_date, start_time, end_time, pickup_location,
                    dropoff_location, order_type, price, remark, dispatch_status,
                    operations_business_area, run_confirmation_status
                ) VALUES (1, ?, '2026-07-24', ?, ?, '大阪市内ホテル', '関西空港', '送机', ?, ?, 'assigned', '大阪营业区域', 'pending')
                """,
                (f"SRC260724{minute:04d}{suffix}", f"{8 + minute // 60:02d}:{minute % 60:02d}", f"{10 + minute // 60:02d}:{minute % 60:02d}", price, f"中文备注 {suffix}"),
            )
            order_id = cursor.lastrowid
            conn.execute("INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status) VALUES (1, ?, ?, ?, 'active')", (order_id, driver_id, vehicle_id))
            conn.commit()
        return order_id

    def confirm(self, order_id, **changes):
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        payload = {
            "order_id": order_id,
            "order_date": row["order_date"],
            "start_time": row["start_time"],
            "operations_business_area": row["operations_business_area"],
            "order_type": row["order_type"],
            "pickup_location": row["pickup_location"],
            "dropoff_location": row["dropoff_location"],
            "price": row["price"],
            **changes,
        }
        return service.confirm_order(order_id, payload, self.actor)

    def add_unassigned_order(self, suffix="I"):
        with closing(database.get_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    tenant_id, oid, order_date, start_time, end_time, pickup_location,
                    dropoff_location, order_type, price, remark, dispatch_status,
                    operations_business_area, run_confirmation_status
                ) VALUES (1, ?, '2026-07-24', '08:00', '10:00', '大阪市内ホテル',
                          '関西空港', '送机', 12460, ?, 'unassigned', '大阪营业区域', 'pending')
                """,
                (f"SRC2607249999{suffix}", f"导入测试 {suffix}"),
            )
            conn.commit()
            return cursor.lastrowid

    def test_daily_v2_fixed_kyoto_group_has_two_auto_checks_and_one_area_risk(self):
        routes = [
            ("京都ホテル", "KIX"),
            ("KIX", "神戸"),
            ("ITM", "京都ホテル"),
        ]
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE vehicles SET plate_number = '京都 300 あ 3827' WHERE id = 2")
            for index, (pickup, dropoff) in enumerate(routes, 1):
                cursor = conn.execute(
                    """
                    INSERT INTO orders (
                        tenant_id, oid, order_date, start_time, end_time,
                        pickup_location, dropoff_location, order_type, price,
                        dispatch_status, operations_business_area,
                        run_confirmation_status
                    ) VALUES (1, ?, '2026-10-16', ?, ?, ?, ?, '接送', NULL,
                              'assigned', '', 'pending')
                    """,
                    (f"D261016{index:04d}", f"{8 + index:02d}:00", f"{9 + index:02d}:00", pickup, dropoff),
                )
                conn.execute(
                    "INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status) VALUES (1, ?, 2, 2, 'active')",
                    (cursor.lastrowid,),
                )
            conn.commit()
        group = service.list_run_groups("2026-10-16", 1)[0]
        self.assertEqual(group["plate_number"], "京都 300 あ 3827")
        self.assertEqual(group["auto_checked_count"], 2)
        self.assertEqual(group["pending_check_count"], 1)
        self.assertEqual(group["operations_manager"], "朱英心")
        self.assertEqual([item["daily_check_status"] for item in group["orders"]], ["auto_passed", "area_risk", "auto_passed"])
        self.assertEqual([item["daily_effective_price"] for item in group["orders"]], [17000, None, 14000])
        snapshot = service.build_document_snapshot(group, "fixed-kyoto-v2")
        self.assertEqual([item["money"]["total_jpy"] for item in snapshot["orders"]], [17000, None, 14000])
        self.assertEqual([item["money"]["fare_jpy"] for item in snapshot["orders"]], [17000, None, 14000])
        self.assertFalse(snapshot["orders"][0]["money"]["price_confirmed"])
        with self.assertRaises(service.DailyGroupPreflightError) as captured:
            service.confirm_and_publish_daily_group(group["key"], self.actor)
        self.assertEqual(captured.exception.issues[0]["order_index"], 2)
        self.assertEqual(captured.exception.issues[0]["status"], "area_risk")

    def test_office_defaults_supply_the_confirmed_operations_manager_names(self):
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE company_registrations SET contact_name = '' WHERE tenant_id = 1")
            conn.commit()
        self.add_order(driver_id=1, vehicle_id=1, suffix="OSAKA-MANAGER")
        self.add_order(driver_id=2, vehicle_id=2, suffix="KYOTO-MANAGER", price=None)
        groups = service.list_run_groups("2026-07-24", 1)
        by_vehicle = {group["vehicle_id"]: group for group in groups}
        self.assertEqual(by_vehicle[1]["operations_manager"], "胡東鍇")
        self.assertEqual(by_vehicle[2]["operations_manager"], "朱英心")
        self.assertEqual(by_vehicle[1]["operations_manager_source"], "office_default")
        self.assertEqual(by_vehicle[2]["operations_manager_source"], "office_default")

    def test_daily_v2_whole_edit_reassigns_to_real_resources_as_unpublished_draft(self):
        order_id = self.add_order(driver_id=2, vehicle_id=2, suffix="WHOLE")
        original = service.list_run_groups("2026-07-24", 1)[0]
        result = service.reassign_daily_group(
            original["key"],
            {"driver_id": 1, "vehicle_id": 1},
            self.actor,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["group_key"], "2026-07-24:1:1")
        self.assertFalse(result["published"])
        self.assertFalse(result["driver_notified"])
        with closing(database.get_connection()) as conn:
            active = conn.execute(
                "SELECT driver_id, vehicle_id, execution_status, published_at FROM assignments WHERE order_id = ? AND status = 'active'",
                (order_id,),
            ).fetchone()
            cancelled = conn.execute(
                "SELECT COUNT(*) FROM assignments WHERE order_id = ? AND status = 'cancelled'",
                (order_id,),
            ).fetchone()[0]
            order = conn.execute(
                "SELECT run_confirmation_status FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        self.assertEqual((active["driver_id"], active["vehicle_id"]), (1, 1))
        self.assertEqual(active["execution_status"], "draft")
        self.assertIsNone(active["published_at"])
        self.assertEqual(cancelled, 1)
        self.assertEqual(order["run_confirmation_status"], "pending")
        self.assertEqual(list_driver_notifications(1), [])

    def document_path(self, document):
        return Path(self.temp.name) / "runtime" / "uploads" / "run_documents" / "1" / "2026-07-24" / document["file_name"]

    def test_raw_six_order_chain_persists_hotels_and_generates_one_stable_three_page_pdf(self):
        raw = """10/9 李力 7495
1️⃣09:30 大阪送机关西 WhatsApp*代收13000日元
2️⃣10:40 关西举牌接机大阪 指定时间 微信
3️⃣13:00 大阪送机关西 微信
4️⃣14:00 关西举牌接机大阪 line
5️⃣17:00 大阪送机关西 微信
6️⃣18:00 关西举牌接机大阪 指定时间 微信"""
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (9, 1, '李力', 'LL', '大阪営業所', 'available', 'available')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status) VALUES (9, 1, '大阪7495', '大阪 300 あ 7495', 'Alphard', 7, 7, 'available')")
            conn.commit()
        parsed_group = parser_service.parse_daily_assignment_text(raw, base_year=2026)["groups"][0]
        result = dispatch_service.import_daily_assignment_group(
            {"driver_id": 9, "vehicle_id": 9, "orders": [item["parsed"] for item in parsed_group["orders"]]},
            self.actor,
        )
        self.assertTrue(result["success"])
        with closing(database.get_connection()) as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM orders WHERE id IN ({}) ORDER BY start_time".format(",".join("?" for _ in result["order_ids"])),
                result["order_ids"],
            ).fetchall()]
        osaka_hotels = {item["name"] for item in hotel_pool("大阪")}
        city_locations = [
            rows[0]["pickup_location"], rows[1]["dropoff_location"], rows[2]["pickup_location"],
            rows[3]["dropoff_location"], rows[4]["pickup_location"], rows[5]["dropoff_location"],
        ]
        self.assertTrue(all(value in osaka_hotels for value in city_locations))
        self.assertEqual([rows[index][side] for index, side in ((0, "pickup_source_text"), (1, "dropoff_source_text"), (2, "pickup_source_text"), (3, "dropoff_source_text"), (4, "pickup_source_text"), (5, "dropoff_source_text"))], ["大阪"] * 6)
        self.assertEqual([row["end_time"] for row in rows], ["10:30", "11:40", "14:00", "15:00", "18:00", "19:00"])
        key = service.group_key("2026-10-09", 9, 9)
        first = service.generate_run_document(key, self.actor)
        second = service.generate_run_document(key, self.actor)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["document_version_id"], second["document_version_id"])
        self.assertEqual(first["page_count"], 2)
        path = service.RUNTIME_DIR / "uploads" / "run_documents" / "1" / "2026-10-09" / first["file_name"]
        self.assertTrue(path.is_file())
        self.assertEqual(len(PdfReader(str(path)).pages), 2)
        text = pdf_text(path)
        self.assertIn("08:30", text)
        self.assertIn("20:00", text)
        self.assertNotIn("大阪市内ホテル", text)
        self.assertNotIn("氏名：SPI", text)
        self.assertNotIn("自動選定ホテルを含む計画案", text)
        self.assertNotIn("本機作成／押印・実際の交付は別途", text)
        self.assertNotIn("予定版", text)
        for hotel in city_locations:
            self.assertIn(hotel, text)
        with closing(database.get_connection()) as conn:
            document_row = conn.execute("SELECT snapshot_json FROM driver_run_documents WHERE id = ?", (first["id"],)).fetchone()
        snapshot = json.loads(document_row["snapshot_json"])
        self.assertEqual([order["contract_party_source"] for order in snapshot["orders"]], ["applicant_slot"] * 6)
        self.assertTrue(all(order["contract_party_name"] in {"C-Trip", "KKday", "Klook", "WEBSITE"} for order in snapshot["orders"]))

    def test_confirmation_generation_reuse_and_version(self):
        first = self.add_order(minute=0, suffix="A")
        second = self.add_order(minute=60, suffix="B")
        group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual((group["confirmed_count"], group["pending_count"]), (0, 2))
        self.assertEqual(group["orders"][0]["recommended_price"], 17000)
        draft_document = service.generate_run_document(group["key"], self.actor)
        self.assertEqual((draft_document["version"], draft_document["page_count"]), (1, 2))
        self.assertTrue(draft_document["document_id"].startswith("doc-"))
        self.assertTrue(draft_document["document_version_id"].startswith("docv-"))
        with closing(database.get_connection()) as conn:
            stored = conn.execute(
                "SELECT * FROM driver_run_documents WHERE id = ?", (draft_document["id"],)
            ).fetchone()
            snapshot = json.loads(stored["snapshot_json"])
            pdf_sha256 = hashlib.sha256(self.document_path(draft_document).read_bytes()).hexdigest()
            self.assertEqual(stored["pdf_sha256"], pdf_sha256)
            self.assertEqual(stored["source_sha256"], stored["source_hash"])
            self.assertEqual(snapshot["document_version_id"], stored["document_version_id"])
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM dispatch_document_batches").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM dispatch_route_nodes").fetchone()[0],
                len(snapshot["route_nodes"]),
            )
            self.assertEqual(
                conn.execute("SELECT event_type FROM dispatch_document_events").fetchone()[0],
                "generated",
            )
        self.confirm(first)
        self.confirm(second)
        group = service.list_run_groups("2026-07-24")[0]
        document = service.generate_run_document(group["key"], self.actor)
        self.assertNotEqual(document["id"], draft_document["id"])
        self.assertEqual((document["version"], document["page_count"]), (2, 2))
        with closing(database.get_connection()) as conn:
            old = conn.execute(
                "SELECT lifecycle_status FROM driver_run_documents WHERE id = ?",
                (draft_document["id"],),
            ).fetchone()
            current = conn.execute(
                "SELECT supersedes_document_version_id FROM driver_run_documents WHERE id = ?",
                (document["id"],),
            ).fetchone()
        self.assertEqual(old["lifecycle_status"], "superseded")
        self.assertEqual(current["supersedes_document_version_id"], draft_document["document_version_id"])
        self.assertEqual(len(PdfReader(str(self.document_path(document))).pages), 2)
        self.assertEqual(service.generate_run_document(group["key"], self.actor)["id"], document["id"])
        self.confirm(first, start_time="09:30")
        updated = service.generate_run_document(group["key"], self.actor)
        self.assertEqual(updated["version"], 3)

    def test_vehicle_affiliation_quote_area_suggestion_and_manual_price_protection(self):
        order_id = self.add_order(driver_id=2, vehicle_id=2, suffix="KYOTO", price=None)
        with closing(database.get_connection()) as conn:
            conn.execute(
                """
                UPDATE orders
                SET pickup_location = '京都市内ホテル', pickup_source_text = '京都',
                    dropoff_location = '関西国際空港', dropoff_source_text = 'KIX',
                    operations_business_area = NULL
                WHERE id = ?
                """,
                (order_id,),
            )
            conn.commit()

        group = next(item for item in service.list_run_groups("2026-07-24") if item["vehicle_id"] == 2)
        order = group["orders"][0]
        self.assertEqual(order["recommended_price"], 17000)
        self.assertEqual(order["recommended_order_category"], "kix_transfer")
        self.assertEqual(order["suggested_business_area"], "京都市域交通圏")
        self.assertEqual(order["vehicle_affiliation"]["office_source"], "vehicle_archive")
        with closing(database.get_connection()) as conn:
            stored = conn.execute(
                "SELECT price, operations_business_area, price_snapshot_json FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        self.assertIsNone(stored["price"])
        self.assertIsNone(stored["operations_business_area"])
        self.assertIsNone(stored["price_snapshot_json"])

        self.confirm(order_id, operations_business_area="京都市域交通圏", price=17000)
        with closing(database.get_connection()) as conn:
            first_snapshot = json.loads(conn.execute(
                "SELECT price_snapshot_json FROM orders WHERE id = ?", (order_id,)
            ).fetchone()["price_snapshot_json"])
        self.assertEqual(first_snapshot["source"], "tariff_recommendation")
        self.assertEqual(first_snapshot["rule_key"], "kyoto_kix")
        self.assertFalse(first_snapshot["financially_confirmed"])

        self.confirm(order_id, price=19500)
        group = next(item for item in service.list_run_groups("2026-07-24") if item["vehicle_id"] == 2)
        self.assertEqual(group["orders"][0]["price"], 19500)
        self.assertEqual(group["orders"][0]["recommended_price"], 17000)
        with closing(database.get_connection()) as conn:
            manual_snapshot = json.loads(conn.execute(
                "SELECT price_snapshot_json FROM orders WHERE id = ?", (order_id,)
            ).fetchone()["price_snapshot_json"])
        self.assertEqual(manual_snapshot["source"], "manual_override")
        self.assertEqual(manual_snapshot["recommended_total_jpy"], 17000)

    def test_route_and_vehicle_office_changes_recalculate_and_stale_existing_pdf(self):
        order_id = self.add_order(price=19500, suffix="RECALC")
        self.confirm(order_id)
        group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual(group["orders"][0]["recommended_price"], 17000)
        service.generate_run_document(group["key"], self.actor)
        self.assertEqual(service.list_run_groups("2026-07-24")[0]["document_status"], "generated")

        self.confirm(
            order_id,
            pickup_location="大阪市内ホテル",
            dropoff_location="京都市内ホテル",
            order_type="城市间接送",
            price=19500,
        )
        changed_group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual(changed_group["orders"][0]["recommended_price"], 21000)
        self.assertEqual(changed_group["orders"][0]["price"], 19500)
        self.assertEqual(changed_group["document_status"], "stale")

        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE vehicles SET office = '京都営業所' WHERE id = 1")
            conn.commit()
        conflict_group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual(conflict_group["vehicle_affiliation"]["status"], "conflict")
        self.assertIsNone(conflict_group["orders"][0]["recommended_price"])
        self.assertEqual(conflict_group["document_status"], "stale")

    def test_unknown_vehicle_model_never_defaults_to_alphard_and_unknown_amount_stays_null(self):
        with closing(database.get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO vehicles (
                    id, tenant_id, plate_no, plate_number, vehicle_type, seats,
                    seat_count, status, office, permitted_business_area
                ) VALUES (3, 1, '大阪9999', '大阪 300 あ 9999', '', 7, 7,
                          'available', '大阪営業所', '大阪市域交通圏')
                """
            )
            conn.commit()
        order_id = self.add_order(vehicle_id=3, suffix="UNKNOWN", price=None)
        group = next(item for item in service.list_run_groups("2026-07-24") if item["vehicle_id"] == 3)
        order = group["orders"][0]
        self.assertIsNone(order["recommended_price"])
        self.assertEqual(order["recommended_price_reason"], "vehicle_type_unknown")
        with closing(database.get_connection()) as conn:
            self.assertIsNone(conn.execute("SELECT price FROM orders WHERE id = ?", (order_id,)).fetchone()["price"])

    def test_draft_pdf_allows_missing_price_but_publish_blocks(self):
        self.add_order(price=None)
        group = service.list_run_groups("2026-07-24")[0]
        self.assertTrue(any("運賃" in item for item in group["validation_issues"]))
        document = service.generate_run_document(group["key"], self.actor)
        self.assertEqual(document["status"], "generated")
        text = pdf_text(self.document_path(document))
        self.assertNotIn("DRAFT", text)
        with self.assertRaisesRegex(ValueError, "運賃"):
            service.review_and_publish_run_document(group["key"], self.actor)

    def test_ambiguous_unconfirmed_plus_120_time_is_not_rewritten_during_preview_or_generation(self):
        order_id = self.add_order(minute=0, suffix="AMBIGUOUS")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET daily_import_group_key = 'legacy-ambiguous', end_time_source = NULL, end_time_confirmed = 0 WHERE id = ?",
                (order_id,),
            )
            conn.commit()
        key = service.list_run_groups("2026-07-24")[0]["key"]
        first = service.generate_run_document(key, self.actor)
        preview = service.get_run_document_preview(key, self.actor)
        second = service.generate_run_document(key, self.actor)
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT end_time, end_time_source, end_time_confirmed FROM orders WHERE id = ?", (order_id,)).fetchone()
        self.assertEqual((row["end_time"], row["end_time_source"], row["end_time_confirmed"]), ("10:00", None, 0))
        self.assertIn("order_1_arrival_time_source_confirmation_required", preview["validation_issues"])
        self.assertEqual(first["id"], second["id"])

    def test_renderer_version_change_forces_a_new_pdf(self):
        self.add_order()
        group_key = service.list_run_groups("2026-07-24")[0]["key"]
        with patch.object(service, "DOCUMENT_RENDERER_VERSION", "test-renderer-a"):
            first = service.generate_run_document(group_key, self.actor)
        with patch.object(service, "DOCUMENT_RENDERER_VERSION", "test-renderer-b"):
            second = service.generate_run_document(group_key, self.actor)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual((first["version"], second["version"]), (1, 2))

    def test_route_node_edit_creates_new_version_and_keeps_published_file(self):
        order_id = self.add_order(suffix="NODE")
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        first = service.generate_run_document(key, self.actor)
        published = service.review_and_publish_run_document(key, self.actor)["document"]
        self.assertEqual(published["id"], first["id"])
        first_path = self.document_path(first)
        first_sha = hashlib.sha256(first_path.read_bytes()).hexdigest()
        preview = service.get_run_document_preview(key, self.actor)
        pickup = next(node for node in preview["nodes"] if node["node_type"] == "pickup")
        edited = service.update_run_document_node(key, {
            "route_node_id": pickup["route_node_id"],
            "planned_location": "ホテル日航大阪 2F",
            "planned_departure_at": "2026-07-24T08:30:00",
        }, self.actor)
        edited_pickup = next(node for node in edited["nodes"] if node["route_node_id"] == pickup["route_node_id"])
        self.assertEqual(edited_pickup["planned_location"], "ホテル日航大阪 2F")
        self.assertEqual(edited_pickup["planned_departure_at"], "2026-07-24T08:30:00")
        replacement = service.generate_run_document(key, self.actor)
        self.assertEqual(replacement["version"], 2)
        self.assertTrue(first_path.is_file())
        self.assertEqual(hashlib.sha256(first_path.read_bytes()).hexdigest(), first_sha)
        with closing(database.get_connection()) as conn:
            old = conn.execute("SELECT status, lifecycle_status FROM driver_run_documents WHERE id = ?", (first["id"],)).fetchone()
            current_snapshot = json.loads(conn.execute("SELECT snapshot_json FROM driver_run_documents WHERE id = ?", (replacement["id"],)).fetchone()[0])
        self.assertEqual(old["status"], "published")
        self.assertEqual(old["lifecycle_status"], "superseded")
        snapshot_text = json.dumps(current_snapshot, ensure_ascii=False)
        self.assertGreaterEqual(snapshot_text.count("ホテル日航大阪 2F"), 2)
        self.assertIn("2026-07-24T08:30:00", snapshot_text)

    def test_document_field_edit_is_whitelisted_and_checks_source_hash(self):
        order_id = self.add_order(suffix="FIELD")
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        generated = service.generate_run_document(key, self.actor)
        service.review_run_document(key, self.actor)
        preview = service.get_run_document_preview(key, self.actor)
        edited = service.update_run_document_field(key, {
            "field_id": f"order:{order_id}:contract_party_name",
            "value": "新しい契約相手",
            "expected_source_hash": preview["source_sha256"],
        }, self.actor)
        field = next(item for item in edited["document_fields"] if item["field_id"] == f"order:{order_id}:contract_party_name")
        self.assertEqual(field["value"], "新しい契約相手")
        with closing(database.get_connection()) as conn:
            order = conn.execute("SELECT agency_name, run_revision, run_confirmation_status FROM orders WHERE id = ?", (order_id,)).fetchone()
            old = conn.execute("SELECT status FROM driver_run_documents WHERE id = ?", (generated["id"],)).fetchone()
        self.assertEqual(order["agency_name"], "新しい契約相手")
        self.assertGreaterEqual(order["run_revision"], 2)
        self.assertEqual(order["run_confirmation_status"], "pending")
        self.assertEqual(old["status"], "stale")
        with self.assertRaisesRegex(ValueError, "document_revision_conflict"):
            service.update_run_document_field(key, {
                "field_id": f"order:{order_id}:applicant_contact",
                "value": "06-1234-5678",
                "expected_source_hash": preview["source_sha256"],
            }, self.actor)

    def test_document_safety_field_override_persists_in_preview(self):
        self.add_order(suffix="SAFETY")
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        edited = service.update_run_document_field(key, {
            "field_id": "operation:safety:waiting_place",
            "value": "第2ターミナル待機場",
            "expected_source_hash": preview["source_sha256"],
        }, self.actor)
        field = next(item for item in edited["document_fields"] if item["field_id"] == "operation:safety:waiting_place")
        self.assertEqual(field["value"], "第2ターミナル待機場")

    def test_workbench_views_share_renderer_page_plan_and_stable_cells(self):
        order_ids = [self.add_order(minute=index * 5, suffix=f"WB{index}", price=0 if index == 2 else 12460) for index in range(11)]
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        views = preview["document_views"]
        self.assertEqual(preview["template_version"], service.DOCUMENT_RENDERER_VERSION)
        self.assertEqual([len(page["order_ids"]) for page in preview["page_plan"]], [10, 1])
        self.assertEqual(
            [page["order_ids"] for page in views["acceptance"]["pages"]],
            [page["order_ids"] for page in views["dispatch"]["pages"]],
        )
        third = views["acceptance"]["pages"][0]["tasks"][2]
        self.assertEqual(third["order_id"], order_ids[2])
        self.assertEqual(third["cells"]["price"]["display_value"], "0")
        self.assertTrue(third["cells"]["pickup_location"]["field_id"].startswith("route_node:"))

    def test_atomic_document_patch_saves_multiple_fields_without_rendering(self):
        first = self.add_order(suffix="PATCH-A")
        second = self.add_order(minute=60, suffix="PATCH-B")
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        pickup = next(node for node in preview["nodes"] if node["order_id"] == first and node["node_type"] == "pickup")
        with closing(database.get_connection()) as conn:
            before_documents = conn.execute("SELECT COUNT(*) FROM driver_run_documents").fetchone()[0]
        updated = service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "client_request_id": "workbench-multi-field-1",
            "patches": [
                {"field_id": f"route_node:{pickup['route_node_id']}:planned_location", "value": "ホテル日航大阪 正面玄関"},
                {"field_id": f"route_node:{pickup['route_node_id']}:planned_departure_at", "value": "2026-07-24T09:15:00"},
                {"field_id": f"order:{first}:applicant_contact", "value": "06-1234-5678"},
            ],
        }, self.actor)
        self.assertEqual(updated["saved_patch_count"], 3)
        changed_node = next(node for node in updated["nodes"] if node["route_node_id"] == pickup["route_node_id"])
        self.assertEqual(changed_node["planned_location"], "ホテル日航大阪 正面玄関")
        self.assertEqual(changed_node["planned_departure_at"], "2026-07-24T09:15:00")
        field = next(item for item in updated["document_fields"] if item["field_id"] == f"order:{first}:applicant_contact")
        self.assertEqual(field["value"], "06-1234-5678")
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM driver_run_documents").fetchone()[0], before_documents)
            untouched = conn.execute("SELECT guest_contact FROM orders WHERE id = ?", (second,)).fetchone()
        self.assertFalse(untouched["guest_contact"])

        replay = service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "client_request_id": "workbench-multi-field-1",
            "patches": [
                {"field_id": f"route_node:{pickup['route_node_id']}:planned_location", "value": "ホテル日航大阪 正面玄関"},
                {"field_id": f"route_node:{pickup['route_node_id']}:planned_departure_at", "value": "2026-07-24T09:15:00"},
                {"field_id": f"order:{first}:applicant_contact", "value": "06-1234-5678"},
            ],
        }, self.actor)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["saved_patch_count"], 0)

    def test_atomic_document_patch_rolls_back_when_any_field_is_invalid(self):
        order_id = self.add_order(suffix="PATCH-ROLLBACK")
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        with self.assertRaisesRegex(ValueError, "document_field_not_editable"):
            service.patch_run_document_draft(key, {
                "expected_source_hash": preview["source_sha256"],
                "patches": [
                    {"field_id": f"order:{order_id}:applicant_contact", "value": "should-not-save"},
                    {"field_id": f"order:{order_id}:internal_secret", "value": "blocked"},
                ],
            }, self.actor)
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT guest_contact FROM orders WHERE id = ?", (order_id,)).fetchone()
        self.assertFalse(row["guest_contact"])

    def test_atomic_document_patch_covers_fee_breakdown_without_confirming_price(self):
        order_id = self.add_order(suffix="PATCH-FEES", price=1000)
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET price_confirmed = 1, fare_jpy = 800, service_fee_jpy = 200 WHERE id = ?",
                (order_id,),
            )
            conn.commit()
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        fee_fields = {
            item["field_id"]: item["value"]
            for item in preview["document_fields"]
            if str(item["field_id"]).startswith(f"order:{order_id}:")
        }
        self.assertEqual(fee_fields[f"order:{order_id}:fare_jpy"], 800)
        self.assertEqual(fee_fields[f"order:{order_id}:service_fee_jpy"], 200)
        updated = service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "patches": [
                {"field_id": f"order:{order_id}:fare_jpy", "value": "900"},
                {"field_id": f"order:{order_id}:service_fee_jpy", "value": "250"},
                {"field_id": f"order:{order_id}:advance_jpy", "value": "300"},
                {"field_id": f"order:{order_id}:toll_fee_jpy", "value": "400"},
                {"field_id": f"order:{order_id}:parking_fee_jpy", "value": "500"},
                {"field_id": f"order:{order_id}:price_jpy", "value": "2350"},
            ],
        }, self.actor)
        self.assertEqual(updated["saved_patch_count"], 6)
        with closing(database.get_connection()) as conn:
            row = conn.execute(
                "SELECT price_jpy, fare_jpy, service_fee_jpy, document_advance_jpy, toll_fee_jpy, parking_fee_jpy, price_confirmed FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        self.assertEqual(tuple(row), (2350, 900, 250, 300, 400, 500, 0))

        replay = service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "patches": [{"field_id": f"order:{order_id}:fare_jpy", "value": "900.00"}],
        }, self.actor)
        self.assertTrue(replay["idempotent_replay"])

    def test_pickup_time_only_moves_auto_suggested_arrival_and_preserves_manual_arrival(self):
        order_id = self.add_order(suffix="PATCH-TIME")
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE orders SET end_time = '09:00', end_time_source = 'suggested_60m', end_time_confirmed = 0 WHERE id = ?", (order_id,))
            conn.commit()
        key = service.list_run_groups("2026-07-24")[0]["key"]
        preview = service.get_run_document_preview(key, self.actor)
        pickup = next(node for node in preview["nodes"] if node["order_id"] == order_id and node["node_type"] == "pickup")
        dropoff = next(node for node in preview["nodes"] if node["order_id"] == order_id and node["node_type"] == "dropoff")
        moved = service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "patches": [{"field_id": f"route_node:{pickup['route_node_id']}:planned_departure_at", "value": "2026-07-24T10:30:00"}],
        }, self.actor)
        moved_dropoff = next(node for node in moved["nodes"] if node["route_node_id"] == dropoff["route_node_id"])
        self.assertEqual(moved_dropoff["planned_arrival_at"], "2026-07-24T11:30:00")

        manual = service.patch_run_document_draft(key, {
            "expected_source_hash": moved["source_sha256"],
            "patches": [{"field_id": f"route_node:{dropoff['route_node_id']}:planned_arrival_at", "value": "2026-07-24T12:45:00"}],
        }, self.actor)
        moved_again = service.patch_run_document_draft(key, {
            "expected_source_hash": manual["source_sha256"],
            "patches": [{"field_id": f"route_node:{pickup['route_node_id']}:planned_departure_at", "value": "2026-07-24T11:00:00"}],
        }, self.actor)
        final_dropoff = next(node for node in moved_again["nodes"] if node["route_node_id"] == dropoff["route_node_id"])
        self.assertEqual(final_dropoff["planned_arrival_at"], "2026-07-24T12:45:00")

    def test_driver_cannot_patch_document_draft(self):
        self.add_order(suffix="PATCH-ROLE")
        key = service.list_run_groups("2026-07-24")[0]["key"]
        with self.assertRaisesRegex(ValueError, "権限"):
            service.patch_run_document_draft(key, {
                "patches": [{"field_id": "operation:safety:waiting_place", "value": "x"}],
            }, {"id": 101, "tenant_id": 1, "role": "driver", "profile_id": 1})

    def test_manual_price_change_requires_price_confirmation_again(self):
        order_id = self.add_order(suffix="PRICE")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET price_confirmed = 1, price_confirmed_by = 'ops', price_confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (order_id,),
            )
            conn.commit()
        self.confirm(order_id, price=18800)
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT price, price_confirmed, price_confirmed_by, price_confirmed_at FROM orders WHERE id = ?", (order_id,)).fetchone()
        self.assertEqual(row["price"], 18800)
        self.assertEqual(row["price_confirmed"], 0)
        self.assertIsNone(row["price_confirmed_by"])
        self.assertIsNone(row["price_confirmed_at"])

    def test_external_edit_resets_confirmation_and_stales_document(self):
        order_id = self.add_order()
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        doc = service.generate_run_document(key, self.actor)
        with closing(database.get_connection()) as conn:
            before = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
            conn.execute("UPDATE orders SET price = 19000 WHERE id = ?", (order_id,))
            conn.commit()
            after = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        self.assertTrue(service.mark_order_changed(order_id, before, after, 1))
        group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual(group["confirmation_status"], "pending")
        self.assertEqual(group["latest_document"]["id"], doc["id"])
        self.assertEqual(group["document_status"], "stale")

    def test_publish_and_driver_isolation(self):
        self.confirm(self.add_order(driver_id=1, vehicle_id=1, suffix="A"))
        self.confirm(self.add_order(driver_id=2, vehicle_id=2, suffix="B"))
        groups = service.list_run_groups("2026-07-24")
        for item in groups:
            service.generate_run_document(item["key"], self.actor)
            service.review_run_document(item["key"], self.actor)
        docs = service.publish_run_documents([item["key"] for item in groups], self.actor)
        self.assertEqual(len(docs), 2)
        own = service.list_driver_run_documents(1)
        other = service.list_driver_run_documents(2)
        self.assertEqual({item["driver_id"] for item in own}, {1})
        self.assertEqual({item["driver_id"] for item in other}, {2})
        self.assertIsNotNone(service.resolve_run_document(own[0]["id"], {"tenant_id": 1, "role": "driver", "profile_id": 1}))
        self.assertIsNone(service.resolve_run_document(other[0]["id"], {"tenant_id": 1, "role": "driver", "profile_id": 1}))

    def test_review_publish_returns_next_group_and_keeps_old_published_version(self):
        first = self.add_order(driver_id=1, vehicle_id=1, suffix="A")
        self.add_order(driver_id=2, vehicle_id=2, suffix="B")
        groups = service.list_run_groups("2026-07-24")
        first_group = next(item for item in groups if item["driver_id"] == 1)
        second_group = next(item for item in groups if item["driver_id"] == 2)
        service.generate_run_document(first_group["key"], self.actor)
        result = service.review_and_publish_run_document(first_group["key"], self.actor)
        self.assertEqual(result["document"]["status"], "published")
        self.assertEqual(result["next_group_key"], second_group["key"])
        original_id = result["document"]["id"]
        self.confirm(first, pickup_location="ホテル日航大阪")
        self.assertEqual(service.list_driver_run_documents(1)[0]["id"], original_id)
        changed_group = next(item for item in service.list_run_groups("2026-07-24") if item["driver_id"] == 1)
        self.assertEqual(changed_group["document_status"], "stale")
        replacement = service.generate_run_document(changed_group["key"], self.actor)
        self.assertEqual(replacement["version"], 2)

    def test_instruction_paginates_without_dropping_orders(self):
        ids = [self.add_order(minute=index * 5, suffix=f"中{index}") for index in range(22)]
        for order_id in ids:
            self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        document = service.generate_run_document(key, self.actor)
        reader = PdfReader(str(self.document_path(document)))
        self.assertEqual(document["page_count"], 6)
        self.assertEqual(len(reader.pages), 6)
        text = pdf_text(self.document_path(document))
        self.assertIn("運送引受書", text)
        self.assertIn("運行指示書", "".join(text.split()))
        self.assertIn("1/3", "".join(text.split()))
        self.assertNotIn("中文备注", text)
        for index in range(22):
            self.assertIn(f"08:{index * 5:02d}" if index < 12 else f"09:{(index - 12) * 5:02d}", text)

    def test_7_pdf_whitelist_excludes_guide_but_keeps_flight(self):
        first = self.add_order(minute=0, suffix="G")
        second = self.add_order(minute=60, suffix="H")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET remark = ?, flight_number = ? WHERE id = ?",
                ("ガイド：坂口千久子：090-9887-3549", "CA725", first),
            )
            conn.commit()
        self.confirm(first)
        self.confirm(second)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        document = service.generate_run_document(key, self.actor)
        text = pdf_text(self.document_path(document))
        self.assertEqual(document["page_count"], 2)
        self.assertNotIn("ガイド", text)
        self.assertNotIn("坂口千久子", text)
        self.assertNotIn("090-9887-3549", text)

    def test_grouping_multi_vehicle_and_publish_permission(self):
        order_id = self.add_order(driver_id=1, vehicle_id=1, suffix="M")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "INSERT INTO assignments (tenant_id, order_id, driver_id, vehicle_id, status) VALUES (1, ?, 2, 2, 'active')",
                (order_id,),
            )
            conn.commit()
        self.confirm(order_id)
        groups = service.list_run_groups("2026-07-24")
        self.assertEqual({(item["driver_id"], item["vehicle_id"]) for item in groups}, {(1, 1), (2, 2)})
        driver_actor = {"id": 21, "tenant_id": 1, "role": "driver", "profile_id": 1}
        with self.assertRaisesRegex(ValueError, "権限"):
            service.publish_run_documents([groups[0]["key"]], driver_actor)
        for item in groups:
            service.generate_run_document(item["key"], self.actor)
            service.review_run_document(item["key"], self.actor)
        published = service.publish_run_documents([item["key"] for item in groups], self.actor)
        self.assertEqual(len(published), 2)

    def test_pdf_requires_explicit_review_before_publish(self):
        order_id = self.add_order()
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        generated = service.generate_run_document(key, self.actor)
        self.assertEqual(generated["status"], "generated")
        with self.assertRaisesRegex(ValueError, "PDF"):
            service.publish_run_documents([key], self.actor)
        reviewed = service.review_run_document(key, self.actor)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertTrue(reviewed["reviewed_at"])
        published = service.publish_run_documents([key], self.actor)
        self.assertEqual(published[0]["status"], "published")

    def test_blank_driver_name_cannot_publish_an_already_reviewed_preview(self):
        order_id = self.add_order(suffix="BLANKDRIVER")
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        service.generate_run_document(key, self.actor)
        service.review_run_document(key, self.actor)
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE drivers SET name = '' WHERE id = 1")
            conn.commit()
        with self.assertRaisesRegex(ValueError, "正式文書名"):
            service.publish_run_documents([key], self.actor)
        with closing(database.get_connection()) as conn:
            status = conn.execute("SELECT status FROM driver_run_documents ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertEqual(status, "reviewed")

    def test_assignment_driver_formal_print_name_precedes_archive_name(self):
        with closing(database.get_connection()) as conn:
            conn.execute("ALTER TABLE drivers ADD COLUMN print_name TEXT")
            conn.execute("UPDATE drivers SET print_name = '正式運転者名' WHERE id = 1")
            conn.commit()
        order_id = self.add_order(suffix="PRINTNAME")
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        document = service.generate_run_document(key, self.actor)
        pages = pdf_pages_text(self.document_path(document))
        self.assertTrue(all("正式運転者名" in page for page in pages))
        self.assertTrue(all("胡东锴" not in page for page in pages))

    def test_preview_marker_is_removed_only_by_formal_publish_and_publication_metadata_is_kept(self):
        order_id = self.add_order(suffix="MARKER")
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE orders SET guest_contact = '06-0000-0000' WHERE id = ?", (order_id,))
            conn.commit()
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        generated = service.generate_run_document(key, self.actor)
        preview_path = self.document_path(generated)
        preview_hash = hashlib.sha256(preview_path.read_bytes()).hexdigest()
        preview_pages = pdf_pages_text(preview_path)
        self.assertTrue(all("確認用・未発行" in page for page in preview_pages))
        self.assertNotIn("連絡：", preview_pages[-1])
        self.assertNotIn("06-0000-0000", preview_pages[-1])

        service.review_run_document(key, self.actor)
        published = service.publish_run_documents([key], self.actor)[0]
        published_path = self.document_path(published)
        published_pages = pdf_pages_text(published_path)
        self.assertTrue(all("確認用・未発行" not in page for page in published_pages))
        self.assertNotEqual(preview_path, published_path)
        self.assertTrue(preview_path.is_file())
        self.assertEqual(preview_hash, hashlib.sha256(preview_path.read_bytes()).hexdigest())
        self.assertEqual(published["pdf_sha256"], hashlib.sha256(published_path.read_bytes()).hexdigest())
        self.assertNotEqual(published["pdf_sha256"], preview_hash)
        publication_date = str(published["published_at"]).split("T", 1)[0]
        self.assertIn(publication_date, "\n".join(published_pages))
        with closing(database.get_connection()) as conn:
            event = conn.execute(
                "SELECT actor_name, event_json FROM dispatch_document_events WHERE event_type = 'published' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        event_payload = json.loads(event["event_json"])
        self.assertEqual(event["actor_name"], self.actor["display_name"])
        self.assertEqual(event_payload["pdf_sha256"], published["pdf_sha256"])
        self.assertEqual(event_payload["source_sha256"], published["source_hash"])

    def test_confirm_generate_review_edit_regenerate_review_publish_flow(self):
        order_id = self.add_order(suffix="FLOW")
        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]

        first = service.generate_run_document(key, self.actor)
        reviewed = service.review_run_document(key, self.actor)
        self.assertEqual(reviewed["status"], "reviewed")

        preview = service.get_run_document_preview(key, self.actor)
        service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "client_request_id": "flow-edit-after-review",
            "patches": [
                {"field_id": f"order:{order_id}:applicant_contact", "value": "06-1111-2222"},
            ],
        }, self.actor)
        changed_group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual(changed_group["confirmation_status"], "pending")
        self.assertEqual(changed_group["document_status"], "stale")
        with self.assertRaisesRegex(ValueError, "PDF"):
            service.publish_run_documents([key], self.actor)

        self.confirm(order_id)
        replacement = service.generate_run_document(key, self.actor)
        self.assertNotEqual(replacement["id"], first["id"])
        self.assertEqual(replacement["version"], first["version"] + 1)
        service.review_run_document(key, self.actor)
        published = service.publish_run_documents([key], self.actor)[0]
        self.assertEqual(published["id"], replacement["id"])
        self.assertEqual(published["status"], "published")
        self.assertEqual(len(list_driver_assignments(1)), 1)

    def test_publish_preflight_blocks_missing_driver_account_without_partial_publish(self):
        first = self.add_order(driver_id=1, vehicle_id=1, suffix="P1")
        second = self.add_order(driver_id=2, vehicle_id=2, suffix="P2")
        self.confirm(first)
        self.confirm(second)
        groups = service.list_run_groups("2026-07-24")
        for item in groups:
            service.generate_run_document(item["key"], self.actor)
            service.review_run_document(item["key"], self.actor)
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE drivers SET user_id = NULL WHERE id = 2")
            conn.commit()
        with self.assertRaises(service.DriverAccountPreflightError) as caught:
            service.publish_run_documents([item["key"] for item in groups], self.actor)
        self.assertEqual(caught.exception.blocked[0]["reason"], "driver_account_missing")
        with closing(database.get_connection()) as conn:
            statuses = [row["status"] for row in conn.execute("SELECT status FROM driver_run_documents ORDER BY id").fetchall()]
        self.assertEqual(statuses, ["reviewed", "reviewed"])

    def test_daily_import_stays_hidden_and_silent_until_pdf_publish(self):
        order_id = self.add_unassigned_order()
        result = dispatch_service.assign_orders(
            [order_id], 1, 1, actor=self.actor,
            notify_driver=False, publish_assignment=False,
        )
        self.assertTrue(result["success"])
        self.assertFalse(result["published"])
        self.assertFalse(result["driver_notified"])
        self.assertEqual(list_driver_assignments(1), [])
        self.assertEqual(list_driver_notifications(1), [])
        with closing(database.get_connection()) as conn:
            assignment = conn.execute("SELECT execution_status, published_at FROM assignments WHERE id = ?", (result["assignment_ids"][0],)).fetchone()
        self.assertEqual(assignment["execution_status"], "draft")
        self.assertIsNone(assignment["published_at"])

        self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        service.generate_run_document(key, self.actor)
        service.review_run_document(key, self.actor)
        service.publish_run_documents([key], self.actor)
        self.assertEqual(len(list_driver_assignments(1)), 1)
        notifications = list_driver_notifications(1)
        self.assertEqual([item["notification_type"] for item in notifications], ["run_document_published"])

    def test_v014_golden_four_orders_are_acceptances_then_dispatch(self):
        channels = ["WeChat", "LINE", "WhatsApp", "Kakao"]
        order_ids = [self.add_order(minute=index * 45, suffix=f"G{index}") for index in range(4)]
        with closing(database.get_connection()) as conn:
            for order_id, channel in zip(order_ids, channels):
                conn.execute(
                    "UPDATE orders SET source_channel = ?, agency_name = '有限会社ツーリズムジャパン', guest_contact = '03-5282-4818' WHERE id = ?",
                    (channel, order_id),
                )
            conn.commit()
        for order_id in order_ids:
            self.confirm(order_id)
        key = service.list_run_groups("2026-07-24")[0]["key"]
        document = service.generate_run_document(key, self.actor)
        reader = PdfReader(str(self.document_path(document)))
        self.assertEqual((document["page_count"], len(reader.pages)), (2, 2))
        pages = pdf_pages_text(self.document_path(document))
        self.assertIn("C-Trip", pages[0])
        self.assertIn("WEBSITE", pages[0])
        acceptance_text = pages[0]
        for fixed_value in (
            "551-0013", "612-8448", "06-6710-9861", "090-1483-4105",
        ):
            self.assertIn(fixed_value, acceptance_text)
        self.assertNotIn("dispatch@example.invalid", acceptance_text)
        dispatch_text = pages[1]
        self.assertNotIn("03-5282-4818", dispatch_text)
        self.assertNotIn("連絡：", dispatch_text)
        with closing(database.get_connection()) as conn:
            contacts = {row[0] for row in conn.execute("SELECT guest_contact FROM orders WHERE id IN ({})".format(",".join("?" for _ in order_ids)), order_ids)}
        self.assertEqual(contacts, {"03-5282-4818"})
        self.assertIn("4", dispatch_text)

    def test_acceptance_applicant_may_be_blank(self):
        order_id = self.add_order(suffix="BLANK")
        self.confirm(order_id)
        group = service.list_run_groups("2026-07-24")[0]
        vm = build_acceptance_view_model(group, group["orders"][0], 0, 1)
        self.assertEqual(vm["applicant"], "")
        self.assertEqual(vm["applicant_phone"], "")
        self.assertNotIn("applicant", vm["missing_fields"])
        document = service.generate_run_document(group["key"], self.actor)
        first_page = pdf_pages_text(self.document_path(document))[0]
        for applicant in ("C-Trip", "KKday", "Klook", "WEBSITE"):
            self.assertIn(applicant, first_page)

    def test_generic_city_locations_use_the_same_hotel_in_both_documents(self):
        order_id = self.add_order(suffix="CITY")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET pickup_location = '大阪市内', dropoff_location = '京都市内' WHERE id = ?",
                (order_id,),
            )
            conn.commit()
        group = service.list_run_groups("2026-07-24")[0]
        document = service.generate_run_document(group["key"], self.actor)
        with closing(database.get_connection()) as conn:
            stored = conn.execute(
                "SELECT pickup_location, dropoff_location, pickup_suggested_location, dropoff_suggested_location FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        self.assertEqual(stored["pickup_location"], stored["pickup_suggested_location"])
        self.assertEqual(stored["dropoff_location"], stored["dropoff_suggested_location"])
        self.assertNotIn(stored["pickup_location"], {"大阪", "大阪市内"})
        self.assertNotIn(stored["dropoff_location"], {"京都", "京都市内"})
        with closing(database.get_connection()) as conn:
            snapshot = json.loads(conn.execute(
                "SELECT snapshot_json FROM driver_run_documents WHERE id = ?", (document["id"],)
            ).fetchone()[0])
        snapshot_text = json.dumps(snapshot, ensure_ascii=False)
        self.assertGreaterEqual(snapshot_text.count(stored["pickup_location"]), 2)
        self.assertGreaterEqual(snapshot_text.count(stored["dropoff_location"]), 2)

    def test_document_location_editor_uses_city_pool_preserves_exact_places_and_manual_override(self):
        order_id = self.add_order(suffix="HOTEL-EDIT")
        key = service.list_run_groups("2026-07-24")[0]["key"]
        expected_source_hash = service.get_run_document_preview(key, self.actor)["source_sha256"]
        observed = {}
        for index, raw in enumerate(("大阪", "京都", "奈良", "神户"), 1):
            preview = service.get_run_document_preview(key, self.actor)
            pickup = next(node for node in preview["nodes"] if node["node_type"] == "pickup")
            updated = service.patch_run_document_draft(key, {
                "expected_source_hash": preview["source_sha256"],
                "client_request_id": f"hotel-city-{index}",
                "patches": [{"field_id": f"route_node:{pickup['route_node_id']}:planned_location", "value": raw}],
            }, self.actor)
            pickup_after = next(node for node in updated["nodes"] if node["route_node_id"] == pickup["route_node_id"])
            observed[raw] = pickup_after["planned_location"]
            self.assertNotEqual(pickup_after["planned_location"], raw)

        for index, exact in enumerate(("大阪站", "大阪駅", "KIX"), 1):
            preview = service.get_run_document_preview(key, self.actor)
            pickup = next(node for node in preview["nodes"] if node["node_type"] == "pickup")
            updated = service.patch_run_document_draft(key, {
                "expected_source_hash": preview["source_sha256"],
                "client_request_id": f"hotel-exact-{index}",
                "patches": [{"field_id": f"route_node:{pickup['route_node_id']}:planned_location", "value": exact}],
            }, self.actor)
            pickup_after = next(node for node in updated["nodes"] if node["route_node_id"] == pickup["route_node_id"])
            self.assertEqual(pickup_after["planned_location"], exact)

        manual_hotel = "ホテル日航大阪 正面玄関"
        preview = service.get_run_document_preview(key, self.actor)
        pickup = next(node for node in preview["nodes"] if node["node_type"] == "pickup")
        service.patch_run_document_draft(key, {
            "expected_source_hash": preview["source_sha256"],
            "client_request_id": "hotel-manual-override",
            "patches": [{"field_id": f"route_node:{pickup['route_node_id']}:planned_location", "value": manual_hotel}],
        }, self.actor)
        reopened = service.get_run_document_preview(key, self.actor)
        reopened_pickup = next(node for node in reopened["nodes"] if node["route_node_id"] == pickup["route_node_id"])
        self.assertEqual(reopened_pickup["planned_location"], manual_hotel)
        document = service.generate_run_document(key, self.actor)
        pages = pdf_pages_text(self.document_path(document))
        self.assertIn(manual_hotel, pages[0])
        self.assertIn(manual_hotel, pages[1])
        self.assertNotEqual(expected_source_hash, reopened["source_sha256"])

    def test_online_channels_render_only_as_website(self):
        channels = ["WeChat", "LINE", "WhatsApp", "Kakao", "website"]
        ids = [self.add_order(minute=index * 20, suffix=f"C{index}") for index in range(len(channels))]
        with closing(database.get_connection()) as conn:
            for order_id, channel in zip(ids, channels):
                conn.execute(
                    "UPDATE orders SET source_channel = ?, order_source = ?, agency_name = '予約者' WHERE id = ?",
                    (channel, channel, order_id),
                )
            conn.commit()
        for order_id in ids:
            self.confirm(order_id)
        document = service.generate_run_document(service.list_run_groups("2026-07-24")[0]["key"], self.actor)
        text = pdf_text(self.document_path(document))
        self.assertGreaterEqual(text.count("ウェブサイト"), len(channels))
        for forbidden in ("LINE", "WhatsApp", "Kakao"):
            self.assertNotIn(forbidden, text)
        with closing(database.get_connection()) as conn:
            stored = [row[0] for row in conn.execute("SELECT source_channel FROM orders ORDER BY id").fetchall()]
        self.assertEqual(stored, channels)

    def test_linked_operation_bounds_are_separate_from_pickup_dropoff(self):
        orders = []
        for index, (pickup, dropoff, start, end) in enumerate(
            (("A", "B", "08:00", "09:00"), ("C", "D", "10:00", "11:00"), ("E", "F", "12:00", "13:00")),
            1,
        ):
            orders.append(
                {
                    "order_id": index,
                    "oid": f"ORDER-{index}",
                    "order_date": "2026-10-05",
                    "start_time": start,
                    "end_time": end,
                    "pickup_location": pickup,
                    "dropoff_location": dropoff,
                    "price": 12000,
                    "agency_name": "申込者",
                    "run_revision": 1,
                }
            )
        group = {
            "business_date": "2026-10-05",
            "driver_name": "姚博",
            "plate_number": "なにわ300あ7007",
            "garage_location": "大寅大阪車庫",
            "garage_out_time": "07:00",
            "garage_in_time": "14:00",
            "company": {"company_name": "株式会社大寅"},
            "orders": orders,
        }
        first, middle, last = [build_acceptance_view_model(group, order, index, 3) for index, order in enumerate(orders)]
        self.assertEqual((first["operation_start_place"], first["operation_end_place"]), ("大寅大阪車庫", "B"))
        self.assertEqual((middle["operation_start_place"], middle["operation_end_place"]), ("B", "D"))
        self.assertEqual((last["operation_start_place"], last["operation_end_place"]), ("D", "大寅大阪車庫"))
        self.assertEqual((middle["pickup_place"], middle["dropoff_place"]), ("C", "D"))

    def test_missing_registered_garage_uses_garage_label(self):
        order = {
            "order_id": 1,
            "oid": "GARAGE-FALLBACK",
            "order_date": "2026-10-05",
            "start_time": "08:00",
            "end_time": "09:00",
            "pickup_location": "大阪市内",
            "dropoff_location": "KIX",
            "price": 12460,
            "run_revision": 1,
        }
        group = {
            "business_date": "2026-10-05",
            "driver_name": "姚博",
            "driver_office": "大阪営業所",
            "plate_number": "なにわ300あ7007",
            "company": {"company_name": "株式会社大寅"},
            "orders": [order],
        }
        acceptance = build_acceptance_view_model(group, order, 0, 1)
        dispatch = build_dispatch_view_model(group)
        self.assertEqual(acceptance["operation_start_place"], "車庫")
        self.assertEqual(acceptance["operation_end_place"], "車庫")
        self.assertEqual((dispatch["garage_out"], dispatch["garage_in"]), ("車庫", "車庫"))

    def test_parser_route_note_feeds_v014_stopovers_without_changing_renderer(self):
        order = {
            "pickup_location": "京都ホテル",
            "dropoff_location": "大阪ホテル",
            "fee_remark": "完整路线：京都ホテル -> 勝尾寺 -> 奈良 -> 大阪ホテル",
        }
        self.assertEqual(service._printable_stopovers_from_route_note(order), ["勝尾寺", "奈良"])

    def test_area_warning_marker_is_exposed_for_review_but_not_renderer_text(self):
        order = {
            "fee_remark": "区域确认：KIX → 京都市域交通圏",
            "area_validation_status": "pending",
            "run_confirmation_status": "pending",
            "operations_business_area": "京都市域交通圏",
        }
        self.assertEqual(service._area_review_from_route_note(order), (True, "KIX → 京都市域交通圏"))
        order["area_validation_status"] = "confirmed"
        self.assertEqual(service._area_review_from_route_note(order), (False, ""))
        order["area_validation_status"] = "pending"
        order["run_confirmation_status"] = "confirmed"
        self.assertEqual(service._area_review_from_route_note(order), (False, ""))

    def test_order_confirmation_records_area_acknowledgement(self):
        order_id = self.add_order(suffix="AREA")
        confirmed = self.confirm(order_id)
        self.assertEqual(confirmed["run_confirmation_status"], "confirmed")
        self.assertEqual(confirmed["area_validation_status"], "confirmed")

    def test_v014_dispatch_pagination_matrix(self):
        expected_pages = {1: 2, 4: 2, 6: 2, 7: 2, 8: 2, 10: 2, 11: 4, 16: 4, 20: 4, 21: 6}
        for order_count, expected in expected_pages.items():
            with self.subTest(order_count=order_count):
                orders = []
                for index in range(order_count):
                    hour = 6 + index
                    orders.append(
                        {
                            "order_id": index + 1,
                            "oid": f"PAGE-{order_count}-{index + 1}",
                            "order_date": "2026-10-05",
                            "start_time": f"{hour % 24:02d}:00",
                            "end_time": f"{(hour + 1) % 24:02d}:00",
                            "pickup_location": f"乗車地{index + 1}",
                            "dropoff_location": f"降車地{index + 1}",
                            "order_type": "送机",
                            "document_kind": "airport_transfer",
                            "price": 12460,
                            "agency_name": "申込者",
                            "guest_contact": "06-0000-0000",
                            "source_channel": "WeChat",
                            "run_revision": 1,
                        }
                    )
                group = {
                    "business_date": "2026-10-05",
                    "driver_id": 7,
                    "vehicle_id": 7,
                    "driver_name": "姚博",
                    "driver_office": "大阪営業所",
                    "operations_manager": "胡東锴",
                    "plate_number": "なにわ300あ7007",
                    "garage_location": "大寅大阪車庫",
                    "garage_out_time": "05:30",
                    "garage_in_time": "23:00",
                    "company": {
                        "company_name": "株式会社大寅",
                        "contact_phone": "06-6710-9861",
                    },
                    "orders": orders,
                }
                path = Path(self.temp.name) / f"pagination-{order_count}.pdf"
                page_count = service._render_pdf(group, path)
                reader = PdfReader(str(path))
                self.assertEqual((page_count, len(reader.pages)), (expected, expected))
                text = pdf_text(path)
                for index in range(order_count):
                    self.assertIn(f"乗車地{index + 1}", text)
                    self.assertIn(f"降車地{index + 1}", text)


if __name__ == "__main__":
    unittest.main()

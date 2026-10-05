import tempfile
import unittest
import warnings
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from backend.db import database
from backend.services import dispatch_service
from backend.services import run_document_service as service
from backend.services.v014_document_renderer import build_acceptance_view_model, build_dispatch_view_model
from backend.services.driver_service import list_driver_assignments
from backend.services.notification_service import list_driver_notifications
from backend.services.tenant_context import set_current_tenant_id

warnings.filterwarnings("ignore", category=ResourceWarning)


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
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, '柚子旅行', 'yuzu-test')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (1, 1, '胡东锴', 'HDK', '大阪营业所', 'available', 'available')")
            conn.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (2, 1, '李成志', 'LCZ', '京都营业所', 'available', 'available')")
            conn.execute("INSERT INTO users (id, tenant_id, username, password_hash, role, display_name, phone, profile_type, profile_id, account_scope, is_active) VALUES (101, 1, 'driver-1', 'test', 'driver', '胡东锴', '08000000001', 'driver', 1, 'driver', 1)")
            conn.execute("INSERT INTO users (id, tenant_id, username, password_hash, role, display_name, phone, profile_type, profile_id, account_scope, is_active) VALUES (102, 1, 'driver-2', 'test', 'driver', '李成志', '08000000002', 'driver', 2, 'driver', 1)")
            conn.execute("UPDATE drivers SET user_id = 101 WHERE id = 1")
            conn.execute("UPDATE drivers SET user_id = 102 WHERE id = 2")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status) VALUES (1, 1, '大阪6832', '大阪 500 あ 6832', 'HiAce', 10, 10, 'available')")
            conn.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status) VALUES (2, 1, '京都7011', '京都 300 い 7011', 'Alphard', 7, 7, 'available')")
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

    def document_path(self, document):
        return Path(self.temp.name) / "runtime" / "uploads" / "run_documents" / "1" / "2026-07-24" / document["file_name"]

    def test_confirmation_generation_reuse_and_version(self):
        first = self.add_order(minute=0, suffix="A")
        second = self.add_order(minute=60, suffix="B")
        group = service.list_run_groups("2026-07-24")[0]
        self.assertEqual((group["confirmed_count"], group["pending_count"]), (0, 2))
        self.assertEqual(group["orders"][0]["recommended_price"], 12460)
        draft_document = service.generate_run_document(group["key"], self.actor)
        self.assertEqual((draft_document["version"], draft_document["page_count"]), (1, 3))
        self.confirm(first)
        self.confirm(second)
        group = service.list_run_groups("2026-07-24")[0]
        document = service.generate_run_document(group["key"], self.actor)
        self.assertEqual(document["id"], draft_document["id"])
        self.assertEqual((document["version"], document["page_count"]), (1, 3))
        self.assertEqual(len(PdfReader(str(self.document_path(document))).pages), 3)
        self.assertEqual(service.generate_run_document(group["key"], self.actor)["id"], document["id"])
        self.confirm(first, start_time="09:30")
        updated = service.generate_run_document(group["key"], self.actor)
        self.assertEqual(updated["version"], 2)

    def test_draft_pdf_allows_missing_price_but_publish_blocks(self):
        self.add_order(price=None)
        group = service.list_run_groups("2026-07-24")[0]
        self.assertTrue(any("運賃" in item for item in group["validation_issues"]))
        document = service.generate_run_document(group["key"], self.actor)
        self.assertEqual(document["status"], "generated")
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(str(self.document_path(document))).pages
        )
        self.assertNotIn("DRAFT", text)
        with self.assertRaisesRegex(ValueError, "運賃"):
            service.review_and_publish_run_document(group["key"], self.actor)

    def test_renderer_version_change_forces_a_new_pdf(self):
        self.add_order()
        group_key = service.list_run_groups("2026-07-24")[0]["key"]
        with patch.object(service, "DOCUMENT_RENDERER_VERSION", "test-renderer-a"):
            first = service.generate_run_document(group_key, self.actor)
        with patch.object(service, "DOCUMENT_RENDERER_VERSION", "test-renderer-b"):
            second = service.generate_run_document(group_key, self.actor)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual((first["version"], second["version"]), (1, 2))

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
        with closing(database.get_connection()) as conn:
            before = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (first,)).fetchone())
            conn.execute("UPDATE orders SET pickup_location = 'ホテル日航大阪' WHERE id = ?", (first,))
            conn.commit()
            after = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (first,)).fetchone())
        self.assertTrue(service.mark_order_changed(first, before, after, 1))
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
        self.assertGreater(document["page_count"], len(ids) + 1)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("運 送 引 受 書", text)
        self.assertIn("運 行 指 示 書", text)
        self.assertIn("運行指示書 1/", text)
        self.assertNotIn("中文备注", text)
        for index in range(22):
            self.assertIn(f"SRC260724{index * 5:04d}", text)

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
        reader = PdfReader(str(self.document_path(document)))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertEqual(document["page_count"], 3)
        self.assertIn("CA725", text)
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
        self.assertEqual((document["page_count"], len(reader.pages)), (5, 5))
        pages = [page.extract_text() or "" for page in reader.pages]
        for index in range(4):
            self.assertIn("運 送 引 受 書", pages[index])
            self.assertIn(f"第 {index + 1} 便 ／ 4 件", pages[index])
        self.assertIn("運 行 指 示 書", pages[4])
        self.assertIn("全日 4 件", pages[4])
        acceptance_text = "\n".join(pages[:4])
        for label in (
            "運送の申込者", "申込方法", "運行の開始／終了", "乗車／降車",
            "運賃・料金", "運送引受者", "大阪　本社", "京都営業所",
            "電 話 番 号", "その他連絡先", "営 業 区 域",
        ):
            self.assertIn(label, acceptance_text)
        for fixed_value in (
            "株式会社大寅（大阪本社　京都営業所）",
            "〒551-0013 大阪府大阪市大正区小林西2丁目10-3",
            "〒612-8448 京都府京都市伏見区竹田東小屋ノ内町95",
            "大阪本社　06-6710-9861（代表）",
            "安全統括　阪本 090-1483-4105",
            "大阪市域交通圏・京都市域交通圏",
        ):
            self.assertIn(fixed_value, acceptance_text)
        self.assertNotIn("dispatch@example.invalid", acceptance_text)
        dispatch_text = pages[4]
        for label in (
            "事業者名", "営業所名", "運行管理者", "作成年月日", "運転者の氏名",
            "自動車登録番号", "全運行の開始／終了", "便", "乗降時刻",
            "乗車・降車・立寄り地", "契約の相手方・連絡先", "配車依頼方法",
            "運行の安全確保", "運行管理者", "指示（印）", "運転者", "確認（印）",
        ):
            self.assertIn(label, dispatch_text)

    def test_acceptance_applicant_may_be_blank(self):
        order_id = self.add_order(suffix="BLANK")
        self.confirm(order_id)
        group = service.list_run_groups("2026-07-24")[0]
        vm = build_acceptance_view_model(group, group["orders"][0], 0, 1)
        self.assertEqual(vm["applicant"], "")
        self.assertEqual(vm["applicant_phone"], "")
        self.assertNotIn("applicant", vm["missing_fields"])
        document = service.generate_run_document(group["key"], self.actor)
        first_page = PdfReader(str(self.document_path(document))).pages[0].extract_text() or ""
        self.assertIn("運送の申込者", first_page)
        self.assertNotIn("氏名又は名称：", first_page)

    def test_generic_city_locations_use_the_same_hotel_in_both_documents(self):
        order_id = self.add_order(suffix="CITY")
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE orders SET pickup_location = '大阪市内', dropoff_location = '京都市内' WHERE id = ?",
                (order_id,),
            )
            conn.commit()
        self.confirm(order_id, pickup_location="大阪市内", dropoff_location="京都市内")
        group = service.list_run_groups("2026-07-24")[0]
        acceptance = build_acceptance_view_model(group, group["orders"][0], 0, 1)
        dispatch = build_dispatch_view_model(group)
        self.assertNotIn(acceptance["pickup_place"], {"大阪", "大阪市内"})
        self.assertNotIn(acceptance["dropoff_place"], {"京都", "京都市内"})
        self.assertIn(f"乗車：{acceptance['pickup_place']}", dispatch["rows"][0]["route"])
        self.assertIn(f"降車：{acceptance['dropoff_place']}", dispatch["rows"][0]["route"])
        document = service.generate_run_document(group["key"], self.actor)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(self.document_path(document))).pages)
        self.assertGreaterEqual(text.count(acceptance["pickup_place"]), 2)
        self.assertGreaterEqual(text.count(acceptance["dropoff_place"]), 2)

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
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(self.document_path(document))).pages)
        self.assertGreaterEqual(text.count("ウェブサイト"), len(channels))
        for forbidden in ("WeChat", "LINE", "WhatsApp", "Kakao", "SNS"):
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
        order = {"fee_remark": "区域确认：KIX → 京都市域交通圏"}
        self.assertEqual(service._area_review_from_route_note(order), (True, "KIX → 京都市域交通圏"))

    def test_v014_dispatch_pagination_matrix(self):
        expected_pages = {1: 2, 4: 5, 7: 8, 8: 9, 10: 11, 11: 13, 16: 19}
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
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                for index in range(order_count):
                    self.assertIn(f"PAGE-{order_count}-{index + 1}", text)


if __name__ == "__main__":
    unittest.main()

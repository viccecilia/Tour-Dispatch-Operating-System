import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database
from backend.services.document_model_service import (
    DAILY_INSPECTION_CONTRACT,
    ROUTE_NODE_ACTUAL_CONTRACT,
    ROUTE_NODE_CONTRACT,
    build_document_snapshot,
    classify_order,
    future_data_contracts,
    normalize_airport_location,
    persist_route_nodes,
    prepare_order_document_fields,
    record_document_event,
    shift_date_time,
    snapshot_source_sha256,
    strip_contact_channels,
    upsert_document_batch,
    validate_document_snapshot,
)
from backend.services.hotel_pool_service import normalize_city_place


class DocumentModelServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "document-model.sqlite3"
        database.init_db(seed=False)

    def tearDown(self):
        database.DB_PATH = self.original_db
        self.temp.cleanup()

    @staticmethod
    def order(index=1, **overrides):
        value = {
            "order_id": index,
            "oid": f"AIR-{index:03d}",
            "order_date": "2026-10-10",
            "start_time": "08:00",
            "end_time": "09:00",
            "pickup_location": "KIX T1 北口",
            "dropoff_location": "大阪市内ホテル",
            "order_type": "空港送迎",
            "price": 24000,
            "parking_fee_jpy": None,
            "printable_stopovers": [],
        }
        value.update(overrides)
        return value

    @classmethod
    def group(cls, count=1, **order_overrides):
        return {
            "tenant_id": 1,
            "business_date": "2026-10-10",
            "driver_id": 7,
            "driver_name": "試験運転者",
            "driver_office": "大阪営業所",
            "vehicle_id": 8,
            "plate_number": "大阪 300 あ 1234",
            "vehicle_type": "HiAce",
            "operations_manager": "運行管理者",
            "garage_location": "大阪車庫",
            "company": {"company_name": "株式会社大寅"},
            "orders": [cls.order(index, **order_overrides) for index in range(1, count + 1)],
        }

    def test_migration_adds_snapshot_and_future_tables_without_fake_rows(self):
        with closing(database.get_connection()) as conn:
            order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
            document_columns = {row["name"] for row in conn.execute("PRAGMA table_info(driver_run_documents)")}
            self.assertTrue({
                "document_kind", "applicant_slot", "pickup_source_text",
                "pickup_parsed_location", "pickup_suggested_location",
                "price_confirmed", "tax_included_confirmed", "price_snapshot_json",
                "end_time_source", "end_time_confirmed",
            }.issubset(order_columns))
            self.assertTrue({
                "document_id", "document_version_id", "run_group_id", "lifecycle_status",
                "snapshot_json", "source_sha256", "pdf_sha256",
            }.issubset(document_columns))
            for table in (
                "dispatch_document_batches", "dispatch_route_nodes",
                "dispatch_route_node_actuals", "driver_daily_inspections",
                "dispatch_document_receipts", "dispatch_document_events",
                "dispatch_route_node_overrides",
            ):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_migration_preserves_and_identifies_legacy_document_rows(self):
        legacy_path = Path(self.temp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
            for migration in sorted(database.MIGRATIONS_PATH.glob("*.sql")):
                if migration.name == "20261009_document_model_phase2a.sql":
                    break
                conn.executescript(migration.read_text(encoding="utf-8"))
            conn.execute(
                """
                INSERT INTO driver_run_documents (
                    tenant_id, business_date, driver_id, vehicle_id, version, status,
                    source_hash, file_name, file_path, file_url
                ) VALUES (1, '2026-10-09', 7, 8, 1, 'published',
                          'legacy-source', 'legacy.pdf', '/legacy/legacy.pdf', '/auth/file')
                """
            )
            conn.executescript(
                (database.MIGRATIONS_PATH / "20261009_document_model_phase2a.sql").read_text(encoding="utf-8")
            )
            row = conn.execute("SELECT * FROM driver_run_documents").fetchone()
            self.assertEqual(row["status"], "published")
            self.assertEqual(row["lifecycle_status"], "published")
            self.assertEqual(row["source_sha256"], "legacy-source")
            self.assertTrue(row["document_id"].startswith("legacy-document-"))
            self.assertTrue(row["document_version_id"].startswith("legacy-version-"))
        finally:
            conn.close()

    def test_airport_normalization_preserves_detail_and_never_rewrites_hotel(self):
        self.assertEqual(normalize_airport_location("関西国際空港 T1 北口"), "KIX T1 北口")
        self.assertEqual(normalize_airport_location("关空T1"), "KIX T1")
        self.assertEqual(normalize_airport_location("関西"), "KIX")
        self.assertEqual(normalize_airport_location("kix第2ターミナル"), "KIX 第2ターミナル")
        self.assertEqual(normalize_airport_location("伊丹空港 南ターミナル"), "ITM 南ターミナル")
        self.assertEqual(normalize_airport_location("神户机场 2号集合点"), "UKB 2号集合点")
        self.assertEqual(normalize_airport_location("関西大学正門"), "関西大学正門")
        self.assertEqual(normalize_airport_location("大阪市内ホテル"), "大阪市内ホテル")

    def test_city_hotel_prefill_is_stable_and_never_fabricates_missing_pools(self):
        first, first_changed = normalize_city_place("大阪市内", "order:77:pickup")
        second, second_changed = normalize_city_place("大阪市内", "order:77:pickup")
        self.assertTrue(first_changed)
        self.assertTrue(second_changed)
        self.assertEqual(first, second)
        self.assertNotIn(first, {"大阪", "大阪市内"})
        self.assertEqual(normalize_city_place("大阪市内ホテル", "order:77:pickup"), (first, True))
        self.assertEqual(normalize_city_place("奈良市内", "order:77:dropoff"), ("奈良市内", False))
        self.assertEqual(normalize_city_place("神戸市内", "order:77:dropoff"), ("神戸市内", False))

    def test_channel_annotations_are_separated_from_location_text(self):
        self.assertEqual(strip_contact_channels("大阪市内ホテル / WeChat:abc123"), "大阪市内ホテル")
        self.assertEqual(strip_contact_channels("KIX T1，LINE：driver77"), "KIX T1")

    def test_generic_city_hotel_is_persisted_once_with_source_and_unconfirmed_candidate(self):
        with closing(database.get_connection()) as conn:
            order_id = conn.execute(
                """INSERT INTO orders (
                    tenant_id, oid, order_date, start_time, end_time,
                    pickup_location, dropoff_location, order_type, price
                ) VALUES (1, 'CITY-PREFILL', '2026-10-10', '08:00', '09:00',
                          '大阪市内ホテル', 'KIX', '送机', 24000)"""
            ).lastrowid
            group = self.group()
            group["orders"] = [{**self.order(), "order_id": order_id, "pickup_location": "大阪市内ホテル", "dropoff_location": "KIX"}]
            prepare_order_document_fields(conn, group)
            first = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
            group["orders"] = [first]
            prepare_order_document_fields(conn, group)
            second = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        self.assertEqual(first["pickup_source_text"], "大阪市内ホテル")
        self.assertEqual(first["pickup_parsed_location"], "大阪市内ホテル")
        self.assertEqual(first["pickup_location"], first["pickup_suggested_location"])
        self.assertNotEqual(first["pickup_location"], "大阪市内ホテル")
        self.assertEqual(first["pickup_location_confirmed"], 0)
        self.assertEqual(second["pickup_location"], first["pickup_location"])
        self.assertEqual(second["pickup_suggested_location"], first["pickup_suggested_location"])

    def test_classification_tracks_changed_business_content(self):
        order = self.order(document_kind="airport_transfer")
        self.assertEqual(classify_order(order), "airport_transfer")
        order.update(order_type="貸切観光", pickup_location="日本橋", dropoff_location="嵐山")
        self.assertEqual(classify_order(order), "charter")

    def test_date_shift_keeps_the_calendar_rollover(self):
        self.assertEqual(
            shift_date_time("2026-10-10", "00:30", -60),
            {"date": "2026-10-09", "time": "23:30", "at": "2026-10-09T23:30:00"},
        )
        self.assertEqual(
            shift_date_time("2026-10-10", "23:30", 60),
            {"date": "2026-10-11", "time": "00:30", "at": "2026-10-11T00:30:00"},
        )
        snapshot = build_document_snapshot(self.group(start_time="00:30", end_time="23:30"))
        self.assertEqual(snapshot["route_nodes"][0]["business_date"], "2026-10-09")
        self.assertEqual(snapshot["route_nodes"][0]["planned_departure_at"], "2026-10-09T23:30:00")
        self.assertEqual(snapshot["route_nodes"][-1]["business_date"], "2026-10-11")
        self.assertEqual(snapshot["route_nodes"][-1]["planned_arrival_at"], "2026-10-11T00:30:00")

    def test_missing_airport_end_time_is_persisted_as_unconfirmed_plus_60_minutes(self):
        with closing(database.get_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    tenant_id, oid, order_date, start_time, pickup_location,
                    dropoff_location, order_type, price
                ) VALUES (1, 'AIR-LATE', '2026-10-10', '23:30', 'KIX T1',
                          '大阪市内ホテル', '空港送迎', 24000)
                """
            )
            order_id = cursor.lastrowid
            group = self.group()
            group["orders"] = [{**self.order(), "order_id": order_id, "start_time": "23:30", "end_time": None}]
            prepare_order_document_fields(conn, group)
            row = conn.execute("SELECT end_date, end_time, end_time_source, end_time_confirmed FROM orders WHERE id = ?", (order_id,)).fetchone()
            conn.commit()
        self.assertEqual((row["end_date"], row["end_time"]), ("2026-10-11", "00:30"))
        self.assertEqual(row["end_time_source"], "suggested_60m")
        self.assertEqual(row["end_time_confirmed"], 0)

    def test_only_marked_legacy_auto_time_is_repaired_and_ambiguous_or_manual_time_is_protected(self):
        with closing(database.get_connection()) as conn:
            legacy_id = conn.execute(
                """INSERT INTO orders (
                    tenant_id, oid, order_date, end_date, start_time, end_time,
                    pickup_location, dropoff_location, order_type, price, daily_import_group_key,
                    end_time_source, end_time_confirmed
                ) VALUES (1, 'LEGACY-120', '2026-10-10', '2026-10-10', '09:30', '11:30',
                          '大阪市内', 'KIX', '送机', 24000, 'daily-group', 'legacy_suggested_120m', 0)"""
            ).lastrowid
            ambiguous_id = conn.execute(
                """INSERT INTO orders (
                    tenant_id, oid, order_date, end_date, start_time, end_time,
                    pickup_location, dropoff_location, order_type, price, daily_import_group_key,
                    end_time_source, end_time_confirmed
                ) VALUES (1, 'AMBIGUOUS-120', '2026-10-10', '2026-10-10', '09:30', '11:30',
                          '大阪市内', 'KIX', '送机', 24000, 'daily-group', NULL, 0)"""
            ).lastrowid
            manual_id = conn.execute(
                """INSERT INTO orders (
                    tenant_id, oid, order_date, end_date, start_time, end_time,
                    pickup_location, dropoff_location, order_type, price, daily_import_group_key,
                    end_time_source, end_time_confirmed
                ) VALUES (1, 'MANUAL-120', '2026-10-10', '2026-10-10', '09:30', '11:30',
                          '大阪市内', 'KIX', '送机', 24000, 'daily-group', 'explicit', 0)"""
            ).lastrowid
            group = self.group()
            group["orders"] = [
                {**self.order(), "order_id": legacy_id, "start_time": "09:30", "end_time": "11:30", "daily_import_group_key": "daily-group", "end_time_source": "legacy_suggested_120m", "end_time_confirmed": 0},
                {**self.order(2), "order_id": ambiguous_id, "start_time": "09:30", "end_time": "11:30", "daily_import_group_key": "daily-group", "end_time_source": None, "end_time_confirmed": 0},
                {**self.order(3), "order_id": manual_id, "start_time": "09:30", "end_time": "11:30", "daily_import_group_key": "daily-group", "end_time_source": "explicit", "end_time_confirmed": 0},
            ]
            prepare_order_document_fields(conn, group, repair_legacy_daily_defaults=True)
            rows = [dict(row) for row in conn.execute("SELECT oid, end_time, end_time_source, end_time_confirmed FROM orders WHERE id IN (?, ?, ?) ORDER BY id", (legacy_id, ambiguous_id, manual_id)).fetchall()]
        self.assertEqual((rows[0]["end_time"], rows[0]["end_time_source"], rows[0]["end_time_confirmed"]), ("10:30", "suggested_60m", 0))
        self.assertEqual((rows[1]["end_time"], rows[1]["end_time_source"], rows[1]["end_time_confirmed"]), ("11:30", None, 0))
        self.assertEqual((rows[2]["end_time"], rows[2]["end_time_source"], rows[2]["end_time_confirmed"]), ("11:30", "explicit", 0))
        snapshot = build_document_snapshot(group)
        self.assertIn("order_2_arrival_time_source_confirmation_required", validate_document_snapshot(snapshot))
        self.assertNotIn("order_3_arrival_time_source_confirmation_required", validate_document_snapshot(snapshot))

    def test_contract_party_uses_per_order_applicant_unless_explicit_agency_is_set(self):
        group = self.group(2)
        group["orders"] = [
            self.order(applicant_slot=2, agency_name="", guest_name="乘客姓名"),
            self.order(2, applicant_slot=3, agency_name="SPI", guest_name="另一位乘客"),
        ]
        snapshot = build_document_snapshot(group)
        self.assertEqual(snapshot["orders"][0]["applicant_name"], "KKday")
        self.assertEqual(snapshot["orders"][0]["contract_party_name"], "KKday")
        self.assertEqual(snapshot["orders"][0]["contract_party_source"], "applicant_slot")
        self.assertEqual(snapshot["orders"][1]["applicant_name"], "Klook")
        self.assertEqual(snapshot["orders"][1]["contract_party_name"], "SPI")
        self.assertEqual(snapshot["orders"][1]["contract_party_source"], "agency_name")

    def test_applicant_slot_is_persisted_and_not_auto_confirmed(self):
        with closing(database.get_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    tenant_id, oid, order_date, start_time, pickup_location,
                    dropoff_location, order_type, price, applicant_slot
                ) VALUES (1, 'AIR-001', '2026-10-10', '08:00', 'KIX T1',
                          '大阪市内ホテル', '空港送迎', 24000, 9)
                """
            )
            order_id = cursor.lastrowid
            group = self.group()
            group["orders"] = [{**self.order(), "order_id": order_id}]
            prepare_order_document_fields(conn, group)
            first = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
            prepare_order_document_fields(conn, group)
            second = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
            conn.commit()
        self.assertIn(first["applicant_slot"], (1, 2, 3, 4))
        self.assertEqual(second["applicant_slot"], first["applicant_slot"])
        self.assertEqual(first["applicant_slot_confirmed"], 0)
        self.assertEqual(first["price_confirmed"], 0)
        self.assertEqual(json.loads(first["price_snapshot_json"])["confirmed"], False)

    def test_airport_pages_keep_all_orders_and_route_ids_are_stable(self):
        first = build_document_snapshot(self.group(21), "docv-first")
        second = build_document_snapshot(self.group(21), "docv-second")
        self.assertEqual([len(page) for page in first["airport_acceptance_pages"]], [10, 10, 1])
        self.assertEqual(sum(map(len, first["airport_acceptance_pages"])), 21)
        self.assertEqual(
            [node["route_node_id"] for node in first["route_nodes"]],
            [node["route_node_id"] for node in second["route_nodes"]],
        )
        self.assertEqual(snapshot_source_sha256(first), snapshot_source_sha256(second))

    def test_route_node_override_updates_both_acceptance_and_dispatch_views(self):
        first = build_document_snapshot(self.group(), "docv-before")
        pickup = next(node for node in first["route_nodes"] if node["node_type"] == "pickup")
        group = self.group()
        group["route_node_overrides"] = [{
            "route_node_id": pickup["route_node_id"],
            "planned_location": "ホテル日航大阪 2F",
            "planned_arrival_at": pickup["planned_arrival_at"],
            "planned_departure_at": "2026-10-10T08:30:00",
            "location_confirmed": 1,
            "changed_fields": ["planned_location", "planned_departure_at"],
        }]
        updated = build_document_snapshot(group, "docv-after")
        updated_pickup = next(node for node in updated["route_nodes"] if node["route_node_id"] == pickup["route_node_id"])
        self.assertEqual(updated_pickup["planned_location"], "ホテル日航大阪 2F")
        self.assertEqual(updated_pickup["planned_departure_at"], "2026-10-10T08:30:00")
        self.assertEqual(updated["orders"][0]["locations"]["pickup"]["confirmed"], "ホテル日航大阪 2F")
        self.assertEqual(updated["orders"][0]["pickup_at"], "2026-10-10T08:30:00")

    def test_snapshot_separates_location_and_money_states(self):
        snapshot = build_document_snapshot(self.group())
        order = snapshot["orders"][0]
        self.assertEqual(order["locations"]["pickup"]["raw"], "KIX T1 北口")
        self.assertEqual(order["locations"]["pickup"]["parsed"], "KIX T1 北口")
        self.assertEqual(order["locations"]["pickup"]["suggested"], "")
        self.assertFalse(order["locations"]["pickup"]["is_confirmed"])
        self.assertFalse(order["money"]["price_confirmed"])
        self.assertIsNone(order["money"]["toll_fee_jpy"])
        self.assertIsNone(order["money"]["parking_fee_jpy"])
        self.assertIn("order_1_price_confirmation_required", validate_document_snapshot(snapshot))
        self.assertNotIn("order_1_parking_fee_jpy_required", validate_document_snapshot(snapshot))

    def test_publish_validation_accepts_a_fully_confirmed_snapshot(self):
        snapshot = build_document_snapshot(self.group(
            applicant_slot=1,
            applicant_slot_confirmed=1,
            pickup_location_confirmed=1,
            dropoff_location_confirmed=1,
            fare_jpy=20000,
            service_fee_jpy=2000,
            document_advance_jpy=0,
            toll_fee_jpy=1000,
            parking_fee_jpy=1000,
            price_confirmed=1,
            tax_included_confirmed=1,
            area_validation_status="confirmed",
            run_confirmation_status="confirmed",
        ))
        self.assertEqual(validate_document_snapshot(snapshot), [])
        self.assertTrue(snapshot["publish_ready"])

    def test_multiday_charter_keeps_manual_locations_and_days(self):
        days = [
            {"date": "2026-10-10", "nodes": [{"sequence_number": 1, "location": "日本橋駅2番出口"}]},
            {"date": "2026-10-11", "nodes": [{"sequence_number": 1, "location": "熊野本宮大社"}]},
        ]
        snapshot = build_document_snapshot(self.group(
            order_type="貸切観光",
            pickup_location="日本橋駅2番出口",
            dropoff_location="京都駅八条口",
            remark=json.dumps({"days": days}, ensure_ascii=False),
        ))
        self.assertEqual(snapshot["airport_acceptance_pages"], [])
        self.assertEqual(len(snapshot["charter_contracts"]), 1)
        contract = snapshot["charter_contracts"][0]
        self.assertEqual(contract["passenger_pickup"], "日本橋駅2番出口")
        self.assertEqual(contract["passenger_dropoff"], "京都駅八条口")
        self.assertEqual([day["date"] for day in contract["days"]], ["2026-10-10", "2026-10-11"])
        self.assertEqual(
            [day["nodes"][0]["location"] for day in contract["days"]],
            ["日本橋駅2番出口", "熊野本宮大社"],
        )
        charter_nodes = [node for node in snapshot["route_nodes"] if node.get("order_id") == 1]
        self.assertEqual([node["business_date"] for node in charter_nodes], ["2026-10-10", "2026-10-11"])
        self.assertTrue(all(node["route_node_id"].startswith("node-") for node in charter_nodes))

    def test_charter_draft_route_node_ids_survive_document_snapshot(self):
        days = [{
            "date": "2026-10-10",
            "nodes": [
                {"route_node_id": "node-draft-pickup", "location": "地下鉄なんば駅14番出口", "departure_time": "09:00"},
                {"route_node_id": "node-draft-dropoff", "location": "京都駅八条口", "arrival_time": "18:00"},
            ],
        }]
        snapshot = build_document_snapshot(self.group(
            order_type="包车",
            pickup_location="地下鉄なんば駅14番出口",
            dropoff_location="京都駅八条口",
            remark=json.dumps({"fixed_tour": {"days": days}}, ensure_ascii=False),
        ))
        contract_nodes = snapshot["charter_contracts"][0]["days"][0]["nodes"]
        self.assertEqual(
            [node["route_node_id"] for node in contract_nodes],
            ["node-draft-pickup", "node-draft-dropoff"],
        )

    def test_persistence_contract_stores_batches_nodes_and_events(self):
        snapshot = build_document_snapshot(self.group(), "docv-persist")
        actor = {"id": 9, "tenant_id": 1, "role": "operations_manager", "display_name": "運行管理者"}
        with closing(database.get_connection()) as conn:
            upsert_document_batch(conn, snapshot)
            persist_route_nodes(conn, snapshot)
            record_document_event(conn, snapshot, "generated", actor, {"version_number": 1})
            conn.commit()
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM dispatch_document_batches").fetchone()[0], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM dispatch_route_nodes").fetchone()[0],
                len(snapshot["route_nodes"]),
            )
            self.assertEqual(conn.execute("SELECT event_type FROM dispatch_document_events").fetchone()[0], "generated")

    def test_future_contracts_keep_plan_actual_and_inspection_separate(self):
        contracts = future_data_contracts()
        self.assertEqual(contracts["route_node"], ROUTE_NODE_CONTRACT)
        self.assertEqual(contracts["route_node_actual"], ROUTE_NODE_ACTUAL_CONTRACT)
        self.assertEqual(contracts["daily_inspection"], DAILY_INSPECTION_CONTRACT)
        self.assertNotIn("actual_arrival_at", ROUTE_NODE_CONTRACT["planned_only"])
        self.assertIn("actual_arrival_at", ROUTE_NODE_ACTUAL_CONTRACT["actual_only"])
        self.assertEqual(
            DAILY_INSPECTION_CONTRACT["separate_from"],
            ("three_month_inspection", "statutory_vehicle_inspection"),
        )


if __name__ == "__main__":
    unittest.main()

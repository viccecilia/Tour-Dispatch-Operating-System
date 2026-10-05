import re
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database
from backend.services import parser_service
from backend.services.hotel_pool_service import hotel_pool
from backend.services.tenant_context import set_current_tenant_id


SAMPLE = """10/5董星 3827
1️⃣09:00ホテルカンラ京都 ⇒ 京都市内観光４時間
ガイド：坂口千久子：090-9887-3549
2️⃣13:00 京都单送天桥立 line"""


class DailyAssignmentParserTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "daily-parser.sqlite3"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, '柚子旅行', 'yuzu-test')")
            conn.commit()

    def tearDown(self):
        database.DB_PATH = self.original_db
        set_current_tenant_id(None)
        self.temp.cleanup()

    def parsed(self):
        return parser_service.parse_daily_assignment_text(SAMPLE)

    def test_1_parses_driver_vehicle_and_two_orders(self):
        result = self.parsed()
        self.assertEqual((result["group_count"], result["order_count"]), (1, 2))
        group = result["groups"][0]
        self.assertEqual((group["driverName"], group["vehicleCode"]), ("董星", "3827"))
        first, second = group["orders"]
        self.assertEqual((first["time"], first["parsed"]["pickup_location"], first["parsed"]["dropoff_location"]), ("09:00", "ホテルカンラ京都", "京都市内観光４時間"))
        self.assertIsNone(first["parsed"].get("price"))
        self.assertIn("坂口千久子", first["remark"])
        self.assertIn("090-9887-3549", first["remark"])
        self.assertEqual(second["time"], "13:00")
        self.assertIn(second["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("京都")})
        self.assertEqual(second["parsed"]["dropoff_location"], "天橋立")
        self.assertIsNone(second["parsed"].get("price"))
        self.assertEqual(second["parsed"]["source_channel"], "LINE")

    def test_2_guide_line_does_not_create_order(self):
        orders = self.parsed()["groups"][0]["orders"]
        self.assertEqual(len(orders), 2)
        self.assertFalse(any(order["time"] == "" for order in orders))

    def test_3_guide_line_does_not_create_driver_group(self):
        groups = self.parsed()["groups"]
        self.assertEqual([group["driverName"] for group in groups], ["董星"])

    def test_4_empty_driver_groups_are_not_returned(self):
        result = parser_service.parse_daily_assignment_text("10/5环球等救急 9999\n备注：暂未安排\n" + SAMPLE)
        self.assertTrue(result["groups"])
        self.assertTrue(all(len(group["orders"]) >= 1 for group in result["groups"]))
        self.assertNotIn("环球等救急", [group["driverName"] for group in result["groups"]])

    def test_5_double_arrow_route_is_split(self):
        order = self.parsed()["groups"][0]["orders"][0]
        self.assertEqual(order["route"], "ホテルカンラ京都 → 京都市内観光４時間")

    def test_6_single_delivery_route_is_split(self):
        order = self.parsed()["groups"][0]["orders"][1]
        self.assertNotEqual(order["parsed"]["pickup_location"], "京都")
        self.assertTrue(order["route"].endswith(" → 天橋立"))
        self.assertNotIn("单送", order["route"])

    def test_7_city_aliases_use_existing_hotel_pools_once(self):
        text = "10/5胡东锴 6832\n1️⃣10:00 大阪-京都 微信*"
        first = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        second = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        osaka_names = {item["name"] for item in hotel_pool("大阪")}
        kyoto_names = {item["name"] for item in hotel_pool("京都")}
        self.assertIn(first["parsed"]["pickup_location"], osaka_names)
        self.assertIn(first["parsed"]["dropoff_location"], kyoto_names)
        self.assertEqual(first["route"], second["route"])
        self.assertNotIn("微信", first["route"])
        self.assertNotIn("*", first["route"])

    def test_7a_excel_hotel_asset_is_the_server_pool(self):
        osaka = hotel_pool("大阪")
        kyoto = hotel_pool("京都")
        self.assertEqual((len(osaka), len(kyoto)), (177, 130))
        self.assertIn("ホテル日航大阪", {item["name"] for item in osaka})
        self.assertIn("ホテルグランヴィア京都", {item["name"] for item in kyoto})
        self.assertNotIn("ザ・リッツ・カールトン大阪", {item["name"] for item in kyoto})

    def test_7b_channel_and_symbols_never_pollute_locations(self):
        text = "10/5胡东锴 6832\n1️⃣10:00 京都市内-岚山 微信*"
        order = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        self.assertIn(order["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("京都")})
        self.assertEqual(order["parsed"]["dropoff_location"], "嵐山")
        self.assertEqual(order["parsed"]["source_channel"], "WeChat")
        self.assertNotRegex(order["route"], r"微信|\*")

    def test_7c_explicit_hotel_and_airports_are_not_replaced(self):
        hotel = parser_service.parse_daily_assignment_text(
            "10/5董星 3827\n1️⃣09:00 ホテルカンラ京都-大阪 微信"
        )["groups"][0]["orders"][0]
        self.assertEqual(hotel["parsed"]["pickup_location"], "ホテルカンラ京都")
        airport = parser_service.parse_daily_assignment_text(
            "10/5董星 3827\n1️⃣09:00 KIX-ITM LINE\n2️⃣12:00 ITM-UKB Whatsup"
        )["groups"][0]["orders"]
        self.assertEqual((airport[0]["parsed"]["pickup_location"], airport[0]["parsed"]["dropoff_location"]), ("KIX", "ITM"))
        self.assertEqual((airport[1]["parsed"]["pickup_location"], airport[1]["parsed"]["dropoff_location"]), ("ITM", "UKB"))
        self.assertEqual(airport[1]["parsed"]["source_channel"], "WhatsApp")

    def test_8_confirmed_server_order_retains_guide_remark(self):
        order = self.parsed()["groups"][0]["orders"][0]
        draft_data = dict(order["parsed"])
        draft_data.update({
            "source_type": "daily_assignment",
            "parse_status": "parsed",
            "remark": order["remark"],
            "source_channel": "daily_assignment",
        })
        draft = parser_service.create_draft(draft_data)
        confirmed = parser_service.confirm_draft(str(draft["id"]))
        with closing(database.get_connection()) as conn:
            stored = conn.execute("SELECT remark, guest_contact FROM orders WHERE id = ?", (confirmed["order_id"],)).fetchone()
        self.assertIn("ガイド：坂口千久子：090-9887-3549", stored["remark"])
        self.assertIsNone(stored["guest_contact"])

    def test_9_null_parse_status_does_not_break_draft_update(self):
        order = self.parsed()["groups"][0]["orders"][0]
        draft_data = dict(order["parsed"])
        draft_data["parse_status"] = "parsed"
        draft = parser_service.create_draft(draft_data)
        updated = parser_service.update_draft(str(draft["id"]), {"parse_status": None, "remark": order["remark"]})
        self.assertEqual(updated["parse_status"], draft["parse_status"])
        self.assertIn("坂口千久子", updated["remark"])

    def test_10_star_fullwidth_colon_and_person_name_do_not_drop_order(self):
        text = "10/5姚博 7007\n3️⃣*13：00大阪送临空（KANG MINKU）公司单"
        order = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        self.assertEqual(order["time"], "13:00")
        self.assertIn(order["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("大阪")})
        self.assertEqual(order["parsed"]["dropoff_location"], "りんくうタウン")
        self.assertEqual(order["parsed"]["guest_name"], "KANG MINKU")
        self.assertNotIn("KANG MINKU", order["route"])

    def test_11_bare_airport_pickup_is_retained_as_unresolved(self):
        text = "10/5姚博 7007\n4️⃣14:50接机 公司单"
        order = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        self.assertEqual((order["time"], order["type"]), ("14:50", "接机"))
        self.assertEqual((order["parsed"]["pickup_location"], order["parsed"]["dropoff_location"]), ("待补", "待补"))
        self.assertEqual(order["route"], "接机 · 地点待补")
        self.assertIn("公司单", order["remark"])

    def test_12_delivery_to_shin_osaka_preserves_direction(self):
        text = "10/5姚博 7007\n1️⃣7:45 送新大阪站 公司单"
        order = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        self.assertIn(order["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("大阪")})
        self.assertEqual(order["parsed"]["dropoff_location"], "新大阪駅")
        self.assertNotEqual(order["parsed"]["pickup_location"], "新大阪駅")

    def test_13_osaka_to_rinkuu_keeps_channel_out_of_locations(self):
        text = "10/5姚博 7007\n2️⃣10:15 大阪单送临空城 微信"
        order = parser_service.parse_daily_assignment_text(text)["groups"][0]["orders"][0]
        self.assertEqual(order["parsed"]["source_channel"], "WeChat")
        self.assertIn(order["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("大阪")})
        self.assertEqual(order["parsed"]["dropoff_location"], "りんくうタウン")
        self.assertNotRegex(order["route"], r"微信|WeChat")

    def test_14_full_yao_bo_sample_has_four_orders(self):
        text = """10/5姚博 7007
1️⃣7:45 送新大阪站 公司单
2️⃣10:15 大阪单送临空城 微信
3️⃣*13：00大阪送临空（KANG MINKU）公司单
4️⃣14:50接机 公司单"""
        result = parser_service.parse_daily_assignment_text(text)
        self.assertEqual((result["group_count"], result["order_count"]), (1, 4))
        self.assertEqual([item["time"] for item in result["groups"][0]["orders"]], ["07:45", "10:15", "13:00", "14:50"])

    def test_15_toyooka_airport_channel_and_group_note_are_separated(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24李成志7011\n1️⃣04:30 豊岡市送机关西 WhatsApp在群里"
        )["groups"][0]["orders"][0]
        self.assertEqual((order["parsed"]["pickup_location"], order["parsed"]["dropoff_location"]), ("豊岡市", "KIX"))
        self.assertEqual(order["parsed"]["source_channel"], "WhatsApp")
        self.assertIn("在群里", order["remark"])
        self.assertNotRegex(order["route"], r"在群里|WhatsApp")

    def test_16_contextual_kix_inference_keeps_settlement_and_water_note(self):
        orders = parser_service.parse_daily_assignment_text(
            "7/24李成志7011\n1️⃣04:30 豊岡市送机关西 WhatsApp在群里\n2️⃣12:40接机京都 日元结算 备水3瓶"
        )["groups"][0]["orders"]
        second = orders[1]
        self.assertEqual(second["parsed"]["pickup_location"], "KIX")
        self.assertIn(second["parsed"]["dropoff_location"], {item["name"] for item in hotel_pool("京都")})
        self.assertEqual(second["parsed"]["driver_settlement_note"], "日元结算")
        self.assertIn("备水3瓶", second["remark"])
        self.assertTrue(second["airportInferred"])
        self.assertTrue(second["areaWarning"])

    def test_17_settlement_never_enters_city_route(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24林泽群3893\n1️⃣10:45 京都-大阪 日元结算"
        )["groups"][0]["orders"][0]
        self.assertEqual(order["parsed"]["driver_settlement_note"], "日元结算")
        self.assertNotIn("日元结算", order["route"])
        self.assertNotIn("日元结算", order["parsed"]["dropoff_location"])

    def test_18_charter_keeps_all_route_nodes(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24高弘强1006\n09:00 京都-胜尾寺-奈良-大阪 包车 line"
        )["groups"][0]["orders"][0]
        self.assertEqual(order["type"], "包车")
        self.assertEqual(len(order["routeNodes"]), 4)
        self.assertEqual(order["routeNodes"][1:3], ["勝尾寺", "奈良"])
        self.assertIn(order["routeNodes"][0], {item["name"] for item in hotel_pool("京都")})
        self.assertIn(order["routeNodes"][-1], {item["name"] for item in hotel_pool("大阪")})
        self.assertEqual(order["parsed"]["source_channel"], "LINE")
        self.assertNotRegex(order["route"], r"包车|line|LINE")

    def test_19_kix_kyoto_flight_and_settlement_are_separated(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24林泽群3893\n1️⃣14:50 关西-京都 CX564 日元结算"
        )["groups"][0]["orders"][0]
        self.assertEqual(order["parsed"]["pickup_location"], "KIX")
        self.assertIn(order["parsed"]["dropoff_location"], {item["name"] for item in hotel_pool("京都")})
        self.assertEqual(order["parsed"]["flight_number"], "CX564")
        self.assertEqual(order["parsed"]["driver_settlement_note"], "日元结算")
        self.assertNotIn("日元结算", order["route"])

    def test_20_kix_aliases_are_normalized_only_as_route_tokens(self):
        aliases = ["关西", "关空", "関空", "関西国際空港", "KIX", "Kansai Airport", "Kansai International Airport"]
        for index, alias in enumerate(aliases):
            with self.subTest(alias=alias):
                order = parser_service.parse_daily_assignment_text(
                    f"7/24测试司机{7100 + index}\n10:00 {alias}接机大阪"
                )["groups"][0]["orders"][0]
                self.assertEqual(order["parsed"]["pickup_location"], "KIX")

    def test_21_itm_and_ukb_explicit_aliases_normalize_but_plain_itami_does_not(self):
        result = parser_service.parse_daily_assignment_text(
            "7/24李力6781\n1️⃣18:00 神户机场接机大阪 儿童座椅2 line\n2️⃣21:35关西接机伊丹 微信"
        )["groups"][0]["orders"]
        self.assertEqual(result[0]["parsed"]["pickup_location"], "UKB")
        self.assertEqual(result[0]["parsed"]["source_channel"], "LINE")
        self.assertEqual(result[1]["parsed"]["pickup_location"], "KIX")
        self.assertEqual(result[1]["parsed"]["dropoff_location"], "伊丹")
        itm = parser_service.parse_daily_assignment_text(
            "7/24测试司机7788\n10:00 大阪送机伊丹机场"
        )["groups"][0]["orders"][0]
        self.assertEqual(itm["parsed"]["dropoff_location"], "ITM")

    def test_22_bare_pickup_does_not_default_to_kix(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24测试司机9999\n14:50接机 公司单"
        )["groups"][0]["orders"][0]
        self.assertEqual((order["parsed"]["pickup_location"], order["parsed"]["dropoff_location"]), ("待补", "待补"))
        self.assertFalse(order["airportInferred"])

    def test_23_osaka_to_ukb_is_explicit(self):
        order = parser_service.parse_daily_assignment_text(
            "7/24白石8256\n07:30 大阪送机神户机场 WhatsApp"
        )["groups"][0]["orders"][0]
        self.assertIn(order["parsed"]["pickup_location"], {item["name"] for item in hotel_pool("大阪")})
        self.assertEqual(order["parsed"]["dropoff_location"], "UKB")

    def test_24_previous_ukb_allows_contextual_kobe_pickup(self):
        orders = parser_service.parse_daily_assignment_text(
            "7/24白石8256\n1️⃣07:30 大阪送机神户机场 WhatsApp\n2️⃣10:00 神户接机"
        )["groups"][0]["orders"]
        self.assertEqual((orders[1]["parsed"]["pickup_location"], orders[1]["parsed"]["dropoff_location"]), ("UKB", "待补"))
        self.assertTrue(orders[1]["airportInferred"])

    def test_25_collect_amount_channel_and_note_do_not_pollute_locations(self):
        orders = parser_service.parse_daily_assignment_text(
            "7/24刘晓丽8298\n1️⃣07:00 大阪送机关西 line 代收14000日元*\n2️⃣10:00 大阪送机关西 增高垫 代收13000日元 WhatsApp\n3️⃣11:35 关西-京都 CA725 携程"
        )["groups"][0]["orders"]
        self.assertEqual([item["parsed"]["collection_amount_jpy"] for item in orders[:2]], [14000.0, 13000.0])
        self.assertEqual([item["parsed"]["source_channel"] for item in orders], ["LINE", "WhatsApp", "携程"])
        self.assertEqual(orders[2]["parsed"]["flight_number"], "CA725")
        for order in orders:
            self.assertNotRegex(order["route"], r"代收|LINE|WhatsApp|携程|增高垫|\*")

    def test_26_area_warning_is_review_only(self):
        warning = parser_service.parse_daily_assignment_text(
            "7/24王启超7728\n09:30 京都-关西 携程 日元结算"
        )["groups"][0]["orders"][0]
        safe = parser_service.parse_daily_assignment_text(
            "7/24胡东锴6832\n10:00 大阪送机关西 WhatsApp"
        )["groups"][0]["orders"][0]
        self.assertTrue(warning["areaWarning"])
        self.assertIn("京都市域交通圏", warning["areaRoute"])
        self.assertFalse(safe["areaWarning"])
        self.assertEqual(safe["areaRoute"].split(" → ")[-1], "KIX")

    def test_27_full_july_24_batch_stays_eleven_drivers_and_thirty_two_orders(self):
        text = """7/24胡东锴 6832
1️⃣10:00 大阪送机关西 10座+7座 WhatsApp
2️⃣12:00 关西举牌接机大阪 指定时间 微信

7/24李成志7011
1️⃣04:30 豊岡市送机关西 WhatsApp在群里
2️⃣12:40接机京都 日元结算 备水3瓶

7/24吕云龙7012
1️⃣10:00 大阪单送新大阪 WhatsApp
2️⃣11:00am ，环球-心斋桥 微信
3️⃣12:25伊丹-大阪 举牌 微信 日元结算
4️⃣14:00 伊丹接机大阪 代收差价2000日元 WhatsApp 指定时间
5️⃣15:12 新大阪-大阪 日元结算

7/24刘晓丽8298
1️⃣07:00 大阪送机关西 line 代收14000日元*
2️⃣10:00 大阪送机关西 增高垫 代收13000日元 WhatsApp
3️⃣11:35 关西-京都 CA725 携程

7/24林泽群3893
1️⃣10:45 京都-大阪 日元结算
2️⃣14:00 神户-关西 日元结算
3️⃣14:50 关西-京都 CX564 日元结算

7/24王启超 7728（京都）
1️⃣09:30 京都-关西 携程 日元结算
2️⃣11:40 关西-京都 HO1505 携程 日元结算

7/24夏天忻1027
1️⃣10:00 大阪送机关西 10座+7座 WhatsApp
2️⃣15:00送机 微信 日元结算 代收17000日元
3️⃣15:15 关西接机大阪 微信 日元结算代收17000日元
4️⃣20:45*接机 KE721（김현민 KIM HYUNMIN）

7/24高弘强1006
09:00 京都-胜尾寺-奈良-大阪 包车 line

7/24白石8256
1️⃣07:30 大阪送机神户机场 WhatsApp
2️⃣10:00 神户接机

7/24姜小涛8253
1️⃣10:00大阪-神戶機場 微信 代收17000日元
2️⃣12:30 神户机场接机大阪 line
3️⃣15:00 大阪送机关西 line
4️⃣18:05 关西-京都 CX598 举牌 日元结算 微信

7/24李力6781
1️⃣09:30 大阪送机关西 line
2️⃣11:00 关西接机京都 3代×3 儿童座椅 line
有合适会追加
3️⃣18:00 神户机场接机大阪 儿童座椅2 line
4️⃣21:35关西接机伊丹 微信"""
        result = parser_service.parse_daily_assignment_text(text)
        self.assertEqual((result["group_count"], result["order_count"]), (11, 32))
        forbidden = re.compile(r"日元结算|日圓結算|微信|WeChat|LINE|line|WhatsApp|Whatsup|Kakao|携程|公司单|包车|代收|返金|在群里|儿童座椅|增高垫")
        for group in result["groups"]:
            for order in group["orders"]:
                for location in order["routeNodes"]:
                    self.assertNotRegex(location, forbidden)


if __name__ == "__main__":
    unittest.main()

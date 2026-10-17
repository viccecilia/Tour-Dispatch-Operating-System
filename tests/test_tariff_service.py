import unittest

from backend.services.tariff_service import (
    TARIFF_RULE_VERSION,
    diagnose_route_fare,
    recommend_route_fare,
    resolve_vehicle_affiliation,
)


class TariffServiceTest(unittest.TestCase):
    def assert_fare(
        self,
        pickup,
        dropoff,
        vehicle,
        office,
        expected,
        order_type="接送",
        remark="",
        **context,
    ):
        result = recommend_route_fare(
            pickup,
            dropoff,
            order_type,
            vehicle,
            remark,
            vehicle_office=office,
            plate_number=context.pop("plate_number", ""),
            **context,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["amount"], expected)
        self.assertEqual(result["rule_version"], TARIFF_RULE_VERSION)
        self.assertTrue(result["match_basis"])

    def test_osaka_transfer_tariffs(self):
        self.assert_fare("大阪市内ホテル", "KIX", "Alphard", "大阪営業所", 11270)
        self.assert_fare("関西空港", "大阪市内", "HiAce", "大阪営業所", 17000)
        self.assert_fare("大阪", "京都", "Alphard", "大阪営業所", 19000)
        self.assert_fare("大阪", "京都", "HiAce", "大阪営業所", 21000)
        self.assert_fare("大阪", "神戸", "Alphard", "大阪営業所", 14000)
        self.assert_fare("大阪", "神户", "HiAce", "大阪営業所", 16000)
        self.assert_fare("大阪", "奈良", "Alphard", "大阪営業所", 14000)
        self.assert_fare("大阪", "奈良", "HiAce", "大阪営業所", 16000)
        self.assert_fare("大阪梅田", "大阪難波", "Alphard", "大阪営業所", 7000)
        self.assert_fare("大阪梅田", "大阪難波", "HiAce", "大阪営業所", 8000)

    def test_osaka_kix_real_hotel_pool_routes(self):
        hotels = (
            "ドーミーイン大阪谷町",
            "インターコンチネンタルホテル大阪",
            "スーパーホテル地下鉄谷町四丁目6号口",
            "ホテルリブマックス大阪淀屋橋",
            "リーガロイヤルホテル大阪",
        )
        for hotel in hotels:
            with self.subTest(hotel=hotel, direction="to_kix"):
                self.assert_fare(hotel, "KIX", "Alphard", "大阪営業所", 11270)
            with self.subTest(hotel=hotel, direction="from_kix"):
                self.assert_fare("KIX", hotel, "Alphard", "大阪営業所", 11270)

    def test_osaka_eight_hour_charter_is_not_reversed_or_ten_hour(self):
        self.assert_fare("大阪", "大阪", "Alphard", "大阪営業所", 41590, "包車", "8H")
        self.assert_fare("大阪", "大阪", "HiAce", "大阪営業所", 46310, "包車", "8時間")
        self.assert_fare("大阪", "大阪", "Alphard", "大阪営業所", 52430, "包車", "10H")
        self.assert_fare("大阪", "大阪", "HiAce", "大阪営業所", 58390, "包車", "10時間")

    def test_kyoto_transfer_tariffs(self):
        self.assert_fare("京都", "KIX", "Alphard", "京都営業所", 17000)
        self.assert_fare("関西空港", "京都", "HiAce", "京都営業所", 18000)
        self.assert_fare("京都駅", "祇園", "Alphard", "京都営業所", 12000)
        self.assert_fare("京都駅", "嵐山", "HiAce", "京都営業所", 13000)
        self.assert_fare("京都", "大阪", "Alphard", "京都営業所", 14000)
        self.assert_fare("京都", "大阪", "HiAce", "京都営業所", 15000)
        self.assert_fare("京都", "奈良", "Alphard", "京都営業所", 14000)
        self.assert_fare("京都", "奈良", "HiAce", "京都営業所", 15000)
        self.assert_fare("京都", "神戸", "Alphard", "京都営業所", 15000)
        self.assert_fare("京都", "神戸", "HiAce", "京都営業所", 16000)

    def test_daily_v2_kyoto_airport_cases_are_explicit_and_traceable(self):
        safe_kix = diagnose_route_fare(
            "京都ホテル", "KIX", "接送", "Alphard",
            vehicle_office="京都営業所", plate_number="京都 300 あ 3827",
            permitted_business_area="京都市域交通圏",
        )
        self.assertEqual(safe_kix["amount"], 17000)
        self.assertEqual(safe_kix["area_assessment"]["status"], "passed")
        safe_itm = diagnose_route_fare(
            "ITM", "京都ホテル", "接送", "Alphard",
            vehicle_office="京都営業所", plate_number="京都 300 あ 3827",
            permitted_business_area="京都市域交通圏",
        )
        self.assertEqual(safe_itm["amount"], 14000)
        self.assertEqual(safe_itm["key"], "kyoto_itm")
        self.assertEqual(safe_itm["area_assessment"]["status"], "passed")
        risky = diagnose_route_fare(
            "KIX", "神戸", "接送", "Alphard",
            vehicle_office="京都営業所", plate_number="京都 300 あ 3827",
            permitted_business_area="京都市域交通圏",
        )
        self.assertFalse(risky["matched"])
        self.assertEqual(risky["area_assessment"]["status"], "risk")

    def test_kyoto_charter_durations_and_unconfigured_prices(self):
        for hours, alpha, hiace in ((2, 12000, 13000), (4, 23400, 25600), (6, 34800, 38200)):
            self.assert_fare("京都", "京都", "Alphard", "京都営業所", alpha, "包车", f"{hours}H")
            self.assert_fare("京都", "京都", "HiAce", "京都営業所", hiace, "包车", f"{hours}時間")
        self.assert_fare("京都", "京都", "Alphard", "京都営業所", 46200, "包车", "8H")
        missing = diagnose_route_fare(
            "京都", "京都", "包车", "HiAce", "8H", vehicle_office="京都営業所"
        )
        self.assertFalse(missing["matched"])
        self.assertIsNone(missing["amount"])
        self.assertEqual(missing["reason"], "vehicle_price_not_configured")
        self.assert_fare("京都", "京都", "Alphard", "京都営業所", 2850, "包车加时", "30分钟")
        missing_overtime = diagnose_route_fare(
            "京都", "京都", "包车加时", "HiAce", "30分钟", vehicle_office="京都営業所"
        )
        self.assertEqual(missing_overtime["reason"], "vehicle_price_not_configured")

    def test_only_kix_is_bidirectional_and_source_city_survives_hotel_replacement(self):
        reverse = diagnose_route_fare(
            "京都", "大阪", "接送", "Alphard", vehicle_office="大阪営業所"
        )
        self.assertFalse(reverse["matched"])
        self.assertEqual(reverse["reason"], "route_or_duration_not_configured")
        result = recommend_route_fare(
            "スイスホテル南海", "関西空港", "送机", "Alphard",
            vehicle_office="大阪営業所", pickup_source_text="大阪"
        )
        self.assertEqual(result["amount"], 11270)
        self.assertEqual(result["match_basis"]["pickup_city"], "osaka")

    def test_vehicle_archive_wins_plate_is_auxiliary_and_conflicts_are_visible(self):
        explicit = resolve_vehicle_affiliation("京都営業所", "京都 300 あ 1000", "京都市域交通圏")
        self.assertEqual(explicit["office_key"], "kyoto")
        self.assertEqual(explicit["status"], "vehicle_archive")
        self.assertFalse(explicit["requires_review"])
        auxiliary = resolve_vehicle_affiliation("", "なにわ 300 あ 2000")
        self.assertEqual(auxiliary["office_key"], "osaka")
        self.assertEqual(auxiliary["status"], "plate_auxiliary")
        self.assertTrue(auxiliary["requires_review"])
        conflict = resolve_vehicle_affiliation("京都営業所", "大阪 300 あ 3000")
        self.assertEqual(conflict["office_key"], "kyoto")
        self.assertEqual(conflict["status"], "conflict")
        self.assertTrue(conflict["requires_review"])

    def test_unknown_vehicle_or_unconfigured_route_has_no_suggestion(self):
        self.assertIsNone(recommend_route_fare("東京", "横浜", "送迎", "HiAce", vehicle_office="大阪営業所"))
        self.assertIsNone(recommend_route_fare("大阪", "KIX", "送迎", "車種未定", vehicle_office="大阪営業所"))
        # Seat count alone must not silently turn an unknown vehicle into Alphard.
        self.assertIsNone(recommend_route_fare("大阪", "KIX", "送迎", "", 7, vehicle_office="大阪営業所"))


if __name__ == "__main__":
    unittest.main()

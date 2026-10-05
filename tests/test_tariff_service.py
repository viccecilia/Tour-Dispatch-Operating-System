import unittest

from backend.services.tariff_service import recommend_route_fare


class TariffServiceTest(unittest.TestCase):
    def assert_fare(self, pickup, dropoff, vehicle, expected, order_type="接送", remark=""):
        result = recommend_route_fare(pickup, dropoff, order_type, vehicle, remark)
        self.assertIsNotNone(result)
        self.assertEqual(result["amount"], expected)

    def test_confirmed_bidirectional_route_tariffs(self):
        self.assert_fare("大阪市内ホテル", "KIX", "HiAce", 12460)
        self.assert_fare("関西空港", "大阪市内", "Alphard", 11270)
        self.assert_fare("京都市内", "大阪市内", "海狮 10座", 15480)
        self.assert_fare("大阪市内", "京都市内", "阿尔法 7座", 13980)
        self.assert_fare("奈良", "大阪市内", "HiAce", 12460)
        self.assert_fare("大阪市内", "神戸空港", "Alphard", 11270)
        self.assert_fare("大阪市内", "大阪市内", "HiAce", 58390, "包車", "10H")
        self.assert_fare("大阪市内", "大阪市内", "Alphard", 52430, "貸切", "10時間")

    def test_unconfirmed_route_or_vehicle_has_no_suggestion(self):
        self.assertIsNone(recommend_route_fare("東京", "横浜", "送迎", "HiAce"))
        self.assertIsNone(recommend_route_fare("大阪", "KIX", "送迎", "車種未定"))


if __name__ == "__main__":
    unittest.main()

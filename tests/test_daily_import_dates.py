import unittest

from backend.services.parser_service import parse_daily_assignment_text


SAMPLE = """10/9 李力 7495
1️⃣09:30 大阪送机关西 WhatsApp*代收13000日元
2️⃣10:40 关西举牌接机大阪 指定时间 微信
3️⃣13:00 大阪送机关西 微信
4️⃣14:00 关西举牌接机大阪 line
5️⃣17:00 大阪送机关西 微信
6️⃣18:00 关西举牌接机大阪 指定时间 微信"""


class DailyImportDateTest(unittest.TestCase):
    def test_explicit_month_day_uses_selected_import_year(self):
        result = parse_daily_assignment_text(SAMPLE, base_year=2026, default_date="2026-10-10")
        self.assertEqual(result["group_count"], 1)
        self.assertEqual(result["order_count"], 6)
        self.assertEqual(result["groups"][0]["serviceDate"], "2026-10-09")
        self.assertTrue(all(item["date"] == "2026-10-09" for item in result["groups"][0]["orders"]))

    def test_missing_header_date_uses_visible_default(self):
        result = parse_daily_assignment_text(
            SAMPLE.replace("10/9 ", "", 1),
            base_year=2026,
            default_date="2026-10-10",
        )
        self.assertEqual(result["groups"][0]["serviceDate"], "2026-10-10")

    def test_multiple_dates_remain_separate_groups(self):
        result = parse_daily_assignment_text(
            SAMPLE + "\n10/12 李力 7495\n1️⃣09:30 大阪送机关西 微信",
            base_year=2026,
            default_date="2026-10-10",
        )
        self.assertEqual([item["serviceDate"] for item in result["groups"]], ["2026-10-09", "2026-10-12"])


if __name__ == "__main__":
    unittest.main()

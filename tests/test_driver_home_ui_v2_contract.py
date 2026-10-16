import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DriverHomeUiV2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = ROOT / "miniapp_yuzu/package_dispatch"
        cls.home_js = (package / "pages/home/index.js").read_text(encoding="utf-8")
        cls.home_wxml = (package / "pages/home/index.wxml").read_text(encoding="utf-8")
        cls.home_wxss = (package / "pages/home/index.wxss").read_text(encoding="utf-8")
        cls.task_wxml = (package / "pages/task/index.wxml").read_text(encoding="utf-8")
        cls.nav_js = (ROOT / "miniapp_yuzu/utils/port-nav.js").read_text(encoding="utf-8")

    def test_driver_uses_one_compact_hero_and_non_driver_home_is_preserved(self):
        self.assertIn('wx:if="{{!isDriverTheme}}" class="hero dashboard-hero"', self.home_wxml)
        self.assertEqual(self.home_wxml.count('class="driver-home-hero"'), 1)
        self.assertIn('<block wx:else>', self.home_wxml)
        for binding in (
            "driverTodayView.driverName",
            "driverTodayView.driverCode",
            "driverTodayView.vehicleText",
            "driverTodayView.dateText",
            "driverTodayView.orderCount",
            "driverTodayView.stateLabel",
            "driverTodayView.flowSummary",
        ):
            self.assertIn(binding, self.home_wxml)

    def test_duplicate_driver_home_modules_are_removed_from_markup(self):
        for removed_class in (
            "driver-today-metrics",
            "driver-flow-section",
            "driver-provisional-entry",
        ):
            self.assertNotIn(removed_class, self.home_wxml)

    def test_four_shortcuts_are_one_fixed_row_and_use_existing_routes(self):
        driver_block = self.home_wxml.split('class="driver-home-shortcuts"', 1)[1].split('</view>\n\n        <view class="driver-home-tasks"', 1)[0]
        self.assertEqual(driver_block.count('class="driver-home-shortcut '), 4)
        for target in ("instruction", "acceptance", "report", "provisional"):
            self.assertIn(f'data-target="{target}"', driver_block)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr))", self.home_wxss)
        self.assertIn("api.downloadAndOpenDocument", self.home_js)
        self.assertIn("driver_task_report_focus", self.home_js)
        self.assertIn("/package_dispatch/pages/provisional/index", self.home_js)

    def test_hero_state_comes_from_selected_date_workflow_facts(self):
        self.assertIn("api.driverWorkflowEvents(driverBusinessDate)", self.home_js)
        self.assertIn("String(item.event_status || 'submitted') === 'submitted'", self.home_js)
        self.assertIn("if (hasInbound) return { label: '已入库'", self.home_js)
        self.assertIn("if (hasOutbound) return { label: '运行中'", self.home_js)
        self.assertIn("return { label: '未出库'", self.home_js)
        self.assertIn("driver_task_yard_focus", self.home_js)

    def test_today_tasks_are_real_sorted_rows_with_required_content(self):
        start = self.home_wxml.index('class="driver-home-tasks"')
        tasks = self.home_wxml[start:]
        for binding in (
            "driverTodayView.orders",
            "item.start_time",
            "item.todayRouteText",
            "item.todayTypeText",
            "item.todayStatusText",
            "item.todayAlertText",
        ):
            self.assertIn(binding, tasks)
        self.assertIn("return merged.sort((a, b) =>", self.home_js)
        self.assertIn("item.start_time", self.home_js)
        self.assertIn("今天没有任务", tasks)
        self.assertNotIn("UIV2-", self.home_js + self.home_wxml)

    def test_task_click_reuses_existing_task_page_and_six_fields(self):
        self.assertIn('bindtap="openDriverTodayTask"', self.home_wxml)
        self.assertIn("wx.reLaunch({ url: '/package_dispatch/pages/task/index' })", self.home_js)
        for label in ("到着場所", "出発時刻", "到着時刻", "降車場所", "到着時メーター", "降車時メーター"):
            self.assertIn(label, self.task_wxml)

    def test_provisional_shortcut_only_counts_actionable_driver_items(self):
        for status in ("needs_information", "pending_company_confirmation", "draft"):
            self.assertIn(status, self.home_js)
        self.assertIn("provisionalHint", self.home_js + self.home_wxml)
        self.assertIn("driver-home-shortcut-badge", self.home_wxml)

    def test_existing_five_driver_tabs_remain(self):
        driver_block = re.search(
            r"driver:\s*\[(.*?)\]\s*\n\s*}",
            self.nav_js.split("const DISPATCH_TABS =", 1)[1],
            re.S,
        )
        self.assertIsNotNone(driver_block)
        self.assertEqual(driver_block.group(1).count("url:"), 5)


if __name__ == "__main__":
    unittest.main()

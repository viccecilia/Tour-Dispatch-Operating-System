import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DriverTaskUiV2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = ROOT / "miniapp_yuzu/package_dispatch"
        cls.task_js = (package / "pages/task/index.js").read_text(encoding="utf-8")
        cls.task_wxml = (package / "pages/task/index.wxml").read_text(encoding="utf-8")
        cls.task_wxss = (package / "pages/task/index.wxss").read_text(encoding="utf-8")
        cls.home_js = (package / "pages/home/index.js").read_text(encoding="utf-8")
        cls.api_js = (package / "utils/api.js").read_text(encoding="utf-8")
        cls.nav_js = (ROOT / "miniapp_yuzu/utils/port-nav.js").read_text(encoding="utf-8")

    def test_page_sections_follow_confirmed_order(self):
        anchors = [
            'class="task-hero',
            'class="panel calendar-panel',
            'id="driver-depart"',
            'id="driver-tasks"',
            'id="driver-return"',
            'id="driver-report"',
        ]
        positions = [self.task_wxml.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("showMonth: false", self.task_js)
        self.assertIn("toggleMonth", self.task_js)
        self.assertIn("week-strip", self.task_wxml)
        self.assertIn("month-grid", self.task_wxml)

    def test_point_calls_auto_collapse_and_keep_real_record_access(self):
        self.assertIn("departExpanded: departed ? focusDepart : true", self.task_js)
        self.assertIn("returnExpanded: returned ? focusReturn : true", self.task_js)
        self.assertIn("点击查看记录", self.task_wxml)
        self.assertIn("修改记录", self.task_wxml)
        self.assertIn("api.driverWorkflowEvents(selectedDateRequest)", self.task_js)
        self.assertIn("driverWorkflowEvents: (date)", self.api_js)
        self.assertIn("/api/driver/workflow-events", self.api_js)
        self.assertIn("const businessDate = this.data.selectedDate || this.data.today", self.task_js)
        self.assertIn("所选日期没有可关联任务", self.task_js)

    def test_m1_six_actual_fields_remain_fixed_two_by_three(self):
        labels = ["到着場所", "出発時刻", "到着時刻", "降車場所", "到着時メーター", "降車時メーター"]
        positions = [self.task_wxml.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            len(re.findall(r'<label><text>(?:到着場所|出発時刻|到着時刻|降車場所|到着時メーター|降車時メーター)</text>', self.task_wxml)),
            6,
        )
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", self.task_wxss)
        self.assertIn("api.driverDayWorkbench(selectedDateRequest)", self.task_js)
        self.assertIn("api.saveDriverRouteNodeActual", self.task_js)
        self.assertIn("driver_route_actual_drafts_v2", self.task_js)
        self.assertIn("statusCode) === 409", self.task_js)

    def test_return_keeps_safety_evidence_but_removes_paper_report_photo(self):
        for required in ("车辆已清扫", "入库点检完成", "入库后酒精确认", "点呼入库完成"):
            self.assertIn(required, self.task_js)
        self.assertIn("请上传入库酒精测试", self.task_js)
        self.assertIn("returnMaterials.alcohol", self.task_wxml)
        self.assertNotIn("returnMaterials.daily_report", self.task_js + self.task_wxml)
        self.assertNotIn("yardAttachment('return', 'daily_report'", self.task_js)
        self.assertNotIn("请上传司机日报", self.task_js)
        self.assertIn("无需上传纸质司机日报照片", self.task_wxml)

    def test_daily_report_truthful_state_and_no_fake_pdf_action(self):
        self.assertIn("已入库・日报待提交", self.task_js)
        self.assertIn("今日已完成", self.task_js)
        self.assertIn("运行结束，日报待提交", self.task_wxml)
        self.assertIn("今日工作已完成", self.task_wxml)
        self.assertIn("dailyReport.status === 'submitted'", self.task_js + self.task_wxml)
        self.assertIn("api.driverDailyReport(selectedDateRequest)", self.task_js)
        self.assertIn("driver_task_report_focus", self.home_js)
        self.assertIn("正式司机日报 PDF 尚未实施", self.task_wxml)
        self.assertNotIn("生成日报PDF", self.task_wxml)
        self.assertNotIn("下载日报PDF", self.task_wxml)

    def test_zero_task_and_existing_five_tabs_are_preserved(self):
        self.assertIn("当天无任务", self.task_js)
        self.assertIn("暂无本人已发布任务", self.task_js)
        self.assertIn("当天没有任务", self.task_wxml)
        driver_block = re.search(r"driver:\s*\[(.*?)\]\s*\n\s*}", self.nav_js.split("const DISPATCH_TABS =", 1)[1], re.S)
        self.assertIsNotNone(driver_block)
        self.assertEqual(driver_block.group(1).count("url:"), 5)
        for path in ("/pages/home/index", "/pages/task/index", "/pages/map/index", "/pages/expense/index", "/pages/profile/index"):
            self.assertIn(path, driver_block.group(1))


if __name__ == "__main__":
    unittest.main()

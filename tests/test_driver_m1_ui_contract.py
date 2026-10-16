import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DriverM1UiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_json = (ROOT / "miniapp_yuzu/app.json").read_text(encoding="utf-8")
        cls.api_js = (ROOT / "miniapp_yuzu/package_dispatch/utils/api.js").read_text(encoding="utf-8")
        cls.home_js = (ROOT / "miniapp_yuzu/package_dispatch/pages/home/index.js").read_text(encoding="utf-8")
        cls.home_wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/home/index.wxml").read_text(encoding="utf-8")
        cls.task_js = (ROOT / "miniapp_yuzu/package_dispatch/pages/task/index.js").read_text(encoding="utf-8")
        cls.task_wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/task/index.wxml").read_text(encoding="utf-8")
        cls.provisional_js = (ROOT / "miniapp_yuzu/package_dispatch/pages/provisional/index.js").read_text(encoding="utf-8")
        cls.provisional_wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/provisional/index.wxml").read_text(encoding="utf-8")
        cls.permissions = (ROOT / "frontend/src/auth/permissions.ts").read_text(encoding="utf-8")
        cls.web_page = (ROOT / "frontend/src/pages/ProvisionalTasksPage.tsx").read_text(encoding="utf-8")

    def test_provisional_page_and_shared_endpoints_are_wired(self):
        self.assertIn('"root": "package_dispatch"', self.app_json)
        self.assertIn('"pages/provisional/index"', self.app_json)
        for path in (
            "/api/driver/provisional-tasks",
            "/api/company/provisional-tasks",
            "/api/company/provisional-finance-summary",
        ):
            self.assertIn(path, self.api_js)
        self.assertIn("臨時業務を記録", self.home_wxml)
        self.assertIn("臨時注文・確認待ち", self.home_wxml)
        self.assertIn("openProvisionalTasks", self.home_js)

    def test_driver_provisional_ui_preserves_offline_and_history_semantics(self):
        self.assertIn("driver_provisional_unsynced_v1", self.provisional_js)
        self.assertIn("本机未同步", self.provisional_wxml)
        self.assertIn("追加历史", self.provisional_wxml)
        self.assertIn("pickup_odometer_km", self.provisional_js)
        self.assertIn("dropoff_odometer_km", self.provisional_js)
        self.assertNotIn("price_jpy", self.provisional_js.split("payloadFromForm()", 1)[1].split("saveDraft()", 1)[0])

    def test_formal_actual_editor_is_fixed_two_by_three_and_uses_phase2a(self):
        labels = ["到着場所", "出発時刻", "到着時刻", "降車場所", "到着時メーター", "降車時メーター"]
        positions = [self.task_wxml.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(re.findall(r'<label><text>(?:到着場所|出発時刻|到着時刻|降車場所|到着時メーター|降車時メーター)</text>', self.task_wxml)), 6)
        self.assertIn("api.driverDayWorkbench", self.task_js)
        self.assertIn("api.saveDriverRouteNodeActual", self.task_js)
        self.assertIn("driver_route_actual_pending_v1", self.task_js)
        self.assertIn("statusCode) === 409", self.task_js)
        self.assertIn("实际值已同步保存", self.task_js)

    def test_web_approval_is_carrier_admin_only(self):
        carrier_block = self.permissions.split("const CARRIER_ADMIN_PAGES", 1)[1].split("const CARRIER_DISPATCHER_PAGES", 1)[0]
        dispatcher_block = self.permissions.split("const CARRIER_DISPATCHER_PAGES", 1)[1].split("const CARRIER_OPERATIONS_PAGES", 1)[0]
        operations_block = self.permissions.split("const CARRIER_OPERATIONS_PAGES", 1)[1].split("const DRIVER_PAGES", 1)[0]
        platform_block = self.permissions.split("const PLATFORM_PAGES", 1)[1].split("const CARRIER_ADMIN_PAGES", 1)[0]
        self.assertIn('"provisional-orders"', carrier_block)
        for block in (dispatcher_block, operations_block, platform_block):
            self.assertNotIn('"provisional-orders"', block)
        for action in ("approve-create", "approve-link", "needs-info", "reject", "pricing"):
            self.assertIn(action, self.web_page)


if __name__ == "__main__":
    unittest.main()

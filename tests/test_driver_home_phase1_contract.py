import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DriverHomePhase1ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home_js = (ROOT / "miniapp_yuzu/package_dispatch/pages/home/index.js").read_text(encoding="utf-8")
        cls.home_wxml = (ROOT / "miniapp_yuzu/package_dispatch/pages/home/index.wxml").read_text(encoding="utf-8")
        cls.api_js = (ROOT / "miniapp_yuzu/package_dispatch/utils/api.js").read_text(encoding="utf-8")
        cls.nav_js = (ROOT / "miniapp_yuzu/utils/port-nav.js").read_text(encoding="utf-8")
        cls.routes_py = (ROOT / "backend/api/routes.py").read_text(encoding="utf-8")
        cls.driver_service_py = (ROOT / "backend/services/driver_service.py").read_text(encoding="utf-8")

    def test_driver_navigation_remains_five_existing_tabs(self):
        for path in (
            "/package_dispatch/pages/home/index",
            "/package_dispatch/pages/task/index",
            "/package_dispatch/pages/map/index",
            "/package_dispatch/pages/expense/index",
            "/package_dispatch/pages/profile/index",
        ):
            self.assertIn(path, self.nav_js)
        dispatch_block = self.nav_js.split("const DISPATCH_TABS =", 1)[1].split("const AGENCY_TABS =", 1)[0]
        driver_block = re.search(r"driver:\s*\[(.*?)\]\s*\n\s*}", dispatch_block, re.S)
        self.assertIsNotNone(driver_block)
        self.assertEqual(driver_block.group(1).count("url:"), 5)

    def test_home_uses_existing_driver_endpoints_only(self):
        for api_call in (
            "api.driverAssignments",
            "api.driverWorkbench",
            "api.driverProfile",
            "api.driverNotifications",
            "api.driverDailyReport",
            "api.driverRunDocuments",
        ):
            self.assertIn(api_call, self.home_js)
        self.assertNotIn("/api/driver-home", self.home_js)
        self.assertIn("driverTodayWorkbenchEnabled", self.home_wxml)
        self.assertIn("<block wx:else>", self.home_wxml)

    def test_operational_actions_still_route_to_old_task_page(self):
        self.assertIn("wx.reLaunch({ url: '/package_dispatch/pages/task/index' })", self.home_js)
        self.assertIn("填写与证据仍在原任务页完成", self.home_wxml)
        self.assertIn("进入原任务页处理", self.home_wxml)

    def test_driver_api_scope_is_enforced_server_side(self):
        self.assertIn('if path.startswith("/api/driver/"):', self.routes_py)
        self.assertIn('self.require_role({"driver"})', self.routes_py)
        self.assertIn('payload["driver_id"] = int(driver_user.get("profile_id") or 0)', self.routes_py)
        self.assertIn("AND a.published_at IS NOT NULL", self.driver_service_py)
        self.assertIn("AND a.driver_id = ?", self.driver_service_py)
        self.assertIn("AND COALESCE(o.is_deleted, 0) = 0", self.driver_service_py)

    def test_existing_api_client_contracts_are_unchanged_and_available(self):
        for path in (
            "/api/driver/assignments",
            "/api/driver/workbench",
            "/api/driver/daily-report",
            "/api/driver/expense",
            "/api/driver/run-documents",
        ):
            self.assertIn(path, self.api_js)


if __name__ == "__main__":
    unittest.main()

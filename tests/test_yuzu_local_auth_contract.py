import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class YuzuLocalAuthContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_js = (ROOT / "miniapp_yuzu/utils/api.js").read_text(encoding="utf-8")
        cls.login_js = (ROOT / "miniapp_yuzu/pages/login/index.js").read_text(encoding="utf-8")

    def test_unified_login_honors_explicit_dispatch_local_override(self):
        self.assertIn("DISPATCH_FORCE_LOCAL_KEY = 'wx_dispatch_force_local_api'", self.api_js)
        self.assertIn("forceLocal ? LOCAL_BASE_URL : TRIAL_BASE_URL", self.api_js)
        self.assertNotIn("wx.removeStorageSync(FORCE_LOCAL_KEY)", self.api_js)

    def test_admin_remains_blocked_except_local_dispatch_devtools(self):
        self.assertIn("allowLocalDispatchAdmin", self.login_js)
        self.assertIn("this.data.port === 'dispatch'", self.login_js)
        self.assertIn("this.isDispatchDevtools()", self.login_js)
        self.assertIn("api.getBaseUrl() === api.LOCAL_BASE_URL", self.login_js)
        self.assertIn("loginCode.toLowerCase() === 'admin' && !allowLocalDispatchAdmin", self.login_js)


if __name__ == "__main__":
    unittest.main()

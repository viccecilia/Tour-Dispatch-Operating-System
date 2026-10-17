import unittest
from unittest.mock import patch

from backend.api import routes


class PasswordLoginWechatPolicyTest(unittest.TestCase):
    def test_disabled_binding_strips_wechat_identity_from_old_miniapp_request(self):
        payload = {
            "username": "08000000000",
            "password": "secret",
            "client_type": "dispatch_miniapp",
            "wx_code": "temporary-code",
            "wx_openid": "openid-must-not-bind",
            "wx_unionid": "unionid-must-not-bind",
        }
        with patch.object(routes, "is_wechat_binding_required", return_value=False):
            normalized, error = routes.apply_password_login_wechat_policy(payload)

        self.assertIsNone(error)
        self.assertEqual(normalized["client_type"], "web")
        self.assertNotIn("wx_code", normalized)
        self.assertNotIn("wx_openid", normalized)
        self.assertNotIn("wx_unionid", normalized)
        self.assertEqual(payload["wx_code"], "temporary-code")

    def test_required_binding_keeps_wechat_code(self):
        payload = {
            "username": "08000000000",
            "password": "secret",
            "client_type": "dispatch_miniapp",
            "wx_code": "temporary-code",
        }
        with patch.object(routes, "is_wechat_binding_required", return_value=True):
            normalized, error = routes.apply_password_login_wechat_policy(payload)

        self.assertIsNone(error)
        self.assertEqual(normalized["client_type"], "dispatch_miniapp")
        self.assertEqual(normalized["wx_code"], "temporary-code")

    def test_required_binding_rejects_miniapp_password_without_identity(self):
        payload = {
            "username": "08000000000",
            "password": "secret",
            "client_type": "dispatch_miniapp",
        }
        with patch.object(routes, "is_wechat_binding_required", return_value=True):
            normalized, error = routes.apply_password_login_wechat_policy(payload)

        self.assertEqual(error, "wx_code_required")
        self.assertEqual(normalized["client_type"], "dispatch_miniapp")


if __name__ == "__main__":
    unittest.main()

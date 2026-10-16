import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from backend.db import database
from backend.services import account_service, audit_service, auth_account_service, auth_service, dispatcher_mobile_service, operation_log_service, wechat_auth_service
from backend.services.travel_agency_service import ensure_travel_agency_schema
from backend.services.account_policy import (
    AGENCY_OWNER_GRANTS,
    CARRIER_ADMIN_GRANTS,
    assert_can_grant_role,
    grantable_roles,
)


class AccountGrantPolicyTest(unittest.TestCase):
    def test_platform_admin_can_grant_every_supported_role(self):
        actor = {"account_scope": "platform", "role": "admin"}
        self.assertEqual(
            grantable_roles(actor, "carrier", 7),
            {"admin", "operations_manager", "dispatcher", "driver"},
        )
        self.assertEqual(
            grantable_roles(actor, "agency", 9),
            {"agency_owner", "agency_customer_service", "agency_guide", "agency_finance"},
        )

    def test_carrier_admin_is_tenant_scoped_and_cannot_grant_admin(self):
        actor = {"account_scope": "carrier", "role": "admin", "tenant_id": 7}
        self.assertEqual(grantable_roles(actor, "carrier", 7), CARRIER_ADMIN_GRANTS)
        self.assertEqual(grantable_roles(actor, "carrier", 8), set())
        self.assertEqual(grantable_roles(actor, "agency", 7), set())
        with self.assertRaises(PermissionError):
            assert_can_grant_role(actor, "carrier", 7, "admin")

    def test_agency_owner_is_company_scoped_and_cannot_grant_owner(self):
        actor = {"account_scope": "agency", "role": "agency_owner", "organization_id": 9}
        self.assertEqual(grantable_roles(actor, "agency", 9), AGENCY_OWNER_GRANTS)
        self.assertEqual(grantable_roles(actor, "agency", 10), set())
        self.assertEqual(grantable_roles(actor, "carrier", 9), set())
        with self.assertRaises(PermissionError):
            assert_can_grant_role(actor, "agency", 9, "agency_owner")

    def test_non_managers_cannot_grant_accounts(self):
        for scope, role in (
            ("carrier", "operations_manager"),
            ("carrier", "dispatcher"),
            ("driver", "driver"),
            ("agency", "agency_customer_service"),
            ("agency", "agency_guide"),
            ("agency", "agency_finance"),
        ):
            with self.subTest(scope=scope, role=role):
                self.assertEqual(grantable_roles({"account_scope": scope, "role": role}, scope, 1), set())


class SupabaseIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "auth.sqlite3"
        database.init_db(seed=False)
        ensure_travel_agency_schema()
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (1, 'Carrier A', 'carrier-a')")
            conn.execute(
                """
                INSERT INTO users (
                    id, tenant_id, username, password_hash, role, display_name,
                    phone, profile_type, profile_id, account_scope,
                    supabase_user_id, is_active
                ) VALUES (11, 1, 'driver-a', 'legacy', 'driver', 'Driver A',
                          '08000000001', 'driver', 101, 'driver', 'auth-driver-a', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO users (
                    id, tenant_id, username, password_hash, role, display_name,
                    phone, profile_type, account_scope, supabase_user_id, is_active
                ) VALUES (13, 1, 'dispatcher-a', 'legacy', 'dispatcher', 'Dispatcher A',
                          '08000000003', 'operator', 'carrier', 'auth-dispatcher-a', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO users (
                    id, tenant_id, username, password_hash, role, display_name,
                    account_scope, is_active
                ) VALUES (12, 1, 'admin', 'legacy', 'admin', 'Platform Admin',
                          'platform', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO travel_agency_companies (
                    id, tenant_id, company_code, company_name, master_phone, status
                ) VALUES (21, 1, 'AG-A', 'Agency A', '08000000002', 'active')
                """
            )
            conn.execute(
                """
                INSERT INTO travel_agency_accounts (
                    id, tenant_id, company_id, role, display_name, phone,
                    status, supabase_user_id
                ) VALUES (22, 1, 21, 'agency_owner', 'Owner A', '08000000002',
                          'active', 'auth-owner-a')
                """
            )
            conn.commit()

    def tearDown(self):
        database.DB_PATH = self.original_db
        self.temp.cleanup()

    def test_driver_principal_uses_explicit_profile_binding(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        self.assertEqual(principal["account_scope"], "driver")
        self.assertEqual(principal["profile_type"], "driver")
        self.assertEqual(principal["profile_id"], 101)
        self.assertEqual(principal["organization_type"], "carrier")

    def test_agency_principal_uses_company_mapping(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-owner-a")
        self.assertEqual(principal["account_scope"], "agency")
        self.assertEqual(principal["organization_id"], 21)
        self.assertEqual(principal["agency_account_id"], 22)

    def test_unknown_supabase_identity_is_rejected(self):
        self.assertIsNone(auth_account_service.resolve_authenticated_principal("unknown"))

    def test_username_only_platform_admin_uses_internal_supabase_alias(self):
        with patch.object(auth_account_service, "SUPABASE_PLATFORM_ADMIN_EMAIL", "admin@trial.tourflow.invalid"):
            self.assertEqual(
                auth_account_service.resolve_login_identifier("admin"),
                "admin@trial.tourflow.invalid",
            )

    def test_linked_phone_login_uses_private_email_alias(self):
        self.assertEqual(
            auth_account_service.resolve_login_identifier("08000000001"),
            "tourflow-user-11@auth.taxi-airport.jp",
        )
        self.assertEqual(
            auth_account_service.resolve_login_identifier("08000000002"),
            "tourflow-agency-22@auth.taxi-airport.jp",
        )

    def test_first_phone_login_binds_wechat_after_supabase_auth(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        session = {
            "token": "supabase-access",
            "access_token": "supabase-access",
            "refresh_token": "supabase-refresh",
            "user": principal,
        }
        with (
            patch.object(auth_service, "supabase_enabled", return_value=True),
            patch.object(auth_service, "sign_in_with_password", return_value=session),
            patch.object(auth_service, "_requires_wechat", return_value=True),
        ):
            result = auth_service.authenticate_phone(
                "08000000001",
                "initial-password",
                wx_openid="wx-first-login",
                client_type="driver_miniapp",
            )

        self.assertEqual(result["refresh_token"], "supabase-refresh")
        with closing(database.get_connection()) as conn:
            row = conn.execute("SELECT wx_openid, wx_bind_status FROM users WHERE id = 11").fetchone()
        self.assertEqual(row["wx_openid"], "wx-first-login")
        self.assertEqual(row["wx_bind_status"], "bound")

        with (
            patch.object(auth_service, "supabase_enabled", return_value=True),
            patch.object(wechat_auth_service, "issue_supabase_session", return_value=session),
        ):
            wechat_result = auth_service.authenticate_wechat(
                wx_openid="wx-first-login",
                client_type="driver_miniapp",
            )
        self.assertIsNotNone(wechat_result)
        self.assertEqual(wechat_result["user"]["id"], 11)

    def test_wechat_login_cannot_bypass_missing_supabase_identity(self):
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE users SET supabase_user_id = NULL, wx_openid = 'wx-unlinked', wx_bind_status = 'bound' WHERE id = 11"
            )
            conn.commit()
        with patch.object(auth_service, "supabase_enabled", return_value=True):
            with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
                auth_service.authenticate_wechat(
                    wx_openid="wx-unlinked",
                    client_type="driver_miniapp",
                )
        self.assertEqual(str(error.exception), "supabase_identity_required")

    def test_unbound_wechat_requires_first_password_login(self):
        with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
            wechat_auth_service.login_with_wechat_identity(
                {"wx_openid": "never-bound", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
            )
        self.assertEqual(str(error.exception), "wechat_not_bound")

    def test_inactive_bound_account_cannot_auto_login(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        identity = {"wx_openid": "disabled-driver", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
        wechat_auth_service.bind_principal_wechat(principal, identity)
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE id = 11")
            conn.commit()
        with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
            wechat_auth_service.login_with_wechat_identity(identity)
        self.assertEqual(str(error.exception), "account_disabled")

    def test_jwt_validation_requires_signature_exp_issuer_and_audience(self):
        fake_client = Mock()
        fake_client.get_signing_key_from_jwt.return_value = Mock(key="public-key")
        with (
            patch.object(auth_account_service, "SUPABASE_URL", "https://example.supabase.co"),
            patch.object(auth_account_service, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"),
            patch.object(auth_account_service, "_jwks_client", fake_client),
            patch.object(auth_account_service.jwt, "decode", return_value={"sub": "auth-driver-a"}) as decode,
        ):
            claims = auth_account_service.verify_supabase_access_token("signed-token")
        self.assertEqual(claims["sub"], "auth-driver-a")
        _, kwargs = decode.call_args
        self.assertEqual(kwargs["audience"], "authenticated")
        self.assertEqual(kwargs["issuer"], "https://example.supabase.co/auth/v1")
        self.assertEqual(set(kwargs["options"]["require"]), {"exp", "sub", "iss", "aud"})

    def test_account_creation_writes_phone_and_hidden_email(self):
        calls = []
        with (
            patch.object(auth_account_service, "_require_admin_key"),
            patch.object(auth_account_service, "_request_json", side_effect=lambda method, path, payload, **kwargs: calls.append(payload) or {"id": "new"}),
        ):
            auth_account_service.create_supabase_account(
                "080-0000-0001",
                "secret1",
                email=auth_account_service.account_login_email("users", 99),
            )
        self.assertEqual(calls[0]["phone"], "+818000000001")
        self.assertEqual(calls[0]["email"], "tourflow-user-99@auth.taxi-airport.jp")
        self.assertTrue(calls[0]["phone_confirm"])
        self.assertTrue(calls[0]["email_confirm"])

    def test_supabase_session_uses_admin_link_then_verify_otp(self):
        requests = []
        responses = [
            {"id": "auth-driver-a", "email": "tourflow-user-11@auth.taxi-airport.jp"},
            {"properties": {"hashed_token": "one-time-hash"}},
            {"access_token": "real-access", "refresh_token": "real-refresh", "user": {"id": "auth-driver-a"}},
        ]
        with (
            patch.object(auth_account_service, "_require_admin_key"),
            patch.object(auth_account_service, "_request_json", side_effect=lambda *args, **kwargs: requests.append((args, kwargs)) or responses.pop(0)),
        ):
            result = auth_account_service.issue_supabase_session("auth-driver-a")
        self.assertEqual(result["access_token"], "real-access")
        self.assertEqual(result["refresh_token"], "real-refresh")
        self.assertEqual(requests[1][0][1], "/auth/v1/admin/generate_link")
        self.assertEqual(requests[2][0][1], "/auth/v1/verify")
        self.assertEqual(requests[2][0][2], {"type": "email", "token_hash": "one-time-hash"})

    def test_cross_table_wechat_binding_conflict_is_rejected(self):
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE users SET wx_openid = 'shared', wx_appid = 'app' WHERE id = 11")
            conn.execute("UPDATE travel_agency_accounts SET wx_openid = 'shared', wx_appid = 'app' WHERE id = 22")
            conn.commit()
        with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
            wechat_auth_service.login_with_wechat_identity(
                {"wx_openid": "shared", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
            )
        self.assertEqual(str(error.exception), "wechat_binding_conflict")

    def test_unified_dispatch_client_accepts_driver_role(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        self.assertEqual(
            wechat_auth_service.bind_principal_wechat(
                principal,
                {"wx_openid": "dispatch-driver", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "dispatch_miniapp"},
            ),
            "bound",
        )

    def test_dispatch_mobile_login_accepts_driver_and_preserves_driver_role(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        auth_result = {"token": "driver-token", "user": principal}
        with patch.object(dispatcher_mobile_service, "authenticate_phone", return_value=auth_result):
            result = dispatcher_mobile_service.login_dispatcher(
                {
                    "phone": "08000000001",
                    "password": "not-read-by-mock",
                    "client_type": "dispatch_miniapp",
                }
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["user"]["role"], "driver")
        self.assertEqual(result["dispatcher"]["dispatcher_role"], "driver")
        self.assertEqual(result["dispatcher"]["dispatcher_id"], 11)

    def test_driver_client_rejects_agency_role(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-owner-a")
        with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
            wechat_auth_service.bind_principal_wechat(
                principal,
                {"wx_openid": "agency-driver", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"},
            )
        self.assertEqual(str(error.exception), "client_role_forbidden")

    def test_binding_same_account_to_different_wechat_is_mismatch(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        identity = {"wx_openid": "first", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
        wechat_auth_service.bind_principal_wechat(principal, identity)
        with self.assertRaises(wechat_auth_service.WechatAuthError) as error:
            wechat_auth_service.bind_principal_wechat(principal, {**identity, "wx_openid": "second"})
        self.assertEqual(str(error.exception), "wechat_binding_mismatch")

    def test_admin_unbind_allows_driver_to_bind_a_new_wechat(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        base = {"wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
        wechat_auth_service.bind_principal_wechat(principal, {**base, "wx_openid": "wechat-a"})
        auth_service.unbind_user_wechat(11, actor="admin-test")
        self.assertEqual(
            wechat_auth_service.bind_principal_wechat(principal, {**base, "wx_openid": "wechat-b"}),
            "bound",
        )

    def test_wechat_login_returns_real_supabase_tokens_not_legacy_jwt(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-driver-a")
        identity = {"wx_openid": "real-session", "wx_unionid": "", "wx_appid": "app", "wx_client_type": "driver_miniapp"}
        wechat_auth_service.bind_principal_wechat(principal, identity)
        expected = {"token": "sb-access", "access_token": "sb-access", "refresh_token": "sb-refresh", "user": principal}
        with (
            patch.object(wechat_auth_service, "issue_supabase_session", return_value=expected),
            patch.object(auth_service, "create_jwt", side_effect=AssertionError("legacy jwt must not be used")),
        ):
            result = wechat_auth_service.login_with_wechat_identity(identity)
        self.assertEqual(result["token"], "sb-access")
        self.assertEqual(result["refresh_token"], "sb-refresh")

    def test_invalid_old_password_does_not_update_supabase(self):
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = 11", (database.hash_password("correct-old"),))
            conn.commit()
        with (
            patch.object(auth_service, "supabase_enabled", return_value=True),
            patch.object(auth_service, "update_self_password") as remote_update,
        ):
            with self.assertRaisesRegex(ValueError, "invalid_old_password"):
                auth_service.change_user_password(11, "wrong-old", "new-secret", access_token="token")
        remote_update.assert_not_called()

    def test_platform_admin_can_set_specific_password_with_supabase_first(self):
        actor = {"role": "admin", "account_scope": "platform", "tenant_id": 1, "username": "platform-admin"}
        with (
            patch.object(account_service, "reset_supabase_password") as remote_reset,
        ):
            account = account_service.set_account_password(11, "TestOnly-Pass-01", actor, tenant_id=1)
        remote_reset.assert_called_once_with("auth-driver-a", "TestOnly-Pass-01")
        self.assertTrue(account["supabase_linked"])
        self.assertTrue(account["must_change_password"])
        self.assertIsNotNone(account["password_changed_at"])

    def test_weak_admin_password_is_rejected_without_remote_write(self):
        actor = {"role": "admin", "account_scope": "platform", "tenant_id": 1}
        with patch.object(account_service, "reset_supabase_password") as remote_reset:
            with self.assertRaisesRegex(ValueError, "password_policy_invalid"):
                account_service.set_account_password(11, "short", actor, tenant_id=1)
        remote_reset.assert_not_called()

    def test_supabase_failure_leaves_local_password_unchanged(self):
        actor = {"role": "admin", "account_scope": "platform", "tenant_id": 1}
        with closing(database.get_connection()) as conn:
            before = conn.execute("SELECT password_hash, password_changed_at FROM users WHERE id = 11").fetchone()
        with patch.object(account_service, "reset_supabase_password", side_effect=auth_account_service.SupabaseAuthError("upstream_failed")):
            with self.assertRaisesRegex(ValueError, "upstream_failed"):
                account_service.set_account_password(11, "TestOnly-Pass-02", actor, tenant_id=1)
        with closing(database.get_connection()) as conn:
            after = conn.execute("SELECT password_hash, password_changed_at FROM users WHERE id = 11").fetchone()
        self.assertEqual(tuple(before), tuple(after))

    def test_carrier_admin_cannot_set_another_tenants_password(self):
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (2, 'Carrier B', 'carrier-b')")
            conn.execute(
                """INSERT INTO users (id, tenant_id, username, password_hash, role, display_name, account_scope, is_active)
                   VALUES (31, 2, 'dispatcher-b', 'legacy', 'dispatcher', 'Dispatcher B', 'carrier', 1)"""
            )
            conn.commit()
        actor = {"role": "admin", "account_scope": "carrier", "tenant_id": 1}
        with self.assertRaises(PermissionError):
            account_service.set_account_password(31, "TestOnly-Pass-03", actor, tenant_id=2)

    def test_password_payload_is_redacted_from_operation_and_audit_serialization(self):
        test_password = "TestOnly-Pass-04"
        path = Path(self.temp.name) / "operations.log"
        with patch.object(operation_log_service, "OPERATION_LOG", path):
            operation_log_service.log_operation("POST", "/api/auth/admin/set-password", {"user_id": 11, "new_password": test_password})
        self.assertNotIn(test_password, path.read_text(encoding="utf-8"))
        self.assertNotIn(test_password, audit_service._json({"new_password": test_password}))

    def test_dispatcher_payload_cannot_impersonate_another_user(self):
        principal = auth_account_service.resolve_authenticated_principal("auth-dispatcher-a")
        context = dispatcher_mobile_service.get_dispatcher_context(
            {"dispatcher_id": "999", "dispatcher_code": "FAKE", "tenant_id": "999"},
            principal,
        )["dispatcher_context"]
        self.assertEqual(context["dispatcher_id"], 13)
        self.assertEqual(context["tenant_id"], 1)
        self.assertNotEqual(context["dispatcher_code"], "FAKE")


if __name__ == "__main__":
    unittest.main()

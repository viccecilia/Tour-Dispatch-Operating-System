import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from backend.db import database
from backend.services import auth_account_service, auth_service
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

        with patch.object(auth_service, "supabase_enabled", return_value=True):
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
            self.assertIsNone(
                auth_service.authenticate_wechat(
                    wx_openid="wx-unlinked",
                    client_type="driver_miniapp",
                )
            )

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


if __name__ == "__main__":
    unittest.main()

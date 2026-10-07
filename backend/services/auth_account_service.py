from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt
from jwt import PyJWKClient

from backend.config import (
    AUTH_MODE,
    SUPABASE_JWKS_URL,
    SUPABASE_PROJECT_ID,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_PLATFORM_ADMIN_EMAIL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from backend.db.database import get_connection
from backend.services.audit_service import record_audit


@dataclass
class SupabaseAuthError(Exception):
    code: str
    status: int = 400
    detail: str = ""

    def __str__(self) -> str:
        return self.code


_jwks_client: PyJWKClient | None = None


def account_login_email(source: str, local_id: int) -> str:
    """Return the private Supabase login alias for a local account.

    The product keeps phone-number login in its own UI.  Supabase phone auth
    requires an SMS provider even when OTP confirmation is disabled, so local
    phone numbers are resolved to confirmed, non-public email aliases instead.
    """
    namespace = "agency" if source == "travel_agency_accounts" else "user"
    return f"tourflow-{namespace}-{int(local_id)}@auth.taxi-airport.jp"


def supabase_enabled() -> bool:
    return AUTH_MODE in {"supabase_dual", "supabase"}


def supabase_admin_ready() -> bool:
    return bool(supabase_enabled() and SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def to_supabase_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "@" in raw:
        return raw.lower()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return f"+{digits}" if digits else ""
    if digits.startswith("81") and len(digits) >= 10:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) >= 10:
        return f"+81{digits[1:]}"
    return f"+{digits}" if digits else ""


def sign_in_with_password(login: str, password: str) -> dict[str, Any]:
    identifier = resolve_login_identifier(login)
    if not identifier or not password:
        raise SupabaseAuthError("invalid_credentials", 401)
    field = "email" if "@" in identifier else "phone"
    payload = _request_json(
        "POST",
        "/auth/v1/token?grant_type=password",
        {field: identifier, "password": password},
        public=True,
    )
    principal = resolve_authenticated_principal(str((payload.get("user") or {}).get("id") or ""))
    if not principal or not principal.get("is_active"):
        raise SupabaseAuthError("invalid_credentials", 401)
    return _session_payload(payload, principal)


def refresh_session(refresh_token: str) -> dict[str, Any]:
    if not refresh_token:
        raise SupabaseAuthError("invalid_refresh_token", 401)
    payload = _request_json(
        "POST",
        "/auth/v1/token?grant_type=refresh_token",
        {"refresh_token": refresh_token},
        public=True,
    )
    principal = resolve_authenticated_principal(str((payload.get("user") or {}).get("id") or ""))
    if not principal or not principal.get("is_active"):
        raise SupabaseAuthError("invalid_refresh_token", 401)
    return _session_payload(payload, principal)


def create_supabase_account(
    phone: str,
    password: str,
    *,
    app_metadata: dict[str, Any] | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    _require_admin_key()
    normalized_phone = to_supabase_phone(phone)
    if not normalized_phone and not email:
        raise SupabaseAuthError("phone_required")
    body: dict[str, Any] = {
        "password": password,
        "app_metadata": app_metadata or {},
    }
    if normalized_phone:
        body.update({"phone": normalized_phone, "phone_confirm": True})
    if email:
        body.update({"email": str(email).strip().lower(), "email_confirm": True})
    return _request_json("POST", "/auth/v1/admin/users", body, admin=True)


def get_supabase_account(auth_user_id: str) -> dict[str, Any]:
    _require_admin_key()
    if not auth_user_id:
        raise SupabaseAuthError("supabase_identity_required")
    return _request_json("GET", f"/auth/v1/admin/users/{auth_user_id}", None, admin=True)


def is_supabase_account_enabled(account: dict[str, Any]) -> bool:
    banned_until = str(account.get("banned_until") or "").strip()
    if not banned_until:
        return True
    try:
        value = datetime.fromisoformat(banned_until.replace("Z", "+00:00"))
        return value <= datetime.now(timezone.utc)
    except ValueError:
        return False


def issue_supabase_session(auth_user_id: str) -> dict[str, Any]:
    """Create a real Supabase session for a server-verified local identity.

    Supabase Admin generate_link supplies a one-time hashed token.  It is
    consumed immediately by the backend through verifyOtp; neither the token
    hash nor the action link is returned to the miniapp.
    """
    account = get_supabase_account(auth_user_id)
    if not is_supabase_account_enabled(account):
        raise SupabaseAuthError("account_disabled", 403)
    email = str(account.get("email") or "").strip().lower()
    if not email:
        raise SupabaseAuthError("supabase_email_alias_required", 409)
    generated = _request_json(
        "POST",
        "/auth/v1/admin/generate_link",
        {"type": "magiclink", "email": email},
        admin=True,
    )
    properties = generated.get("properties") if isinstance(generated.get("properties"), dict) else {}
    token_hash = str(generated.get("hashed_token") or properties.get("hashed_token") or "")
    if not token_hash:
        raise SupabaseAuthError("supabase_session_issue_failed", 502)
    payload = _request_json(
        "POST",
        "/auth/v1/verify",
        {"type": "email", "token_hash": token_hash},
        public=True,
    )
    returned_id = str((payload.get("user") or {}).get("id") or "")
    if returned_id != auth_user_id:
        raise SupabaseAuthError("supabase_identity_mismatch", 502)
    principal = resolve_authenticated_principal(auth_user_id)
    if not principal or not principal.get("is_active"):
        raise SupabaseAuthError("account_disabled", 403)
    return _session_payload(payload, principal)


def update_supabase_phone(auth_user_id: str, phone: str) -> dict[str, Any]:
    return update_supabase_account(auth_user_id, {"phone": to_supabase_phone(phone), "phone_confirm": True})


def reset_supabase_password(auth_user_id: str, password: str) -> dict[str, Any]:
    return update_supabase_account(auth_user_id, {"password": password})


def disable_supabase_account(auth_user_id: str) -> dict[str, Any]:
    # A long finite ban is reversible through the same Admin API.
    return update_supabase_account(auth_user_id, {"ban_duration": "876000h"})


def enable_supabase_account(auth_user_id: str) -> dict[str, Any]:
    return update_supabase_account(auth_user_id, {"ban_duration": "none"})


def update_supabase_account(auth_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_admin_key()
    if not auth_user_id:
        raise SupabaseAuthError("supabase_identity_required")
    return _request_json("PUT", f"/auth/v1/admin/users/{auth_user_id}", payload, admin=True)


def delete_supabase_account(auth_user_id: str) -> None:
    _require_admin_key()
    if auth_user_id:
        _request_json("DELETE", f"/auth/v1/admin/users/{auth_user_id}", None, admin=True)


def update_self_password(access_token: str, new_password: str) -> dict[str, Any]:
    if len(str(new_password or "")) < 6:
        raise SupabaseAuthError("password_too_short")
    return _request_json(
        "PUT",
        "/auth/v1/user",
        {"password": new_password},
        access_token=access_token,
        public=True,
    )


def sign_out(access_token: str) -> None:
    _request_json("POST", "/auth/v1/logout?scope=global", {}, access_token=access_token, public=True)


def verify_supabase_access_token(token: str) -> dict[str, Any]:
    global _jwks_client
    if not (token and SUPABASE_JWKS_URL and SUPABASE_URL):
        raise SupabaseAuthError("invalid_access_token", 401)
    try:
        if _jwks_client is None:
            _jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, lifespan=300)
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except Exception as exc:
        raise SupabaseAuthError("invalid_access_token", 401, type(exc).__name__) from exc


def resolve_authenticated_principal(auth_user_id: str) -> dict[str, Any] | None:
    if not auth_user_id:
        return None
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT u.*, t.name AS tenant_name, t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.supabase_user_id = ?
            LIMIT 1
            """,
            (auth_user_id,),
        ).fetchone()
        if user:
            row = dict(user)
            scope = str(row.get("account_scope") or ("driver" if row.get("role") == "driver" else "carrier"))
            tenant_name = row.get("tenant_name") or "DAITORA"
            tenant_slug = row.get("tenant_slug") or "daitora"
            company_code = re.sub(r"[^0-9A-Za-z]", "", str(tenant_slug).upper()) or "DAITORA"
            return {
                "auth_user_id": auth_user_id,
                "id": row["id"],
                "local_user_id": row["id"],
                "agency_account_id": None,
                "username": row["username"],
                "display_name": row["display_name"],
                "phone": row.get("phone") or "",
                "account_scope": scope,
                "role": row["role"],
                "tenant_id": int(row.get("tenant_id") or 1),
                "organization_type": "platform" if scope == "platform" else "carrier",
                "organization_id": None if scope == "platform" else int(row.get("tenant_id") or 1),
                "profile_type": row.get("profile_type"),
                "profile_id": row.get("profile_id"),
                "wx_bind_status": row.get("wx_bind_status") or "unbound",
                "must_change_password": bool(row.get("must_change_password")),
                "is_active": bool(row.get("is_active")),
                "tenant_name": tenant_name,
                "tenant_slug": tenant_slug,
                "company_code": company_code,
                "account_login": re.sub(r"\D", "", str(row.get("phone") or "")) or row["username"],
                "tenant": {
                    "id": int(row.get("tenant_id") or 1),
                    "name": tenant_name,
                    "slug": tenant_slug,
                    "company_code": company_code,
                },
            }
        try:
            agency = conn.execute(
                """
                SELECT a.*, c.company_code, c.company_name
                FROM travel_agency_accounts a
                JOIN travel_agency_companies c
                  ON c.id = a.company_id AND c.tenant_id = a.tenant_id
                WHERE a.supabase_user_id = ?
                LIMIT 1
                """,
                (auth_user_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            agency = None
    if not agency:
        return None
    row = dict(agency)
    return {
        "auth_user_id": auth_user_id,
        "id": f"agency:{row['id']}",
        "local_user_id": None,
        "agency_account_id": row["id"],
        "username": row.get("phone") or row.get("display_name"),
        "display_name": row["display_name"],
        "phone": row.get("phone") or "",
        "account_scope": "agency",
        "role": row["role"],
        "tenant_id": int(row.get("tenant_id") or 1),
        "organization_type": "agency",
        "organization_id": int(row["company_id"]),
        "company_id": int(row["company_id"]),
        "company_code": row.get("company_code"),
        "company_name": row.get("company_name"),
        "profile_type": "agency_account",
        "profile_id": int(row["id"]),
        "wx_bind_status": row.get("wx_bind_status") or "unbound",
        "must_change_password": bool(row.get("must_change_password")),
        "is_active": str(row.get("status") or "active") == "active",
    }


def link_identity(
    *,
    auth_user_id: str,
    local_user_id: int | None = None,
    agency_account_id: int | None = None,
    actor: str = "system",
) -> None:
    if bool(local_user_id) == bool(agency_account_id):
        raise ValueError("identity_link_target_required")
    with get_connection() as conn:
        duplicate_user = conn.execute(
            "SELECT id FROM users WHERE supabase_user_id = ? AND id != COALESCE(?, -1)",
            (auth_user_id, local_user_id),
        ).fetchone()
        duplicate_agency = conn.execute(
            "SELECT id FROM travel_agency_accounts WHERE supabase_user_id = ? AND id != COALESCE(?, -1)",
            (auth_user_id, agency_account_id),
        ).fetchone()
        if duplicate_user or duplicate_agency:
            raise ValueError("supabase_identity_already_linked")
        if local_user_id:
            conn.execute(
                "UPDATE users SET supabase_user_id = ?, auth_linked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (auth_user_id, local_user_id),
            )
            entity_type, entity_id = "user", local_user_id
        else:
            conn.execute(
                "UPDATE travel_agency_accounts SET supabase_user_id = ?, auth_linked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (auth_user_id, agency_account_id),
            )
            entity_type, entity_id = "travel_agency_account", agency_account_id
        conn.commit()
    record_audit(
        "supabase_identity_link",
        entity_type,
        entity_id,
        after={"supabase_user_id": auth_user_id},
        actor=actor,
        source_path="/api/accounts",
    )


def resolve_login_identifier(login: str) -> str:
    value = str(login or "").strip()
    if not value:
        return ""
    if "@" in value:
        return value.lower()
    digits = re.sub(r"\D", "", value)
    try:
        with get_connection() as conn:
            platform = conn.execute(
                """
                SELECT id FROM users
                WHERE LOWER(username) = LOWER(?)
                  AND account_scope = 'platform' AND role = 'admin' AND is_active = 1
                LIMIT 1
                """,
                (value,),
            ).fetchone()
    except sqlite3.OperationalError:
        platform = None
    if platform and SUPABASE_PLATFORM_ADMIN_EMAIL:
        return SUPABASE_PLATFORM_ADMIN_EMAIL
    try:
        with get_connection() as conn:
            agency = conn.execute(
                """
                SELECT a.id, a.supabase_user_id
                FROM agencies ag
                JOIN travel_agency_companies c
                  ON UPPER(c.company_code) = UPPER(ag.agency_code)
                 AND c.tenant_id = ag.tenant_id
                JOIN travel_agency_accounts a
                  ON a.company_id = c.id AND a.tenant_id = c.tenant_id
                 AND a.role = 'agency_owner' AND COALESCE(a.status, 'active') = 'active'
                WHERE UPPER(ag.portal_code) = UPPER(?)
                ORDER BY a.id LIMIT 1
                """,
                (value,),
            ).fetchone()
    except sqlite3.OperationalError:
        agency = None
    if agency and agency["supabase_user_id"]:
        return account_login_email("travel_agency_accounts", int(agency["id"]))

    linked_matches: list[tuple[str, int]] = []
    if digits:
        try:
            with get_connection() as conn:
                for row in conn.execute(
                    """
                    SELECT id, phone FROM users
                    WHERE is_active = 1 AND COALESCE(supabase_user_id, '') <> ''
                    """
                ).fetchall():
                    if re.sub(r"\D", "", str(row["phone"] or "")) == digits:
                        linked_matches.append(("users", int(row["id"])))
                for row in conn.execute(
                    """
                    SELECT id, phone FROM travel_agency_accounts
                    WHERE COALESCE(status, 'active') = 'active'
                      AND COALESCE(supabase_user_id, '') <> ''
                    """
                ).fetchall():
                    if re.sub(r"\D", "", str(row["phone"] or "")) == digits:
                        linked_matches.append(("travel_agency_accounts", int(row["id"])))
        except sqlite3.OperationalError:
            linked_matches = []
    if len(linked_matches) == 1:
        return account_login_email(*linked_matches[0])
    return to_supabase_phone(digits or value)


def _session_payload(payload: dict[str, Any], principal: dict[str, Any]) -> dict[str, Any]:
    access_token = str(payload.get("access_token") or "")
    return {
        "token": access_token,
        "access_token": access_token,
        "refresh_token": str(payload.get("refresh_token") or ""),
        "expires_in": payload.get("expires_in"),
        "expires_at": payload.get("expires_at"),
        "user": principal,
    }


def _request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    *,
    public: bool = False,
    admin: bool = False,
    access_token: str = "",
) -> dict[str, Any]:
    if not SUPABASE_URL:
        raise SupabaseAuthError("supabase_not_configured", 503)
    key = SUPABASE_SERVICE_ROLE_KEY if admin else SUPABASE_PUBLISHABLE_KEY
    if not key:
        raise SupabaseAuthError("supabase_admin_not_configured" if admin else "supabase_not_configured", 503)
    headers = {"apikey": key, "Content-Type": "application/json"}
    # New sb_secret_* values are opaque API keys, not JWTs.  Legacy
    # service_role values remain valid Bearer tokens.
    bearer = ("" if SUPABASE_SERVICE_ROLE_KEY.startswith("sb_secret_") else SUPABASE_SERVICE_ROLE_KEY) if admin else access_token
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(f"{SUPABASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(raw)
        except json.JSONDecodeError:
            error_payload = {}
        code = str(error_payload.get("error_code") or error_payload.get("code") or "supabase_request_failed")
        if exc.code in {400, 401} and path.startswith("/auth/v1/token"):
            code = "invalid_credentials"
        raise SupabaseAuthError(code, exc.code) from exc
    except (URLError, TimeoutError) as exc:
        raise SupabaseAuthError("supabase_unavailable", 503, type(exc).__name__) from exc


def _require_admin_key() -> None:
    if not supabase_admin_ready():
        raise SupabaseAuthError("supabase_admin_not_configured", 503)

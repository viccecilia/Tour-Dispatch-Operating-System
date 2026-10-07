from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.config import WECHAT_MINIAPP_APPID, WECHAT_MINIAPP_SECRET
from backend.db.database import get_connection
from backend.services.auth_account_service import (
    SupabaseAuthError,
    issue_supabase_session,
    resolve_authenticated_principal,
)
from backend.services.audit_service import record_audit


@dataclass
class WechatAuthError(Exception):
    code: str
    status: int = 400

    def __str__(self) -> str:
        return self.code


DRIVER_CLIENTS = {"driver_miniapp", "miniapp_driver"}
DISPATCH_CLIENTS = {"dispatch_miniapp", "miniapp_dispatch", "company_lite"}
AGENCY_CLIENTS = {"agency_miniapp", "miniapp_agency"}
ALLOWED_CLIENTS = DRIVER_CLIENTS | DISPATCH_CLIENTS | AGENCY_CLIENTS
DISPATCH_ROLES = {"admin", "dispatcher", "operations_manager"}
AGENCY_ROLES = {"agency_owner", "agency_customer_service", "agency_guide", "agency_finance"}


def exchange_wechat_code(wx_code: str | None, client_type: str) -> dict[str, str]:
    code = str(wx_code or "").strip()
    client = _normalize_client_type(client_type)
    if not code:
        raise WechatAuthError("wx_code_required")
    if not WECHAT_MINIAPP_APPID or not WECHAT_MINIAPP_SECRET:
        raise WechatAuthError("wechat_code_exchange_unavailable", 503)
    query = urlencode(
        {
            "appid": WECHAT_MINIAPP_APPID,
            "secret": WECHAT_MINIAPP_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    try:
        with urlopen(f"https://api.weixin.qq.com/sns/jscode2session?{query}", timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise WechatAuthError("wechat_code_exchange_failed", 502) from exc
    if data.get("errcode") or not data.get("openid"):
        raise WechatAuthError("wechat_code_exchange_failed", 401)
    return {
        "wx_openid": str(data.get("openid") or ""),
        "wx_unionid": str(data.get("unionid") or ""),
        "wx_appid": WECHAT_MINIAPP_APPID,
        "wx_client_type": client,
    }


def bind_principal_wechat(principal: dict[str, Any], identity: dict[str, str]) -> str:
    _ensure_wechat_identity_schema()
    _assert_principal_client(principal, identity.get("wx_client_type") or "")
    target = _target(principal)
    matches = _matching_targets(identity)
    other = [item for item in matches if item != target]
    if len(matches) > 1:
        _audit("wechat_binding_conflict", principal, identity)
        raise WechatAuthError("wechat_binding_conflict", 409)
    if other:
        _audit("wechat_already_bound", principal, identity)
        raise WechatAuthError("wechat_already_bound", 409)

    table, local_id = target
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT wx_openid, wx_unionid, wx_appid, wx_client_type FROM {table} WHERE id = ?",
            (local_id,),
        ).fetchone()
        if not row:
            raise WechatAuthError("account_not_found", 404)
        current_openid = str(row["wx_openid"] or "")
        current_unionid = str(row["wx_unionid"] or "")
        current_appid = str(row["wx_appid"] or "")
        same_union = bool(identity.get("wx_unionid") and current_unionid == identity["wx_unionid"])
        same_open = bool(
            current_openid == identity["wx_openid"]
            and (not current_appid or current_appid == identity["wx_appid"])
        )
        if (current_openid or current_unionid) and not (same_union or same_open):
            _audit("wechat_binding_mismatch", principal, identity)
            raise WechatAuthError("wechat_binding_mismatch", 409)
        conn.execute(
            f"""
            UPDATE {table}
            SET wx_openid = ?, wx_unionid = ?, wx_appid = ?, wx_client_type = ?,
                wx_bound_at = COALESCE(wx_bound_at, CURRENT_TIMESTAMP),
                wx_bind_status = 'bound', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                identity["wx_openid"],
                identity.get("wx_unionid") or None,
                identity["wx_appid"],
                identity["wx_client_type"],
                local_id,
            ),
        )
        conn.commit()
    _audit("wechat_bind", principal, identity)
    return "ok" if current_openid or current_unionid else "bound"


def login_with_wechat_identity(identity: dict[str, str]) -> dict[str, Any]:
    _ensure_wechat_identity_schema()
    matches = _matching_targets(identity)
    if not matches:
        raise WechatAuthError("wechat_not_bound", 404)
    if len(matches) != 1:
        _audit("wechat_binding_conflict", None, identity)
        raise WechatAuthError("wechat_binding_conflict", 409)
    auth_user_id = _auth_user_id_for_target(matches[0])
    if not auth_user_id:
        raise WechatAuthError("supabase_identity_required", 409)
    principal = _principal_for_target(matches[0])
    if not principal or not principal.get("is_active"):
        raise WechatAuthError("account_disabled", 403)
    _assert_principal_client(principal, identity.get("wx_client_type") or "")
    try:
        result = issue_supabase_session(auth_user_id)
    except SupabaseAuthError as exc:
        raise WechatAuthError(str(exc), exc.status) from exc
    _mark_login(principal)
    _audit("wechat_auto_login_ok", principal, identity)
    return result


def login_with_wechat_code(wx_code: str | None, client_type: str) -> dict[str, Any]:
    return login_with_wechat_identity(exchange_wechat_code(wx_code, client_type))


def _ensure_wechat_identity_schema() -> None:
    """Keep existing Trial databases compatible before the first agency login."""
    required = {
        "wx_openid": "TEXT",
        "wx_unionid": "TEXT",
        "wx_appid": "TEXT",
        "wx_client_type": "TEXT",
        "wx_bind_status": "TEXT NOT NULL DEFAULT 'unbound'",
        "wx_bound_at": "TEXT",
    }
    with get_connection() as conn:
        for table in ("users", "travel_agency_accounts"):
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            present = {
                str(row["name"])
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in required.items():
                if column not in present:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()


def _matching_targets(identity: dict[str, str]) -> list[tuple[str, int]]:
    openid = str(identity.get("wx_openid") or "")
    unionid = str(identity.get("wx_unionid") or "")
    appid = str(identity.get("wx_appid") or "")
    targets: set[tuple[str, int]] = set()
    with get_connection() as conn:
        for table in ("users", "travel_agency_accounts"):
            try:
                rows = conn.execute(
                    f"""
                    SELECT id FROM {table}
                    WHERE (COALESCE(?, '') <> '' AND wx_unionid = ?)
                       OR (COALESCE(?, '') <> '' AND wx_openid = ?
                           AND (COALESCE(wx_appid, '') = '' OR wx_appid = ?))
                    """,
                    (unionid, unionid, openid, openid, appid),
                ).fetchall()
            except Exception:
                rows = []
            targets.update((table, int(row["id"])) for row in rows)
    return sorted(targets)


def _target(principal: dict[str, Any]) -> tuple[str, int]:
    if principal.get("agency_account_id"):
        return "travel_agency_accounts", int(principal["agency_account_id"])
    if principal.get("local_user_id") or principal.get("id"):
        return "users", int(principal.get("local_user_id") or principal["id"])
    raise WechatAuthError("account_not_found", 404)


def _principal_for_target(target: tuple[str, int]) -> dict[str, Any] | None:
    auth_user_id = _auth_user_id_for_target(target)
    return resolve_authenticated_principal(auth_user_id) if auth_user_id else None


def _auth_user_id_for_target(target: tuple[str, int]) -> str:
    table, local_id = target
    with get_connection() as conn:
        row = conn.execute(f"SELECT supabase_user_id FROM {table} WHERE id = ?", (local_id,)).fetchone()
    return str(row["supabase_user_id"] or "") if row else ""


def _normalize_client_type(client_type: str) -> str:
    value = str(client_type or "").strip().lower()
    if value not in ALLOWED_CLIENTS:
        raise WechatAuthError("invalid_client_type")
    return value


def _assert_principal_client(principal: dict[str, Any], client_type: str) -> None:
    client = _normalize_client_type(client_type)
    role = str(principal.get("role") or "")
    scope = str(principal.get("account_scope") or "")
    allowed = (
        (client in DRIVER_CLIENTS and role == "driver" and scope == "driver")
        or (client in DISPATCH_CLIENTS and role in DISPATCH_ROLES and scope in {"carrier", "platform"})
        or (client in AGENCY_CLIENTS and role in AGENCY_ROLES and scope == "agency")
    )
    if not allowed:
        raise WechatAuthError("client_role_forbidden", 403)


def _mark_login(principal: dict[str, Any]) -> None:
    table, local_id = _target(principal)
    with get_connection() as conn:
        conn.execute(f"UPDATE {table} SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (local_id,))
        conn.commit()


def _audit(action: str, principal: dict[str, Any] | None, identity: dict[str, str]) -> None:
    target = None
    if principal:
        try:
            target = _target(principal)[1]
        except WechatAuthError:
            target = None
    record_audit(
        action,
        "auth",
        target,
        after={
            "client_type": identity.get("wx_client_type"),
            "account_scope": principal.get("account_scope") if principal else None,
            "role": principal.get("role") if principal else None,
        },
        actor="auth",
        source_path="/api/auth/wechat-login",
    )

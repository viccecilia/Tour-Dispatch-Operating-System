import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.config import DEMO_MODE, JWT_EXPIRES_SECONDS, JWT_SECRET, SUPER_WECHAT_IDS, TRIAL_MODE, WECHAT_MINIAPP_APPID, WECHAT_MINIAPP_SECRET
from backend.db.database import get_connection, hash_password
from backend.services.audit_service import record_audit
from backend.services.tenant_context import get_current_tenant_id, set_current_tenant_id


ROLES = {"admin", "dispatcher", "operations_manager", "driver"}
MINIAPP_CLIENTS = {"driver_miniapp", "dispatch_miniapp", "miniapp_driver", "miniapp_dispatch"}
DEFAULT_COMPANY_CODE = "DAITORA"


def company_code_for_tenant(tenant_slug: str | None = None, tenant_name: str | None = None) -> str:
    raw = str(tenant_slug or tenant_name or DEFAULT_COMPANY_CODE).strip()
    if raw.lower() in {"demo", "demo travel company"}:
        return DEFAULT_COMPANY_CODE
    code = "".join(ch for ch in raw.upper() if ch.isalnum())
    return code or DEFAULT_COMPANY_CODE


def split_company_account(account: str | None) -> tuple[str | None, str]:
    text = str(account or "").strip()
    if "-" not in text:
        return None, text
    prefix, rest = text.split("-", 1)
    return company_code_for_tenant(prefix), rest.strip()


def company_login_name(phone: str | None, tenant_slug: str | None = None, tenant_name: str | None = None) -> str:
    digits = normalize_phone(phone or "")
    code = company_code_for_tenant(tenant_slug, tenant_name)
    return f"{code}-{digits}" if digits else code


def authenticate(username: str, password: str) -> Optional[dict]:
    company_code, phone_part = split_company_account(username)
    if company_code and normalize_phone(phone_part):
        return authenticate_phone(username, password)
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                u.id,
                u.tenant_id,
                u.username,
                u.password_hash,
                u.role,
                u.display_name,
                u.phone,
                u.profile_type,
                u.profile_id,
                u.wx_bind_status,
                u.must_change_password,
                u.is_active,
                t.name AS tenant_name,
                t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()

    if not user or not user["is_active"]:
        return None
    if user["password_hash"] != hash_password(password):
        return None
    if user["role"] not in ROLES:
        return None

    public = public_user(dict(user))
    _mark_login(public["id"])
    return {"token": create_jwt(public), "user": public}


def authenticate_phone(phone: str, password: str, wx_openid: str | None = None, wx_unionid: str | None = None, client_type: str = "web") -> Optional[dict]:
    requested_company_code, phone_part = split_company_account(phone)
    normalized = normalize_phone(phone_part)
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                u.id,
                u.tenant_id,
                u.username,
                u.password_hash,
                u.role,
                u.display_name,
                u.phone,
                u.profile_type,
                u.profile_id,
                u.wx_openid,
                u.wx_unionid,
                u.wx_bound_at,
                u.wx_bind_status,
                u.must_change_password,
                u.is_active,
                t.name AS tenant_name,
                t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE REPLACE(REPLACE(REPLACE(COALESCE(u.phone, ''), '-', ''), ' ', ''), '+', '') = ?
               OR u.username = ?
               OR u.username = ?
            ORDER BY u.is_active DESC, u.id ASC
            LIMIT 1
            """,
            (normalized, phone, company_login_name(normalized)),
        ).fetchone()
        if user and requested_company_code:
            row_company = company_code_for_tenant(user["tenant_slug"], user["tenant_name"])
            if requested_company_code != row_company:
                _audit_auth("login_fail", {"phone": phone, "reason": "company_mismatch", "company_code": requested_company_code})
                return None
    if not user or not user["is_active"]:
        _audit_auth("login_fail", {"phone": phone, "reason": "user_not_found_or_inactive"})
        return None
    if user["password_hash"] != hash_password(password):
        _audit_auth("login_fail", {"phone": phone, "reason": "invalid_password"})
        return None
    user_data = dict(user)
    if _requires_wechat(client_type, user_data["role"]):
        if not wx_openid:
            _audit_auth("login_fail", {"phone": phone, "reason": "wechat_openid_required"})
            return {"error": "wechat_openid_required"}  # type: ignore[return-value]
        bind_result = _ensure_wechat_binding(user_data, wx_openid, wx_unionid)
        if bind_result == "mismatch":
            _audit_auth("wechat_binding_mismatch", {"phone": phone, "user_id": user_data["id"], "client_type": client_type})
            return {"error": "wechat_binding_mismatch"}  # type: ignore[return-value]
        user_data = _load_user_public(user_data["id"]) or user_data
    public = public_user(user_data)
    _mark_login(public["id"])
    _audit_auth("login_ok", {"phone": phone, "user_id": public["id"], "role": public["role"], "client_type": client_type})
    return {"token": create_jwt(public), "user": public}


def authenticate_wechat(wx_openid: str | None = None, wx_unionid: str | None = None, client_type: str = "dispatch_miniapp") -> Optional[dict]:
    openid = str(wx_openid or "").strip()
    unionid = str(wx_unionid or "").strip()
    if not openid and not unionid:
        return None
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                u.id,
                u.tenant_id,
                u.username,
                u.role,
                u.display_name,
                u.phone,
                u.profile_type,
                u.profile_id,
                u.wx_bind_status,
                u.must_change_password,
                u.is_active,
                t.name AS tenant_name,
                t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.is_active = 1
              AND (
                  (COALESCE(u.wx_openid, '') <> '' AND u.wx_openid = ?)
                  OR (COALESCE(u.wx_unionid, '') <> '' AND u.wx_unionid = ?)
              )
            ORDER BY u.id ASC
            LIMIT 1
            """,
            (openid, unionid),
        ).fetchone()
    if not user:
        _audit_auth("wechat_auto_login_fail", {"reason": "wechat_not_bound", "client_type": client_type})
        return None
    user_data = dict(user)
    if user_data["role"] not in ROLES:
        _audit_auth("wechat_auto_login_fail", {"user_id": user_data["id"], "reason": "invalid_role", "client_type": client_type})
        return None
    public = public_user(user_data)
    _mark_login(public["id"])
    _audit_auth("wechat_auto_login_ok", {"user_id": public["id"], "role": public["role"], "client_type": client_type})
    return {"token": create_jwt(public), "user": public}


def resolve_wechat_login_code(wx_code: str | None) -> dict:
    code = str(wx_code or "").strip()
    if not code:
        return {}
    if not WECHAT_MINIAPP_APPID or not WECHAT_MINIAPP_SECRET:
        raise ValueError("wechat_code_exchange_unavailable")
    query = urlencode(
        {
            "appid": WECHAT_MINIAPP_APPID,
            "secret": WECHAT_MINIAPP_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"
    with urlopen(url, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("errcode"):
        raise ValueError(f"wechat_code_exchange_failed:{data.get('errcode')}")
    return {
        "wx_openid": data.get("openid") or "",
        "wx_unionid": data.get("unionid") or "",
    }


def register_bound_account(payload: dict) -> dict:
    phone = str(payload.get("phone") or "").strip()
    password = str(payload.get("password") or "").strip()
    role = str(payload.get("role") or "").strip()
    display_name = str(payload.get("display_name") or "").strip()
    wx_openid = str(payload.get("wx_openid") or "").strip()
    wx_unionid = str(payload.get("wx_unionid") or "").strip()
    client_type = str(payload.get("client_type") or "web").strip()
    if not phone:
        raise ValueError("phone_required")
    if not password:
        raise ValueError("password_required")
    if role not in ROLES:
        raise ValueError("invalid_role")
    normalized = normalize_phone(phone)
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        existing = _find_user_by_phone(conn, normalized)
        if existing and existing["is_active"] and existing["password_hash"]:
            raise ValueError("account_already_registered")
        if role == "driver":
            profile = _find_driver_profile(conn, tenant_id, normalized)
            if not profile:
                raise ValueError("driver_phone_not_preloaded")
            profile_type = "driver"
            profile_id = profile["id"]
            display_name = display_name or profile["name"] or phone
            if profile["user_id"]:
                existing = conn.execute("SELECT * FROM users WHERE id = ?", (profile["user_id"],)).fetchone()
        else:
            profile = _find_operator_profile(conn, tenant_id, normalized, role)
            if not profile:
                raise ValueError("operator_phone_not_preloaded")
            profile_type = "operator"
            profile_id = profile["profile_id"]
            display_name = display_name or profile["display_name"] or phone
            existing = conn.execute("SELECT * FROM users WHERE id = ?", (profile["user_id"],)).fetchone()

        if existing:
            user_id = existing["id"]
            conn.execute(
                """
                UPDATE users
                SET phone = ?,
                    username = ?,
                    password_hash = ?,
                    role = ?,
                    display_name = ?,
                    profile_type = ?,
                    profile_id = ?,
                    is_active = 1,
                    password_changed_at = CURRENT_TIMESTAMP,
                    must_change_password = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (phone, company_login_name(phone), hash_password(password), role, display_name, profile_type, profile_id, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (
                    tenant_id, username, password_hash, role, display_name, phone,
                    profile_type, profile_id, is_active, password_changed_at, must_change_password, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP)
                """,
                (tenant_id, company_login_name(phone), hash_password(password), role, display_name, phone, profile_type, profile_id),
            )
            user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        if profile_type == "driver":
            conn.execute("UPDATE drivers SET user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (user_id, tenant_id, profile_id))
        else:
            conn.execute("UPDATE operator_profiles SET user_id = ?, phone = COALESCE(NULLIF(phone, ''), ?), updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?", (user_id, phone, tenant_id, profile_id))
        conn.commit()
    if _requires_wechat(client_type, role):
        if not wx_openid:
            raise ValueError("wechat_openid_required")
        _ensure_wechat_binding(_load_user_public(user_id) or {"id": user_id}, wx_openid, wx_unionid)
    user = _load_user_public(user_id)
    if not user:
        raise ValueError("account_not_found")
    _audit_auth("register_bind", {"user_id": user_id, "phone": phone, "role": role, "profile_type": user.get("profile_type"), "profile_id": user.get("profile_id")})
    public = public_user(user)
    return {"token": create_jwt(public), "user": public}


def reset_user_password_to_phone_tail(user_id: int | str, actor: str = "system") -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? AND tenant_id = ?", (user_id, get_current_tenant_id())).fetchone()
        if not row:
            return None
        tail = phone_password_tail(row["phone"] or row["username"])
        if not tail:
            raise ValueError("phone_tail_unavailable")
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_changed_at = CURRENT_TIMESTAMP,
                must_change_password = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (hash_password(tail), user_id, get_current_tenant_id()),
        )
        conn.commit()
    user = _load_user_public(int(user_id))
    _audit_auth("password_reset", {"user_id": user_id, "reset_to": "phone_last_6"}, actor=actor)
    return public_user(user) if user else None


def change_user_password(user_id: int | str, old_password: str, new_password: str, actor: str = "system") -> dict | None:
    if not old_password or not new_password:
        raise ValueError("password_required")
    if len(str(new_password)) < 6:
        raise ValueError("password_too_short")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? AND tenant_id = ?", (user_id, get_current_tenant_id())).fetchone()
        if not row:
            return None
        if row["password_hash"] != hash_password(old_password):
            raise ValueError("invalid_old_password")
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_changed_at = CURRENT_TIMESTAMP,
                must_change_password = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (hash_password(new_password), user_id, get_current_tenant_id()),
        )
        conn.commit()
    user = _load_user_public(int(user_id))
    _audit_auth("password_change", {"user_id": user_id}, actor=actor)
    return public_user(user) if user else None


def phone_password_tail(phone: str | None) -> str:
    digits = normalize_phone(phone or "")
    return digits[-6:] if len(digits) >= 6 else ""


def unbind_user_wechat(user_id: int | str, actor: str = "system") -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? AND tenant_id = ?", (user_id, get_current_tenant_id())).fetchone()
        if not row:
            return None
        before = public_user(dict(row))
        conn.execute(
            """
            UPDATE users
            SET wx_openid = NULL,
                wx_unionid = NULL,
                wx_bound_at = NULL,
                wx_bind_status = 'unbound',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (user_id, get_current_tenant_id()),
        )
        conn.commit()
    after = _load_user_public(int(user_id))
    record_audit("wechat_unbind", "user", user_id, before=before, after=after, actor=actor, source_path="/api/auth/admin/unbind-wechat")
    return public_user(after) if after else None


def get_user_by_token(token: str) -> Optional[dict]:
    payload = verify_jwt(token)
    if not payload:
        return None

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                u.id,
                u.tenant_id,
                u.username,
                u.role,
                u.display_name,
                u.phone,
                u.profile_type,
                u.profile_id,
                u.wx_bind_status,
                u.must_change_password,
                u.is_active,
                t.name AS tenant_name,
                t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.id = ? AND u.tenant_id = ?
            """,
            (payload.get("sub"), payload.get("tenant_id")),
        ).fetchone()

    if not user or not user["is_active"]:
        return None
    return public_user(dict(user))


def create_jwt(user: dict) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id") or 1,
        "profile_type": user.get("profile_type"),
        "profile_id": user.get("profile_id"),
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _b64_bytes(hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def verify_jwt(token: str) -> Optional[dict]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}"
        expected = _b64_bytes(hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_part):
            return None
        payload = json.loads(_b64_decode(payload_part).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def public_user(user: dict) -> dict:
    user.pop("password_hash", None)
    user.pop("wx_openid", None)
    user.pop("wx_unionid", None)
    user["is_active"] = bool(user.get("is_active", 1))
    user["must_change_password"] = bool(user.get("must_change_password", 0))
    user["tenant_id"] = int(user.get("tenant_id") or 1)
    tenant_name = user.pop("tenant_name", None) or "DAITORA"
    tenant_slug = user.pop("tenant_slug", None) or "daitora"
    company_code = company_code_for_tenant(tenant_slug, tenant_name)
    user["company_code"] = company_code
    user["account_login"] = company_login_name(user.get("phone") or user.get("username"), tenant_slug, tenant_name)
    user["tenant"] = {
        "id": user["tenant_id"],
        "name": tenant_name,
        "slug": tenant_slug,
        "company_code": company_code,
    }
    return user


def normalize_phone(phone: str | None) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _mark_login(user_id: int | str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()


def _requires_wechat(client_type: str, role: str) -> bool:
    if DEMO_MODE or TRIAL_MODE:
        return False
    return client_type in MINIAPP_CLIENTS and role in {"driver", "dispatcher", "operations_manager", "admin"}


def _ensure_wechat_binding(user: dict, wx_openid: str, wx_unionid: str | None = None) -> str:
    user_id = user["id"]
    current = user.get("wx_openid")
    if _is_super_wechat(wx_openid, wx_unionid):
        _audit_auth("super_wechat_login", {"user_id": user_id, "wx_bind_status": user.get("wx_bind_status") or "unbound"})
        return "ok"
    if current and current != wx_openid:
        return "mismatch"
    if current == wx_openid:
        return "ok"
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET wx_openid = ?,
                wx_unionid = ?,
                wx_bound_at = CURRENT_TIMESTAMP,
                wx_bind_status = 'bound',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (wx_openid, wx_unionid or None, user_id),
        )
        conn.commit()
    _audit_auth("wechat_bind", {"user_id": user_id, "wx_bind_status": "bound"})
    return "bound"


def _is_super_wechat(wx_openid: str | None = None, wx_unionid: str | None = None) -> bool:
    return any(value and value in SUPER_WECHAT_IDS for value in (wx_openid, wx_unionid))


def _load_user_public(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.*, t.name AS tenant_name, t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def _find_user_by_phone(conn, normalized: str):
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
           OR REPLACE(REPLACE(REPLACE(COALESCE(username, ''), '-', ''), ' ', ''), '+', '') = ?
        ORDER BY is_active DESC, id ASC
        LIMIT 1
        """,
        (normalized, normalized),
    ).fetchone()


def _find_driver_profile(conn, tenant_id: int, normalized: str):
    return conn.execute(
        """
        SELECT *
        FROM drivers
        WHERE tenant_id = ?
          AND REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (tenant_id, normalized),
    ).fetchone()


def _find_operator_profile(conn, tenant_id: int, normalized: str, role: str):
    return conn.execute(
        """
        SELECT p.id AS profile_id, p.phone, u.id AS user_id, u.role, u.display_name
        FROM operator_profiles p
        JOIN users u ON u.id = p.user_id AND u.tenant_id = p.tenant_id
        WHERE p.tenant_id = ?
          AND u.role = ?
          AND (
              REPLACE(REPLACE(REPLACE(COALESCE(p.phone, ''), '-', ''), ' ', ''), '+', '') = ?
              OR REPLACE(REPLACE(REPLACE(COALESCE(u.phone, ''), '-', ''), ' ', ''), '+', '') = ?
          )
        ORDER BY u.is_active ASC, u.id ASC
        LIMIT 1
        """,
        (tenant_id, role, normalized, normalized),
    ).fetchone()


def _audit_auth(action: str, payload: dict, actor: str = "auth") -> None:
    tenant_id = payload.get("tenant_id") or get_current_tenant_id()
    set_current_tenant_id(tenant_id)
    record_audit(action, "auth", payload.get("user_id") or payload.get("phone"), after=payload, actor=actor, source_path="/api/auth")


def _b64_json(payload: dict) -> str:
    return _b64_bytes(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

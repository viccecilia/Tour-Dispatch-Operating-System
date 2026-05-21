import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from backend.config import JWT_EXPIRES_SECONDS, JWT_SECRET
from backend.db.database import get_connection, hash_password


def authenticate(username: str, password: str) -> Optional[dict]:
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
    if user["role"] not in {"admin", "dispatcher", "driver"}:
        return None

    public = public_user(dict(user))
    return {"token": create_jwt(public), "user": public}


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
    user["is_active"] = bool(user.get("is_active", 1))
    user["tenant_id"] = int(user.get("tenant_id") or 1)
    user["tenant"] = {
        "id": user["tenant_id"],
        "name": user.pop("tenant_name", None) or "Demo Travel Company",
        "slug": user.pop("tenant_slug", None) or "demo",
    }
    return user


def _b64_json(payload: dict) -> str:
    return _b64_bytes(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

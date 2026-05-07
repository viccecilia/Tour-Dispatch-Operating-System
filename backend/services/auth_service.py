import secrets
from typing import Optional

from backend.db.database import get_connection, hash_password


_TOKENS: dict[str, int] = {}


def authenticate(username: str, password: str) -> Optional[dict]:
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, username, password_hash, role, display_name, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if not user or not user["is_active"]:
        return None
    if user["password_hash"] != hash_password(password):
        return None
    if user["role"] != "admin":
        return None

    token = secrets.token_urlsafe(24)
    _TOKENS[token] = user["id"]
    return {"token": token, "user": public_user(dict(user))}


def get_user_by_token(token: str) -> Optional[dict]:
    user_id = _TOKENS.get(token)
    if not user_id:
        return None

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, username, role, display_name, is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if not user or not user["is_active"]:
        return None
    return public_user(dict(user))


def public_user(user: dict) -> dict:
    user.pop("password_hash", None)
    user["is_active"] = bool(user.get("is_active", 1))
    return user

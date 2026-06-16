from __future__ import annotations

from typing import Any


PLATFORM_PERMISSIONS = {
    "platform.company_registration.manage",
}


def account_scope(user: dict[str, Any] | None) -> str:
    if not user:
        return ""
    scope = str(user.get("account_scope") or "").strip()
    if scope:
        return scope
    if str(user.get("username") or "").strip() == "admin":
        return "platform"
    if user.get("role") == "driver":
        return "driver"
    return "carrier"


def has_permission(user: dict[str, Any] | None, permission: str) -> bool:
    if permission in PLATFORM_PERMISSIONS:
        return account_scope(user) == "platform" and user.get("role") == "admin"
    return False

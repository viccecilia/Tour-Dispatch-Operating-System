from __future__ import annotations

from typing import Any


CARRIER_ROLES = {"admin", "operations_manager", "dispatcher", "driver"}
AGENCY_ROLES = {"agency_owner", "agency_customer_service", "agency_guide", "agency_finance"}
CARRIER_ADMIN_GRANTS = {"operations_manager", "dispatcher", "driver"}
AGENCY_OWNER_GRANTS = {"agency_customer_service", "agency_guide", "agency_finance"}


def can_manage_accounts(actor: dict[str, Any]) -> bool:
    scope = str(actor.get("account_scope") or "")
    role = str(actor.get("role") or "")
    return (scope == "platform" and role == "admin") or (scope == "carrier" and role == "admin") or (
        scope == "agency" and role == "agency_owner"
    )


def grantable_roles(actor: dict[str, Any], target_scope: str, target_organization_id: int | None) -> set[str]:
    scope = str(actor.get("account_scope") or "")
    role = str(actor.get("role") or "")
    if scope == "platform" and role == "admin":
        return CARRIER_ROLES if target_scope == "carrier" else (AGENCY_ROLES if target_scope == "agency" else set())
    if (
        scope == "carrier"
        and role == "admin"
        and target_scope == "carrier"
        and int(actor.get("tenant_id") or 0) == int(target_organization_id or 0)
    ):
        return CARRIER_ADMIN_GRANTS
    if (
        scope == "agency"
        and role == "agency_owner"
        and target_scope == "agency"
        and int(actor.get("organization_id") or actor.get("company_id") or 0) == int(target_organization_id or 0)
    ):
        return AGENCY_OWNER_GRANTS
    return set()


def assert_can_grant_role(
    actor: dict[str, Any],
    target_scope: str,
    target_organization_id: int | None,
    target_role: str,
) -> None:
    if target_role not in grantable_roles(actor, target_scope, target_organization_id):
        raise PermissionError("account_grant_forbidden")


def assert_can_manage_target(actor: dict[str, Any], target: dict[str, Any]) -> None:
    target_scope = str(target.get("account_scope") or "")
    target_org = target.get("organization_id") or target.get("company_id") or target.get("tenant_id")
    target_role = str(target.get("role") or "")
    assert_can_grant_role(actor, target_scope, int(target_org or 0), target_role)

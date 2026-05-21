from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


def list_plans() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM plans
            WHERE status = 'active'
            ORDER BY monthly_price ASC
            """
        ).fetchall()
    return [_decode_plan(row) for row in rows]


def get_subscription() -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.*, p.name AS plan_name, p.monthly_price, p.features_json, p.limits_json
            FROM tenant_subscriptions s
            JOIN plans p ON p.code = s.plan_code
            WHERE s.tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO tenant_subscriptions (tenant_id, plan_code, status, started_at, updated_at)
                VALUES (?, 'free', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (tenant_id,),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT s.*, p.name AS plan_name, p.monthly_price, p.features_json, p.limits_json
                FROM tenant_subscriptions s
                JOIN plans p ON p.code = s.plan_code
                WHERE s.tenant_id = ?
                """,
                (tenant_id,),
            ).fetchone()
    subscription = dict(row)
    subscription["plan"] = {
        "code": subscription["plan_code"],
        "name": subscription.pop("plan_name"),
        "monthly_price": subscription.pop("monthly_price"),
        "features": _json(subscription.pop("features_json")),
        "limits": _json(subscription.pop("limits_json")),
    }
    return subscription


def update_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    plan_code = str(payload.get("plan_code") or "").strip().lower()
    status = str(payload.get("status") or "active").strip().lower()
    if not plan_code:
        raise ValueError("missing_required_fields:plan_code")
    if status not in {"active", "trialing", "paused", "cancelled"}:
        raise ValueError("invalid_subscription_status")
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        plan = conn.execute("SELECT 1 FROM plans WHERE code = ? AND status = 'active'", (plan_code,)).fetchone()
        if not plan:
            raise ValueError("plan_not_found")
        conn.execute(
            """
            INSERT INTO tenant_subscriptions (tenant_id, plan_code, status, started_at, expires_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id) DO UPDATE SET
                plan_code = excluded.plan_code,
                status = excluded.status,
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (tenant_id, plan_code, status, payload.get("expires_at")),
        )
        conn.commit()
    return get_subscription()


def record_usage(feature: str, quantity: int = 1) -> None:
    feature = str(feature or "").strip()
    if not feature:
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (tenant_id, feature, quantity, usage_date)
            VALUES (?, ?, ?, ?)
            """,
            (get_current_tenant_id(), feature, int(quantity or 1), date.today().isoformat()),
        )
        conn.commit()


def get_usage() -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    today = date.today().isoformat()
    month = today[:7]
    with get_connection() as conn:
        usage_events = [
            dict(row)
            for row in conn.execute(
                """
                SELECT feature, SUM(quantity) AS quantity
                FROM usage_events
                WHERE tenant_id = ? AND substr(usage_date, 1, 7) = ?
                GROUP BY feature
                ORDER BY feature
                """,
                (tenant_id, month),
            ).fetchall()
        ]
        actual = {
            "orders": _count(conn, "SELECT COUNT(*) AS total FROM orders WHERE tenant_id = ? AND COALESCE(is_deleted, 0) = 0", (tenant_id,)),
            "parser_drafts": _count(conn, "SELECT COUNT(*) AS total FROM order_drafts WHERE tenant_id = ?", (tenant_id,)),
            "drivers": _count(conn, "SELECT COUNT(*) AS total FROM drivers WHERE tenant_id = ?", (tenant_id,)),
            "vehicles": _count(conn, "SELECT COUNT(*) AS total FROM vehicles WHERE tenant_id = ?", (tenant_id,)),
            "assignments": _count(conn, "SELECT COUNT(*) AS total FROM assignments WHERE tenant_id = ?", (tenant_id,)),
            "incidents": _count(conn, "SELECT COUNT(*) AS total FROM incidents WHERE tenant_id = ?", (tenant_id,)),
        }
    subscription = get_subscription()
    limits = subscription["plan"]["limits"]
    return {
        "month": month,
        "actual": actual,
        "usage_events": usage_events,
        "limits": limits,
        "limit_status": {
            "orders": _limit_status(actual["orders"], limits.get("orders_per_month")),
            "parser_drafts": _limit_status(actual["parser_drafts"], limits.get("parser_runs_per_month")),
            "drivers": _limit_status(actual["drivers"], limits.get("drivers")),
            "vehicles": _limit_status(actual["vehicles"], limits.get("vehicles")),
        },
    }


def get_feature_flags() -> dict[str, Any]:
    subscription = get_subscription()
    return subscription["plan"]["features"]


def is_feature_enabled(feature: str) -> bool:
    flags = get_feature_flags()
    return bool(flags.get(feature))


def get_billing_overview() -> dict[str, Any]:
    subscription = get_subscription()
    return {
        "subscription": subscription,
        "plans": list_plans(),
        "usage": get_usage(),
        "feature_flags": subscription["plan"]["features"],
    }


def _decode_plan(row) -> dict[str, Any]:
    item = dict(row)
    item["features"] = _json(item.pop("features_json"))
    item["limits"] = _json(item.pop("limits_json"))
    return item


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


def _limit_status(value: int, limit: Any) -> dict[str, Any]:
    if limit in (None, "", 0):
        return {"value": value, "limit": None, "percent": 0, "exceeded": False}
    limit = int(limit)
    percent = round(value / limit * 100, 1) if limit else 0
    return {"value": value, "limit": limit, "percent": percent, "exceeded": value > limit}


def _count(conn, sql: str, params: tuple[Any, ...]) -> int:
    return int(conn.execute(sql, params).fetchone()["total"])

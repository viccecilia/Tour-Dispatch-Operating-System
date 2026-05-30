from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


def list_auction_listings(status: str | None = "listed") -> list[dict[str, Any]]:
    sql = [
        """
        SELECT
            l.*,
            o.oid,
            o.order_date,
            o.end_date,
            o.start_time,
            o.end_time,
            o.pickup_location,
            o.dropoff_location,
            o.order_type,
            o.vehicle_type,
            o.agency_name,
            o.price,
            o.remark,
            seller.name AS seller_company_name,
            seller.slug AS seller_company_code,
            buyer.name AS buyer_company_name,
            buyer.slug AS buyer_company_code
        FROM auction_listings l
        JOIN orders o ON o.id = l.order_id
        LEFT JOIN tenants seller ON seller.id = l.seller_tenant_id
        LEFT JOIN tenants buyer ON buyer.id = l.buyer_tenant_id
        WHERE COALESCE(o.is_deleted, 0) = 0
        """
    ]
    params: list[Any] = []
    if status and status != "all":
        sql.append("AND l.status = ?")
        params.append(status)
    sql.append("ORDER BY l.published_at DESC, l.id DESC")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def create_auction_listings(payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    order_ids = _normalize_ids(payload.get("order_ids") or payload.get("order_id"))
    if not order_ids:
        raise ValueError("missing_order_ids")

    start_price = _money(payload.get("start_price_jpy") or payload.get("start_price"))
    buyout_price = _money(payload.get("buyout_price_jpy") or payload.get("buyout_price"))
    if start_price <= 0:
        raise ValueError("missing_start_price")
    if buyout_price <= 0:
        raise ValueError("missing_buyout_price")
    if buyout_price < start_price:
        raise ValueError("buyout_price_less_than_start_price")

    tenant_id = get_current_tenant_id()
    actor_id = actor.get("id") if actor else None
    actor_name = actor.get("name") or actor.get("username") if actor else None
    created: list[dict[str, Any]] = []

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM orders
            WHERE id IN ({",".join("?" for _ in order_ids)})
              AND tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
            """,
            [*order_ids, tenant_id],
        ).fetchall()
        if len(rows) != len(order_ids):
            raise ValueError("order_not_found")

        for row in rows:
            existing = conn.execute(
                """
                SELECT id
                FROM auction_listings
                WHERE order_id = ? AND status IN ('listed', 'bidding', 'claimed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            if existing:
                raise ValueError("order_already_in_auction")
            if row["dispatch_status"] not in ("unassigned", "auction_cancelled"):
                raise ValueError("order_not_unassigned")

            cursor = conn.execute(
                """
                INSERT INTO auction_listings (
                    order_id, owner_tenant_id, seller_tenant_id, status,
                    start_price_jpy, buyout_price_jpy, current_bid_jpy,
                    published_by_user_id, published_by_name, note, updated_at
                )
                VALUES (?, ?, ?, 'listed', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row["id"],
                    tenant_id,
                    tenant_id,
                    start_price,
                    buyout_price,
                    start_price,
                    actor_id,
                    actor_name,
                    payload.get("note"),
                ),
            )
            conn.execute(
                """
                UPDATE orders
                SET dispatch_status = 'auction_listed',
                    execution_status = 'auction_listed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (row["id"], tenant_id),
            )
            created.append({"listing_id": cursor.lastrowid, "order_id": row["id"], "oid": row["oid"]})
        conn.commit()

    return {"success": True, "listings": created, "count": len(created)}


def _normalize_ids(value: Any) -> list[int]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[int] = []
    for item in values:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in result:
            result.append(number)
    return result


def _money(value: Any) -> float:
    if value is None or value == "":
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0

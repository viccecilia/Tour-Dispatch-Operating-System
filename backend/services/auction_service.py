from typing import Any

from backend.db.database import get_connection
from backend.services.auth_service import company_code_for_tenant
from backend.services.flight_info_service import FLIGHT_INFO_FIELDS, ensure_flight_info_schema
from backend.services.order_number_service import actor_account_code, append_company_order_oid
from backend.services.tenant_context import get_current_tenant_id

AUCTION_LISTING_COLUMNS = {
    "listing_code": "TEXT",
    "publish_round": "INTEGER NOT NULL DEFAULT 1",
    "current_bidder_tenant_id": "INTEGER",
}


def list_auction_listings(status: str | None = "listed") -> list[dict[str, Any]]:
    ensure_flight_info_schema()
    sql = [
        """
        SELECT
            l.*,
            CASE WHEN l.expires_at IS NOT NULL THEN CAST(ROUND((julianday(l.expires_at) - julianday(l.published_at)) * 24) AS INTEGER) END AS auction_duration_hours,
            o.oid,
            o.order_date,
            o.end_date,
            o.start_time,
            o.end_time,
            o.pickup_location,
            o.dropoff_location,
            o.order_type,
            o.vehicle_type,
            o.passenger_count,
            o.luggage_count,
            o.flight_number,
            o.flight_date,
            o.flight_airline,
            o.flight_origin,
            o.flight_destination,
            o.flight_terminal,
            o.flight_gate,
            o.flight_status,
            o.flight_scheduled_departure,
            o.flight_scheduled_arrival,
            o.flight_estimated_departure,
            o.flight_estimated_arrival,
            o.flight_actual_departure,
            o.flight_actual_arrival,
            o.flight_provider,
            o.flight_last_checked_at,
            o.flight_manual_note,
            o.price,
            o.price_jpy,
            o.execution_status,
            o.settlement_status,
            o.agency_settlement_status,
            o.payment_amount_jpy,
            o.carrier_payment_requested_at,
            o.carrier_payment_request_note,
            o.agency_payment_receipt_url,
            o.agency_payment_receipt_name,
            o.agency_payment_uploaded_at,
            o.carrier_payment_confirmed_at,
            o.carrier_payment_confirmed_by,
            CASE WHEN o.itinerary_pdf_url IS NOT NULL AND o.itinerary_pdf_url != '' THEN 1 ELSE 0 END AS has_itinerary_pdf,
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
        ensure_auction_listing_schema(conn)
        _expire_auction_listings(conn)
        return [_public_listing(dict(row)) for row in conn.execute(" ".join(sql), params).fetchall()]


def create_auction_listings(payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    order_ids = _normalize_ids(payload.get("order_ids") or payload.get("order_id"))
    order_oids = _normalize_text_ids(payload.get("order_oids") or payload.get("order_oid"))
    if not order_ids and not order_oids:
        raise ValueError("missing_order_ids")

    start_price = _money(payload.get("start_price_jpy") or payload.get("start_price"))
    buyout_price = _money(payload.get("buyout_price_jpy") or payload.get("buyout_price"))
    duration_hours = _auction_duration_hours(payload.get("auction_duration_hours") or payload.get("duration_hours") or payload.get("expires_hours"))
    if start_price <= 0:
        raise ValueError("missing_start_price")
    if buyout_price <= 0:
        raise ValueError("missing_buyout_price")
    if buyout_price > start_price:
        raise ValueError("buyout_price_greater_than_start_price")

    tenant_id = get_current_tenant_id()
    actor_id = actor.get("id") if actor else None
    actor_name = actor.get("name") or actor.get("username") if actor else None
    created: list[dict[str, Any]] = []

    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        rows = _fetch_orders_for_listing(conn, order_ids, order_oids, tenant_id)
        expected_count = len(order_ids) if order_ids else len(order_oids)
        if len(rows) != expected_count:
            raise ValueError("order_not_found")

        for row in rows:
            if _invalid_route(row):
                raise ValueError("invalid_order_route")
            existing = conn.execute(
                """
                SELECT id, status, COALESCE(bid_count, 0) AS bid_count
                FROM auction_listings
                WHERE order_id = ? AND status IN ('listed', 'bidding', 'claimed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            if existing:
                if existing["status"] == "listed" and int(existing["bid_count"] or 0) == 0:
                    conn.execute(
                        """
                        UPDATE auction_listings
                        SET start_price_jpy = ?,
                            buyout_price_jpy = ?,
                            current_bid_jpy = ?,
                            expires_at = DATETIME('now', ?),
                            note = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            start_price,
                            buyout_price,
                            start_price,
                            f"+{duration_hours} hours",
                            payload.get("note"),
                            existing["id"],
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
                created.append({
                    "listing_id": existing["id"],
                    "order_id": row["id"],
                    "oid": row["oid"],
                    "already_listed": True,
                    "auction_duration_hours": duration_hours,
                })
                continue
            if row["dispatch_status"] not in ("unassigned", "auction_cancelled", "auction_expired"):
                raise ValueError("order_not_unassigned")

            publish_round = _next_publish_round(conn, row["id"])
            listing_code = _build_listing_code(conn, row["oid"], tenant_id)
            cursor = conn.execute(
                """
                INSERT INTO auction_listings (
                    order_id, owner_tenant_id, seller_tenant_id, status,
                    start_price_jpy, buyout_price_jpy, current_bid_jpy,
                    listing_code, publish_round,
                    published_by_user_id, published_by_name, expires_at, note, updated_at
                )
                VALUES (?, ?, ?, 'listed', ?, ?, ?, ?, ?, ?, ?, DATETIME('now', ?), ?, CURRENT_TIMESTAMP)
                """,
                (
                    row["id"],
                    tenant_id,
                    tenant_id,
                    start_price,
                    buyout_price,
                    start_price,
                    listing_code,
                    publish_round,
                    actor_id,
                    actor_name,
                    f"+{duration_hours} hours",
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
            created.append({
                "listing_id": cursor.lastrowid,
                "order_id": row["id"],
                "oid": row["oid"],
                "listing_code": listing_code,
                "publish_round": publish_round,
                "auction_duration_hours": duration_hours,
            })
        conn.commit()

    return {"success": True, "listings": created, "count": len(created)}


def claim_auction_listing(listing_id: int | str, payload: dict[str, Any] | None = None, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        listing_id_int = int(listing_id)
    except (TypeError, ValueError):
        raise ValueError("invalid_listing_id") from None

    tenant_id = get_current_tenant_id()
    buyer_tenant_id = _buyer_tenant_id(payload, actor)
    if buyer_tenant_id <= 0:
        raise ValueError("missing_buyer_tenant_id")
    buyer_price = _money(payload.get("claim_price_jpy") or payload.get("buyout_price_jpy") or payload.get("price_jpy"))

    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        _expire_auction_listings(conn)
        listing = conn.execute(
            """
            SELECT l.*, o.tenant_id AS order_tenant_id, o.oid, o.order_date
            FROM auction_listings l
            JOIN orders o ON o.id = l.order_id
            WHERE l.id = ?
            """,
            (listing_id_int,),
        ).fetchone()
        if not listing:
            raise ValueError("listing_not_found")
        if listing["status"] not in ("listed", "bidding"):
            raise ValueError("listing_not_claimable")
        if int(listing["seller_tenant_id"]) == int(tenant_id):
            raise ValueError("cannot_claim_own_listing")
        final_price = buyer_price or float(listing["buyout_price_jpy"] or listing["current_bid_jpy"] or 0)
        buyout_floor = float(listing["buyout_price_jpy"] or 0)
        start_price = float(listing["start_price_jpy"] or 0)
        if final_price <= 0:
            raise ValueError("missing_claim_price")
        if buyout_floor and final_price < buyout_floor:
            raise ValueError("claim_price_less_than_buyout_price")
        if start_price and final_price > start_price:
            raise ValueError("claim_price_greater_than_start_price")
        buyer_tenant = conn.execute(
            "SELECT slug, name FROM tenants WHERE id = ?",
            (buyer_tenant_id,),
        ).fetchone()
        buyer_code = _tenant_order_code(dict(buyer_tenant) if buyer_tenant else None, buyer_tenant_id)
        serial = _next_buyer_order_serial(conn, buyer_tenant_id, listing["order_date"], buyer_code, listing_id_int)
        claimed_oid = _unique_claimed_oid(
            conn,
            append_company_order_oid(
                listing["oid"],
                company_code=buyer_code,
                order_date=listing["order_date"],
                account_code=actor_account_code(actor, "A1"),
                serial=serial,
            ),
        )
        conn.execute(
            """
            UPDATE auction_listings
            SET status = 'claimed',
                buyer_tenant_id = ?,
                current_bid_jpy = ?,
                bid_count = COALESCE(bid_count, 0) + 1,
                sold_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (buyer_tenant_id, final_price, listing_id_int),
        )
        conn.execute(
            """
            UPDATE orders
            SET oid = ?,
                dispatch_status = 'auction_claimed',
                execution_status = 'auction_claimed',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (claimed_oid, listing["order_id"], listing["seller_tenant_id"]),
        )
        conn.commit()
    claimed = list_auction_listings("claimed")
    match = next((item for item in claimed if int(item["id"]) == listing_id_int), None)
    return match or {"id": listing_id_int, "status": "claimed", "buyer_tenant_id": buyer_tenant_id, "current_bid_jpy": final_price}


def bid_auction_listing(listing_id: int | str, payload: dict[str, Any] | None = None, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        listing_id_int = int(listing_id)
    except (TypeError, ValueError):
        raise ValueError("invalid_listing_id") from None

    tenant_id = get_current_tenant_id()
    step = _money(payload.get("step_jpy") or 20) or 20
    if step <= 0:
        raise ValueError("invalid_bid_step")

    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        _expire_auction_listings(conn)
        listing = conn.execute(
            """
            SELECT *
            FROM auction_listings
            WHERE id = ?
            """,
            (listing_id_int,),
        ).fetchone()
        if not listing:
            raise ValueError("listing_not_found")
        if listing["status"] not in ("listed", "bidding"):
            raise ValueError("listing_not_biddable")
        if int(listing["seller_tenant_id"]) == int(tenant_id):
            raise ValueError("cannot_bid_own_listing")
        if listing["current_bidder_tenant_id"] and int(listing["current_bidder_tenant_id"]) == int(tenant_id):
            raise ValueError("already_leading_bid")

        current = float(listing["current_bid_jpy"] or listing["start_price_jpy"] or 0)
        buyout_floor = float(listing["buyout_price_jpy"] or 0)
        if buyout_floor and current <= buyout_floor:
            raise ValueError("already_at_buyout_price")
        next_price = max(buyout_floor, current - step)
        conn.execute(
            """
            UPDATE auction_listings
            SET status = 'bidding',
                current_bid_jpy = ?,
                current_bidder_tenant_id = ?,
                bid_count = COALESCE(bid_count, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_price, tenant_id, listing_id_int),
        )
        conn.commit()
    listings = list_auction_listings("bidding") + list_auction_listings("listed")
    match = next((item for item in listings if int(item["id"]) == listing_id_int), None)
    return match or {"id": listing_id_int, "status": "bidding", "current_bid_jpy": next_price}


def refresh_expired_auction_listings() -> int:
    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        count = _expire_auction_listings(conn)
        conn.commit()
    return count


def ensure_auction_listing_schema(conn) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(auction_listings)").fetchall()}
    for column, definition in AUCTION_LISTING_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE auction_listings ADD COLUMN {column} {definition}")
    _backfill_listing_codes(conn)


def _backfill_listing_codes(conn) -> None:
    rows = conn.execute(
        """
        SELECT l.id, l.order_id, l.seller_tenant_id, l.published_at, l.listing_code, l.publish_round, o.oid
        FROM auction_listings l
        JOIN orders o ON o.id = l.order_id
        WHERE l.listing_code IS NULL
           OR l.listing_code = ''
           OR l.publish_round IS NULL
           OR l.publish_round <= 0
        ORDER BY COALESCE(l.published_at, l.created_at, l.id), l.id
        """
    ).fetchall()
    if not rows:
        return
    serials: dict[tuple[int, str], int] = {}
    rounds: dict[int, int] = {}
    existing_codes = {
        row["listing_code"]
        for row in conn.execute(
            "SELECT listing_code FROM auction_listings WHERE listing_code IS NOT NULL AND listing_code != ''"
        ).fetchall()
    }
    for row in conn.execute(
        """
        SELECT order_id, COALESCE(MAX(publish_round), 0) AS max_round
        FROM auction_listings
        WHERE publish_round IS NOT NULL AND publish_round > 0
        GROUP BY order_id
        """
    ).fetchall():
        rounds[int(row["order_id"])] = int(row["max_round"] or 0)
    for row in rows:
        seller_id = int(row["seller_tenant_id"] or 0)
        date_key = _listing_date_key(row["published_at"])
        serial_key = (seller_id, date_key)
        serials[serial_key] = serials.get(serial_key, _existing_listing_serial(conn, seller_id, date_key)) + 1
        order_id = int(row["order_id"])
        rounds[order_id] = rounds.get(order_id, 0) + 1
        base = str(row["oid"] or "").strip() or f"ORDER{order_id}"
        serial = serials[serial_key]
        while True:
            listing_code = f"{base}-H{date_key}-{serial:03d}"
            if listing_code not in existing_codes:
                break
            serial += 1
        serials[serial_key] = serial
        existing_codes.add(listing_code)
        conn.execute(
            """
            UPDATE auction_listings
            SET listing_code = COALESCE(NULLIF(listing_code, ''), ?),
                publish_round = CASE WHEN publish_round IS NULL OR publish_round <= 0 THEN ? ELSE publish_round END
            WHERE id = ?
            """,
            (listing_code, rounds[order_id], row["id"]),
        )


def _listing_date_key(value: Any) -> str:
    text = str(value or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8][2:]
    return "000000"


def _existing_listing_serial(conn, seller_tenant_id: int, date_key: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(CAST(SUBSTR(listing_code, -3) AS INTEGER)), 0) AS serial
        FROM auction_listings
        WHERE seller_tenant_id = ?
          AND listing_code LIKE ?
        """,
        (seller_tenant_id, f"%-H{date_key}-%"),
    ).fetchone()
    return int(row["serial"] or 0)


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


def _normalize_text_ids(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _fetch_orders_for_listing(conn, order_ids: list[int], order_oids: list[str], tenant_id: int) -> list[Any]:
    by_id = {}
    if order_oids:
        oid_rows = conn.execute(
            f"""
            SELECT *
            FROM orders
            WHERE oid IN ({",".join("?" for _ in order_oids)})
              AND tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
            """,
            [*order_oids, tenant_id],
        ).fetchall()
        for row in oid_rows:
            by_id[int(row["id"])] = row
    if order_ids:
        id_rows = conn.execute(
            f"""
            SELECT *
            FROM orders
            WHERE id IN ({",".join("?" for _ in order_ids)})
              AND tenant_id = ?
              AND COALESCE(is_deleted, 0) = 0
            """,
            [*order_ids, tenant_id],
        ).fetchall()
        for row in id_rows:
            by_id[int(row["id"])] = row
    return list(by_id.values())


def _money(value: Any) -> float:
    if value is None or value == "":
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _tenant_order_code(row: dict[str, Any] | None, tenant_id: Any) -> str:
    code = company_code_for_tenant((row or {}).get("slug"), (row or {}).get("name"))
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())[:5] or f"T{tenant_id}"


def _next_buyer_order_serial(conn, buyer_tenant_id: int, order_date: Any, buyer_code: str, listing_id: int) -> int:
    date_text = str(order_date or "").replace("-", "").replace("/", "")
    if len(date_text) == 8:
        date_text = date_text[2:]
    pattern = f"%-{buyer_code}{date_text}%"
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM auction_listings l
        JOIN orders o ON o.id = l.order_id
        WHERE l.buyer_tenant_id = ?
          AND l.id <= ?
          AND o.order_date = ?
          AND o.oid LIKE ?
        """,
        (buyer_tenant_id, listing_id, str(order_date), pattern),
    ).fetchone()
    return int(row["count"] if row else 0) + 1


def _unique_claimed_oid(conn, oid: str) -> str:
    base = oid
    suffix = 1
    while conn.execute("SELECT 1 FROM orders WHERE oid = ? LIMIT 1", (oid,)).fetchone():
        suffix += 1
        oid = f"{base}-{suffix:02d}"
    return oid


def _buyer_tenant_id(payload: dict[str, Any], actor: dict[str, Any] | None) -> int:
    value = payload.get("buyer_tenant_id") or payload.get("carrier_tenant_id")
    if value is None and actor:
        value = actor.get("tenant_id")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _auction_duration_hours(value: Any) -> int:
    try:
        hours = int(value or 1)
    except (TypeError, ValueError):
        hours = 1
    if hours not in {1, 2, 4}:
        raise ValueError("invalid_auction_duration_hours")
    return hours


def _invalid_location(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    normalized = text.replace("？", "?").replace("-", "").replace(" ", "")
    return bool(normalized) and set(normalized) <= {"?"}


def _invalid_route(row: Any) -> bool:
    return _invalid_location(row["pickup_location"]) or _invalid_location(row["dropoff_location"])


def _next_publish_round(conn, order_id: Any) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(publish_round), 0) AS round
        FROM auction_listings
        WHERE order_id = ?
        """,
        (order_id,),
    ).fetchone()
    return int(row["round"] or 0) + 1


def _build_listing_code(conn, oid: Any, seller_tenant_id: int) -> str:
    row = conn.execute("SELECT SUBSTR(STRFTIME('%Y%m%d', 'now'), 3) AS date_key").fetchone()
    date_key = row["date_key"] if row and row["date_key"] else "000000"
    serial_row = conn.execute(
        """
        SELECT COALESCE(MAX(CAST(SUBSTR(listing_code, -3) AS INTEGER)), 0) AS serial
        FROM auction_listings
        WHERE seller_tenant_id = ?
          AND DATE(published_at) = DATE('now')
          AND listing_code IS NOT NULL
          AND listing_code != ''
        """,
        (seller_tenant_id,),
    ).fetchone()
    serial = int(serial_row["serial"] or 0) + 1
    base = str(oid or "").strip() or "ORDER"
    while True:
        code = f"{base}-H{date_key}-{serial:03d}"
        exists = conn.execute("SELECT 1 FROM auction_listings WHERE listing_code = ? LIMIT 1", (code,)).fetchone()
        if not exists:
            return code
        serial += 1


def _expire_auction_listings(conn) -> int:
    ensure_auction_listing_schema(conn)
    rows = conn.execute(
        """
        SELECT id, order_id, seller_tenant_id
        FROM auction_listings
        WHERE status IN ('listed', 'bidding')
          AND buyer_tenant_id IS NULL
          AND expires_at IS NOT NULL
          AND DATETIME(expires_at) <= DATETIME('now')
        """
    ).fetchall()
    if not rows:
        return 0
    listing_ids = [row["id"] for row in rows]
    order_ids = [row["order_id"] for row in rows]
    conn.execute(
        f"""
        UPDATE auction_listings
        SET status = 'expired',
            updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({",".join("?" for _ in listing_ids)})
        """,
        listing_ids,
    )
    conn.execute(
        f"""
        UPDATE orders
        SET dispatch_status = 'auction_expired',
            execution_status = 'auction_expired',
            updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({",".join("?" for _ in order_ids)})
        """,
        order_ids,
    )
    return len(rows)


def _public_listing(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "order_id": row.get("order_id"),
        "owner_tenant_id": row.get("owner_tenant_id"),
        "seller_tenant_id": row.get("seller_tenant_id"),
        "buyer_tenant_id": row.get("buyer_tenant_id"),
        "status": row.get("status"),
        "start_price_jpy": row.get("start_price_jpy"),
        "buyout_price_jpy": row.get("buyout_price_jpy"),
        "current_bid_jpy": row.get("current_bid_jpy"),
        "bid_count": row.get("bid_count"),
        "current_bidder_tenant_id": row.get("current_bidder_tenant_id"),
        "listing_code": row.get("listing_code"),
        "publish_round": row.get("publish_round"),
        "published_at": row.get("published_at"),
        "expires_at": row.get("expires_at"),
        "auction_duration_hours": row.get("auction_duration_hours"),
        "sold_at": row.get("sold_at"),
        "cancelled_at": row.get("cancelled_at"),
        "oid": row.get("oid"),
        "order_date": row.get("order_date"),
        "end_date": row.get("end_date"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "pickup_location": row.get("pickup_location"),
        "dropoff_location": row.get("dropoff_location"),
        "order_type": row.get("order_type"),
        "vehicle_type": row.get("vehicle_type"),
        "passenger_count": row.get("passenger_count"),
        "luggage_count": row.get("luggage_count"),
        **{field: row.get(field) for field in FLIGHT_INFO_FIELDS},
        "price": row.get("price"),
        "price_jpy": row.get("price_jpy"),
        "execution_status": row.get("execution_status"),
        "settlement_status": row.get("settlement_status"),
        "agency_settlement_status": row.get("agency_settlement_status"),
        "payment_amount_jpy": row.get("payment_amount_jpy"),
        "carrier_payment_requested_at": row.get("carrier_payment_requested_at"),
        "carrier_payment_request_note": row.get("carrier_payment_request_note"),
        "agency_payment_receipt_url": row.get("agency_payment_receipt_url"),
        "agency_payment_receipt_name": row.get("agency_payment_receipt_name"),
        "agency_payment_uploaded_at": row.get("agency_payment_uploaded_at"),
        "carrier_payment_confirmed_at": row.get("carrier_payment_confirmed_at"),
        "carrier_payment_confirmed_by": row.get("carrier_payment_confirmed_by"),
        "has_itinerary_pdf": bool(row.get("has_itinerary_pdf")),
    }


def get_auction_listing_detail(listing_id: int | str, actor: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        listing_id_int = int(listing_id)
    except (TypeError, ValueError):
        raise ValueError("invalid_listing_id") from None
    ensure_flight_info_schema()
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        ensure_auction_listing_schema(conn)
        row = conn.execute(
            """
            SELECT l.*,
                   o.*,
                   ag.contact_name AS agency_contact_name,
                   ag.contact_phone AS agency_contact_phone,
                   ag.contact_wechat AS agency_contact_wechat,
                   ag.contact_line AS agency_contact_line,
                   ag.contact_whatsapp AS agency_contact_whatsapp,
                   seller.name AS seller_company_name,
                   buyer.name AS buyer_company_name,
                   buyer.slug AS buyer_company_code
            FROM auction_listings l
            JOIN orders o ON o.id = l.order_id
            LEFT JOIN agencies ag ON ag.id = o.agency_id AND ag.tenant_id = o.tenant_id
            LEFT JOIN tenants seller ON seller.id = l.seller_tenant_id
            LEFT JOIN tenants buyer ON buyer.id = l.buyer_tenant_id
            WHERE l.id = ? AND COALESCE(o.is_deleted, 0) = 0
            """,
            (listing_id_int,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    is_seller = int(item.get("seller_tenant_id") or 0) == int(tenant_id)
    is_buyer = int(item.get("buyer_tenant_id") or 0) == int(tenant_id)
    if not (is_seller or is_buyer):
        raise ValueError("listing_detail_forbidden")
    if item.get("status") not in {"claimed", "sold"} and not is_seller:
        raise ValueError("listing_detail_not_available_before_claim")
    return item

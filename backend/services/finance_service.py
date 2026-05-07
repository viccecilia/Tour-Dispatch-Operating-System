from datetime import date

from backend.db.database import get_connection


def get_finance_summary() -> dict:
    today = date.today().isoformat()
    with get_connection() as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS order_count,
                COALESCE(SUM(price), 0) AS total_amount,
                COALESCE(SUM(CASE WHEN settlement_status = 'pending' THEN price ELSE 0 END), 0) AS pending_amount,
                COALESCE(SUM(CASE WHEN settlement_status = 'settled' THEN price ELSE 0 END), 0) AS settled_amount,
                COALESCE(SUM(CASE WHEN order_date = ? THEN price ELSE 0 END), 0) AS today_amount,
                SUM(CASE WHEN price IS NULL OR price = 0 THEN 1 ELSE 0 END) AS missing_price_orders
            FROM orders
            WHERE COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        ).fetchone()
        by_agency = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(agency_name, ''), '未填写旅行社') AS agency_name,
                    COUNT(*) AS order_count,
                    COALESCE(SUM(price), 0) AS total_amount,
                    COALESCE(SUM(CASE WHEN settlement_status = 'pending' THEN price ELSE 0 END), 0) AS pending_amount
                FROM orders
                WHERE COALESCE(is_deleted, 0) = 0
                GROUP BY COALESCE(NULLIF(agency_name, ''), '未填写旅行社')
                ORDER BY pending_amount DESC, total_amount DESC, agency_name
                LIMIT 20
                """
            ).fetchall()
        ]
        pending_orders = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, oid, order_date, start_time, pickup_location, dropoff_location, agency_name, price
                FROM orders
                WHERE settlement_status = 'pending' AND COALESCE(is_deleted, 0) = 0
                ORDER BY order_date DESC, start_time DESC, id DESC
                LIMIT 20
                """
            ).fetchall()
        ]

    return {
        "date": today,
        "order_count": totals["order_count"],
        "total_amount": totals["total_amount"],
        "pending_amount": totals["pending_amount"],
        "settled_amount": totals["settled_amount"],
        "today_amount": totals["today_amount"],
        "missing_price_orders": totals["missing_price_orders"],
        "by_agency": by_agency,
        "pending_orders": pending_orders,
    }

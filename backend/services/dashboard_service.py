from datetime import date

from backend.db.database import get_connection


def get_summary() -> dict:
    today = date.today().isoformat()
    with get_connection() as conn:
        today_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_date = ? AND COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        )
        today_assigned_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_date = ?
              AND dispatch_status = 'assigned'
              AND COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        )
        today_unassigned_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_date = ?
              AND dispatch_status = 'unassigned'
              AND COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        )
        today_exception_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_date = ?
              AND dispatch_status = 'exception'
              AND COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        )
        today_pending_settlement_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE order_date = ?
              AND settlement_status = 'pending'
              AND COALESCE(is_deleted, 0) = 0
            """,
            (today,),
        )
        unassigned_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE dispatch_status = 'unassigned' AND COALESCE(is_deleted, 0) = 0
            """,
        )
        assigned_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE dispatch_status = 'assigned' AND COALESCE(is_deleted, 0) = 0
            """,
        )
        pending_settlement_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE settlement_status = 'pending' AND COALESCE(is_deleted, 0) = 0
            """,
        )
        missing_price_orders = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE (price IS NULL OR price = 0) AND COALESCE(is_deleted, 0) = 0
            """,
        )
        available_drivers = _count(conn, "SELECT COUNT(*) AS total FROM drivers WHERE status = 'available'")
        available_vehicles = _count(conn, "SELECT COUNT(*) AS total FROM vehicles WHERE status = 'available'")
        pending_drafts = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM order_drafts
            WHERE parse_status IN ('pending', 'parsed', 'failed')
            """,
        )
        today_parsed_drafts = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM order_drafts
            WHERE date(created_at) = ? AND parse_status IN ('parsed', 'confirmed')
            """,
            (today,),
        )
        failed_drafts = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM order_drafts
            WHERE parse_status = 'failed'
            """,
        )
        execution_counts = {
            status: _count(
                conn,
                """
                SELECT COUNT(*) AS total
                FROM assignments a
                JOIN orders o ON o.id = a.order_id
                WHERE a.status = 'active'
                  AND o.order_date = ?
                  AND a.execution_status = ?
                  AND COALESCE(o.is_deleted, 0) = 0
                """,
                (today, status),
            )
            for status in ("confirmed", "departed", "arrived", "in_service", "completed", "returned")
        }
        unreported_assignments = _count(
            conn,
            """
            SELECT COUNT(*) AS total
            FROM assignments a
            JOIN orders o ON o.id = a.order_id
            LEFT JOIN driver_reports r ON r.assignment_id = a.id
            WHERE a.status = 'active'
              AND o.order_date = ?
              AND COALESCE(o.is_deleted, 0) = 0
              AND r.id IS NULL
            """,
            (today,),
        )

    return {
        "date": today,
        "today_orders": today_orders,
        "today_assigned_orders": today_assigned_orders,
        "today_unassigned_orders": today_unassigned_orders,
        "today_exception_orders": today_exception_orders,
        "today_pending_settlement_orders": today_pending_settlement_orders,
        "unassigned_orders": unassigned_orders,
        "assigned_orders": assigned_orders,
        "pending_settlement_orders": pending_settlement_orders,
        "missing_price_orders": missing_price_orders,
        "available_drivers": available_drivers,
        "available_vehicles": available_vehicles,
        "pending_drafts": pending_drafts,
        "today_parsed_drafts": today_parsed_drafts,
        "failed_drafts": failed_drafts,
        "today_confirmed_orders": execution_counts["confirmed"],
        "today_departed_orders": execution_counts["departed"],
        "today_arrived_orders": execution_counts["arrived"],
        "today_in_service_orders": execution_counts["in_service"],
        "today_completed_orders": execution_counts["completed"],
        "today_returned_orders": execution_counts["returned"],
        "unreported_assignments": unreported_assignments,
        "nav": ["首页", "订单", "派车", "日历", "解析", "司机", "车辆", "财务"],
    }


def _count(conn, sql: str, params: tuple = ()) -> int:
    return conn.execute(sql, params).fetchone()["total"]

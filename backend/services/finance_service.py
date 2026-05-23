import csv
import io
from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


SETTLED_STATUSES = {"settled", "paid"}
PENDING_STATUSES = {"pending", "unsettled", ""}
DRIVER_SETTLEMENT_STATUSES = {"pending", "settled", "paid", "unsettled"}
AGENCY_SETTLEMENT_STATUSES = {"pending", "settled", "paid", "unsettled"}
DRIVER_EXPENSE_PENDING_STATUSES = {"submitted", "in_hand"}
DRIVER_EXPENSE_STATUSES = {"unsubmitted", "submitted", "in_hand", "confirmed", "rejected"}


def get_finance_summary(params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    ledger = get_finance_ledger(params)
    driver_expenses = get_driver_expense_summary(params)
    orders = ledger["orders"]
    today = date.today().isoformat()
    return {
        "date": today,
        "order_count": ledger["summary"]["total_orders"],
        "total_amount": ledger["summary"]["total_amount"],
        "pending_amount": ledger["summary"]["agency_pending_amount"],
        "settled_amount": ledger["summary"]["agency_settled_amount"],
        "today_amount": sum(_num(item.get("price")) for item in orders if item.get("order_date") == today),
        "missing_price_orders": sum(1 for item in orders if not _num(item.get("price"))),
        "by_agency": _group_amount(orders, "agency_name"),
        "by_driver": _group_amount(orders, "driver_name"),
        "by_vehicle": _group_amount(orders, "vehicle_plate"),
        "orders": orders,
        "pending_orders": [item for item in orders if item.get("agency_settlement_status") in PENDING_STATUSES][:30],
        "driver_expense_summary": driver_expenses,
        "ledger": ledger,
    }


def get_finance_ledger(params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    where, values = _finance_filters(params)
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = [
            _decorate_order(dict(row))
            for row in conn.execute(
                f"""
                SELECT
                    o.id AS order_id,
                    o.id,
                    o.oid,
                    o.order_date,
                    o.end_date,
                    o.start_time,
                    o.end_time,
                    o.agency_id,
                    COALESCE(NULLIF(o.agency_name, ''), ag.name, ag.company_name) AS agency_name,
                    ag.agency_code,
                    o.order_type,
                    o.vehicle_type,
                    o.execution_status,
                    o.dispatch_status,
                    COALESCE(NULLIF(o.agency_settlement_status, ''), o.settlement_status, 'pending') AS agency_settlement_status,
                    COALESCE(NULLIF(o.settlement_status, ''), o.agency_settlement_status, 'pending') AS settlement_status,
                    COALESCE(NULLIF(o.driver_settlement_status, ''), 'pending') AS driver_settlement_status,
                    COALESCE(o.price, o.price_jpy, 0) AS price,
                    COALESCE(o.driver_advance_amount, 0) AS driver_advance_amount,
                    COALESCE(o.driver_collect_amount, o.collection_amount_jpy, 0) AS driver_collect_amount,
                    COALESCE(o.driver_settlement_amount, 0) AS driver_settlement_amount,
                    o.driver_settlement_note,
                    o.pickup_location,
                    o.dropoff_location,
                    o.guest_name,
                    o.guest_contact,
                    o.remark,
                    o.fee_remark,
                    o.created_at,
                    a.id AS assignment_id,
                    d.id AS driver_id,
                    d.name AS driver_name,
                    v.id AS vehicle_id,
                    v.plate_number AS vehicle_plate,
                    v.vehicle_type AS assigned_vehicle_type
                FROM orders o
                LEFT JOIN assignments a ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
                LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = o.tenant_id
                LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = o.tenant_id
                LEFT JOIN agencies ag ON ag.id = o.agency_id AND ag.tenant_id = o.tenant_id
                WHERE o.tenant_id = ? AND COALESCE(o.is_deleted, 0) = 0 {where}
                ORDER BY o.order_date DESC, o.start_time DESC, o.id DESC
                LIMIT 800
                """,
                [tenant_id, *values],
            ).fetchall()
        ]
    return {
        "orders": rows,
        "summary": {**_ledger_summary(rows), **get_driver_expense_summary(params)},
        "filters": params,
    }


def list_finance_driver_expenses(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    where, values = _driver_expense_filters(params)
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = [
            _decorate_driver_expense(dict(row))
            for row in conn.execute(
                f"""
                SELECT
                    e.*,
                    d.name AS driver_name,
                    d.driver_code,
                    o.oid,
                    o.order_date,
                    o.start_time,
                    o.end_time,
                    o.pickup_location,
                    o.dropoff_location,
                    o.order_type,
                    a.vehicle_id,
                    v.plate_number AS vehicle_plate
                FROM driver_expense_reports e
                LEFT JOIN drivers d ON d.id = e.driver_id AND d.tenant_id = e.tenant_id
                LEFT JOIN assignments a ON a.id = e.assignment_id AND a.tenant_id = e.tenant_id
                LEFT JOIN orders o ON o.id = COALESCE(e.order_id, a.order_id) AND o.tenant_id = e.tenant_id
                LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = e.tenant_id
                WHERE e.tenant_id = ? {where}
                ORDER BY
                    CASE WHEN e.submit_status IN ('submitted', 'in_hand') THEN 0 ELSE 1 END,
                    e.created_at DESC,
                    e.id DESC
                LIMIT 500
                """,
                [tenant_id, *values],
            ).fetchall()
        ]
    return {
        "expenses": rows,
        "summary": _driver_expense_summary(rows),
        "filters": params,
    }


def get_driver_expense_summary(params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _driver_expense_summary(list_finance_driver_expenses(params)["expenses"])


def get_finance_driver_expense(expense_id: Any) -> dict[str, Any] | None:
    result = list_finance_driver_expenses({"expense_id": expense_id})
    return result["expenses"][0] if result["expenses"] else None


def update_finance_driver_expense(expense_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    status = str(payload.get("submit_status") or payload.get("status") or "").strip()
    if status and status not in DRIVER_EXPENSE_STATUSES:
        raise ValueError("invalid_driver_expense_status")
    fields: list[str] = []
    values: list[Any] = []
    if status:
        fields.append("submit_status = ?")
        values.append(status)
        if status == "confirmed":
            fields.append("confirmed_at = CURRENT_TIMESTAMP")
        if status == "rejected":
            fields.append("confirmed_at = NULL")
    if "note" in payload:
        fields.append("note = ?")
        values.append("" if payload.get("note") is None else str(payload.get("note")))
    if "amount" in payload:
        fields.append("amount = ?")
        values.append(_num(payload.get("amount")))
    if not fields:
        return get_finance_driver_expense(expense_id)
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE driver_expense_reports
            SET {", ".join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            [*values, _to_int(expense_id), get_current_tenant_id()],
        )
        conn.commit()
    expense = get_finance_driver_expense(expense_id)
    if expense:
        _sync_order_finance_amounts(expense)
    return expense


def get_driver_settlement_stats(params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    where, values = _finance_filters(params, include_driver_settlement=False)
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT
                    d.id AS driver_id,
                    COALESCE(NULLIF(d.name, ''), '未派司机') AS driver_name,
                    COUNT(DISTINCT o.id) AS completed_order_count,
                    SUM(CASE WHEN o.order_type IN ('接机', '送机', '机场接送', 'airport_pickup', 'airport_dropoff', 'airport') THEN 1 ELSE 0 END) AS airport_order_count,
                    SUM(CASE WHEN o.order_type IN ('包车', 'charter') THEN 1 ELSE 0 END) AS charter_order_count,
                    SUM(CASE WHEN o.order_type NOT IN ('接机', '送机', '机场接送', 'airport_pickup', 'airport_dropoff', 'airport', '包车', 'charter') OR o.order_type IS NULL THEN 1 ELSE 0 END) AS other_order_count,
                    COALESCE(SUM(o.price), 0) AS total_order_amount,
                    COALESCE(SUM(o.driver_advance_amount), 0) AS driver_advance_amount,
                    COALESCE(SUM(COALESCE(o.driver_collect_amount, o.collection_amount_jpy, 0)), 0) AS driver_collect_amount,
                    COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('pending', 'unsettled', '') THEN o.driver_settlement_amount ELSE 0 END), 0) AS pending_driver_settlement_amount,
                    COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('settled', 'paid') THEN o.driver_settlement_amount ELSE 0 END), 0) AS settled_driver_settlement_amount
                FROM orders o
                JOIN assignments a ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
                LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = o.tenant_id
                WHERE o.tenant_id = ?
                  AND COALESCE(o.is_deleted, 0) = 0
                  AND o.execution_status IN ('completed', 'returned')
                  {where}
                GROUP BY d.id, d.name
                ORDER BY completed_order_count DESC, total_order_amount DESC
                """,
                [tenant_id, *values],
            ).fetchall()
        ]
    return {
        "stats": rows,
        "summary": {
            "driver_count": len(rows),
            "completed_order_count": sum(_int(row.get("completed_order_count")) for row in rows),
            "airport_order_count": sum(_int(row.get("airport_order_count")) for row in rows),
            "charter_order_count": sum(_int(row.get("charter_order_count")) for row in rows),
            "other_order_count": sum(_int(row.get("other_order_count")) for row in rows),
            "total_order_amount": sum(_num(row.get("total_order_amount")) for row in rows),
            "driver_advance_amount": sum(_num(row.get("driver_advance_amount")) for row in rows),
            "driver_collect_amount": sum(_num(row.get("driver_collect_amount")) for row in rows),
            "pending_driver_settlement_amount": sum(_num(row.get("pending_driver_settlement_amount")) for row in rows),
            "settled_driver_settlement_amount": sum(_num(row.get("settled_driver_settlement_amount")) for row in rows),
        },
    }


def get_driver_income_summary(driver_id: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    driver_id_int = _to_int(driver_id)
    today = date.today().isoformat()
    month = params.get("month") or today[:7]
    date_from = params.get("date_from") or f"{month}-01"
    date_to = params.get("date_to") or _month_end(month)
    with get_connection() as conn:
        today_row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT o.id) AS order_count,
                COALESCE(SUM(CASE WHEN o.execution_status IN ('completed', 'returned') THEN 1 ELSE 0 END), 0) AS completed_count,
                COALESCE(SUM(COALESCE(o.driver_salary_jpy, 0)), 0) AS salary_amount,
                COALESCE(SUM(COALESCE(o.driver_advance_amount, 0)), 0) AS advance_amount,
                COALESCE(SUM(COALESCE(o.driver_collect_amount, o.collection_amount_jpy, 0)), 0) AS collect_amount,
                COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('pending', 'unsettled', '') THEN COALESCE(o.driver_settlement_amount, 0) ELSE 0 END), 0) AS pending_settlement_amount,
                COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('settled', 'paid') THEN COALESCE(o.driver_settlement_amount, 0) ELSE 0 END), 0) AS settled_amount
            FROM orders o
            JOIN assignments a ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
            WHERE o.tenant_id = ?
              AND COALESCE(o.is_deleted, 0) = 0
              AND a.driver_id = ?
              AND o.order_date = ?
            """,
            (get_current_tenant_id(), driver_id_int, today),
        ).fetchone()
        month_row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT o.id) AS order_count,
                COALESCE(SUM(CASE WHEN o.execution_status IN ('completed', 'returned') THEN 1 ELSE 0 END), 0) AS completed_count,
                COALESCE(SUM(CASE WHEN o.order_type IN ('接机', '送机', '机场接送', 'airport_pickup', 'airport_dropoff', 'airport') THEN 1 ELSE 0 END), 0) AS airport_order_count,
                COALESCE(SUM(CASE WHEN o.order_type IN ('包车', 'charter') THEN 1 ELSE 0 END), 0) AS charter_order_count,
                COALESCE(SUM(COALESCE(o.driver_salary_jpy, 0)), 0) AS salary_amount,
                COALESCE(SUM(COALESCE(o.driver_advance_amount, 0)), 0) AS advance_amount,
                COALESCE(SUM(COALESCE(o.driver_collect_amount, o.collection_amount_jpy, 0)), 0) AS collect_amount,
                COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('pending', 'unsettled', '') THEN COALESCE(o.driver_settlement_amount, 0) ELSE 0 END), 0) AS pending_settlement_amount,
                COALESCE(SUM(CASE WHEN COALESCE(o.driver_settlement_status, 'pending') IN ('settled', 'paid') THEN COALESCE(o.driver_settlement_amount, 0) ELSE 0 END), 0) AS settled_amount
            FROM orders o
            JOIN assignments a ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
            WHERE o.tenant_id = ?
              AND COALESCE(o.is_deleted, 0) = 0
              AND a.driver_id = ?
              AND o.order_date >= ?
              AND o.order_date <= ?
            """,
            (get_current_tenant_id(), driver_id_int, date_from, date_to),
        ).fetchone()
        recent_rows = conn.execute(
            """
            SELECT
                o.id AS order_id,
                o.oid,
                o.order_date,
                o.start_time,
                o.end_time,
                o.pickup_location,
                o.dropoff_location,
                o.order_type,
                o.execution_status,
                COALESCE(o.driver_salary_jpy, 0) AS driver_salary_jpy,
                COALESCE(o.driver_advance_amount, 0) AS driver_advance_amount,
                COALESCE(o.driver_collect_amount, o.collection_amount_jpy, 0) AS driver_collect_amount,
                COALESCE(o.driver_settlement_amount, 0) AS driver_settlement_amount,
                COALESCE(o.driver_settlement_status, 'pending') AS driver_settlement_status
            FROM orders o
            JOIN assignments a ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
            WHERE o.tenant_id = ?
              AND COALESCE(o.is_deleted, 0) = 0
              AND a.driver_id = ?
              AND o.order_date >= ?
              AND o.order_date <= ?
            ORDER BY o.order_date DESC, o.start_time DESC, o.id DESC
            LIMIT 30
            """,
            (get_current_tenant_id(), driver_id_int, date_from, date_to),
        ).fetchall()
    return {
        "driver_id": driver_id_int,
        "today": _income_row(today_row),
        "month": month,
        "date_from": date_from,
        "date_to": date_to,
        "monthly": _income_row(month_row, include_type_counts=True),
        "recent_orders": [_driver_income_order(dict(row)) for row in recent_rows],
        "note": "司机端只展示司机工资、垫付、代收和司机结算状态，不展示订单销售价格。",
    }


def update_finance_order(order_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "price": "REAL",
        "driver_advance_amount": "REAL",
        "driver_collect_amount": "REAL",
        "driver_settlement_amount": "REAL",
        "driver_settlement_status": "TEXT",
        "driver_settlement_note": "TEXT",
        "agency_settlement_status": "TEXT",
        "settlement_status": "TEXT",
        "fee_remark": "TEXT",
    }
    fields: list[str] = []
    values: list[Any] = []
    for key, kind in allowed.items():
        if key not in payload:
            continue
        value = payload.get(key)
        if key in {"driver_settlement_status"} and value not in DRIVER_SETTLEMENT_STATUSES:
            raise ValueError("invalid_driver_settlement_status")
        if key in {"agency_settlement_status", "settlement_status"} and value not in AGENCY_SETTLEMENT_STATUSES:
            raise ValueError("invalid_agency_settlement_status")
        fields.append(f"{key} = ?")
        values.append(_num(value) if kind == "REAL" else ("" if value is None else str(value)))
    if "agency_settlement_status" in payload and "settlement_status" not in payload:
        fields.append("settlement_status = ?")
        values.append(str(payload.get("agency_settlement_status") or "pending"))
    if not fields:
        return get_finance_order(order_id)
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE orders
            SET {", ".join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ? AND COALESCE(is_deleted, 0) = 0
            """,
            [*values, _to_int(order_id), get_current_tenant_id()],
        )
        conn.commit()
    return get_finance_order(order_id)


def update_settlement(order_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return update_finance_order(order_id, payload)


def get_finance_order(order_id: str) -> dict[str, Any] | None:
    ledger = get_finance_ledger({"order_id": order_id})
    return ledger["orders"][0] if ledger["orders"] else None


def export_finance_csv(params: dict[str, Any] | None = None) -> str:
    data = get_finance_ledger(params)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "订单号",
        "日期",
        "开始",
        "结束",
        "旅行社",
        "司机",
        "车辆",
        "订单类型",
        "执行状态",
        "订单价格",
        "司机垫付",
        "司机代收",
        "司机结算状态",
        "旅行社结算状态",
        "路线",
        "备注",
    ])
    for item in data["orders"]:
        writer.writerow([
            item.get("oid") or item.get("order_id"),
            item.get("order_date"),
            item.get("start_time"),
            item.get("end_time"),
            item.get("agency_name") or "",
            item.get("driver_name") or "",
            item.get("vehicle_plate") or "",
            item.get("order_type") or "",
            item.get("execution_status") or "",
            item.get("price") or 0,
            item.get("driver_advance_amount") or 0,
            item.get("driver_collect_amount") or 0,
            item.get("driver_settlement_status") or "",
            item.get("agency_settlement_status") or "",
            f"{item.get('pickup_location') or ''} -> {item.get('dropoff_location') or ''}",
            item.get("remark") or "",
        ])
    return "\ufeff" + output.getvalue()


def _finance_filters(params: dict[str, Any], include_driver_settlement: bool = True) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if params.get("order_id"):
        clauses.append("AND o.id = ?")
        values.append(_to_int(params["order_id"]))
    if params.get("settlement_status"):
        clauses.append("AND COALESCE(o.agency_settlement_status, o.settlement_status, 'pending') = ?")
        values.append(params["settlement_status"])
    if include_driver_settlement and params.get("driver_settlement_status"):
        clauses.append("AND COALESCE(o.driver_settlement_status, 'pending') = ?")
        values.append(params["driver_settlement_status"])
    if params.get("agency_name"):
        clauses.append("AND COALESCE(o.agency_name, '') LIKE ?")
        values.append(f"%{params['agency_name']}%")
    if params.get("driver_id"):
        clauses.append("AND a.driver_id = ?")
        values.append(_to_int(params["driver_id"]))
    if params.get("driver_name"):
        clauses.append("AND COALESCE(d.name, '') LIKE ?")
        values.append(f"%{params['driver_name']}%")
    if params.get("order_type"):
        clauses.append("AND o.order_type = ?")
        values.append(params["order_type"])
    if params.get("execution_status"):
        mapped = _execution_status_values(params["execution_status"])
        clauses.append(f"AND o.execution_status IN ({','.join('?' for _ in mapped)})")
        values.extend(mapped)
    if params.get("date_from"):
        clauses.append("AND o.order_date >= ?")
        values.append(params["date_from"])
    if params.get("date_to"):
        clauses.append("AND o.order_date <= ?")
        values.append(params["date_to"])
    return " ".join(clauses), values


def _driver_expense_filters(params: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if params.get("expense_id"):
        clauses.append("AND e.id = ?")
        values.append(_to_int(params["expense_id"]))
    if params.get("driver_id"):
        clauses.append("AND e.driver_id = ?")
        values.append(_to_int(params["driver_id"]))
    if params.get("order_id"):
        clauses.append("AND COALESCE(e.order_id, a.order_id) = ?")
        values.append(_to_int(params["order_id"]))
    if params.get("expense_kind"):
        clauses.append("AND e.expense_kind = ?")
        values.append(params["expense_kind"])
    if params.get("submit_status"):
        statuses = [item.strip() for item in str(params["submit_status"]).split(",") if item.strip()]
        if statuses:
            clauses.append(f"AND e.submit_status IN ({','.join('?' for _ in statuses)})")
            values.extend(statuses)
    if params.get("date_from"):
        clauses.append("AND COALESCE(o.order_date, date(e.created_at)) >= ?")
        values.append(params["date_from"])
    if params.get("date_to"):
        clauses.append("AND COALESCE(o.order_date, date(e.created_at)) <= ?")
        values.append(params["date_to"])
    return " ".join(clauses), values


def _execution_status_values(status: str) -> list[str]:
    groups = {
        "not_started": ["assigned", "confirmed"],
        "running": ["departed", "arrived", "in_service"],
        "finished": ["completed", "returned"],
    }
    return groups.get(status, [status])


def _decorate_order(row: dict[str, Any]) -> dict[str, Any]:
    row["vehicle_plate"] = row.get("vehicle_plate") or ""
    row["execution_group"] = _execution_group(row.get("execution_status"))
    row["driver_settlement_amount"] = _driver_settlement_amount(row)
    row["agency_settlement_status"] = row.get("agency_settlement_status") or row.get("settlement_status") or "pending"
    row["settlement_status"] = row["agency_settlement_status"]
    return row


def _decorate_driver_expense(row: dict[str, Any]) -> dict[str, Any]:
    row["amount"] = _num(row.get("amount"))
    row["status_label"] = {
        "unsubmitted": "未提交",
        "submitted": "待财务确认",
        "in_hand": "待财务确认",
        "confirmed": "财务已确认",
        "rejected": "财务已驳回",
    }.get(str(row.get("submit_status") or ""), row.get("submit_status") or "-")
    row["kind_label"] = "司机垫付" if row.get("expense_kind") == "advance" else "司机代收"
    row["is_pending_finance"] = row.get("submit_status") in DRIVER_EXPENSE_PENDING_STATUSES
    return row


def _driver_expense_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pending = [item for item in rows if item.get("submit_status") in DRIVER_EXPENSE_PENDING_STATUSES]
    confirmed = [item for item in rows if item.get("submit_status") == "confirmed"]
    rejected = [item for item in rows if item.get("submit_status") == "rejected"]
    return {
        "driver_expense_pending_count": len(pending),
        "driver_expense_pending_amount": sum(_num(item.get("amount")) for item in pending),
        "driver_expense_confirmed_count": len(confirmed),
        "driver_expense_confirmed_amount": sum(_num(item.get("amount")) for item in confirmed),
        "driver_expense_rejected_count": len(rejected),
        "driver_expense_rejected_amount": sum(_num(item.get("amount")) for item in rejected),
        "driver_advance_pending_amount": sum(_num(item.get("amount")) for item in pending if item.get("expense_kind") == "advance"),
        "driver_collect_pending_amount": sum(_num(item.get("amount")) for item in pending if item.get("expense_kind") == "collect"),
    }


def _sync_order_finance_amounts(expense: dict[str, Any]) -> None:
    order_id = _to_int(expense.get("order_id"))
    if order_id <= 0:
        return
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN expense_kind = 'advance' AND submit_status = 'confirmed' THEN amount ELSE 0 END), 0) AS advance_amount,
                COALESCE(SUM(CASE WHEN expense_kind = 'collect' AND submit_status = 'confirmed' THEN amount ELSE 0 END), 0) AS collect_amount
            FROM driver_expense_reports
            WHERE tenant_id = ? AND order_id = ?
            """,
            (tenant_id, order_id),
        ).fetchone()
        conn.execute(
            """
            UPDATE orders
            SET driver_advance_amount = ?,
                driver_collect_amount = ?,
                driver_settlement_amount = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (
                _num(row["advance_amount"] if row else 0),
                _num(row["collect_amount"] if row else 0),
                _num(row["advance_amount"] if row else 0) - _num(row["collect_amount"] if row else 0),
                tenant_id,
                order_id,
            ),
        )
        conn.commit()


def _driver_settlement_amount(row: dict[str, Any]) -> float:
    explicit = _num(row.get("driver_settlement_amount"))
    if explicit:
        return explicit
    return _num(row.get("driver_advance_amount")) - _num(row.get("driver_collect_amount"))


def _execution_group(status: Any) -> str:
    status = str(status or "assigned")
    if status in {"assigned", "confirmed"}:
        return "未执行"
    if status in {"departed", "arrived", "in_service"}:
        return "执行中"
    if status in {"completed", "returned"}:
        return "已完成"
    return status


def _ledger_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_orders": len(rows),
        "total_amount": sum(_num(item.get("price")) for item in rows),
        "agency_pending_amount": sum(_num(item.get("price")) for item in rows if item.get("agency_settlement_status") not in SETTLED_STATUSES),
        "agency_settled_amount": sum(_num(item.get("price")) for item in rows if item.get("agency_settlement_status") in SETTLED_STATUSES),
        "driver_pending_amount": sum(_num(item.get("driver_settlement_amount")) for item in rows if item.get("driver_settlement_status") not in SETTLED_STATUSES),
        "driver_settled_amount": sum(_num(item.get("driver_settlement_amount")) for item in rows if item.get("driver_settlement_status") in SETTLED_STATUSES),
        "driver_advance_amount": sum(_num(item.get("driver_advance_amount")) for item in rows),
        "driver_collect_amount": sum(_num(item.get("driver_collect_amount")) for item in rows),
    }


def _group_amount(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in rows:
        label = item.get(key) or "未填写"
        target = grouped.setdefault(label, {"order_count": 0, "total_amount": 0, "pending_amount": 0, "settled_amount": 0})
        target["order_count"] += 1
        target["total_amount"] += _num(item.get("price"))
        if item.get("agency_settlement_status") in SETTLED_STATUSES:
            target["settled_amount"] += _num(item.get("price"))
        else:
            target["pending_amount"] += _num(item.get("price"))
    return [
        {key: label, **values}
        for label, values in sorted(grouped.items(), key=lambda pair: pair[1]["total_amount"], reverse=True)
    ][:30]


def _income_row(row: Any, include_type_counts: bool = False) -> dict[str, Any]:
    data = dict(row) if row else {}
    result = {
        "order_count": _int(data.get("order_count")),
        "completed_count": _int(data.get("completed_count")),
        "salary_amount": _num(data.get("salary_amount")),
        "advance_amount": _num(data.get("advance_amount")),
        "collect_amount": _num(data.get("collect_amount")),
        "pending_settlement_amount": _num(data.get("pending_settlement_amount")),
        "settled_amount": _num(data.get("settled_amount")),
    }
    if include_type_counts:
        result["airport_order_count"] = _int(data.get("airport_order_count"))
        result["charter_order_count"] = _int(data.get("charter_order_count"))
    return result


def _driver_income_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": row.get("order_id"),
        "oid": row.get("oid"),
        "order_date": row.get("order_date"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "pickup_location": row.get("pickup_location"),
        "dropoff_location": row.get("dropoff_location"),
        "order_type": row.get("order_type"),
        "execution_status": row.get("execution_status"),
        "driver_salary_jpy": _num(row.get("driver_salary_jpy")),
        "driver_advance_amount": _num(row.get("driver_advance_amount")),
        "driver_collect_amount": _num(row.get("driver_collect_amount")),
        "driver_settlement_amount": _num(row.get("driver_settlement_amount")),
        "driver_settlement_status": row.get("driver_settlement_status") or "pending",
    }


def _month_end(month: str) -> str:
    try:
        year, month_num = [int(part) for part in str(month).split("-", 1)]
        if month_num == 12:
            return f"{year:04d}-12-31"
        next_month = date(year, month_num + 1, 1)
        end = date.fromordinal(next_month.toordinal() - 1)
        return end.isoformat()
    except (TypeError, ValueError):
        return date.today().isoformat()


def _num(value: Any) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1

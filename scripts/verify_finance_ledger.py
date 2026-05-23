import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def main() -> None:
    global TOKEN
    init_db(seed=True)
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    suffix = str(int(datetime.now().timestamp()))

    driver = request("POST", "/api/resources/drivers", {"name": f"财务验证司机{suffix}", "phone": f"FIN-{suffix}", "status": "available"})["driver"]
    vehicle = request("POST", "/api/resources/vehicles", {"plate_number": f"FIN{suffix[-6:]}", "vehicle_type": "ハイエース", "seat_count": 10, "status": "available"})["vehicle"]
    order = request(
        "POST",
        "/api/orders",
        {
            "order_date": date.today().isoformat(),
            "start_time": "07:30",
            "end_time": "09:00",
            "pickup_location": "关西机场",
            "dropoff_location": "大阪市内",
            "order_type": "接机",
            "vehicle_type": "10座",
            "agency_name": "财务验证旅行社",
            "price": 68000,
            "driver_salary_jpy": 9000,
            "settlement_status": "pending",
            "remark": "finance ledger smoke",
        },
    )["order"]
    assigned = request("POST", "/api/dispatch/assign", {"order_ids": [order["id"]], "driver_id": driver["id"], "vehicle_id": vehicle["id"]})
    assert assigned.get("success"), assigned
    assignment_id = assigned["assignment_ids"][0]

    advance_expense = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver["id"],
            "assignment_id": assignment_id,
            "expense_kind": "advance",
            "category": "parking",
            "amount": 12000,
            "note": "司机垫付停车费",
            "submit_status": "submitted",
        },
    )
    collect_expense = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver["id"],
            "assignment_id": assignment_id,
            "expense_kind": "collect",
            "category": "fare",
            "amount": 35000,
            "note": "司机代收车费",
            "submit_status": "submitted",
        },
    )
    assert advance_expense.get("success"), advance_expense
    assert collect_expense.get("success"), collect_expense
    pending_expenses = request("GET", f"/api/finance/driver-expenses?{urllib.parse.urlencode({'driver_id': driver['id'], 'submit_status': 'submitted,in_hand'})}")
    assert pending_expenses["summary"]["driver_expense_pending_count"] >= 2, pending_expenses
    confirmed_expense = request("PUT", f"/api/finance/driver-expenses/{advance_expense['expense_id']}", {"submit_status": "confirmed"})["expense"]
    rejected_expense = request("PUT", f"/api/finance/driver-expenses/{collect_expense['expense_id']}", {"submit_status": "rejected", "note": "测试驳回"})["expense"]

    for report_type in ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"]:
        report = request(
            "POST",
            "/api/driver/report",
            {
                "driver_id": driver["id"],
                "assignment_id": assignment_id,
                "report_type": report_type,
                "location_text": "财务验证位置",
            },
        )
        assert report.get("success"), report

    updated = request(
        "PUT",
        f"/api/finance/orders/{order['id']}",
        {
            "driver_advance_amount": 12000,
            "driver_collect_amount": 35000,
            "driver_settlement_amount": 23000,
            "driver_settlement_status": "pending",
            "agency_settlement_status": "pending",
            "fee_remark": "司机垫付停车费，现场代收现金",
        },
    )["order"]

    params = urllib.parse.urlencode({"driver_id": driver["id"], "date_from": date.today().isoformat(), "date_to": date.today().isoformat()})
    ledger = request("GET", f"/api/finance/ledger?{params}")
    stats = request("GET", f"/api/finance/driver-stats?{params}")
    income = request("GET", f"/api/driver/income?{params}")
    expense_pool = request("GET", f"/api/finance/driver-expenses?{urllib.parse.urlencode({'driver_id': driver['id']})}")
    driver_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver['id']}")["assignment"]
    audits = request("GET", f"/api/audit/logs?{urllib.parse.urlencode({'action': 'finance_update', 'entity_id': order['id'], 'limit': 20})}")["logs"]
    expense_audits = request("GET", f"/api/audit/logs?{urllib.parse.urlencode({'action': 'finance_driver_expense_update', 'entity_id': advance_expense['expense_id'], 'limit': 20})}")["logs"]

    ledger_order = next((item for item in ledger["orders"] if item["order_id"] == order["id"]), None)
    driver_stat = next((item for item in stats["stats"] if item.get("driver_id") == driver["id"]), None)
    result = {
        "login_user": login["user"]["username"],
        "order_id": order["id"],
        "assignment_id": assignment_id,
        "finance_update_driver_advance": updated.get("driver_advance_amount"),
        "ledger_contains_order": ledger_order is not None,
        "ledger_driver_collect_amount": ledger_order.get("driver_collect_amount") if ledger_order else None,
        "ledger_execution_status": ledger_order.get("execution_status") if ledger_order else None,
        "finance_expense_pending_before": pending_expenses["summary"]["driver_expense_pending_count"],
        "confirmed_expense_status": confirmed_expense.get("submit_status"),
        "rejected_expense_status": rejected_expense.get("submit_status"),
        "expense_pool_count": len(expense_pool.get("expenses", [])),
        "finance_dashboard_driver_expense_pending": ledger["summary"].get("driver_expense_pending_count"),
        "driver_stats_completed_orders": driver_stat.get("completed_order_count") if driver_stat else None,
        "driver_stats_airport_orders": driver_stat.get("airport_order_count") if driver_stat else None,
        "driver_income_today_salary": income.get("today", {}).get("salary_amount"),
        "driver_income_month_pending": income.get("monthly", {}).get("pending_settlement_amount"),
        "driver_income_hides_order_price": all("price" not in item for item in income.get("recent_orders", [])),
        "driver_endpoint_hides_price": "price" not in driver_detail,
        "audit_finance_update_written": len(audits) > 0,
        "audit_driver_expense_update_written": len(expense_audits) > 0,
    }
    required = [
        result["ledger_contains_order"],
        result["ledger_driver_collect_amount"] == 35000,
        result["ledger_execution_status"] == "returned",
        result["finance_expense_pending_before"] >= 2,
        result["confirmed_expense_status"] == "confirmed",
        result["rejected_expense_status"] == "rejected",
        result["expense_pool_count"] >= 2,
        result["driver_stats_completed_orders"] >= 1,
        result["driver_stats_airport_orders"] >= 1,
        result["driver_income_today_salary"] >= 9000,
        result["driver_income_month_pending"] >= 23000,
        result["driver_income_hides_order_price"],
        result["driver_endpoint_hides_price"],
        result["audit_finance_update_written"],
        result["audit_driver_expense_update_written"],
    ]
    if not all(required):
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

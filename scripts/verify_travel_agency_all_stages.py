from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "runtime" / "test_dbs" / "travel_agency_all_stages.sqlite3"
TEST_DB.parent.mkdir(parents=True, exist_ok=True)
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["WX_DISPATCH_DB"] = str(TEST_DB)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import init_db  # noqa: E402
from backend.services.tenant_context import set_current_tenant_id  # noqa: E402
from backend.services.travel_agency_service import (  # noqa: E402
    ROLE_MATRIX,
    award_listing,
    create_account,
    create_company,
    create_customer,
    create_guide,
    create_marketplace_draft,
    create_order,
    finance_export_csv,
    finance_ledger,
    list_accounts,
    list_audit,
    list_companies,
    list_customers,
    list_guide_events,
    list_guides,
    list_marketplace,
    list_orders,
    parse_order_text,
    record_guide_event,
    stage_summary,
    submit_quote,
    transition_order,
)


STAGE_ROUNDS = {
    "TA-STAGE-00": ["TA-S00-R01", "TA-S00-R02", "TA-S00-R03", "TA-S00-R04", "TA-S00-R05", "TA-S00-R06"],
    "TA-STAGE-01": ["TA-S01-R01", "TA-S01-R02", "TA-S01-R03", "TA-S01-R04", "TA-S01-R05", "TA-S01-R06"],
    "TA-STAGE-02": ["TA-S02-R01", "TA-S02-R02", "TA-S02-R03", "TA-S02-R04", "TA-S02-R05", "TA-S02-R06"],
    "TA-STAGE-03": ["TA-S03-R01", "TA-S03-R02", "TA-S03-R03", "TA-S03-R04", "TA-S03-R05", "TA-S03-R06"],
    "TA-STAGE-04": ["TA-S04-R01", "TA-S04-R02", "TA-S04-R03", "TA-S04-R04", "TA-S04-R05", "TA-S04-R06", "TA-S04-R07"],
    "TA-STAGE-05": ["TA-S05-R01", "TA-S05-R02", "TA-S05-R03", "TA-S05-R04", "TA-S05-R05", "TA-S05-R06"],
    "TA-STAGE-06": ["TA-S06-R01", "TA-S06-R02", "TA-S06-R03", "TA-S06-R04", "TA-S06-R05", "TA-S06-R06", "TA-S06-R07"],
    "TA-STAGE-07": ["TA-S07-R01", "TA-S07-R02", "TA-S07-R03", "TA-S07-R04", "TA-S07-R05", "TA-S07-R06", "TA-S07-R07", "TA-S07-R08"],
}


def assert_true(name: str, condition: bool, detail: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def verify_static_files() -> list[str]:
    checked: list[str] = []
    for stage, rounds in STAGE_ROUNDS.items():
        stage_file = next((ROOT / "docs" / "travel_agency_stages").glob(f"{stage}*.md"))
        text = stage_file.read_text(encoding="utf-8", errors="ignore")
        for round_id in rounds:
            assert_true(f"{round_id}_declared", round_id in text, stage_file.name)
            result_file = ROOT / "runtime" / "task_results" / stage / f"{round_id}-RESULT.md"
            assert_true(f"{round_id}_result_file", result_file.exists(), str(result_file))
        checked.append(stage_file.name)

    route_text = read("backend/api/routes.py")
    for needle in [
        "/api/travel-agency/companies",
        "/api/travel-agency/orders/parse",
        "/api/travel-agency/marketplace",
        "/api/travel-agency/finance/ledger",
        "/api/travel-agency/audit",
    ]:
        assert_true(f"route_{needle}", needle in route_text)

    service_text = read("backend/services/travel_agency_service.py")
    for needle in ["tenant_id", "company_id", "ROLE_MATRIX", "finance_export_csv", "record_guide_event"]:
        assert_true(f"service_{needle}", needle in service_text)

    return checked


def main() -> None:
    init_db(seed=True)
    static_checked = verify_static_files()
    set_current_tenant_id(1)

    company = create_company(
        {
            "company_code": "DAITORA",
            "company_name": "Daitora Travel",
            "master_phone": "080-1234-5678",
            "master_display_name": "Daitora Owner",
            "wx_bind_required": True,
        },
        "verify",
    )
    assert_true("company_created", company["company_code"] == "DAITORA")
    assert_true("master_account_seeded", len(list_accounts(company["id"])) == 1)
    assert_true("owner_permissions", "finance" in ROLE_MATRIX["agency_owner"])

    cs = create_account({"company_id": company["id"], "role": "agency_customer_service", "display_name": "CS One", "phone": "080-1111-2222"}, "verify")
    finance = create_account({"company_id": company["id"], "role": "agency_finance", "display_name": "Finance One", "phone": "080-3333-4444"}, "verify")
    assert_true("subaccounts_created", cs["role"] == "agency_customer_service" and finance["role"] == "agency_finance")
    assert_true("password_tail_seed", cs["password_seed"] == "1112222"[-6:] or len(cs["password_seed"]) == 6, cs)

    guide = create_guide({"company_id": company["id"], "name": "Guide A", "phone": "090-1000-2000", "languages": "zh,ja"}, "verify")
    customer = create_customer({"company_id": company["id"], "customer_name": "VIP Zhang", "source_channel": "wechat", "route_preference": "airport"}, "verify")
    assert_true("guide_customer", guide["company_id"] == company["id"] and customer["company_id"] == company["id"])

    parsed = parse_order_text({"raw_text": "2026-06-10 09:30 from KIX to Osaka hotel 4 pax hiace"})
    assert_true("parse_preview", parsed["start_time"] == "09:30" and parsed["passenger_count"] == 4, parsed)

    order = create_order(
        {
            "company_id": company["id"],
            "customer_id": customer["id"],
            "order_date": "2026-06-10",
            "start_time": "09:30",
            "pickup_location": "KIX",
            "dropoff_location": "Osaka hotel",
            "passenger_count": 4,
            "vehicle_type": "hiace",
            "customer_budget_jpy": 52000,
            "guide_payable_jpy": 8000,
            "raw_text": parsed["raw_text"],
        },
        "verify",
    )
    confirmed = transition_order(order["id"], "confirm", actor="verify")
    assigned = transition_order(confirmed["id"], "assign-guide", {"guide_id": guide["id"]}, "verify")
    requested = transition_order(assigned["id"], "vehicle-request", actor="verify")
    assert_true("order_flow", requested["order_status"] == "guide_assigned" and requested["dispatch_status"] == "vehicle_requested", requested)

    listing = create_marketplace_draft(
        {"order_id": order["id"], "start_price_jpy": 35000, "buyout_price_jpy": 45000, "protected_floor_jpy": 30000},
        "verify",
    )
    quote = submit_quote(listing["id"], {"carrier_name": "Carrier A", "quote_price_jpy": 42000, "service_level": "A"}, "verify")
    awarded = award_listing(listing["id"], {"carrier_name": quote["carrier_name"], "quote_price_jpy": quote["quote_price_jpy"]}, "verify")
    assert_true("marketplace_awarded", awarded["status"] == "awarded", awarded)

    event = record_guide_event(
        {
            "order_id": order["id"],
            "guide_id": guide["id"],
            "event_type": "pickup_arrived",
            "location_text": "KIX T1",
            "evidence_url": "local://evidence/pickup.jpg",
        },
        "verify",
    )
    assert_true("guide_event", event["event_type"] == "pickup_arrived")
    settled = transition_order(order["id"], "settle", {"settlement_status": "settled"}, "verify")
    assert_true("settled", settled["settlement_status"] == "settled")

    ledger = finance_ledger({"company_id": company["id"]})
    csv_text = finance_export_csv({"company_id": company["id"]})
    assert_true("finance_profit", ledger["summary"]["gross_profit_jpy"] == 2000.0, ledger)
    assert_true("csv_export", "order_no" in csv_text and "TA01-" in csv_text, csv_text)

    assert_true("lists", len(list_companies()) == 1 and len(list_guides(company["id"])) == 1 and len(list_customers(company["id"])) == 1)
    assert_true("orders_filtered", len(list_orders({"company_id": company["id"]})) == 1)
    assert_true("marketplace_listed", len(list_marketplace({"status": "awarded"})) == 1)
    assert_true("events_listed", len(list_guide_events(order["id"])) == 1)
    assert_true("audit_written", len(list_audit(company["id"])) >= 10)
    assert_true("summary_counts", stage_summary()["orders"] == 1)

    set_current_tenant_id(2)
    other_company = create_company({"company_code": "OTHER", "company_name": "Other Travel", "master_phone": "080-9999-0000"}, "verify")
    create_order({"company_id": other_company["id"], "order_date": "2026-06-11", "customer_budget_jpy": 100}, "verify")
    assert_true("tenant2_has_one_order", len(list_orders()) == 1)
    set_current_tenant_id(1)
    assert_true("tenant1_still_isolated", len(list_orders()) == 1 and list_orders()[0]["company_id"] == company["id"])

    result = {
        "ok": True,
        "db": str(TEST_DB),
        "stages": STAGE_ROUNDS,
        "static_stage_files_checked": static_checked,
        "tenant1_summary": stage_summary(),
        "checks": {
            "company": company["company_code"],
            "accounts": len(list_accounts(company["id"])),
            "orders": len(list_orders({"company_id": company["id"]})),
            "marketplace": len(list_marketplace()),
            "guide_events": len(list_guide_events(order["id"])),
            "audit_logs": len(list_audit(company["id"])),
            "csv_has_header": "order_no" in csv_text,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

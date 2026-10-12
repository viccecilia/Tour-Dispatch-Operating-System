from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.document_model_service import build_document_snapshot
from backend.services.v014_hire_document_renderer import render_hire_sample_packet


def sample_group() -> dict:
    airport_orders = [
        {
            "id": 101,
            "oid": "APT-101",
            "document_kind": "airport_transfer",
            "order_type": "関西空港送迎",
            "order_date": "2026-10-05",
            "start_time": "07:45",
            "end_time": "08:45",
            "pickup_location": "スーパーホテル地下鉄谷町四丁目6号口",
            "dropoff_location": "新大阪駅",
            "pickup_location_confirmed": 1,
            "dropoff_location_confirmed": 1,
            "applicant_slot": 2,
            "applicant_slot_confirmed": 1,
            "fare_jpy": 11270,
            "service_fee_jpy": 0,
            "document_advance_jpy": 0,
            "price": 11270,
            "price_confirmed": 1,
            "tax_included_confirmed": 1,
            "run_confirmation_status": "confirmed",
            "area_validation_status": "confirmed",
        },
        {
            "id": 102,
            "oid": "APT-102",
            "document_kind": "airport_transfer",
            "order_type": "関西空港送迎",
            "order_date": "2026-10-05",
            "start_time": "10:15",
            "end_time": "11:15",
            "pickup_location": "Holiday Inn Osaka Namba by IHG",
            "dropoff_location": "KIX",
            "pickup_location_confirmed": 1,
            "dropoff_location_confirmed": 1,
            "applicant_slot": 3,
            "applicant_slot_confirmed": 1,
            "fare_jpy": 11270,
            "service_fee_jpy": 0,
            "document_advance_jpy": 0,
            "price": 11270,
            "price_confirmed": 1,
            "tax_included_confirmed": 1,
            "run_confirmation_status": "confirmed",
            "area_validation_status": "confirmed",
        },
        {
            "id": 103,
            "oid": "APT-103",
            "document_kind": "airport_transfer",
            "order_type": "伊丹空港送迎",
            "order_date": "2026-10-05",
            "start_time": "13:00",
            "end_time": "14:00",
            "pickup_location": "ホテル阪急インターナショナル",
            "dropoff_location": "KIX",
            "pickup_location_confirmed": 1,
            "dropoff_location_confirmed": 1,
            "applicant_slot": 4,
            "applicant_slot_confirmed": 1,
            "fare_jpy": 11270,
            "service_fee_jpy": 0,
            "document_advance_jpy": 0,
            "price": 11270,
            "price_confirmed": 1,
            "tax_included_confirmed": 1,
            "run_confirmation_status": "confirmed",
            "area_validation_status": "confirmed",
        },
        {
            "id": 104,
            "oid": "APT-104",
            "document_kind": "airport_transfer",
            "order_type": "神戸空港送迎",
            "order_date": "2026-10-05",
            "start_time": "14:50",
            "end_time": "15:50",
            "pickup_location": "KIX",
            "dropoff_location": "キャノピーbyヒルトン大阪梅田",
            "pickup_location_confirmed": 1,
            "dropoff_location_confirmed": 1,
            "applicant_slot": 2,
            "applicant_slot_confirmed": 1,
            "fare_jpy": 11270,
            "service_fee_jpy": 0,
            "document_advance_jpy": 0,
            "price": 11270,
            "price_confirmed": 1,
            "tax_included_confirmed": 1,
            "run_confirmation_status": "confirmed",
            "area_validation_status": "confirmed",
        },
    ]
    charter_order = {
        "id": 201,
        "oid": "CHARTER-201",
        "document_kind": "charter",
        "order_type": "貸切観光",
        "order_date": "2026-10-10",
        "end_date": "2026-10-11",
        "start_time": "08:00",
        "end_time": "18:00",
        "pickup_location": "車庫",
        "dropoff_location": "車庫",
        "pickup_location_confirmed": 1,
        "dropoff_location_confirmed": 1,
        "fare_jpy": 92400,
        "service_fee_jpy": 0,
        "document_advance_jpy": 0,
        "price": 92400,
        "price_confirmed": 1,
        "tax_included_confirmed": 1,
        "run_confirmation_status": "confirmed",
        "area_validation_status": "confirmed",
        "remark": json.dumps(
            {
                "days": [
                    {
                        "date": "2026-10-10",
                        "nodes": [
                            {"location": "車庫", "departure_time": "08:00", "node_type": "pickup"},
                            {"location": "ヒルトン京都", "arrival_time": "09:00", "departure_time": "10:00", "node_type": "via"},
                            {"location": "奈良", "arrival_time": "12:00", "departure_time": "13:00", "node_type": "via"},
                            {"location": "大阪", "arrival_time": "15:00", "departure_time": "16:00", "node_type": "via"},
                            {"location": "ヒルトン京都", "arrival_time": "17:00", "departure_time": "18:00", "node_type": "via"},
                        ],
                    },
                    {
                        "date": "2026-10-11",
                        "nodes": [
                            {"location": "車庫", "departure_time": "08:00", "node_type": "pickup"},
                            {"location": "ヒルトン京都", "arrival_time": "09:00", "departure_time": "10:00", "node_type": "via"},
                            {"location": "高野山", "arrival_time": "13:00", "departure_time": "15:00", "node_type": "via"},
                            {"location": "ヒルトン京都", "arrival_time": "17:00", "departure_time": "18:00", "node_type": "via"},
                            {"location": "車庫", "arrival_time": "18:00", "node_type": "dropoff"},
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
    }
    return {
        "tenant_id": 8204,
        "business_date": "2026-10-05",
        "driver_id": 37,
        "driver_name": "姚博",
        "driver_office": "大阪営業所",
        "vehicle_id": 23,
        "plate_number": "なにわ300あ7007",
        "vehicle_type": "Alphard",
        "operations_manager": "胡東鍇",
        "garage_location": "車庫",
        "garage_out_time": "07:00",
        "garage_in_time": "17:50",
        "safe_wait": "空港指定待機場所",
        "safe_attention": "空港周辺及び観光地周辺",
        "safe_other": "全乗員のシートベルト着用を確認してから発車すること。",
        "company": {"company_name": "株式会社大寅"},
        "orders": airport_orders + [charter_order],
    }


def main() -> None:
    output_dir = ROOT / "output" / "pdf"
    font = ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf"
    combined_group = sample_group()
    groups = [
        ("V014_phase2b_airport_sample.pdf", {**deepcopy(combined_group), "orders": deepcopy(combined_group["orders"][:4])}, "docv-v014-airport-sample"),
        ("V014_phase2b_charter_sample.pdf", {**deepcopy(combined_group), "business_date": "2026-10-10", "driver_name": "董星", "driver_office": "京都営業所", "plate_number": "京都300あ3827", "operations_manager": "朱 英心", "garage_out_time": "08:00", "garage_in_time": "18:00", "orders": [deepcopy(combined_group["orders"][4])]}, "docv-v014-charter-sample"),
        ("V014_hire_renderer_sample.pdf", deepcopy(combined_group), "docv-v014-hire-sample"),
    ]
    for file_name, group, version_id in groups:
        snapshot = build_document_snapshot(group, version_id)
        if version_id == "docv-v014-airport-sample":
            snapshot["created_date"] = "2026-10-10"
            snapshot["route_code"] = "R53"
            for order in snapshot["orders"]:
                order["money"]["parking_fee_jpy"] = 1
                order["money"]["toll_fee_jpy"] = 1
                order["applicant_name"] = " "
                order["applicant_contact"] = " "
        elif version_id == "docv-v014-charter-sample":
            snapshot["created_date"] = "2026-10-09"
            snapshot["route_code"] = "R9"
        output = output_dir / file_name
        pages = render_hire_sample_packet(snapshot, output, jp_font_path=font)
        print(f"generated={output}")
        print(f"pages={pages}")
        print(f"publish_ready={snapshot['publish_ready']}")


if __name__ == "__main__":
    main()

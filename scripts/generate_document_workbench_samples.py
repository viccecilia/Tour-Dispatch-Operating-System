from __future__ import annotations

import json
import runpy
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.document_model_service import build_document_snapshot
from backend.services.v014_hire_document_renderer import render_hire_sample_packet
sample_group = runpy.run_path(str(ROOT / "scripts" / "generate_v014_hire_sample_pdf.py"))["sample_group"]


def airport_group(count: int) -> dict:
    source = sample_group()
    templates = deepcopy(source["orders"][:4])
    orders = []
    for index in range(count):
        order = deepcopy(templates[index % len(templates)])
        hour = 7 + index
        order.update(
            {
                "id": 1000 + index,
                "oid": f"WORKBENCH-{count:02d}-{index + 1:02d}",
                "start_time": f"{hour:02d}:00",
                "end_time": f"{hour + 1:02d}:00",
                "pickup_location": (
                    "ホテルロイヤルクラシック大阪 正面玄関 団体乗降スペース"
                    if index % 2 == 0
                    else "関西国際空港 第1ターミナル 国際線到着ロビー 北口"
                ),
                "dropoff_location": (
                    "関西国際空港 第1ターミナル 4階 国際線出発口"
                    if index % 2 == 0
                    else "キャノピーbyヒルトン大阪梅田 正面エントランス"
                ),
                "agency_name": f"株式会社テスト旅行 契約担当{index + 1}",
                "guest_contact": f"06-1234-{5600 + index:04d}",
            }
        )
        orders.append(order)
    return {**deepcopy(source), "orders": orders, "garage_out_time": "06:00", "garage_in_time": "19:00"}


def charter_group(*, multi_day: bool) -> dict:
    source = sample_group()
    order = deepcopy(source["orders"][4])
    if not multi_day:
        route = json.loads(order["remark"])
        route["days"] = route["days"][:1]
        order["remark"] = json.dumps(route, ensure_ascii=False)
        order["end_date"] = order["order_date"]
    return {
        **deepcopy(source),
        "business_date": "2026-10-10",
        "driver_name": "董星",
        "driver_office": "京都営業所",
        "plate_number": "京都300あ3827",
        "operations_manager": "朱 英心",
        "garage_out_time": "08:00",
        "garage_in_time": "18:00",
        "orders": [order],
    }


def main() -> None:
    output_dir = ROOT / "output" / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf"
    cases = [
        ("DAITORA_workbench_airport_06.pdf", airport_group(6), "workbench-airport-06"),
        ("DAITORA_workbench_airport_10.pdf", airport_group(10), "workbench-airport-10"),
        ("DAITORA_workbench_airport_11.pdf", airport_group(11), "workbench-airport-11"),
        ("DAITORA_workbench_charter_day.pdf", charter_group(multi_day=False), "workbench-charter-day"),
        ("DAITORA_workbench_charter_multiday.pdf", charter_group(multi_day=True), "workbench-charter-multiday"),
    ]
    report = []
    for file_name, group, version_id in cases:
        snapshot = build_document_snapshot(group, version_id)
        output = output_dir / file_name
        pages = render_hire_sample_packet(snapshot, output, jp_font_path=font)
        report.append({"file": str(output), "pages": pages, "orders": len(group["orders"])})
        print(f"generated={output} pages={pages}")
    (output_dir / "DAITORA_workbench_samples.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

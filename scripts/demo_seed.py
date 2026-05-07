import json
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db
from backend.services.dispatch_service import assign_orders
from backend.services.driver_service import submit_driver_report
from backend.services.order_service import create_order
from backend.services.parser_service import confirm_draft, parse_text_to_draft
from backend.services.resource_service import create_driver, create_vehicle


ORDER_TYPES = ["接机", "送机", "包车"]
VEHICLE_TYPES = ["商务车", "阿尔法", "海狮", "中巴"]
AGENCIES = ["东京旅运", "樱花旅行", "富士观光", "关西地接"]
PICKUPS = ["成田机场", "羽田机场", "东京站", "银座", "新宿", "大阪市内"]
DROPOFFS = ["东京站", "银座酒店", "成田机场", "羽田机场", "京都酒店", "大阪市内"]


def main() -> None:
    init_db(seed=True)
    today = date.today()
    suffix = today.strftime("%Y%m%d")
    drivers = [
        create_driver({"name": f"演示司机{i + 1}-{suffix}", "phone": f"DEMO-D-{suffix}-{i + 1}", "status": "available"})
        for i in range(6)
    ]
    vehicles = [
        create_vehicle(
            {
                "plate_number": f"DEMO-{suffix}-{i + 1:02d}",
                "vehicle_type": VEHICLE_TYPES[i % len(VEHICLE_TYPES)],
                "seat_count": [6, 7, 10, 18][i % 4],
                "status": "available",
            }
        )
        for i in range(8)
    ]

    direct_orders = []
    for i in range(28):
        day = today + timedelta(days=i % 7)
        start_hour = 7 + (i % 10)
        order = create_order(
            {
                "order_date": day.isoformat(),
                "start_time": f"{start_hour:02d}:00",
                "end_time": f"{start_hour + 1:02d}:20",
                "pickup_location": PICKUPS[i % len(PICKUPS)],
                "dropoff_location": DROPOFFS[i % len(DROPOFFS)],
                "order_type": ORDER_TYPES[i % len(ORDER_TYPES)],
                "vehicle_type": VEHICLE_TYPES[i % len(VEHICLE_TYPES)],
                "passenger_count": 1 + (i % 6),
                "luggage_count": i % 4,
                "guest_name": f"演示客人{i + 1}",
                "guest_contact": f"090-DEMO-{i + 1:04d}",
                "agency_name": AGENCIES[i % len(AGENCIES)],
                "price": 18000 + i * 1000,
                "remark": "demo_seed 手工订单",
            }
        )
        direct_orders.append(order)

    parser_orders = []
    draft_texts = [
        "今天 10:00 成田机场->东京站 4人 2箱 ALPHARD 王先生 旅行社:东京旅运 23000日元",
        "5/7 12:30 羽田机场->银座 2位 商务车 李先生 18000日元",
        "关西机场送大阪市内 6人 丰田海狮 15:30 陈先生",
        "羽田接机 16:00 银座 2位客人 阿尔法",
        "5月8日 成田机场->新宿 3人 1箱 商务车",
        "今天 09:30 大阪市内->京都 5人 海狮",
        "5/9 11:00 东京站->羽田机场 2人 送机",
        "今天 14:00 银座->成田机场 1人 1箱",
        "5月10日 13:00 新宿->东京站 4人 中巴",
        "今天 18:30 羽田机场->东京 2人",
        "5/11 08:00 成田机场->酒店 6人 海狮",
        "无法完全识别但要保留的演示自由文本",
    ]
    for text in draft_texts:
        draft = parse_text_to_draft(text)
        if draft["parse_status"] == "parsed" and len(parser_orders) < 10:
            parser_orders.append(confirm_draft(str(draft["id"]))["order"])

    all_orders = direct_orders + parser_orders
    assigned_ids = []
    for i, order in enumerate(all_orders[:24]):
        driver = drivers[i % len(drivers)]
        vehicle = vehicles[i % len(vehicles)]
        result = assign_orders([order["id"]], driver["id"], vehicle["id"])
        if result["success"]:
            assigned_ids.extend(result["assignment_ids"])

    report_flows = [
        ["confirm_order"],
        ["confirm_order", "depart_yard"],
        ["confirm_order", "depart_yard", "arrive_pickup"],
        ["confirm_order", "depart_yard", "arrive_pickup", "start_service"],
        ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order"],
        ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"],
    ]
    for i, assignment_id in enumerate(assigned_ids[:18]):
        driver = drivers[i % len(drivers)]
        for report_type in report_flows[i % len(report_flows)]:
            submit_driver_report(
                {
                    "driver_id": driver["id"],
                    "assignment_id": assignment_id,
                    "report_type": report_type,
                    "latitude": 35.68,
                    "longitude": 139.76,
                    "location_text": "演示位置",
                    "note": f"demo {report_type}",
                }
            )

    result = {
        "demo_drivers": len(drivers),
        "demo_vehicles": len(vehicles),
        "direct_orders": len(direct_orders),
        "parser_confirmed_orders": len(parser_orders),
        "assigned_orders": len(assigned_ids),
        "report_seeded_assignments": min(18, len(assigned_ids)),
        "draft_texts": len(draft_texts),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

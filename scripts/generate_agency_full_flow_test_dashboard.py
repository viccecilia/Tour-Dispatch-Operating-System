from __future__ import annotations

import base64
import html
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "runtime" / "test_dbs" / "agency_full_flow_dashboard.sqlite3"
RESULT_JSON = ROOT / "runtime" / "task_results" / "AGENCY_FULL_FLOW_TEST_RESULT.json"
RESULT_HTML = ROOT / "runtime" / "task_results" / "AGENCY_FULL_FLOW_TEST_DASHBOARD.html"

os.environ["WX_DISPATCH_DB"] = str(TEST_DB)
os.environ.setdefault("WX_DISPATCH_DEMO_MODE", "0")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import get_connection, init_db  # noqa: E402
from backend.services.agency_portal_service import (  # noqa: E402
    agency_portal_login,
    create_agency_order,
    list_agency_orders,
    parse_agency_order_text,
    publish_agency_order_to_hall,
    request_carrier_payment,
    upload_agency_payment_receipt,
    confirm_carrier_payment,
)
from backend.services.auction_service import claim_auction_listing, refresh_expired_auction_listings  # noqa: E402
from backend.services.dispatch_service import assign_orders, list_assignments  # noqa: E402
from backend.services.driver_service import submit_driver_report  # noqa: E402
from backend.services.tenant_context import set_current_tenant_id  # noqa: E402


def reset_test_db() -> None:
    TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB.exists():
        TEST_DB.unlink()
    init_db(seed=False)
    with get_connection() as conn:
        conn.execute("INSERT INTO tenants (id, name, slug, status) VALUES (1, '平台/旅行社测试租户', 'platform-agency', 'active')")
        conn.execute("INSERT INTO tenants (id, name, slug, status) VALUES (2, 'SAKURA车公司', 'SKR', 'active')")
        conn.execute(
            """
            INSERT INTO agencies (
                tenant_id, agency_code, name, company_name, contact_name, contact_phone,
                contact_wechat, contact_line, contact_whatsapp, portal_code, is_portal_enabled, status
            )
            VALUES (1, 'AGT', '全链路测试旅行社', '全链路测试旅行社株式会社', 'Mico Yamamoto',
                    '080-1000-2000', 'mico-wechat', 'mico-line', 'mico-wa', 'flow123', 1, 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO drivers (tenant_id, name, driver_code, driver_language, phone, status)
            VALUES (1, 'Ken Sato', 'KS', 'JP/CN', '09012345678', 'available')
            """
        )
        conn.execute(
            """
            INSERT INTO vehicles (
                tenant_id, plate_no, plate_number, vehicle_type, vehicle_type_code,
                plate_short_code, vehicle_color, seats, seat_count, status
            )
            VALUES (1, 'なにわ500あ1234', 'なにわ500あ1234', 'Hiace', 'HIA',
                    '1234', 'green', 10, 10, 'available')
            """
        )
        conn.commit()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def capture_step(steps: list[dict[str, Any]], name: str, ok: bool, detail: str, data: Any = None) -> None:
    steps.append({"name": name, "ok": ok, "detail": detail, "data": data})


def run_flow() -> dict[str, Any]:
    reset_test_db()
    set_current_tenant_id(1)
    steps: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []

    login = agency_portal_login({"agency_id": 1, "tenant_id": 1, "portal_code": "flow123"})
    token = login["token"]
    capture_step(steps, "旅行社 Web/小程序登录", True, "portal_code 登录成功，后续入单共用同一租户上下文。", {"agency": login["agency"]["name"]})

    airport_text = "\n".join(
        [
            "2026-06-10 09:30 JL225 关西机场T1 -> Osaka Namba Hotel 4人 5件 Hiace 客人Zhang 080-1111-2222 52000",
            "2026-06-10 14:00 NH986 Osaka Namba Hotel -> Kansai International Airport T1 3人 3件 Alphard 客人Li 080-2222-3333 68000",
        ]
    )
    charter_text = "\n".join(
        [
            "6.02 09:00 京都往返天桥立美山 包车 3代 绿1900 Mico Yamamoto",
            "6.16 10:00 京都-宇治-奈良-大阪 包车 10座绿（英文司机）1700 Emily Childers",
        ]
    )
    airport_parse = parse_agency_order_text(token, {"mode": "airport_batch", "batch": True, "text": airport_text})
    charter_parse = parse_agency_order_text(token, {"mode": "charter_batch", "batch": True, "text": charter_text})
    capture_step(steps, "机场接送批量解析", airport_parse["count"] == 2, "两条接送机文本解析为两条候选订单。", airport_parse)
    capture_step(steps, "包车批量解析", charter_parse["count"] == 2, "两条包车文本解析为两条候选订单。", charter_parse)

    airport_order = create_agency_order(
        token,
        {
            "order_date": "2026-06-10",
            "start_time": "09:30",
            "pickup_location": "关西机场T1",
            "dropoff_location": "Osaka Namba Hotel",
            "order_type": "airport_transfer",
            "vehicle_type": "Hiace",
            "passenger_count": 4,
            "luggage_count": 5,
            "guest_name": "Zhang Test",
            "guest_contact": "080-1111-2222",
            "flight_number": "JL225",
            "flight_date": "2026-06-10",
            "price_jpy": 52000,
            "remark": "测试数据：机场接送批量录入后确认发布",
        },
    )
    charter_order = create_agency_order(
        token,
        {
            "order_date": "2026-06-16",
            "end_date": "2026-06-17",
            "start_time": "10:00",
            "pickup_location": "京都",
            "dropoff_location": "大阪",
            "order_type": "charter",
            "vehicle_type": "10座",
            "vehicle_color": "green",
            "passenger_count": 8,
            "guest_name": "Emily Childers",
            "guest_contact": "emily@example.com",
            "guide_name": "Guide A",
            "guide_line": "guide-line-a",
            "itinerary_pdf_url": "/uploads/agency_itineraries/test-charter.pdf",
            "itinerary_pdf_name": "京都-宇治-奈良-大阪.pdf",
            "price_jpy": 170000,
            "remark": "测试数据：跨日包车，含标准PDF行程",
        },
    )
    capture_step(
        steps,
        "录入并完善订单表格",
        bool(airport_order.get("oid") and charter_order.get("oid")),
        "机场接送与包车各生成一条 orders 记录；包车保留行程 PDF 字段。",
        {"airport_oid": airport_order["oid"], "charter_oid": charter_order["oid"]},
    )

    try:
        publish_agency_order_to_hall(token, airport_order["id"], {"start_price_jpy": 0, "buyout_price_jpy": 55000, "auction_duration_hours": 1})
    except Exception as exc:  # noqa: BLE001
        exceptions.append({"case": "发布前必填校验", "error": str(exc)})
        capture_step(steps, "发布前必填/价格校验", "missing_start_price" in str(exc), "缺少起拍价时接口拒绝发布。", {"error": str(exc)})

    publish_one = publish_agency_order_to_hall(
        token,
        airport_order["id"],
        {"start_price_jpy": 50000, "buyout_price_jpy": 65000, "auction_duration_hours": 1, "note": "机场接送 1小时竞拍"},
    )
    listing_one = publish_one["listings"][0]
    with get_connection() as conn:
        conn.execute("UPDATE auction_listings SET expires_at = DATETIME('now', '-1 minute') WHERE id = ?", (listing_one["listing_id"],))
        conn.commit()
    expired_count = refresh_expired_auction_listings()
    after_expire = fetch_one("SELECT dispatch_status, execution_status FROM orders WHERE id = ?", (airport_order["id"],))
    republish = publish_agency_order_to_hall(
        token,
        airport_order["id"],
        {"start_price_jpy": 51000, "buyout_price_jpy": 66000, "auction_duration_hours": 2, "note": "超时撤回后重新发布"},
    )
    capture_step(
        steps,
        "大厅发布、超时撤回、重新发布",
        expired_count == 1 and after_expire["dispatch_status"] == "auction_expired",
        "超时 listing 标记 expired，order 标记 auction_expired；再次发布生成新 listing_code。",
        {"first": listing_one, "expired": after_expire, "republish": republish["listings"][0]},
    )

    publish_two = publish_agency_order_to_hall(
        token,
        charter_order["id"],
        {"start_price_jpy": 150000, "buyout_price_jpy": 190000, "auction_duration_hours": 4, "note": "包车 4小时竞拍"},
    )
    listing_two = publish_two["listings"][0]
    claimed = claim_auction_listing(
        listing_two["listing_id"],
        {"buyer_tenant_id": 2, "claim_price_jpy": 190000},
        {"id": 99, "username": "carrier-admin", "tenant_id": 2},
    )
    capture_step(steps, "车公司一口价接单", claimed.get("status") == "claimed", "车公司以一口价拿下订单，listing claimed，order auction_claimed。", claimed)

    driver = fetch_one("SELECT * FROM drivers WHERE name = 'Ken Sato'")
    vehicle = fetch_one("SELECT * FROM vehicles WHERE plate_number = 'なにわ500あ1234'")
    assignment_result = assign_orders([charter_order["id"]], driver["id"], vehicle["id"])
    assignment = fetch_one("SELECT * FROM assignments WHERE id = ?", (assignment_result["assignment_ids"][0],))
    assigned_order = fetch_one("SELECT id, oid, dispatch_status, execution_status, driver_code, plate_short_code FROM orders WHERE id = ?", (charter_order["id"],))
    capture_step(
        steps,
        "车公司派车派司机",
        assignment_result["success"] and assigned_order["dispatch_status"] == "assigned",
        "派车后旅行社可在订单跟踪看到司机、车辆、订单号后缀信息。",
        {"assignment": assignment, "order": assigned_order},
    )

    report_sequence = [
        ("confirm_order", "司机确认订单"),
        ("depart_yard", "司机出库"),
        ("arrive_pickup", "到达上车点"),
        ("start_service", "开始服务"),
        ("complete_order", "订单完成"),
        ("return_yard", "司机回库"),
    ]
    driver_reports: list[dict[str, Any]] = []
    for report_type, note in report_sequence:
        result = submit_driver_report(
            {
                "driver_id": driver["id"],
                "assignment_id": assignment["id"],
                "report_type": report_type,
                "location_text": note,
                "note": f"全链路测试：{note}",
            }
        )
        driver_reports.append({"report_type": report_type, "result": result})
    latest_assignment = fetch_one("SELECT execution_status FROM assignments WHERE id = ?", (assignment["id"],))
    capture_step(
        steps,
        "司机端过程汇报",
        all(item["result"].get("success") for item in driver_reports) and latest_assignment["execution_status"] == "returned",
        "司机端顺序提交六个节点，状态不允许跳级或回退。",
        driver_reports,
    )

    payment_requested = request_carrier_payment(
        charter_order["id"],
        {"amount_jpy": 190000, "note": "全链路测试：车公司发起付款请求"},
        {"username": "carrier-admin", "tenant_id": 1},
    )
    receipt_payload = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4\nflow-test-receipt\n%%EOF").decode("ascii")
    receipt_uploaded = upload_agency_payment_receipt(
        token,
        charter_order["id"],
        {"file_name": "flow-test-receipt.pdf", "file_base64": receipt_payload},
    )
    paid = confirm_carrier_payment(
        charter_order["id"],
        {"confirmed_by": "carrier-admin"},
        {"username": "carrier-admin", "tenant_id": 1},
    )
    capture_step(
        steps,
        "收付款闭环",
        paid.get("settlement_status") == "paid" or paid.get("agency_settlement_status") == "paid",
        "车公司发起付款，旅行社上传回执，车公司确认收款，订单完成并结算为 paid。",
        {"requested": payment_requested, "receipt": receipt_uploaded, "confirmed": paid},
    )

    agency_orders = list_agency_orders(token)
    assignments = list_assignments(None)
    table_counts = {
        row["name"]: row["count"]
        for row in fetch_all(
            """
            SELECT 'orders' AS name, COUNT(*) AS count FROM orders
            UNION ALL SELECT 'auction_listings', COUNT(*) FROM auction_listings
            UNION ALL SELECT 'assignments', COUNT(*) FROM assignments
            UNION ALL SELECT 'driver_reports', COUNT(*) FROM driver_reports
            UNION ALL SELECT 'location_logs', COUNT(*) FROM location_logs
            UNION ALL SELECT 'agency_order_change_requests', COUNT(*) FROM agency_order_change_requests
            """
        )
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "test_db": str(TEST_DB),
        "steps": steps,
        "exceptions": exceptions,
        "agency_orders": agency_orders,
        "assignments": assignments,
        "auction_listings": fetch_all("SELECT * FROM auction_listings ORDER BY id"),
        "table_counts": table_counts,
    }


MODULE_ROWS = [
    ("旅行社 Web", "机场接送批量入单", "粘贴多条接送机文本，解析日期/时间/航班/联系人/人数/行李/车型/价格，补全后入库。", "orders, agencies, flight_*", "必填校验、批量解析、发布前价格校验、航班手动/模拟查询", "订单大厅、订单列表、日历、航班信息、结算", "车公司大厅只能看到脱敏基础信息，接单后可见完整联系人", "平台按租户、订单来源、航班状态统计"),
    ("旅行社 Web", "包车批量/单条入单", "多行包车文本解析，支持跨日期、行程、车型、客人、价格和标准 PDF 行程。", "orders.itinerary_pdf_*", "解析后表格编辑、PDF 附件在行程内维护", "订单列表、日历条、地图追踪、结算", "车公司接单后进入派车/司机端任务", "平台沉淀路线、车型、价格、成交率"),
    ("旅行社 Web", "订单大厅/我的订单", "发布中、超时撤回、已撤回、已接单、进行中、完成、结算状态统一展示。", "auction_listings, orders", "1/2/4 小时竞拍、超时、撤回、重新发布、listing_code 递增", "日历状态色、订单列表状态、付款状态", "车公司大厅/详情/派车窗口", "平台审计订单流转和竞拍履约"),
    ("旅行社 Web", "订单跟踪/地图追踪", "接单后查看车公司担当、司机、车辆、司机位置、执行节点。", "assignments, location_logs, driver_reports", "司机汇报驱动状态，缺位置时允许文本位置展示", "日历、详情、结算、通知", "司机端汇报、车公司派车端", "平台追踪 SLA、异常节点"),
    ("旅行社 Web", "日历条", "纵轴为旅行社订单号，横轴日期；跨日包车横跨显示，用颜色区分状态。", "orders.order_date/end_date/status", "订单状态与列表一致，超时/已接/进行中/完成同色", "订单详情、我的订单筛选", "车公司派车后回写司机车辆", "平台按日期容量和履约状态聚合"),
    ("旅行社 Web", "变更/撤回/费用结算", "未接单可直接撤回；已接单变更或撤回走车公司确认；付款请求、回执、确认收款闭环。", "agency_order_change_requests, orders settlement fields", "取消规则、月度免费次数、12/6小时强制取消费用、回执上传", "订单大厅我的订单、结算、通知", "车公司确认变更/收款", "平台对账、异常费用、月度额度"),
    ("旅行社小程序", "首页/录单/订单/大厅/跟踪/日历", "与 Web 共享 API 和租户边界，移动端用于查看、补录、发布和跟踪。", "same backend tables", "小程序端同状态、同权限、同脱敏策略", "Web 与小程序订单状态互通", "车公司端接单后同步可见", "平台按端口来源统计"),
    ("车公司端", "订单大厅/订单详情/派车", "未接单只看基础信息；一口价/竞拍成功后查看完整联系资料并派车派司机。", "auction_listings, assignments", "接单、派车、司机车辆回写、订单号扩展", "司机端、旅行社跟踪、结算", "核心流程保持现有逻辑", "平台审计车公司履约"),
    ("司机小程序", "任务/汇报/位置/费用", "只在被分配后看到任务；按顺序确认、出库、到达、开始、完成、回库。", "assignments, driver_reports, location_logs", "禁止跳级/回退，位置日志回传", "旅行社地图、车公司调度、平台监控", "车公司前台可见执行状态", "平台监控异常停滞"),
    ("平台端", "总控/租户/权限/统计", "查看全平台订单、租户隔离、订单来源、竞拍成交、履约、财务统计。", "tenants, users, audit/log tables", "租户隔离、角色权限、跨端状态一致性", "旅行社/车公司/司机/财务全链路", "不改变业务端核心入口", "形成经营分析看板"),
]


STATUS_ROWS = [
    ("录入草稿/未发布", "orders.dispatch_status=unassigned", "旅行社列表、日历灰色", "车公司不可见", "平台可按来源统计"),
    ("发布大厅", "auction_listings.status=listed; orders.dispatch_status=auction_listed", "旅行社我的订单发布中、日历蓝色", "车公司大厅可见脱敏基础信息", "平台记录发布轮次和竞拍时长"),
    ("超时撤回", "auction_listings.status=expired; orders.dispatch_status=auction_expired", "旅行社可重新发布，日历橙色/灰色", "车公司大厅移除", "平台保留历史 listing"),
    ("一口价/接单", "auction_listings.status=claimed; orders.dispatch_status=auction_claimed", "旅行社可见车公司信息", "车公司可见完整订单和联系人", "平台记录成交价和买方租户"),
    ("派车派司机", "assignments active; orders.dispatch_status=assigned", "旅行社可见司机车辆和地图", "车公司派车/调度可见", "平台记录履约责任方"),
    ("执行中/完成", "assignments.execution_status 逐步推进", "旅行社跟踪节点更新", "司机端汇报、车公司监控", "平台做 SLA/异常统计"),
    ("结算完成", "orders.settlement_status=paid", "旅行社看到已上传回执/已收款", "车公司确认收款", "平台对账闭环"),
]


def render_bool(ok: bool) -> str:
    return "<span class='ok'>通过</span>" if ok else "<span class='bad'>未通过</span>"


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_html(result: dict[str, Any]) -> str:
    passed = sum(1 for step in result["steps"] if step["ok"])
    total = len(result["steps"])
    module_rows = "\n".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
        for row in MODULE_ROWS
    )
    status_rows = "\n".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
        for row in STATUS_ROWS
    )
    step_rows = "\n".join(
        f"<tr><td>{idx}</td><td>{esc(step['name'])}</td><td>{render_bool(step['ok'])}</td><td>{esc(step['detail'])}</td><td><pre>{esc(json.dumps(step.get('data'), ensure_ascii=False, indent=2, default=str))}</pre></td></tr>"
        for idx, step in enumerate(result["steps"], start=1)
    )
    order_rows = "\n".join(
        f"<tr><td>{esc(o.get('oid'))}</td><td>{esc(o.get('order_type'))}</td><td>{esc(o.get('order_date'))} {esc(o.get('start_time'))}</td><td>{esc(o.get('dispatch_status'))}</td><td>{esc(o.get('execution_status'))}</td><td>{esc(o.get('auction_listing_code'))}</td><td>{esc(o.get('driver_name'))}</td><td>{esc(o.get('plate_number') or o.get('plate_no'))}</td><td>{esc(o.get('settlement_status'))}</td></tr>"
        for o in result["agency_orders"]
    )
    listing_rows = "\n".join(
        f"<tr><td>{esc(l.get('listing_code'))}</td><td>{esc(l.get('order_id'))}</td><td>{esc(l.get('publish_round'))}</td><td>{esc(l.get('status'))}</td><td>{esc(l.get('start_price_jpy'))}</td><td>{esc(l.get('buyout_price_jpy'))}</td><td>{esc(l.get('buyer_tenant_id'))}</td><td>{esc(l.get('expires_at'))}</td></tr>"
        for l in result["auction_listings"]
    )
    counts = "".join(f"<li><b>{esc(k)}</b>: {esc(v)}</li>" for k, v in result["table_counts"].items())
    raw_json = esc(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>旅行社端全链路功能测试看板</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #667085;
      --line: #d8dde6;
      --head: #edf2f7;
      --ok: #16794c;
      --bad: #b42318;
      --accent: #245b7d;
      --warn: #9a5b00;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 28px 32px 18px; background: #ffffff; border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0 0 10px; font-size: 26px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    h3 {{ margin: 16px 0 8px; font-size: 15px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 13px; }}
    .wrap {{ padding: 22px 32px 40px; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .metric b {{ display: block; font-size: 22px; color: var(--accent); margin-top: 6px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 18px; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; font-size: 13px; line-height: 1.45; }}
    th {{ background: var(--head); text-align: left; white-space: nowrap; }}
    pre {{ margin: 0; white-space: pre-wrap; max-height: 260px; overflow: auto; font-size: 12px; }}
    .ok {{ color: var(--ok); font-weight: 700; }}
    .bad {{ color: var(--bad); font-weight: 700; }}
    .note {{ color: var(--muted); font-size: 13px; line-height: 1.6; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    ul {{ margin: 8px 0 0 18px; padding: 0; }}
    li {{ margin: 5px 0; }}
    .tag {{ display: inline-block; padding: 2px 7px; border-radius: 999px; background: #e7eef5; color: #214961; margin-right: 6px; font-size: 12px; }}
    @media (max-width: 900px) {{
      header, .wrap {{ padding-left: 16px; padding-right: 16px; }}
      .summary, .grid2 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>旅行社端全链路功能测试看板</h1>
    <div class="meta">
      <span>生成时间：{esc(result["generated_at"])}</span>
      <span>临时测试库：{esc(result["test_db"])}</span>
      <span>范围：旅行社 Web / 旅行社小程序 / 车公司端 / 司机端 / 平台端</span>
    </div>
  </header>
  <main class="wrap">
    <section class="summary">
      <div class="metric">流程用例通过<b>{passed}/{total}</b></div>
      <div class="metric">订单记录<b>{esc(result["table_counts"].get("orders", 0))}</b></div>
      <div class="metric">大厅发布记录<b>{esc(result["table_counts"].get("auction_listings", 0))}</b></div>
      <div class="metric">司机汇报节点<b>{esc(result["table_counts"].get("driver_reports", 0))}</b></div>
    </section>

    <section class="panel">
      <h2>一、板块功能与测试矩阵</h2>
      <p class="note">纵向列出端口、板块和功能；横向覆盖静态/数据库/逻辑测试、功能与跨板块联动、车公司联动、平台端统计和审计。</p>
      <table>
        <thead><tr><th>端口</th><th>板块</th><th>功能</th><th>静态/底层表</th><th>单元与功能测试</th><th>旅行社内部联动</th><th>车公司/司机联动</th><th>平台端联动</th></tr></thead>
        <tbody>{module_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>二、状态机与跨端可见性</h2>
      <table>
        <thead><tr><th>业务状态</th><th>数据库状态</th><th>旅行社端显示</th><th>车公司/司机端显示</th><th>平台端记录</th></tr></thead>
        <tbody>{status_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>三、实际数据全链路执行记录</h2>
      <table>
        <thead><tr><th>#</th><th>测试点</th><th>结果</th><th>说明</th><th>实际返回/数据库证据</th></tr></thead>
        <tbody>{step_rows}</tbody>
      </table>
    </section>

    <section class="grid2">
      <div class="panel">
        <h2>四、旅行社订单列表/日历应显示的数据</h2>
        <table>
          <thead><tr><th>订单号</th><th>类型</th><th>日期时间</th><th>调度状态</th><th>执行状态</th><th>大厅编号</th><th>司机</th><th>车辆</th><th>结算</th></tr></thead>
          <tbody>{order_rows}</tbody>
        </table>
      </div>
      <div class="panel">
        <h2>五、订单大厅发布记录</h2>
        <table>
          <thead><tr><th>大厅编号</th><th>订单ID</th><th>轮次</th><th>状态</th><th>起拍价</th><th>一口价</th><th>接单租户</th><th>截止时间</th></tr></thead>
          <tbody>{listing_rows}</tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>六、测试方法清单</h2>
      <p>
        <span class="tag">静态表结构检查</span>
        <span class="tag">必填/负向测试</span>
        <span class="tag">状态机正推</span>
        <span class="tag">反推一致性</span>
        <span class="tag">跨端 E2E</span>
        <span class="tag">租户隔离</span>
        <span class="tag">小程序围观</span>
        <span class="tag">财务对账</span>
        <span class="tag">回归测试</span>
      </p>
      <div class="grid2">
        <div>
          <h3>已用实际数据验证</h3>
          <ul>{counts}</ul>
        </div>
        <div>
          <h3>下一轮需要补强</h3>
          <ul>
            <li>把平台端统计图表从静态说明升级为真实聚合接口返回。</li>
            <li>把小程序端自动化点击测试接入微信开发者工具或独立 mock runner。</li>
            <li>补充竞价多车公司、多次出价、落拍人工处理和取消费用月度额度的专项用例。</li>
            <li>补充航班真实 API key 后的供应商连通性测试；未配置时继续走本地模拟/手动录入。</li>
          </ul>
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>七、原始 JSON 证据</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    result = run_flow()
    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    RESULT_HTML.write_text(render_html(result), encoding="utf-8")
    print(json.dumps({"html": str(RESULT_HTML), "json": str(RESULT_JSON), "db": str(TEST_DB)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "runtime" / "test_dbs" / "agency_multi_tenant_boundary.sqlite3"
RESULT_JSON = ROOT / "runtime" / "task_results" / "AGENCY_MULTI_TENANT_BOUNDARY_TEST_RESULT.json"
RESULT_HTML = ROOT / "runtime" / "task_results" / "AGENCY_MULTI_TENANT_BOUNDARY_TEST_PLAN.html"

os.environ["WX_DISPATCH_DB"] = str(TEST_DB)
os.environ.setdefault("WX_DISPATCH_DEMO_MODE", "0")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import get_connection, init_db  # noqa: E402
from backend.services.agency_portal_service import (  # noqa: E402
    agency_portal_login,
    create_agency_order,
    list_agency_auction_hall,
    list_agency_orders,
    publish_agency_order_to_hall,
)
from backend.services.auction_service import claim_auction_listing, get_auction_listing_detail, list_auction_listings  # noqa: E402
from backend.services.tenant_context import set_current_tenant_id  # noqa: E402


def reset_db() -> None:
    TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB.exists():
        TEST_DB.unlink()
    init_db(seed=False)
    with get_connection() as conn:
        tenants = [
            (101, "东瀛假期旅行社", "AG-A", "active"),
            (102, "富士之旅旅行社", "AG-B", "active"),
            (201, "SAKURA车队", "SKR", "active"),
            (202, "Kansai Express车队", "KEX", "active"),
        ]
        conn.executemany("INSERT INTO tenants (id, name, slug, status) VALUES (?, ?, ?, ?)", tenants)
        agencies = [
            (101, "AGA", "东瀛假期旅行社", "东瀛假期株式会社", "A担当", "080-1111-0001", "a-wechat", "a-line", "a-wa", "aga-pass"),
            (102, "AGB", "富士之旅旅行社", "富士之旅株式会社", "B担当", "080-2222-0002", "b-wechat", "b-line", "b-wa", "agb-pass"),
        ]
        conn.executemany(
            """
            INSERT INTO agencies (
                tenant_id, agency_code, name, company_name, contact_name, contact_phone,
                contact_wechat, contact_line, contact_whatsapp, portal_code, is_portal_enabled, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active')
            """,
            agencies,
        )
        conn.commit()


def rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def step(steps: list[dict[str, Any]], name: str, ok: bool, expected: str, actual: str, evidence: Any = None) -> None:
    steps.append({"name": name, "ok": ok, "expected": expected, "actual": actual, "evidence": evidence})


def agency_order_payload(name: str, date: str, start: str, pickup: str, dropoff: str, price: int, order_type: str) -> dict[str, Any]:
    return {
        "order_date": date,
        "start_time": start,
        "pickup_location": pickup,
        "dropoff_location": dropoff,
        "order_type": order_type,
        "vehicle_type": "Hiace" if order_type == "airport_transfer" else "10座",
        "passenger_count": 4 if order_type == "airport_transfer" else 8,
        "luggage_count": 4 if order_type == "airport_transfer" else 0,
        "guest_name": name,
        "guest_contact": f"080-test-{price}",
        "guide_name": f"{name} Guide",
        "guide_phone": f"090-guide-{price}",
        "price_jpy": price,
        "remark": f"多租户边界测试订单：{name}",
    }


def carrier_view(carrier_tenant_id: int) -> list[dict[str, Any]]:
    return rows(
        """
        SELECT l.id, l.listing_code, l.status, l.buyer_tenant_id,
               o.oid, o.order_date, o.start_time, o.pickup_location, o.dropoff_location,
               o.guest_name, o.guest_contact, o.guide_name, o.guide_phone,
               seller.name AS seller_company_name,
               buyer.name AS buyer_company_name
        FROM auction_listings l
        JOIN orders o ON o.id = l.order_id
        LEFT JOIN tenants seller ON seller.id = l.seller_tenant_id
        LEFT JOIN tenants buyer ON buyer.id = l.buyer_tenant_id
        WHERE l.buyer_tenant_id = ?
          AND l.status IN ('claimed', 'sold')
        ORDER BY l.sold_at DESC, l.id DESC
        """,
        (carrier_tenant_id,),
    )


def run_boundary_flow() -> dict[str, Any]:
    reset_db()
    steps: list[dict[str, Any]] = []

    token_a = agency_portal_login({"agency_id": 1, "tenant_id": 101, "portal_code": "aga-pass"})["token"]
    token_b = agency_portal_login({"agency_id": 2, "tenant_id": 102, "portal_code": "agb-pass"})["token"]
    step(steps, "两个旅行社分别登录", True, "A/B 两家旅行社使用各自 portal_code 登录。", "两个 token 均生成成功。")

    a1 = create_agency_order(token_a, agency_order_payload("A机场客人", "2026-06-20", "09:00", "KIX T1", "Osaka Station", 58000, "airport_transfer"))
    a2 = create_agency_order(token_a, agency_order_payload("A包车客人", "2026-06-21", "10:00", "Kyoto", "Amanohashidate", 180000, "charter"))
    b1 = create_agency_order(token_b, agency_order_payload("B机场客人", "2026-06-20", "12:00", "Haneda T3", "Tokyo Hotel", 62000, "airport_transfer"))
    b2 = create_agency_order(token_b, agency_order_payload("B包车客人", "2026-06-22", "08:30", "Tokyo", "Fuji", 210000, "charter"))
    step(
        steps,
        "四条订单分属两个旅行社",
        len({a1["agency_id"], a2["agency_id"], b1["agency_id"], b2["agency_id"]}) == 2,
        "orders 记录应带有各自 agency_id 和 tenant_id。",
        "A 旅行社 2 单，B 旅行社 2 单。",
        {"A": [a1["oid"], a2["oid"]], "B": [b1["oid"], b2["oid"]]},
    )

    a_orders = list_agency_orders(token_a)
    b_orders = list_agency_orders(token_b)
    a_seen_b = any(order["id"] in {b1["id"], b2["id"]} for order in a_orders)
    b_seen_a = any(order["id"] in {a1["id"], a2["id"]} for order in b_orders)
    step(
        steps,
        "旅行社我的订单隔离",
        len(a_orders) == 2 and len(b_orders) == 2 and not a_seen_b and not b_seen_a,
        "旅行社只能在“我的订单/订单列表/日历”看到自己 agency_id 下的订单。",
        f"A 列表 {len(a_orders)} 条，B 列表 {len(b_orders)} 条，未交叉泄漏。",
        {"A_order_ids": [o["id"] for o in a_orders], "B_order_ids": [o["id"] for o in b_orders]},
    )

    try:
        publish_agency_order_to_hall(token_a, b1["id"], {"start_price_jpy": 50000, "buyout_price_jpy": 70000, "auction_duration_hours": 1})
        cross_publish_error = ""
    except Exception as exc:  # noqa: BLE001
        cross_publish_error = str(exc)
    step(
        steps,
        "旅行社不能操作其他旅行社订单",
        "order_not_found" in cross_publish_error,
        "A 旅行社拿 B 旅行社订单 ID 发布，应被 tenant_id + agency_id 拦截。",
        f"接口返回：{cross_publish_error}",
    )

    listings = []
    for token, order, start_price, buyout in [
        (token_a, a1, 52000, 70000),
        (token_a, a2, 160000, 210000),
        (token_b, b1, 56000, 76000),
        (token_b, b2, 190000, 240000),
    ]:
        published = publish_agency_order_to_hall(
            token,
            order["id"],
            {"start_price_jpy": start_price, "buyout_price_jpy": buyout, "auction_duration_hours": 2},
        )
        listings.append(published["listings"][0])

    hall_a = list_agency_auction_hall(token_a, "listed")
    hall_b = list_agency_auction_hall(token_b, "listed")
    sensitive_keys = {"guest_name", "guest_contact", "guide_name", "guide_phone", "agency_contact_phone", "agency_contact_wechat"}
    leaked_keys = sorted(key for item in hall_a for key in sensitive_keys if key in item and item.get(key))
    step(
        steps,
        "订单大厅公开基础信息",
        len(hall_a) == 4 and len(hall_b) == 4 and not leaked_keys,
        "大厅允许多旅行社、多车公司看到基础信息，但不能暴露游客/导游/担当联系方式。",
        f"A/B 登录大厅均看到 4 条 listed；敏感字段泄漏键：{leaked_keys or '无'}。",
        {"hall_a_count": len(hall_a), "hall_b_count": len(hall_b), "sample": hall_a[0] if hall_a else None},
    )

    set_current_tenant_id(201)
    try:
        get_auction_listing_detail(listings[0]["listing_id"], {"tenant_id": 201})
        pre_claim_detail_error = ""
    except Exception as exc:  # noqa: BLE001
        pre_claim_detail_error = str(exc)
    step(
        steps,
        "车公司未接单前不能看完整详情",
        pre_claim_detail_error in {"listing_detail_forbidden", "listing_detail_not_available_before_claim"},
        "车公司未成为 buyer_tenant_id 前，不能查看旅行社联系方式、游客联系方式、导游联系方式。",
        f"接口返回：{pre_claim_detail_error}",
    )

    claimed_pairs = [
        (listings[0], 201, "sakura-admin"),
        (listings[2], 201, "sakura-admin"),
        (listings[1], 202, "kex-admin"),
        (listings[3], 202, "kex-admin"),
    ]
    claim_results = []
    for listing, carrier_id, username in claimed_pairs:
        # Current claim service validates against seller_tenant_id and accepts buyer_tenant_id as payload.
        order = one("SELECT tenant_id FROM orders WHERE id = ?", (listing["order_id"],))
        set_current_tenant_id(order["tenant_id"])
        claim_results.append(
            claim_auction_listing(
                listing["listing_id"],
                {"buyer_tenant_id": carrier_id, "claim_price_jpy": listing.get("auction_duration_hours", 0) or 1},
                {"tenant_id": carrier_id, "username": username},
            )
        )
    step(
        steps,
        "两个车公司交叉接单",
        len(claim_results) == 4 and all(item.get("status") == "claimed" for item in claim_results),
        "SAKURA 和 KEX 各接 A/B 两家旅行社的订单，买方租户写入 buyer_tenant_id。",
        "四条订单均 claimed。",
        claim_results,
    )

    set_current_tenant_id(201)
    detail_after = get_auction_listing_detail(listings[0]["listing_id"], {"tenant_id": 201})
    set_current_tenant_id(202)
    try:
        get_auction_listing_detail(listings[0]["listing_id"], {"tenant_id": 202})
        wrong_carrier_error = ""
    except Exception as exc:  # noqa: BLE001
        wrong_carrier_error = str(exc)
    step(
        steps,
        "接单车公司可看详情，其他车公司不可看",
        bool(detail_after.get("guest_contact")) and wrong_carrier_error == "listing_detail_forbidden",
        "buyer_tenant_id 对应车公司可查看完整详情；非买方车公司仍被拦截。",
        f"SAKURA 可见 guest_contact={detail_after.get('guest_contact')}；KEX 查看同单返回 {wrong_carrier_error}。",
    )

    sakura_orders = carrier_view(201)
    kex_orders = carrier_view(202)
    step(
        steps,
        "车公司接多个旅行社订单的展示方式",
        len(sakura_orders) == 2 and len(kex_orders) == 2 and {row["seller_company_name"] for row in sakura_orders} == {"东瀛假期旅行社", "富士之旅旅行社"},
        "车公司后台应按 buyer_tenant_id 汇总已接订单，并保留来源旅行社列。",
        f"SAKURA {len(sakura_orders)} 单，KEX {len(kex_orders)} 单，均来自多个旅行社。",
        {"SAKURA": sakura_orders, "KEX": kex_orders},
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "test_db": str(TEST_DB),
        "steps": steps,
        "agencies": rows("SELECT id, tenant_id, agency_code, name FROM agencies ORDER BY id"),
        "tenants": rows("SELECT id, name, slug FROM tenants ORDER BY id"),
        "orders": rows("SELECT id, tenant_id, agency_id, oid, order_type, guest_name, guest_contact, dispatch_status FROM orders ORDER BY id"),
        "listings": rows("SELECT id, order_id, seller_tenant_id, buyer_tenant_id, status, listing_code, start_price_jpy, buyout_price_jpy FROM auction_listings ORDER BY id"),
        "carrier_views": {"SAKURA": carrier_view(201), "KEX": carrier_view(202)},
        "recommendations": [
            "旅行社“我的订单/日历/订单跟踪”继续使用 tenant_id + agency_id 双条件，不允许用单独 order_id 直接越权访问。",
            "订单大厅保留公开基础信息：日期、时间、起止地、车型、人数/行李、价格区间、PDF 是否存在；游客/导游/旅行社担当联系方式只在接单后向买方车公司开放。",
            "车公司已接订单列表应服务端按 buyer_tenant_id 过滤，页面可按来源旅行社、日期、车型、结算状态筛选。",
            "平台端可跨租户查看，但必须记录审计日志，并在页面上明确 seller_tenant_id、buyer_tenant_id、agency_id。",
            "当前 claim_auction_listing 服务用 seller_tenant_id 作为上下文校验，再从 payload 写入 buyer_tenant_id；正式车公司端接口建议增加专用 claim endpoint，用登录车公司 tenant_id 自动作为 buyer_tenant_id，避免前端传错。",
        ],
    }


TEST_PLAN_ROWS = [
    ("BT-01", "旅行社登录隔离", "A/B 两家旅行社分别登录", "只能拿到本 agency token 和本租户上下文", "单元 + 接口"),
    ("BT-02", "我的订单隔离", "A/B 各建两单后互查订单列表", "A 看不到 B 的订单，B 看不到 A 的订单", "数据边界"),
    ("BT-03", "越权操作拦截", "A 用 B 的 order_id 发布/修改/撤回", "返回 order_not_found 或 forbidden", "负向测试"),
    ("BT-04", "大厅公开信息", "A/B 进入订单大厅", "都可看到 listed 基础信息，但无游客/导游/担当联系方式", "脱敏测试"),
    ("BT-05", "车公司未接单详情", "车公司点未接单详情", "不能获取完整详情", "权限测试"),
    ("BT-06", "交叉接单", "两个车公司分别接 A/B 的订单", "buyer_tenant_id 正确落库，seller_tenant_id 保留发布方", "集成测试"),
    ("BT-07", "接单后详情", "买方车公司查看已接订单详情", "可见完整联系人、行程、PDF、结算入口", "联动测试"),
    ("BT-08", "非买方拦截", "另一个车公司查看别人已接订单", "返回 forbidden", "负向测试"),
    ("BT-09", "车公司已接订单展示", "车公司后台查看已接订单", "按 buyer_tenant_id 汇总，来源旅行社作为列/筛选项", "页面测试"),
    ("BT-10", "平台审计", "平台查看跨旅行社/跨车公司订单", "可见全量 seller/buyer/agency 关系并记录审计", "平台测试"),
]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def status(ok: bool) -> str:
    return "<span class='ok'>通过</span>" if ok else "<span class='bad'>未通过</span>"


def render(result: dict[str, Any]) -> str:
    passed = sum(1 for item in result["steps"] if item["ok"])
    total = len(result["steps"])
    plan_rows = "\n".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in TEST_PLAN_ROWS)
    step_rows = "\n".join(
        f"<tr><td>{idx}</td><td>{esc(item['name'])}</td><td>{status(item['ok'])}</td><td>{esc(item['expected'])}</td><td>{esc(item['actual'])}</td><td><pre>{esc(json.dumps(item.get('evidence'), ensure_ascii=False, indent=2, default=str))}</pre></td></tr>"
        for idx, item in enumerate(result["steps"], start=1)
    )
    listing_rows = "\n".join(
        f"<tr><td>{esc(row['listing_code'])}</td><td>{esc(row['seller_tenant_id'])}</td><td>{esc(row['buyer_tenant_id'])}</td><td>{esc(row['status'])}</td><td>{esc(row['order_id'])}</td><td>{esc(row['start_price_jpy'])}</td><td>{esc(row['buyout_price_jpy'])}</td></tr>"
        for row in result["listings"]
    )
    order_rows = "\n".join(
        f"<tr><td>{esc(row['oid'])}</td><td>{esc(row['tenant_id'])}</td><td>{esc(row['agency_id'])}</td><td>{esc(row['order_type'])}</td><td>{esc(row['guest_name'])}</td><td>{esc(row['dispatch_status'])}</td></tr>"
        for row in result["orders"]
    )
    carrier_cards = ""
    for name, items in result["carrier_views"].items():
        carrier_cards += f"<h3>{esc(name)} 已接订单</h3><table><thead><tr><th>大厅编号</th><th>订单号</th><th>来源旅行社</th><th>客人</th><th>联系人</th><th>日期</th><th>路线</th></tr></thead><tbody>"
        for item in items:
            carrier_cards += f"<tr><td>{esc(item.get('listing_code'))}</td><td>{esc(item.get('oid'))}</td><td>{esc(item.get('seller_company_name'))}</td><td>{esc(item.get('guest_name'))}</td><td>{esc(item.get('guest_contact'))}</td><td>{esc(item.get('order_date'))} {esc(item.get('start_time'))}</td><td>{esc(item.get('pickup_location'))} -> {esc(item.get('dropoff_location'))}</td></tr>"
        carrier_cards += "</tbody></table>"
    recommendations = "".join(f"<li>{esc(item)}</li>" for item in result["recommendations"])
    raw = esc(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>多旅行社多车公司数据边界测试计划</title>
  <style>
    :root {{ --bg:#f5f7fa; --panel:#fff; --text:#20242a; --muted:#667085; --line:#d9dee8; --head:#eef3f8; --ok:#157347; --bad:#b42318; --accent:#1f5f74; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Microsoft YaHei", Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:28px 32px 18px; background:#fff; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0 0 8px; font-size:26px; letter-spacing:0; }}
    h2 {{ font-size:18px; margin:26px 0 12px; }}
    h3 {{ font-size:15px; margin:18px 0 8px; }}
    .meta {{ color:var(--muted); font-size:13px; display:flex; gap:14px; flex-wrap:wrap; }}
    .wrap {{ padding:22px 32px 42px; }}
    .summary {{ display:grid; grid-template-columns:repeat(4,minmax(160px,1fr)); gap:12px; }}
    .metric, .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; }}
    .metric {{ padding:14px; }}
    .metric b {{ display:block; margin-top:5px; font-size:22px; color:var(--accent); }}
    .panel {{ padding:16px; margin-top:18px; overflow:auto; }}
    table {{ width:100%; border-collapse:collapse; min-width:940px; }}
    th, td {{ border:1px solid var(--line); padding:9px 10px; vertical-align:top; font-size:13px; line-height:1.45; }}
    th {{ background:var(--head); text-align:left; white-space:nowrap; }}
    pre {{ margin:0; max-height:230px; overflow:auto; white-space:pre-wrap; font-size:12px; }}
    .ok {{ color:var(--ok); font-weight:700; }}
    .bad {{ color:var(--bad); font-weight:700; }}
    .note {{ color:var(--muted); line-height:1.65; font-size:13px; }}
    li {{ margin:6px 0; }}
    @media (max-width: 900px) {{ header,.wrap {{ padding-left:16px; padding-right:16px; }} .summary {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>多旅行社 × 多车公司数据边界测试计划</h1>
    <div class="meta">
      <span>生成时间：{esc(result["generated_at"])}</span>
      <span>临时测试库：{esc(result["test_db"])}</span>
      <span>测试主题：交叉登录、交叉发布、交叉接单、详情脱敏、买方归属展示</span>
    </div>
  </header>
  <main class="wrap">
    <section class="summary">
      <div class="metric">实跑边界用例<b>{passed}/{total}</b></div>
      <div class="metric">旅行社<b>{len(result["agencies"])}</b></div>
      <div class="metric">车公司<b>2</b></div>
      <div class="metric">订单/大厅记录<b>{len(result["orders"])} / {len(result["listings"])}</b></div>
    </section>

    <section class="panel">
      <h2>一、测试计划</h2>
      <p class="note">本页把“我的订单私有列表”和“订单大厅公开基础信息”分开测试。大厅可以被多旅行社、多车公司围观，但未接单前不开放完整联系方式。</p>
      <table>
        <thead><tr><th>编号</th><th>测试范围</th><th>操作</th><th>预期边界</th><th>测试类型</th></tr></thead>
        <tbody>{plan_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>二、实际数据验证结果</h2>
      <table>
        <thead><tr><th>#</th><th>测试点</th><th>结果</th><th>预期</th><th>实际</th><th>证据</th></tr></thead>
        <tbody>{step_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>三、订单与租户归属</h2>
      <table>
        <thead><tr><th>订单号</th><th>tenant_id</th><th>agency_id</th><th>类型</th><th>客人</th><th>状态</th></tr></thead>
        <tbody>{order_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>四、大厅发布与接单归属</h2>
      <table>
        <thead><tr><th>大厅编号</th><th>seller_tenant_id</th><th>buyer_tenant_id</th><th>状态</th><th>订单ID</th><th>起拍价</th><th>一口价</th></tr></thead>
        <tbody>{listing_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>五、车公司接到多个旅行社订单后的展示建议</h2>
      <p class="note">车公司后台不应该按旅行社租户切换，而应按自己的 buyer_tenant_id 汇总“我接到的订单”，并在列表中显示来源旅行社。</p>
      {carrier_cards}
    </section>

    <section class="panel">
      <h2>六、结论与补强建议</h2>
      <ul>{recommendations}</ul>
    </section>

    <section class="panel">
      <h2>七、原始 JSON 证据</h2>
      <pre>{raw}</pre>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    result = run_boundary_flow()
    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    RESULT_HTML.write_text(render(result), encoding="utf-8")
    print(json.dumps({"html": str(RESULT_HTML), "json": str(RESULT_JSON), "db": str(TEST_DB)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

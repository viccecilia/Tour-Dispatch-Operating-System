import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from datetime import date
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
FRONTEND_URL = os.environ.get("WX_DISPATCH_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
TOKEN = ""

DEMO_TEXT = """5.29 08:00 关西接机大阪 10座600
5.29 10:20 大阪单送京都 3代 绿450
5.29 13:30 京都-奈良-大阪 包车 10座 儿童座椅*1 1600（高速另算）
5.29 18:10 大阪送机关西 3代 绿450"""


def request(method: str, path: str, payload: dict | None = None, *, token: bool = True) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN and token:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BACKEND_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def login() -> None:
    global TOKEN
    request("GET", "/api/ping", token=False)
    auth = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"}, token=False)
    TOKEN = auth["token"]


def ids_from_list(path: str, key: str) -> set[int]:
    data = request("GET", path)
    return {int(item["id"]) for item in data.get(key, []) if item.get("id") is not None}


def list_new_drafts(before_ids: set[int]) -> list[dict]:
    data = request("GET", "/api/parser/drafts")
    rows = [item for item in data.get("drafts", []) if int(item.get("id") or 0) not in before_ids and item.get("parse_status") != "confirmed"]
    return sorted(rows, key=lambda item: int(item.get("id") or 0))


def list_new_unassigned_orders(before_ids: set[int]) -> list[dict]:
    data = request("GET", "/api/dispatch/unassigned-orders")
    rows = [item for item in data.get("orders", []) if int(item.get("id") or 0) not in before_ids]
    return sorted(rows, key=lambda item: (item.get("order_date") or "", item.get("start_time") or "", item.get("id") or 0))


def normalize_drafts_for_today(drafts: list[dict]) -> None:
    today = date.today().isoformat()
    demo_specs = [
        ("08:00", "09:10", "关西机场", "大阪市内酒店", "接机", "10座", 620),
        ("10:20", "11:40", "大阪市内酒店", "京都站", "单送", "3代绿牌", 450),
        ("13:30", "16:40", "京都", "奈良-大阪", "包车", "10座", 1600),
        ("18:10", "19:20", "大阪市内酒店", "关西机场", "送机", "3代绿牌", 450),
    ]
    run_code = datetime.now().strftime("%H%M%S")
    for index, (draft, spec) in enumerate(zip(drafts[:4], demo_specs, strict=False), start=1):
        start_time, end_time, pickup, dropoff, order_type, vehicle_type, price = spec
        request(
            "PUT",
            f"/api/parser/drafts/{draft['id']}",
            {
                "oid": f"UI{date.today().strftime('%y%m%d')}-{run_code}-{index:02d}",
                "order_date": today,
                "end_date": today,
                "start_time": start_time,
                "end_time": end_time,
                "pickup_location": pickup,
                "dropoff_location": dropoff,
                "order_type": order_type,
                "vehicle_type": vehicle_type,
                "price": price,
                "guest_name": "演示客人",
                "guest_contact": "090-0000-1234",
                "agency_name": "演示旅行社",
                "parse_status": "parsed",
                "remark": f"UI演示人工修正：{pickup} -> {dropoff}",
            },
        )


def pick_vehicle(vehicle_id: int | None) -> dict:
    vehicles = request("GET", "/api/resources/vehicles").get("vehicles", [])
    if vehicle_id:
        found = next((item for item in vehicles if int(item.get("id") or 0) == vehicle_id), None)
        if found:
            return found
        raise RuntimeError(f"vehicle_id={vehicle_id} not found")
    suffix = datetime.now().strftime("%H%M%S")
    return request(
        "POST",
        "/api/resources/vehicles",
        {"plate_number": f"UI-DEMO-{suffix}", "vehicle_type": "ハイエース 10座", "seat_count": 10, "status": "available"},
    )["vehicle"]


def click_unique(locator, label: str) -> None:
    count = locator.count()
    if count != 1:
        raise RuntimeError(f"{label} locator expected 1 match, got {count}")
    locator.click()


def main() -> None:
    parser = argparse.ArgumentParser(description="Visible browser UI demo: parser -> dispatch -> driver confirm.")
    parser.add_argument("--driver-id", type=int, default=1)
    parser.add_argument("--vehicle-id", type=int, default=0)
    parser.add_argument("--slow-ms", type=int, default=450)
    parser.add_argument("--keep-open-seconds", type=int, default=20)
    parser.add_argument("--manual-driver-confirm", action="store_true", help="Pause after dispatch so the operator can tap confirm in WeChat DevTools.")
    args = parser.parse_args()

    login()
    before_drafts = ids_from_list("/api/parser/drafts", "drafts")
    before_unassigned = ids_from_list("/api/dispatch/unassigned-orders", "orders")
    vehicle = pick_vehicle(args.vehicle_id or None)

    screenshot_dir = ROOT_DIR / "runtime" / "demo_runs" / f"browser_ui_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=args.slow_ms)
        context = browser.new_context(viewport={"width": 1440, "height": 920})
        context.add_init_script(f"window.localStorage.setItem('wx_dispatch_token', {json.dumps(TOKEN)});")
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())

        print("1/7 打开订单解析页，粘贴真实订单文本")
        page.goto(f"{FRONTEND_URL}/#parser")
        page.get_by_test_id("parser-input").fill(DEMO_TEXT)
        page.screenshot(path=screenshot_dir / "01-parser-input.png", full_page=False)

        print("2/7 点击批量解析，生成待确认草稿")
        page.get_by_test_id("parser-parse-button").click()
        page.get_by_text("已拆分并生成", exact=False).wait_for(timeout=15000)
        drafts = list_new_drafts(before_drafts)
        if len(drafts) < 4:
            raise RuntimeError(f"expected at least 4 new drafts, got {len(drafts)}")
        normalize_drafts_for_today(drafts)
        page.reload()
        page.get_by_test_id("parser-input").wait_for(timeout=10000)
        page.screenshot(path=screenshot_dir / "02-parser-drafts.png", full_page=False)

        print("3/7 模拟解析有偏差：打开第一条草稿编辑价格并保存")
        first_draft_id = int(drafts[0]["id"])
        row = page.locator(f'[data-testid="parser-draft-row"][data-draft-id="{first_draft_id}"]')
        row.scroll_into_view_if_needed()
        row.get_by_test_id("parser-edit-draft-button").click()
        page.get_by_test_id("parser-edit-price").fill("620")
        page.get_by_test_id("parser-save-draft-button").click()
        page.get_by_text("草稿已保存", exact=False).wait_for(timeout=15000)
        page.screenshot(path=screenshot_dir / "03-parser-edit-save.png", full_page=False)

        print("4/7 点击原地确认，把草稿写入订单池")
        for draft in drafts[:4]:
            draft_row = page.locator(f'[data-testid="parser-draft-row"][data-draft-id="{int(draft["id"])}"]')
            draft_row.scroll_into_view_if_needed()
            checkbox = draft_row.locator('input[type="checkbox"]')
            if not checkbox.is_checked():
                checkbox.check()
        page.get_by_test_id("parser-confirm-selected-button").click()
        page.get_by_text("已确认", exact=False).wait_for(timeout=20000)
        orders = list_new_unassigned_orders(before_unassigned)
        if len(orders) < 4:
            raise RuntimeError(f"expected at least 4 new unassigned orders, got {len(orders)}")
        target_orders = orders[:4]
        page.screenshot(path=screenshot_dir / "04-parser-confirmed.png", full_page=False)

        print("5/7 打开派车页，选择 4 个订单、司机和车辆")
        page.goto(f"{FRONTEND_URL}/#dispatch")
        for order in target_orders:
            order_row = page.locator(f'[data-testid="dispatch-order-row"][data-order-id="{int(order["id"])}"]')
            order_row.scroll_into_view_if_needed()
            order_row.click()
        driver_card = page.locator(f'[data-testid="dispatch-driver-card"][data-driver-id="{args.driver_id}"]')
        driver_card.scroll_into_view_if_needed()
        driver_card.click()
        vehicle_card = page.locator(f'[data-testid="dispatch-vehicle-card"][data-vehicle-id="{int(vehicle["id"])}"]')
        vehicle_card.scroll_into_view_if_needed()
        vehicle_card.click()
        page.screenshot(path=screenshot_dir / "05-dispatch-selected.png", full_page=False)

        print("6/7 点击批量派车，司机端会收到订单")
        page.get_by_test_id("dispatch-assign-button").click()
        page.get_by_text("派车完成", exact=False).wait_for(timeout=20000)
        page.screenshot(path=screenshot_dir / "06-dispatch-assigned.png", full_page=False)

        print("7/7 司机端确认接单，后台状态变为已确认")
        assignments = request("GET", f"/api/driver/assignments?driver_id={args.driver_id}").get("assignments", [])
        order_ids = {int(order["id"]) for order in target_orders}
        assigned_rows = [item for item in assignments if int(item.get("order_id") or 0) in order_ids]
        if args.manual_driver_confirm:
            print("请现在到微信开发者工具司机端点击“确认接单”。完成后回到这个窗口按 Enter 继续。")
            input()
        else:
            for item in assigned_rows:
                request(
                    "POST",
                    "/api/driver/report",
                    {
                        "driver_id": args.driver_id,
                        "assignment_id": item["assignment_id"],
                        "report_type": "confirm_order",
                        "location_text": "司机端确认接单",
                        "note": "UI 演示：司机点击确认接单",
                    },
                )
        page.goto(f"{FRONTEND_URL}/#driver-monitor")
        page.screenshot(path=screenshot_dir / "07-driver-confirmed.png", full_page=False)

        result = {
            "driver_id": args.driver_id,
            "vehicle_id": int(vehicle["id"]),
            "draft_ids": [int(item["id"]) for item in drafts[:4]],
            "order_ids": [int(item["id"]) for item in target_orders],
            "assignment_ids": [int(item["assignment_id"]) for item in assigned_rows],
            "screenshots": str(screenshot_dir),
        }
        result_path = screenshot_dir / "result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"截图和结果已保存：{screenshot_dir}")
        if args.keep_open_seconds > 0:
            print(f"浏览器保持 {args.keep_open_seconds} 秒，方便观察。")
            time.sleep(args.keep_open_seconds)
        browser.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()

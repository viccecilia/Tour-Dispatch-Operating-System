import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")


CHARTER_TEXT = """Ashwin Arora
5.09 11:00 大阪往返天桥立美山 包车 3代 绿 1900
5.10 11:00 大阪-奈良-宇治-京都 包车 3代 绿 1500
5.11 11:00 京都市内 包车 3代 绿 1500
5.12 10:00 铃鹿-京都 包车 10座绿牌 儿童座椅*2  2000若綺 黃
5.14 京都往返天桥立美山 包车 10座绿牌 儿童座椅*2（+座椅2000） 1900Kuan-Ying Chen
Chris Lo
5.14 10:00 大阪-奈良-大阪 包车 3代 绿1500
5.16 10:00 京都市内 包车 3代 绿1400
5.15 08:30 京都-美山-龟岗-京都 包车 10座 儿童座椅  1600（美山+7000）權晃 李
5.15 10:00 关西酒店-胜尾寺-京都-大津-京都 包车 3代 绿 1700+5000日元 Sau Ping Yeung 以上是包车订单。"""


TRANSFER_TEXT = """3.29 10:00 大阪单送名古屋 10座 1700
3.29 14:10 关西接机大阪 10座600
3.29 08:05 关西接机大阪 10座600
3.29 08:00/20:00 环球往返接送 3代600
3.29 07:30 大阪单送新大阪 3代 300
---
3.29 08:20 京都送机关西 3代 绿800
3.29 19:30 京都单送关西酒店 3代绿 600+4000
3.29 14:00 关西接机京都 3代 绿800
3.29 11:00 大阪送机神户机场 3代 绿450
3.29 07:30 大阪送机关西 3代 绿450
3.29 11:30 大阪送机关西 3代 儿童座椅 绿450
3.29 13:00 大阪单送关西酒店 3代 绿450
3.29 11:25 关西接机大阪 3代 儿童座椅 绿450
3.29 13:05 关西接机大阪 3代 绿450
3.29 15:00 关西接机大阪 3代 绿450
3.29 16:10 关西接机大阪 3代 绿450
3.29 19:30 关西接机大阪 3代 绿450
3.29 21:15 关西接机大阪 3代 绿450
以上是送迎订单。"""


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def assert_true(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)


def main() -> None:
    ping = request("GET", "/api/ping")
    assert_true("ping", ping.get("ok") is True)

    response = request("POST", "/api/parser/text", {"text": f"{CHARTER_TEXT}\n{TRANSFER_TEXT}", "batch": True})
    drafts = response.get("drafts", [])
    assert_true("batch_count", response.get("count") == 27)
    assert_true("all_raw_text_kept", all(draft.get("raw_text") for draft in drafts))

    charter = [draft for draft in drafts if "包车" in draft.get("raw_text", "")]
    transfers = [draft for draft in drafts if any(token in draft.get("raw_text", "") for token in ["接机", "送机", "接送", "单送"])]
    assert_true("charter_split", len(charter) == 9)
    assert_true("transfer_split", len(transfers) == 18)
    assert_true("multi_stop_route", any("大阪" in str(d.get("pickup_location")) and "京都" in str(d.get("dropoff_location")) for d in drafts))
    assert_true("no_space_price", any("绿1500" in d.get("raw_text", "") and float(d.get("price") or 0) == 1500 for d in drafts))
    assert_true("fee_note_kept", any("美山+7000" in str(d.get("fee_remark") or d.get("remark") or "") for d in drafts))
    assert_true("child_seat_kept", any("儿童座椅*2" in str(d.get("fee_remark") or d.get("remark") or "") for d in drafts))

    first = drafts[0]
    updated = request(
        "PUT",
        f"/api/parser/drafts/{first['id']}",
        {
            "pickup_location": "大阪市",
            "dropoff_location": "天桥立美山",
            "remark": "R013 人工修正后确认",
            "parse_status": "parsed",
        },
    )["draft"]
    confirmed = request("POST", f"/api/parser/drafts/{first['id']}/confirm")
    order = request("GET", f"/api/orders/{confirmed['order_id']}")["order"]
    failed = request("POST", "/api/parser/text", {"text": "完全无法识别但必须保留的测试文本"})
    orders = request("GET", "/api/orders").get("orders", [])

    result = {
        "ping_ok": ping.get("ok") is True,
        "batch_count": response.get("count"),
        "charter_count": len(charter),
        "transfer_count": len(transfers),
        "raw_text_kept": all(draft.get("raw_text") for draft in drafts),
        "updated_pickup": updated.get("pickup_location"),
        "confirmed_order_id": confirmed.get("order_id"),
        "confirmed_order_visible": any(item.get("id") == order.get("id") for item in orders),
        "failed_status": failed.get("parse_status"),
        "failed_raw_text_kept": failed.get("draft", {}).get("raw_text") == "完全无法识别但必须保留的测试文本",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

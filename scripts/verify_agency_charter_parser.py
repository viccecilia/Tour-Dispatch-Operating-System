from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import init_db
from backend.services.agency_portal_service import _agency_parsed_order, _split_agency_batch_text


SAMPLE = (
    "6.09日京都-安来(路程4小时)2300\n"
    "6.10日 松江-神户(路程3小时)2300\n"
    "6.11日神户-京都市区游玩（含岚山小火车门票）1600\n"
    "6.12日 京都游玩旧竹林院，浮御堂白须神社(optional)琵琶湖Biwako1900"
)

ROUTE_CHAIN_SAMPLE = (
    "6.08 神户-箕面-池田-神户 包车 3代 绿\n"
    "6.12 岡山市-玉野市-岡山市 包车 3代 绿\n"
    "6.14 仓敷市-福山-尾道市 包车 3代 绿\n"
    "6.15 尾道市 包车 3代 绿\n"
    "6.16 尾道市-三原市-广岛 包车 3代 绿"
)

EXPECTED = [
    ("2026-06-09", "09:00", "13:00", "京都", "安来", 2300.0),
    ("2026-06-10", "09:00", "12:00", "松江", "神户", 2300.0),
    ("2026-06-11", "09:00", "19:00", "神户", "京都市区游玩", 1600.0),
    ("2026-06-12", "09:00", "19:00", "京都", "琵琶湖Biwako", 1900.0),
]

ROUTE_CHAIN_EXPECTED = [
    ("2026-06-08", "09:00", "19:00", "神户", "神户", "3代", "神户 -> 箕面 -> 池田 -> 神户"),
    ("2026-06-12", "09:00", "19:00", "岡山市", "岡山市", "3代", "岡山市 -> 玉野市 -> 岡山市"),
    ("2026-06-14", "09:00", "19:00", "仓敷市", "尾道市", "3代", "仓敷市 -> 福山 -> 尾道市"),
    ("2026-06-15", "09:00", "19:00", "尾道市", "尾道市", "3代", "尾道市 包车"),
    ("2026-06-16", "09:00", "19:00", "尾道市", "广岛", "3代", "尾道市 -> 三原市 -> 广岛"),
]


def main() -> None:
    init_db(seed=True)
    chunks = _split_agency_batch_text(SAMPLE)
    assert len(chunks) == len(EXPECTED), f"expected {len(EXPECTED)} chunks, got {len(chunks)}"
    for index, (chunk, expected) in enumerate(zip(chunks, EXPECTED, strict=True), start=1):
        parsed = _agency_parsed_order(chunk, "batch_charter")
        actual = (
            parsed.get("order_date"),
            parsed.get("start_time"),
            parsed.get("end_time"),
            parsed.get("pickup_location"),
            parsed.get("dropoff_location"),
            parsed.get("price"),
        )
        assert actual == expected, f"order {index}: expected {expected}, got {actual}"

    route_chunks = _split_agency_batch_text(ROUTE_CHAIN_SAMPLE)
    assert len(route_chunks) == len(ROUTE_CHAIN_EXPECTED), f"expected {len(ROUTE_CHAIN_EXPECTED)} route chunks, got {len(route_chunks)}"
    for index, (chunk, expected) in enumerate(zip(route_chunks, ROUTE_CHAIN_EXPECTED, strict=True), start=1):
        parsed = _agency_parsed_order(chunk, "batch_charter")
        actual = (
            parsed.get("order_date"),
            parsed.get("start_time"),
            parsed.get("end_time"),
            parsed.get("pickup_location"),
            parsed.get("dropoff_location"),
            parsed.get("vehicle_type"),
        )
        expected_head = expected[:6]
        assert actual == expected_head, f"route order {index}: expected {expected_head}, got {actual}"
        assert expected[6] in str(parsed.get("remark") or ""), f"route order {index}: missing full route in {parsed.get('remark')}"
    print("agency charter parser ok")


if __name__ == "__main__":
    main()

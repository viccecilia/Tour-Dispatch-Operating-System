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

EXPECTED = [
    ("2026-06-09", "09:00", "13:00", "京都", "安来", 2300.0),
    ("2026-06-10", "09:00", "12:00", "松江", "神户", 2300.0),
    ("2026-06-11", "09:00", "19:00", "神户", "京都市区", 1600.0),
    ("2026-06-12", "09:00", "19:00", "京都", "琵琶湖Biwako", 1900.0),
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
    print("agency charter parser ok")


if __name__ == "__main__":
    main()

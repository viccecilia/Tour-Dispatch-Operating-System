from __future__ import annotations

import re
import unicodedata
from typing import Any


ROUTE_TARIFFS: dict[str, dict[str, Any]] = {
    "osaka_kix": {"label": "大阪市内 ↔ KIX", "hiace": 12460, "alphard": 11270},
    "kyoto_osaka": {"label": "京都市内 ↔ 大阪市内", "hiace": 15480, "alphard": 13980},
    "osaka_kobe_nara": {"label": "大阪市内 ↔ 神戸／奈良", "hiace": 12460, "alphard": 11270},
    "osaka_10h_charter": {"label": "大阪 10H 貸切", "hiace": 58390, "alphard": 52430},
}

OSAKA_PATTERN = re.compile(r"大阪|心斎橋|心斋桥|黒門|黑门|通天閣|通天阁|新大阪|梅田|難波|なんば|天王寺|海遊館|海游馆|(?<![A-Z0-9])USJ(?![A-Z0-9])|ユニバーサル", re.I)
KIX_PATTERN = re.compile(r"(?<![A-Z0-9])KIX(?![A-Z0-9])|関西国際空港|関西空港|关西机场|關西機場|关空|關空|関空", re.I)
KYOTO_PATTERN = re.compile(r"京都", re.I)
KOBE_NARA_PATTERN = re.compile(r"神戸|神户|奈良", re.I)
TEN_HOUR_PATTERN = re.compile(r"(?<![0-9])10\s*(?:H|HR|HOURS?)(?![A-Z])|10\s*(?:小时|小時|時間)", re.I)
CHARTER_PATTERN = re.compile(r"包车|包車|貸切|日游|一日游", re.I)


def recommend_route_fare(
    pickup_location: Any,
    dropoff_location: Any,
    order_type: Any,
    vehicle_type: Any,
    remark: Any = "",
    seat_count: Any = None,
) -> dict[str, Any] | None:
    """Return a directional-neutral confirmed tariff without changing stored order data."""
    pickup = _text(pickup_location)
    dropoff = _text(dropoff_location)
    endpoints = f"{pickup} {dropoff}"
    context = f"{endpoints} {_text(order_type)} {_text(remark)}"
    vehicle = _vehicle_bucket(vehicle_type, seat_count)
    if not vehicle:
        return None

    has_osaka = bool(OSAKA_PATTERN.search(endpoints))
    tariff_key = None
    if has_osaka and CHARTER_PATTERN.search(context) and TEN_HOUR_PATTERN.search(context):
        tariff_key = "osaka_10h_charter"
    elif has_osaka and KIX_PATTERN.search(endpoints):
        tariff_key = "osaka_kix"
    elif has_osaka and KYOTO_PATTERN.search(endpoints):
        tariff_key = "kyoto_osaka"
    elif has_osaka and KOBE_NARA_PATTERN.search(endpoints):
        tariff_key = "osaka_kobe_nara"
    if not tariff_key:
        return None

    tariff = ROUTE_TARIFFS[tariff_key]
    return {
        "key": tariff_key,
        "label": tariff["label"],
        "vehicle": vehicle,
        "amount": int(tariff[vehicle]),
    }


def _vehicle_bucket(vehicle_type: Any, seat_count: Any = None) -> str:
    text = _text(vehicle_type)
    if re.search(r"HiAce|Hiyace|ハイエース|海狮|海獅|10\s*座", text, re.I):
        return "hiace"
    if re.search(r"Alphard|アルファード|阿尔法|阿爾法|3\s*代|7\s*座", text, re.I):
        return "alphard"
    try:
        seats = int(seat_count or 0)
    except (TypeError, ValueError):
        seats = 0
    if seats >= 9:
        return "hiace"
    if 1 <= seats <= 8:
        return "alphard"
    return ""


def _text(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()

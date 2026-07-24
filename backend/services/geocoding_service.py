from __future__ import annotations

import json
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any

from backend.services.location_service import clean_text


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TourFlowDispatch/1.0 (internal geocoding)"

FIXED_LOCATIONS: dict[str, tuple[float, float]] = {
    "KIX": (34.4347, 135.2440),
    "KIX-T1": (34.4340, 135.2438),
    "KIX-T2": (34.4273, 135.2307),
    "ITM": (34.7855, 135.4382),
    "UKB": (34.6320, 135.2239),
    "NRT": (35.7719, 140.3929),
    "HND": (35.5494, 139.7798),
}


def geocode_order_locations(payload: dict[str, Any]) -> dict[str, float | None]:
    pickup = _resolve_location(payload.get("pickup_location"))
    dropoff = _resolve_location(payload.get("dropoff_location"))
    return {
        "pickup_latitude": pickup[0] if pickup else None,
        "pickup_longitude": pickup[1] if pickup else None,
        "dropoff_latitude": dropoff[0] if dropoff else None,
        "dropoff_longitude": dropoff[1] if dropoff else None,
    }


def _resolve_location(value: Any) -> tuple[float, float] | None:
    text = clean_text(value)
    if not text:
        return None
    code = _normalize_fixed_code(text)
    if code:
        return FIXED_LOCATIONS.get(code)
    return _query_nominatim(text)


def _normalize_fixed_code(text: str) -> str | None:
    normalized = text.strip().upper()
    if normalized in FIXED_LOCATIONS:
        return normalized
    lowered = text.lower()
    if any(token in text for token in ["関西国際空港", "关西国际机场", "关西国际空港", "Kansai International Airport"]) or "kix" in lowered:
        if "t2" in lowered or "terminal 2" in lowered:
            return "KIX-T2"
        if "t1" in lowered or "terminal 1" in lowered:
            return "KIX-T1"
        return "KIX"
    if any(token in text for token in ["伊丹机场", "大阪伊丹机场", "大阪国际机场", "伊丹空港"]) or "itm" in lowered:
        return "ITM"
    if any(token in text for token in ["神户机场", "神戸空港"]) or "ukb" in lowered:
        return "UKB"
    if any(token in text for token in ["成田机场", "成田空港"]) or "nrt" in lowered:
        return "NRT"
    if any(token in text for token in ["羽田机场", "羽田空港"]) or "hnd" in lowered:
        return "HND"
    return None


@lru_cache(maxsize=512)
def _query_nominatim(query: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "jp",
            "accept-language": "ja,en",
        }
    )
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if not payload:
        return None
    first = payload[0]
    try:
        return float(first["lat"]), float(first["lon"])
    except Exception:
        return None

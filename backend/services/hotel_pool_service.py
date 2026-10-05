from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOTEL_ASSET_PATH = PROJECT_ROOT / "backend" / "assets" / "hotel_pools.json"
HOTEL_SOURCE_PATH = PROJECT_ROOT / "release" / "daitora_offline_documents_v14_kix_hotels_resources.html"
CITY_ALIASES = {
    "大阪": "大阪",
    "大阪市内": "大阪",
    "京都": "京都",
    "京都市内": "京都",
}


@lru_cache(maxsize=1)
def load_hotel_source() -> dict[str, Any]:
    """Load the server hotel pool, with the V0.14 HTML as a rollback fallback."""
    if HOTEL_ASSET_PATH.is_file():
        try:
            value = json.loads(HOTEL_ASSET_PATH.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("hotels"), list):
                return value
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    if not HOTEL_SOURCE_PATH.is_file():
        return {"source": "", "hotels": []}
    source = HOTEL_SOURCE_PATH.read_text(encoding="utf-8")
    marker = "const HOTEL_SOURCE ="
    start = source.find(marker)
    if start < 0:
        return {"source": "", "hotels": []}
    start += len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(source[start:].lstrip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"source": "", "hotels": []}
    return value if isinstance(value, dict) else {"source": "", "hotels": []}


def hotel_pool(city: str) -> list[dict[str, Any]]:
    canonical = CITY_ALIASES.get(str(city or "").strip(), str(city or "").strip())
    return [
        item
        for item in load_hotel_source().get("hotels", [])
        if isinstance(item, dict)
        and item.get("city") == canonical
        and bool(item.get("enabled"))
        and bool(item.get("pool"))
        and str(item.get("name") or "").strip()
    ]


def normalize_city_place(value: Any, stable_key: str) -> tuple[str, bool]:
    """Replace only an exact city alias with one enabled pool hotel.

    Selection is random-looking but stable for the same order key. The selected
    hotel is stored by the parser; the PDF adapter uses the same key as a safety
    net for older orders whose city alias has not yet been expanded.
    """
    text = str(value or "").strip()
    city = CITY_ALIASES.get(text)
    if not city:
        return text, False
    candidates = hotel_pool(city)
    if not candidates:
        return text, False
    digest = hashlib.sha256(f"{stable_key}|{city}".encode("utf-8")).digest()
    selected = candidates[int.from_bytes(digest[:8], "big") % len(candidates)]
    return str(selected["name"]).strip(), True

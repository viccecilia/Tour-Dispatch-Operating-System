from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

from backend.db.database import ORDER_COLUMNS, get_connection


FLIGHT_INFO_FIELDS = [
    "flight_number",
    "flight_date",
    "flight_airline",
    "flight_origin",
    "flight_destination",
    "flight_terminal",
    "flight_gate",
    "flight_status",
    "flight_scheduled_departure",
    "flight_scheduled_arrival",
    "flight_estimated_departure",
    "flight_estimated_arrival",
    "flight_actual_departure",
    "flight_actual_arrival",
    "flight_provider",
    "flight_last_checked_at",
    "flight_manual_note",
]

AIRLINE_PREFIXES = {
    "JL": "Japan Airlines",
    "JAL": "Japan Airlines",
    "NH": "All Nippon Airways",
    "ANA": "All Nippon Airways",
    "MM": "Peach Aviation",
    "GK": "Jetstar Japan",
    "ZG": "ZIPAIR",
    "KE": "Korean Air",
    "OZ": "Asiana Airlines",
    "BR": "EVA Air",
    "CI": "China Airlines",
    "CA": "Air China",
    "MU": "China Eastern Airlines",
    "CZ": "China Southern Airlines",
}

AIRPORT_ALIASES = {
    "KIX": ["kix", "kansai", "关西", "关空", "関西", "関空"],
    "ITM": ["itm", "itami", "伊丹"],
    "UKB": ["ukb", "kobe airport", "神户机场", "神戸空港"],
    "HND": ["hnd", "haneda", "羽田"],
    "NRT": ["nrt", "narita", "成田"],
    "NGO": ["ngo", "chubu", "centrair", "中部"],
}

OFFICIAL_SOURCE_URLS = {
    "KIX": "https://www.kansai-airport.or.jp/en/flight/search",
    "ITM": "https://www.osaka-airport.co.jp/en/flight/",
    "UKB": "https://www.kairport.co.jp/en/flight/",
    "HND": "https://tokyo-haneda.com/flight/index.html",
    "NRT": "https://www.narita-airport.jp/en/flight/",
    "JL": "https://www.fstatus.jal.co.jp/jal/flight/list?lang=en",
    "JAL": "https://www.fstatus.jal.co.jp/jal/flight/list?lang=en",
    "NH": "https://www.ana.co.jp/en/jp/guide/flight-status/",
    "ANA": "https://www.ana.co.jp/en/jp/guide/flight-status/",
}


def ensure_flight_info_schema() -> None:
    with get_connection() as conn:
        _ensure_flight_info_schema_conn(conn)
        conn.commit()


def _ensure_flight_info_schema_conn(conn) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
    for column in FLIGHT_INFO_FIELDS:
        if column not in existing:
            definition = ORDER_COLUMNS.get(column, "TEXT")
            conn.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")


def query_flight_info(payload: dict[str, Any]) -> dict[str, Any]:
    flight_number = normalize_flight_number(payload.get("flight_number") or payload.get("number"))
    if not flight_number:
        raise ValueError("missing_flight_number")
    flight_date = _date_text(payload.get("flight_date") or payload.get("order_date")) or datetime.now().date().isoformat()
    route_text = " ".join(
        str(payload.get(key) or "")
        for key in ("pickup_location", "dropoff_location", "flight_origin", "flight_destination")
    )
    airport_code = _infer_airport_code(route_text)
    provider = (os.environ.get("WX_DISPATCH_FLIGHT_PROVIDER") or "").strip().lower()
    api_key = (os.environ.get("WX_DISPATCH_FLIGHT_API_KEY") or "").strip()

    # Real providers are deliberately gated until a provider and API key are confirmed.
    mode = "mock" if not provider or provider == "mock" or not api_key else "provider_pending"
    flight = _mock_flight(flight_number, flight_date, payload, airport_code)
    if mode == "provider_pending":
        flight["flight_manual_note"] = (
            f"已配置供应商 {provider}，但真实查询适配器尚未开启；当前仍返回本地模拟结果。"
        )
    flight["flight_provider"] = "local_mock" if mode == "mock" else f"{provider}:local_mock"
    flight["flight_last_checked_at"] = _now_text()
    return {
        "mode": mode,
        "flight": flight,
        "official_sources": official_sources_for_flight(flight_number, route_text),
    }


def build_flight_update(payload: dict[str, Any], order: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_flight_info_schema()
    source = payload.get("flight") if isinstance(payload.get("flight"), dict) else payload
    merged = {**(order or {}), **source}
    lookup = bool(payload.get("lookup") or payload.get("query"))
    if lookup:
        merged.update(query_flight_info(merged)["flight"])
    data = {field: _clean(merged.get(field)) for field in FLIGHT_INFO_FIELDS if field in merged}
    if data.get("flight_number"):
        data["flight_number"] = normalize_flight_number(data["flight_number"])
    if not data.get("flight_date"):
        data["flight_date"] = _date_text(merged.get("order_date"))
    if not data.get("flight_provider"):
        data["flight_provider"] = "manual"
    data["flight_last_checked_at"] = data.get("flight_last_checked_at") or _now_text()
    return {key: value for key, value in data.items() if value not in (None, "")}


def official_sources_for_flight(flight_number: str, route_text: str = "") -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    airline_code = _airline_code(flight_number)
    airport_code = _infer_airport_code(route_text)
    if airline_code and airline_code in OFFICIAL_SOURCE_URLS:
        sources.append({
            "label": f"{airline_code} airline flight status",
            "url": OFFICIAL_SOURCE_URLS[airline_code],
        })
    if airport_code and airport_code in OFFICIAL_SOURCE_URLS:
        sources.append({
            "label": f"{airport_code} airport flight search",
            "url": OFFICIAL_SOURCE_URLS[airport_code],
        })
    for code in ("KIX", "HND", "NRT"):
        if code != airport_code:
            sources.append({"label": f"{code} airport flight search", "url": OFFICIAL_SOURCE_URLS[code]})
    return sources[:4]


def normalize_flight_number(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", "", text)
    match = re.search(r"([A-Z]{2,3}\d{1,4}[A-Z]?)", text)
    return match.group(1) if match else text


def extract_flight_number(text: str) -> str:
    match = re.search(r"(?:航班|flight|便名)?\s*([A-Za-z]{2,3}\s?\d{2,4}[A-Za-z]?)", text or "", re.IGNORECASE)
    return normalize_flight_number(match.group(1)) if match else ""


def _mock_flight(flight_number: str, flight_date: str, payload: dict[str, Any], airport_code: str) -> dict[str, Any]:
    airline_code = _airline_code(flight_number)
    is_airport_pickup = _looks_like_airport_pickup(payload)
    base_time = _combine_datetime(flight_date, payload.get("start_time")) or datetime.now().replace(second=0, microsecond=0)
    if is_airport_pickup:
        scheduled_arrival = base_time
        scheduled_departure = base_time - timedelta(hours=2, minutes=15)
    else:
        scheduled_departure = base_time
        scheduled_arrival = base_time + timedelta(hours=2, minutes=15)
    status = _mock_status(scheduled_departure, scheduled_arrival)
    actual_departure = scheduled_departure if status in {"已经起飞", "已经落地"} else None
    actual_arrival = scheduled_arrival if status == "已经落地" else None
    return {
        "flight_number": flight_number,
        "flight_date": flight_date,
        "flight_airline": AIRLINE_PREFIXES.get(airline_code, airline_code or "未知航空"),
        "flight_origin": _clean(payload.get("flight_origin")) or ("HND" if airport_code != "HND" else "KIX"),
        "flight_destination": _clean(payload.get("flight_destination")) or airport_code or "KIX",
        "flight_terminal": _clean(payload.get("flight_terminal")) or _mock_terminal(airport_code, airline_code),
        "flight_gate": _clean(payload.get("flight_gate")),
        "flight_status": status,
        "flight_scheduled_departure": scheduled_departure.strftime("%Y-%m-%d %H:%M"),
        "flight_scheduled_arrival": scheduled_arrival.strftime("%Y-%m-%d %H:%M"),
        "flight_estimated_departure": scheduled_departure.strftime("%Y-%m-%d %H:%M"),
        "flight_estimated_arrival": scheduled_arrival.strftime("%Y-%m-%d %H:%M"),
        "flight_actual_departure": actual_departure.strftime("%Y-%m-%d %H:%M") if actual_departure else "",
        "flight_actual_arrival": actual_arrival.strftime("%Y-%m-%d %H:%M") if actual_arrival else "",
        "flight_manual_note": "本地模拟结果，仅用于 MVP 联动测试；实际运行请以航空公司或机场官网/API 为准。",
    }


def _mock_status(scheduled_departure: datetime, scheduled_arrival: datetime) -> str:
    now = datetime.now()
    if now < scheduled_departure:
        return "前方候机"
    if now < scheduled_arrival:
        return "已经起飞"
    return "已经落地"


def _mock_terminal(airport_code: str, airline_code: str) -> str:
    if airport_code == "NRT" and airline_code in {"JL", "JAL"}:
        return "T2"
    if airport_code == "NRT" and airline_code in {"NH", "ANA"}:
        return "T1"
    if airport_code in {"KIX", "HND"}:
        return "T1"
    return ""


def _looks_like_airport_pickup(payload: dict[str, Any]) -> bool:
    pickup = str(payload.get("pickup_location") or "").lower()
    dropoff = str(payload.get("dropoff_location") or "").lower()
    pickup_airport = bool(_infer_airport_code(pickup))
    dropoff_airport = bool(_infer_airport_code(dropoff))
    if pickup_airport and not dropoff_airport:
        return True
    if dropoff_airport and not pickup_airport:
        return False
    text = f"{payload.get('order_type') or ''} {pickup} {dropoff}".lower()
    return "pickup" in text or "接" in text


def _infer_airport_code(text: str) -> str:
    lower = (text or "").lower()
    for code, aliases in AIRPORT_ALIASES.items():
        if any(alias.lower() in lower for alias in aliases):
            return code
    return ""


def _airline_code(flight_number: str) -> str:
    match = re.match(r"([A-Z]{2,3})", flight_number or "")
    return match.group(1) if match else ""


def _combine_datetime(date_value: Any, time_value: Any) -> datetime | None:
    date_text = _date_text(date_value)
    time_text = str(time_value or "").strip()[:5]
    if not date_text or not re.match(r"^\d{1,2}:\d{2}$", time_text):
        return None
    try:
        return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("/", "-").replace(".", "-")
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", text):
        year, month, day = text.split("-")
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""

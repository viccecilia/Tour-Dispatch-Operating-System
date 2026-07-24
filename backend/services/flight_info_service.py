from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from html import unescape
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    "ITM": "https://www.osaka-airport.co.jp/en/flight/search",
    "UKB": "https://www.kairport.co.jp/en/flight/search",
    "HND": "https://tokyo-haneda.com/flight/index.html",
    "NRT": "https://www.narita-airport.jp/en/flight/",
    "JL": "https://www.fstatus.jal.co.jp/jal/flight/list?lang=en",
    "JAL": "https://www.fstatus.jal.co.jp/jal/flight/list?lang=en",
    "NH": "https://www.ana.co.jp/en/jp/guide/flight-status/",
    "ANA": "https://www.ana.co.jp/en/jp/guide/flight-status/",
}

OFFICIAL_AIRPORT_SEARCH_CODES = {"KIX", "ITM", "UKB"}
OFFICIAL_SEARCH_HEADERS = {
    "User-Agent": "TourFlow Flight Monitor/0.1 (+official airport search)",
    "Accept-Language": "en-US,en;q=0.9",
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

    mode = "mock"
    if provider in {"official", "official_web", "airport_web"}:
        try:
            flight = _query_official_airport_web(flight_number, flight_date, payload, airport_code)
            mode = "official_web_live"
        except Exception as exc:
            flight = _mock_flight(flight_number, flight_date, payload, airport_code)
            flight["flight_manual_note"] = f"官方机场页未查到实时结果，已回退本地模拟：{exc}"
            flight["flight_provider"] = "official_web:fallback_mock"
    elif provider == "aviationstack" and api_key:
        try:
            flight = _query_aviationstack(flight_number, flight_date, payload, airport_code, api_key)
            mode = "aviationstack_live"
        except Exception as exc:
            flight = _mock_flight(flight_number, flight_date, payload, airport_code)
            flight["flight_manual_note"] = f"Aviationstack 查询失败，已回退本地模拟：{exc}"
            flight["flight_provider"] = "aviationstack:fallback_mock"
    else:
        flight = _mock_flight(flight_number, flight_date, payload, airport_code)
    if not flight.get("flight_provider"):
        flight["flight_provider"] = "local_mock" if mode == "mock" else provider
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


def _query_official_airport_web(
    flight_number: str,
    flight_date: str,
    payload: dict[str, Any],
    airport_code: str,
) -> dict[str, Any]:
    target_airports = _official_airport_candidates(payload, airport_code)
    direction = "ARR" if _looks_like_airport_pickup(payload) else "DEP"
    date_tokens = _official_date_tokens(flight_date)
    if not date_tokens:
        raise ValueError("official_date_out_of_range")
    durations = _official_duration_slots(payload.get("start_time"))
    best_card: dict[str, Any] | None = None
    best_airport = ""
    best_date_token = ""
    best_update = ""
    for airport in target_airports:
        source_url = OFFICIAL_SOURCE_URLS.get(airport)
        if not source_url:
            continue
        for date_token in date_tokens:
            for duration in durations:
                html = _fetch_official_airport_html(
                    source_url,
                    {
                        "direction": direction,
                        "date": date_token,
                        "duration": duration,
                        "target": "all",
                    },
                )
                update_time = _extract_official_update_time(html)
                for card in _extract_official_flight_cards(html, source_url):
                    if not _card_matches_flight(card, flight_number):
                        continue
                    score = _score_official_card(card, airport, payload)
                    if not best_card or score > best_card.get("_score", -1):
                        card["_score"] = score
                        best_card = card
                        best_airport = airport
                        best_date_token = date_token
                        best_update = update_time
    if not best_card:
        raise ValueError("official_flight_not_found")
    return _map_official_card_to_flight(
        best_card,
        flight_number=flight_number,
        flight_date=flight_date,
        payload=payload,
        airport_code=best_airport or airport_code,
        direction=direction,
        date_token=best_date_token,
        update_time=best_update,
    )


def _official_airport_candidates(payload: dict[str, Any], airport_code: str) -> list[str]:
    candidates: list[str] = []
    for value in [
        airport_code,
        _infer_airport_code(str(payload.get("flight_origin") or "")),
        _infer_airport_code(str(payload.get("flight_destination") or "")),
        _infer_airport_code(str(payload.get("pickup_location") or "")),
        _infer_airport_code(str(payload.get("dropoff_location") or "")),
    ]:
        if value and value in OFFICIAL_AIRPORT_SEARCH_CODES and value not in candidates:
            candidates.append(value)
    for code in ("KIX", "ITM", "UKB"):
        if code not in candidates:
            candidates.append(code)
    return candidates


def _official_date_tokens(flight_date: str) -> list[str]:
    target = _parse_date_value(flight_date)
    if not target:
        return ["today"]
    today = datetime.now().date()
    delta = (target - today).days
    mapping = {0: "today", -1: "yesterday", 1: "tomorrow"}
    if delta in mapping:
        return [mapping[delta]]
    if delta < -1:
        return ["yesterday", "today"]
    if delta > 1:
        return ["today", "tomorrow"]
    return ["today"]


def _official_duration_slots(start_time: Any) -> list[str]:
    text = str(start_time or "").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if match:
        hour = max(0, min(23, int(match.group(1))))
        slots: list[str] = []
        for candidate in [hour - 1, hour, hour + 1]:
            if 0 <= candidate <= 23:
                slot = f"{candidate:02d}:00-{candidate + 1:02d}:00"
                if slot not in slots:
                    slots.append(slot)
        return slots
    return [f"{hour:02d}:00-{hour + 1:02d}:00" for hour in range(24)]


def _fetch_official_airport_html(base_url: str, params: dict[str, str]) -> str:
    url = f"{base_url}?{urlencode(params)}"
    request = Request(url, headers=OFFICIAL_SEARCH_HEADERS)
    with urlopen(request, timeout=18) as response:
        return response.read().decode("utf-8", "ignore")


def _extract_official_update_time(html: str) -> str:
    match = re.search(r'flight-list-date">\s*Update time:\s*<em>([^<]+)</em>', html, re.IGNORECASE)
    return _strip_html(match.group(1)) if match else ""


def _extract_official_flight_cards(html: str, source_url: str) -> list[dict[str, Any]]:
    marker = 'data-component-id="kix_ui:flight_item"'
    positions: list[int] = []
    start = 0
    while True:
        index = html.find(marker, start)
        if index < 0:
            break
        positions.append(index)
        start = index + len(marker)
    cards: list[dict[str, Any]] = []
    for idx, position in enumerate(positions):
        block_start = html.rfind("<div", 0, position)
        block_end = positions[idx + 1] if idx + 1 < len(positions) else html.find("</div>\n\n  </div>", position)
        if block_start < 0:
            continue
        if block_end < 0:
            block_end = min(len(html), position + 5000)
        block = html[block_start:block_end]
        number = _extract_first(block, r"<strong>\s*([A-Z0-9]+)\s*</strong>")
        if not number:
            continue
        airline_line = _extract_first(block, r'flight-card-port-code">\s*<strong>[^<]+</strong>\s*/\s*([^<]+)<')
        port_name = _extract_first(block, r'flight-card-port-name">([^<]+)<')
        terminal = _extract_first(block, r"Terminal:\s*<strong>([^<]+)</strong>")
        scheduled_time = _extract_first(block, r'flight-card-delay-time">([^<]+)<')
        current_time = _extract_first(block, r'flight-card-current-time">([^<]+)<')
        status = _extract_first(block, r'data-flight-state="[^"]+">([^<]+)<')
        detail_href = _extract_first(block, r'<a\s+href="([^"]+)"')
        shares = re.findall(r'flight-card-share">([^<]+)<', block, re.IGNORECASE)
        cards.append(
            {
                "flight_number": normalize_flight_number(number),
                "codeshares": [normalize_flight_number(item) for item in shares if normalize_flight_number(item)],
                "airline": _strip_html(airline_line),
                "port_name": _strip_html(port_name),
                "terminal": _strip_html(terminal),
                "scheduled_time": _strip_html(scheduled_time),
                "current_time": _strip_html(current_time),
                "status": _strip_html(status).upper(),
                "detail_url": _join_source_url(source_url, detail_href),
            }
        )
    return cards


def _card_matches_flight(card: dict[str, Any], flight_number: str) -> bool:
    target = normalize_flight_number(flight_number)
    if not target:
        return False
    if normalize_flight_number(card.get("flight_number")) == target:
        return True
    for codeshare in card.get("codeshares") or []:
        if normalize_flight_number(codeshare) == target:
            return True
    return False


def _score_official_card(card: dict[str, Any], airport_code: str, payload: dict[str, Any]) -> int:
    score = 0
    if airport_code:
        score += 3
    if card.get("terminal"):
        score += 1
    if card.get("current_time"):
        score += 1
    target_port = str(payload.get("flight_origin") or payload.get("flight_destination") or "").upper()
    port_name = str(card.get("port_name") or "").upper()
    if target_port and target_port in port_name:
        score += 2
    return score


def _map_official_card_to_flight(
    card: dict[str, Any],
    *,
    flight_number: str,
    flight_date: str,
    payload: dict[str, Any],
    airport_code: str,
    direction: str,
    date_token: str,
    update_time: str,
) -> dict[str, Any]:
    result = {
        "flight_number": normalize_flight_number(card.get("flight_number") or flight_number),
        "flight_date": _date_text(flight_date),
        "flight_airline": _clean(card.get("airline")) or AIRLINE_PREFIXES.get(_airline_code(flight_number), _airline_code(flight_number) or "未知航空"),
        "flight_terminal": _clean(card.get("terminal")),
        "flight_gate": "",
        "flight_status": _map_official_status(card.get("status")),
        "flight_provider": f"official:{airport_code.lower() or 'airport'}",
        "flight_manual_note": _build_official_manual_note(card, update_time),
    }
    if direction == "ARR":
        result["flight_origin"] = _clean(card.get("port_name")) or _clean(payload.get("flight_origin"))
        result["flight_destination"] = airport_code or _clean(payload.get("flight_destination")) or "KIX"
        result["flight_scheduled_arrival"] = _date_time_on(flight_date, card.get("scheduled_time"), date_token)
        current = _date_time_on(flight_date, card.get("current_time"), date_token)
        if _status_is_final_arrival(card.get("status")):
            result["flight_actual_arrival"] = current
            result["flight_estimated_arrival"] = current
        else:
            result["flight_estimated_arrival"] = current
    else:
        result["flight_origin"] = airport_code or _clean(payload.get("flight_origin")) or "KIX"
        result["flight_destination"] = _clean(card.get("port_name")) or _clean(payload.get("flight_destination"))
        result["flight_scheduled_departure"] = _date_time_on(flight_date, card.get("scheduled_time"), date_token)
        current = _date_time_on(flight_date, card.get("current_time"), date_token)
        if _status_is_final_departure(card.get("status")):
            result["flight_actual_departure"] = current
            result["flight_estimated_departure"] = current
        else:
            result["flight_estimated_departure"] = current
    return result


def _map_official_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    mapping = {
        "ARRIVED": "已落地",
        "LANDED": "已落地",
        "DELAYED": "延误",
        "CANCELLED": "已取消",
        "BOARDING": "登机中",
        "DEPARTED": "已起飞",
        "ON TIME": "正常",
        "SCHEDULED": "计划中",
    }
    return mapping.get(text, text or "待确认")


def _status_is_final_arrival(value: Any) -> bool:
    return str(value or "").strip().upper() in {"ARRIVED", "LANDED"}


def _status_is_final_departure(value: Any) -> bool:
    return str(value or "").strip().upper() in {"DEPARTED", "AIRBORNE", "BOARDING"}


def _build_official_manual_note(card: dict[str, Any], update_time: str) -> str:
    parts = []
    if update_time:
        parts.append(f"机场页更新时间 {update_time}")
    shares = [item for item in (card.get("codeshares") or []) if item]
    if shares:
        parts.append("共享航班 " + "/".join(shares))
    if card.get("detail_url"):
        parts.append(f"详情 {card['detail_url']}")
    return "；".join(parts)


def _extract_first(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return _strip_html(match.group(1)) if match else ""


def _strip_html(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _join_source_url(base_url: str, detail_href: str) -> str:
    if not detail_href:
        return ""
    if detail_href.startswith("http://") or detail_href.startswith("https://"):
        return detail_href
    match = re.match(r"^(https?://[^/]+)", base_url)
    root = match.group(1) if match else ""
    if detail_href.startswith("/") and root:
        return f"{root}{detail_href}"
    return detail_href


def _query_aviationstack(
    flight_number: str,
    flight_date: str,
    payload: dict[str, Any],
    airport_code: str,
    api_key: str,
) -> dict[str, Any]:
    params = {
        "access_key": api_key,
        "flight_iata": flight_number,
        "flight_date": flight_date,
        "limit": 10,
    }
    url = f"http://api.aviationstack.com/v1/flights?{urlencode(params)}"
    with urlopen(url, timeout=12) as response:
        body = json.loads(response.read().decode("utf-8"))
    if body.get("error"):
        info = body["error"]
        raise ValueError(info.get("message") or info.get("type") or "aviationstack_error")
    rows = body.get("data") or []
    best = _pick_aviationstack_flight(rows, flight_number, flight_date, payload, airport_code)
    if not best:
        raise ValueError("flight_not_found")
    return _map_aviationstack_flight(best, flight_number, flight_date, payload, airport_code)


def _pick_aviationstack_flight(
    rows: list[dict[str, Any]],
    flight_number: str,
    flight_date: str,
    payload: dict[str, Any],
    airport_code: str,
) -> dict[str, Any] | None:
    normalized_flight = normalize_flight_number(flight_number)
    expected_airport = airport_code or _infer_airport_code(
        f"{payload.get('pickup_location') or ''} {payload.get('dropoff_location') or ''} {payload.get('flight_origin') or ''} {payload.get('flight_destination') or ''}"
    )
    best_row: dict[str, Any] | None = None
    best_score = -1
    for row in rows:
        current_number = normalize_flight_number(_deep_get(row, "flight", "iata") or _deep_get(row, "flight", "icao") or "")
        if current_number and current_number != normalized_flight:
            continue
        score = 0
        if str(row.get("flight_date") or "") == flight_date:
            score += 3
        departure_iata = str(_deep_get(row, "departure", "iata") or "").upper()
        arrival_iata = str(_deep_get(row, "arrival", "iata") or "").upper()
        if expected_airport and expected_airport in {departure_iata, arrival_iata}:
            score += 2
        if _looks_like_airport_pickup(payload):
            if departure_iata == expected_airport:
                score += 1
        elif arrival_iata == expected_airport:
            score += 1
        if score > best_score:
            best_row = row
            best_score = score
    return best_row


def _map_aviationstack_flight(
    row: dict[str, Any],
    flight_number: str,
    flight_date: str,
    payload: dict[str, Any],
    airport_code: str,
) -> dict[str, Any]:
    departure = row.get("departure") or {}
    arrival = row.get("arrival") or {}
    airline = row.get("airline") or {}
    flight = row.get("flight") or {}
    live = row.get("live") or {}
    is_pickup = _looks_like_airport_pickup(payload)
    terminal_source = arrival if is_pickup else departure
    gate_source = arrival if is_pickup else departure
    departure_delay = _clean(departure.get("delay"))
    arrival_delay = _clean(arrival.get("delay"))
    provider_note = ""
    if departure_delay:
        provider_note = f"Departure delay {departure_delay} min"
    elif arrival_delay:
        provider_note = f"Arrival delay {arrival_delay} min"
    return {
        "flight_number": normalize_flight_number(_deep_get(flight, "iata") or flight_number),
        "flight_date": _date_text(row.get("flight_date")) or flight_date,
        "flight_airline": _clean(airline.get("name")) or AIRLINE_PREFIXES.get(_airline_code(flight_number), _airline_code(flight_number) or "未知航空"),
        "flight_origin": _clean(departure.get("iata")) or _clean(departure.get("airport")) or _clean(payload.get("flight_origin")) or ("HND" if airport_code != "HND" else "KIX"),
        "flight_destination": _clean(arrival.get("iata")) or _clean(arrival.get("airport")) or _clean(payload.get("flight_destination")) or airport_code or "KIX",
        "flight_terminal": _clean(terminal_source.get("terminal") or departure.get("terminal") or arrival.get("terminal")),
        "flight_gate": _clean(gate_source.get("gate") or departure.get("gate") or arrival.get("gate")),
        "flight_status": _map_aviationstack_status(row.get("flight_status")),
        "flight_scheduled_departure": _datetime_text(departure.get("scheduled")),
        "flight_scheduled_arrival": _datetime_text(arrival.get("scheduled")),
        "flight_estimated_departure": _datetime_text(departure.get("estimated") or departure.get("actual")),
        "flight_estimated_arrival": _datetime_text(arrival.get("estimated") or arrival.get("actual")),
        "flight_actual_departure": _datetime_text(departure.get("actual")),
        "flight_actual_arrival": _datetime_text(arrival.get("actual")),
        "flight_provider": "aviationstack",
        "flight_manual_note": provider_note or _clean(live.get("updated")) or "",
    }


def _map_aviationstack_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "scheduled": "计划中",
        "active": "飞行中",
        "landed": "已落地",
        "cancelled": "已取消",
        "incident": "异常",
        "diverted": "备降",
    }
    return mapping.get(text, str(value or "").strip() or "待确认")


def _deep_get(source: dict[str, Any], *keys: str) -> Any:
    current: Any = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def _parse_date_value(value: Any):
    text = _date_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
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


def _datetime_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized[:19], fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    match = re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", normalized)
    return match.group(0) if match else text[:16]


def _date_time_on(flight_date: str, time_value: Any, date_token: str = "today") -> str:
    time_text = str(time_value or "").strip()
    if not re.match(r"^\d{1,2}:\d{2}$", time_text):
        return ""
    target_date = _parse_date_value(flight_date) or datetime.now().date()
    if date_token == "yesterday":
        target_date = datetime.now().date() - timedelta(days=1)
    elif date_token == "tomorrow":
        target_date = datetime.now().date() + timedelta(days=1)
    return f"{target_date.isoformat()} {time_text}"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""

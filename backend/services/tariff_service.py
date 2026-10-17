from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from typing import Any

from backend.services.hotel_pool_service import load_hotel_source


TARIFF_RULE_VERSION = "daitora-auto-tariff-20261017-v4-hotel-pool-city"

# Recommendation rules only. Applying one never confirms company revenue or
# driver settlement; those remain explicit company-admin actions.
ROUTE_TARIFFS: dict[str, dict[str, Any]] = {
    "osaka_kix": {"label": "大阪市内 ↔ KIX", "hiace": 17000, "alphard": 11270},
    "osaka_kyoto": {"label": "大阪 → 京都", "hiace": 21000, "alphard": 19000},
    "osaka_kobe": {"label": "大阪 → 神戸", "hiace": 16000, "alphard": 14000},
    "osaka_nara": {"label": "大阪 → 奈良", "hiace": 16000, "alphard": 14000},
    "osaka_local": {"label": "大阪市内接送", "hiace": 8000, "alphard": 7000},
    "osaka_8h_charter": {"label": "大阪包車 8H", "hiace": 46310, "alphard": 41590},
    # Existing independently confirmed rule retained because V2 did not change it.
    "osaka_10h_charter": {"label": "大阪包車 10H", "hiace": 58390, "alphard": 52430},
    "kyoto_kix": {"label": "京都市内 ↔ KIX", "hiace": 18000, "alphard": 17000},
    # Confirmed airport-to-Kyoto transfer.  This is deliberately an explicit
    # ITM rule; it must not make every Osaka/Kyoto route bidirectional.
    "kyoto_itm": {"label": "ITM → 京都市内", "hiace": 15000, "alphard": 14000},
    "kyoto_local": {"label": "京都市内接送", "hiace": 13000, "alphard": 12000},
    "kyoto_osaka": {"label": "京都 → 大阪", "hiace": 15000, "alphard": 14000},
    "kyoto_nara": {"label": "京都 → 奈良", "hiace": 15000, "alphard": 14000},
    "kyoto_kobe": {"label": "京都 → 神戸", "hiace": 16000, "alphard": 15000},
    "kyoto_2h_charter": {"label": "京都包車 2H", "hiace": 13000, "alphard": 12000},
    "kyoto_4h_charter": {"label": "京都包車 4H", "hiace": 25600, "alphard": 23400},
    "kyoto_6h_charter": {"label": "京都包車 6H", "hiace": 38200, "alphard": 34800},
    "kyoto_8h_charter": {"label": "京都包車 8H", "hiace": None, "alphard": 46200},
    "kyoto_overtime_30m": {"label": "京都包車加時 30 分鐘", "hiace": None, "alphard": 2850},
}

OSAKA_PATTERN = re.compile(
    r"大阪|心斎橋|心斋桥|黒門|黑门|通天閣|通天阁|新大阪|梅田|難波|なんば|天王寺|"
    r"海遊館|海游馆|日本橋|日本桥|道頓堀|道顿堀|(?<![A-Z0-9])USJ(?![A-Z0-9])|ユニバーサル",
    re.I,
)
KIX_PATTERN = re.compile(
    r"(?<![A-Z0-9])KIX(?![A-Z0-9])|関西国際空港|関西空港|关西机场|關西機場|关空|關空|関空",
    re.I,
)
ITM_PATTERN = re.compile(
    r"(?<![A-Z0-9])ITM(?![A-Z0-9])|大阪国際空港|伊丹空港|伊丹机场|伊丹機場",
    re.I,
)
KYOTO_PATTERN = re.compile(r"京都|祇園|祗园|嵐山|岚山|伏見|伏见", re.I)
KOBE_PATTERN = re.compile(r"神戸|神户", re.I)
NARA_PATTERN = re.compile(r"奈良", re.I)
CHARTER_PATTERN = re.compile(r"包车|包車|貸切|日游|一日游|一日遊|charter", re.I)
OVERTIME_PATTERN = re.compile(r"加时|加時|延长|延長|超时|超時|overtime", re.I)


def resolve_vehicle_affiliation(
    vehicle_office: Any,
    plate_number: Any,
    permitted_business_area: Any = "",
) -> dict[str, Any]:
    """Resolve a pricing office without treating plate locality as a permit."""
    office_text = _text(vehicle_office)
    plate_text = _text(plate_number)
    explicit = _office_key(office_text)
    plate = _plate_office_key(plate_text)
    conflict = bool(explicit and plate and explicit != plate)
    office_key = explicit or plate
    if conflict:
        status = "conflict"
        message = f"車両台帳は{_office_label(explicit)}、車牌は{_office_label(plate)}を示しています。所属と許可資料を確認してください。"
    elif explicit:
        status = "vehicle_archive"
        message = "車両台帳の所属営業所を使用"
    elif plate:
        status = "plate_auxiliary"
        message = "車牌地域からの補助判定です。所属営業所と許可資料を確認してください。"
    else:
        status = "missing"
        message = "車両の所属営業所を判定できません"

    configured_area = _text(permitted_business_area)
    suggested_area = configured_area or {
        "osaka": "大阪市域交通圏",
        "kyoto": "京都市域交通圏",
    }.get(office_key, "")
    area_source = "vehicle_permit_archive" if configured_area else (
        "office_suggestion" if office_key else "missing"
    )
    return {
        "office_key": office_key,
        "office_label": _office_label(office_key),
        "office_source": "vehicle_archive" if explicit else ("plate_auxiliary" if plate else "missing"),
        "archive_office": office_text,
        "plate_office": _office_label(plate),
        "permitted_business_area": configured_area,
        "suggested_business_area": suggested_area,
        "business_area_source": area_source,
        "status": status,
        "requires_review": status in {"conflict", "plate_auxiliary", "missing"} or not configured_area,
        "message": message,
    }


def diagnose_route_fare(
    pickup_location: Any,
    dropoff_location: Any,
    order_type: Any,
    vehicle_type: Any,
    remark: Any = "",
    seat_count: Any = None,
    *,
    vehicle_office: Any = "",
    plate_number: Any = "",
    vehicle_type_code: Any = "",
    vehicle_group: Any = "",
    permitted_business_area: Any = "",
    pickup_source_text: Any = "",
    dropoff_source_text: Any = "",
    start_time: Any = "",
    end_time: Any = "",
    duration_minutes: Any = None,
    business_date: Any = "",
) -> dict[str, Any]:
    affiliation = resolve_vehicle_affiliation(vehicle_office, plate_number, permitted_business_area)
    vehicle = _vehicle_bucket(vehicle_type, seat_count, vehicle_type_code, vehicle_group)
    pickup_city = _endpoint_city(pickup_location, pickup_source_text)
    dropoff_city = _endpoint_city(dropoff_location, dropoff_source_text)
    context = " ".join(_text(value) for value in (order_type, remark) if _text(value))
    minutes = _duration_minutes(context, start_time, end_time, duration_minutes)
    category = _order_category(context, pickup_city, dropoff_city)
    rule_key = _match_rule(
        affiliation.get("office_key") or "",
        pickup_city,
        dropoff_city,
        category,
        minutes,
        context,
    )
    basis = {
        "business_date": _text(business_date),
        "office": affiliation.get("office_key") or "",
        "office_source": affiliation.get("office_source") or "",
        "plate_number": _text(plate_number),
        "vehicle": vehicle,
        "vehicle_type": _text(vehicle_type),
        "vehicle_type_code": _text(vehicle_type_code),
        "pickup_city": pickup_city,
        "dropoff_city": dropoff_city,
        "pickup_source_text": _text(pickup_source_text),
        "dropoff_source_text": _text(dropoff_source_text),
        "category": category,
        "duration_minutes": minutes,
    }
    diagnostic: dict[str, Any] = {
        "rule_version": TARIFF_RULE_VERSION,
        "matched": False,
        "key": rule_key or "",
        "label": "",
        "vehicle": vehicle,
        "amount": None,
        "order_category": category,
        "affiliation": affiliation,
        "match_basis": basis,
        "reason": "",
    }
    if not affiliation.get("office_key"):
        diagnostic["reason"] = "vehicle_office_unknown"
        diagnostic["area_assessment"] = assess_route_area(diagnostic)
        return diagnostic
    if not vehicle:
        diagnostic["reason"] = "vehicle_type_unknown"
        diagnostic["area_assessment"] = assess_route_area(diagnostic)
        return diagnostic
    if not rule_key:
        diagnostic["reason"] = "route_or_duration_not_configured"
        diagnostic["area_assessment"] = assess_route_area(diagnostic)
        return diagnostic
    tariff = ROUTE_TARIFFS[rule_key]
    amount = tariff.get(vehicle)
    diagnostic["label"] = str(tariff["label"])
    if amount is None:
        diagnostic["reason"] = "vehicle_price_not_configured"
        diagnostic["area_assessment"] = assess_route_area(diagnostic)
        return diagnostic
    diagnostic.update({"matched": True, "amount": int(amount), "reason": "matched"})
    diagnostic["area_assessment"] = assess_route_area(diagnostic)
    return diagnostic


def assess_route_area(diagnostic: dict[str, Any]) -> dict[str, Any]:
    """Return an operational check without asserting a legal permit.

    Vehicle archive/permit data remains the authority.  A configured tariff
    match is safe for automatic document checking; an unmatched route whose
    known endpoints both fall outside the vehicle's office is surfaced as a
    risk and never auto-confirmed.
    """
    affiliation = diagnostic.get("affiliation") or {}
    basis = diagnostic.get("match_basis") or {}
    office = str(basis.get("office") or "")
    pickup = str(basis.get("pickup_city") or "")
    dropoff = str(basis.get("dropoff_city") or "")
    if affiliation.get("requires_review"):
        return {
            "status": "needs_review",
            "label": "营业所／许可资料待核对",
            "reason": str(affiliation.get("message") or "vehicle_affiliation_requires_review"),
        }
    if diagnostic.get("matched"):
        return {
            "status": "passed",
            "label": "营业区域自动核对通过",
            "reason": str(diagnostic.get("key") or "matched_tariff_rule"),
        }
    if office and pickup and dropoff and office not in {pickup, dropoff}:
        return {
            "status": "risk",
            "label": "营业区域风险",
            "reason": f"{pickup}_to_{dropoff}_outside_{office}_office",
        }
    return {
        "status": "needs_review",
        "label": "营业区域待核对",
        "reason": str(diagnostic.get("reason") or "route_not_configured"),
    }


def recommend_route_fare(
    pickup_location: Any,
    dropoff_location: Any,
    order_type: Any,
    vehicle_type: Any,
    remark: Any = "",
    seat_count: Any = None,
    **context: Any,
) -> dict[str, Any] | None:
    """Return a traceable recommendation without changing stored order data."""
    diagnostic = diagnose_route_fare(
        pickup_location,
        dropoff_location,
        order_type,
        vehicle_type,
        remark,
        seat_count,
        **context,
    )
    return diagnostic if diagnostic["matched"] else None


def price_snapshot(
    diagnostic: dict[str, Any],
    effective_amount: Any,
    *,
    vehicle_id: Any,
) -> dict[str, Any]:
    try:
        effective = int(float(str(effective_amount).strip()))
    except (TypeError, ValueError):
        effective = None
    recommended = diagnostic.get("amount")
    source = "tariff_recommendation" if recommended is not None and effective == recommended else "manual_override"
    return {
        "source": source,
        "rule_version": diagnostic.get("rule_version") or TARIFF_RULE_VERSION,
        "rule_key": diagnostic.get("key") or "",
        "rule_label": diagnostic.get("label") or "",
        "recommended_total_jpy": recommended,
        "effective_total_jpy": effective,
        "vehicle_id": int(vehicle_id or 0) or None,
        "match_basis": diagnostic.get("match_basis") or {},
        "affiliation": diagnostic.get("affiliation") or {},
        "matched": bool(diagnostic.get("matched")),
        "reason": diagnostic.get("reason") or "",
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "financially_confirmed": False,
    }


def _match_rule(
    office: str,
    pickup_city: str,
    dropoff_city: str,
    category: str,
    minutes: int | None,
    context: str,
) -> str | None:
    if category == "charter":
        if office == "osaka" and minutes in {480, 600}:
            return f"osaka_{minutes // 60}h_charter"
        if office == "kyoto":
            if OVERTIME_PATTERN.search(context) and minutes == 30:
                return "kyoto_overtime_30m"
            if minutes in {120, 240, 360, 480}:
                return f"kyoto_{minutes // 60}h_charter"
        return None

    if office == "osaka":
        if {pickup_city, dropoff_city} == {"osaka", "kix"}:
            return "osaka_kix"
        if pickup_city == "osaka" and dropoff_city in {"kyoto", "kobe", "nara"}:
            return f"osaka_{dropoff_city}"
        if pickup_city == dropoff_city == "osaka":
            return "osaka_local"
    if office == "kyoto":
        if {pickup_city, dropoff_city} == {"kyoto", "kix"}:
            return "kyoto_kix"
        if pickup_city == "itm" and dropoff_city == "kyoto":
            return "kyoto_itm"
        if pickup_city == "kyoto" and dropoff_city in {"osaka", "kobe", "nara"}:
            return f"kyoto_{dropoff_city}"
        if pickup_city == dropoff_city == "kyoto":
            return "kyoto_local"
    return None


def _order_category(context: str, pickup_city: str, dropoff_city: str) -> str:
    if CHARTER_PATTERN.search(context):
        return "charter"
    if {"kix", "itm"} & {pickup_city, dropoff_city}:
        return "kix_transfer"
    if pickup_city and pickup_city == dropoff_city:
        return "local_transfer"
    if pickup_city and dropoff_city:
        return "intercity_transfer"
    return "unknown"


def _endpoint_city(location: Any, source_text: Any = "") -> str:
    # Source text is retained after a generic city is replaced by a stable
    # hotel, so inspect it first instead of relying on the hotel name.
    text = " ".join(part for part in (_text(source_text), _text(location)) if part)
    if KIX_PATTERN.search(text):
        return "kix"
    if ITM_PATTERN.search(text):
        return "itm"
    if OSAKA_PATTERN.search(text):
        return "osaka"
    if KYOTO_PATTERN.search(text):
        return "kyoto"
    if KOBE_PATTERN.search(text):
        return "kobe"
    if NARA_PATTERN.search(text):
        return "nara"
    hotel_city = _hotel_pool_city(location)
    if hotel_city:
        return hotel_city
    return ""


@lru_cache(maxsize=1)
def _hotel_city_index() -> tuple[tuple[str, str], ...]:
    city_keys = {"大阪": "osaka", "京都": "kyoto", "奈良": "nara", "神戸": "kobe"}
    values: list[tuple[str, str]] = []
    for item in load_hotel_source().get("hotels", []):
        if not isinstance(item, dict) or not item.get("enabled"):
            continue
        city = city_keys.get(_text(item.get("city")))
        name = _place_match_key(item.get("name"))
        if city and name:
            values.append((name, city))
    return tuple(values)


def _hotel_pool_city(location: Any) -> str:
    """Resolve concrete hotels through the existing verified hotel pool."""
    target = _place_match_key(location)
    if len(target) < 4:
        return ""
    for hotel_name, city in _hotel_city_index():
        if target == hotel_name:
            return city
        if min(len(target), len(hotel_name)) >= 8 and (target in hotel_name or hotel_name in target):
            return city
    return ""


def _place_match_key(value: Any) -> str:
    return re.sub(r"[\s\u3000\-\u30fb·〈〉()\uff08\uff09]", "", _text(value)).lower()


def _duration_minutes(context: str, start_time: Any, end_time: Any, explicit: Any) -> int | None:
    try:
        if explicit not in (None, ""):
            return int(explicit)
    except (TypeError, ValueError):
        pass
    normalized = _text(context)
    minute_match = re.search(r"(?<!\d)(30)\s*(?:M|MIN|分钟|分鐘|分)(?!\w)", normalized, re.I)
    if minute_match:
        return 30
    hour_match = re.search(r"(?<!\d)(2|4|6|8|10)\s*(?:H|HR|HOURS?|小时|小時|時間)(?!\w)", normalized, re.I)
    if hour_match:
        return int(hour_match.group(1)) * 60
    try:
        start = datetime.strptime(_text(start_time), "%H:%M")
        end = datetime.strptime(_text(end_time), "%H:%M")
    except ValueError:
        return None
    minutes = int((end - start).total_seconds() // 60)
    if minutes < 0:
        minutes += 24 * 60
    return minutes or None


def _vehicle_bucket(
    vehicle_type: Any,
    seat_count: Any = None,
    vehicle_type_code: Any = "",
    vehicle_group: Any = "",
) -> str:
    # Numeric seat count alone is not a confirmed model. It is retained in the
    # signature for compatibility and diagnostics only.
    del seat_count
    text = " ".join(_text(value) for value in (vehicle_type_code, vehicle_type, vehicle_group) if _text(value))
    if re.search(r"(?:^|\W)H(?:$|\W)|HiAce|Hiyace|ハイエース|海狮|海獅|10\s*座", text, re.I):
        return "hiace"
    if re.search(r"(?:^|\W)A(?:$|\W)|Alphard|Vellfire|アルファード|ヴェルファイア|阿尔法|阿爾法|3\s*代|7\s*座", text, re.I):
        return "alphard"
    return ""


def _office_key(value: str) -> str:
    if re.search(r"京都", value, re.I):
        return "kyoto"
    if re.search(r"大阪|なにわ", value, re.I):
        return "osaka"
    return ""


def _plate_office_key(value: str) -> str:
    if re.search(r"京都", value, re.I):
        return "kyoto"
    if re.search(r"大阪|なにわ", value, re.I):
        return "osaka"
    return ""


def _office_label(value: str) -> str:
    return {"osaka": "大阪営業所", "kyoto": "京都営業所"}.get(value, "")


def _text(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend.services.hotel_pool_service import normalize_city_place


DOCUMENT_MODEL_VERSION = "v014-phase2a-1"
AIRPORT_APPLICANTS = ("C-Trip", "KKday", "Klook", "WEBSITE")
SAFETY_DEFAULTS = {
    "waiting_place": "空港指定待機場所",
    "attention_place": "空港周辺及び観光地周辺",
    "other_instruction": "全乗員のシートベルト着用を確認してから発車すること。",
}
AIRPORT_PATTERNS = (
    ("KIX", re.compile(r"(?:\bKIX\b|関西国際空港|関西空港|关西国际机场|關西國際機場|关西机场|關西機場|关空|關空|関空)", re.I)),
    ("ITM", re.compile(r"(?:\bITM\b|大阪国際空港(?:（伊丹）)?|大阪国际机场|大阪國際機場|伊丹空港|伊丹机场|伊丹機場)", re.I)),
    ("UKB", re.compile(r"(?:\bUKB\b|神戸空港|神户机场|神戶機場)", re.I)),
)
CONTACT_CHANNEL_PATTERN = re.compile(
    r"(?:[\s,，/／|｜·・;；]*(?:WeChat|微信|LINE|WhatsApp|Kakao)(?:\s*[:：]\s*[^\s,，/／|｜;；]+)?)",
    re.I,
)
PUBLISHABLE_LIFECYCLE_STATUSES = {"draft", "generated", "reviewed", "published", "superseded", "revoked"}


ROUTE_NODE_CONTRACT = {
    "required": (
        "route_node_id", "run_group_id", "document_version_id", "driver_id", "vehicle_id",
        "business_date", "sequence_number", "node_type",
    ),
    "node_types": ("garage_out", "pickup", "via", "dropoff", "wait", "rest", "garage_in"),
    "planned_only": ("planned_location", "planned_arrival_at", "planned_departure_at", "load_status"),
}
ROUTE_NODE_ACTUAL_CONTRACT = {
    "required": ("route_node_id", "run_group_id", "driver_id", "vehicle_id", "business_date"),
    "actual_only": (
        "actual_arrival_at", "actual_departure_at", "odometer_km", "actual_location",
        "actual_node_status", "change_reason", "entered_by", "entered_at",
    ),
    "source_binding": ("source_document_version_id", "source_sha256"),
    "concurrency": ("revision", "client_request_id", "expected_revision"),
}
DAILY_INSPECTION_CONTRACT = {
    "required": ("inspection_id", "vehicle_id", "business_date", "driver_id", "run_group_id"),
    "fields": (
        "inspection_items", "inspection_result", "defects", "inspected_at", "submitted_by",
        "reviewed_by", "reviewed_at", "linked_daily_record_id",
    ),
    "separate_from": ("three_month_inspection", "statutory_vehicle_inspection"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: Any, length: int = 24) -> str:
    raw = "|".join(str(part if part is not None else "") for part in parts)
    return f"{prefix}-{sha256_text(raw)[:length]}"


def make_run_group_id(tenant_id: Any, business_date: Any, driver_id: Any, vehicle_id: Any) -> str:
    return stable_id("run", tenant_id, business_date, driver_id, vehicle_id)


def make_document_id(run_group_id: str) -> str:
    return stable_id("doc", run_group_id)


def make_document_version_id() -> str:
    return f"docv-{uuid.uuid4()}"


def normalize_airport_location(value: Any) -> str:
    """Normalize only explicit airport names while preserving terminal/meeting detail."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    if re.search(r"(?:ホテル|酒店|飯店|饭店|旅館|旅馆|\bhotel\b)", text, re.I):
        return text
    kix_match = re.match(
        r"^(?:KIX|関空|关空|關空|関西国際空港|関西空港|关西国际机场|關西國際機場|关西机场|關西機場|関西|关西|關西)"
        r"(?=$|[\s　Tt0-9第タ旅国集合到着出発])",
        text,
        re.I,
    )
    if kix_match:
        suffix = text[kix_match.end() :].strip(" 　,，/／-－")
        if suffix and not suffix.startswith(("T", "t", "第", "タ", "旅", "国", "集合", "到着", "出発")):
            return text
        return f"KIX {suffix}".strip()
    for code, pattern in AIRPORT_PATTERNS:
        match = pattern.search(text)
        if match:
            suffix = (text[: match.start()] + " " + text[match.end() :]).strip(" 　,，/／-－")
            return f"{code} {suffix}".strip()
    return text


def strip_contact_channels(value: Any) -> str:
    """Remove chat-channel annotations from a place without changing the source text."""
    return re.sub(r"\s+", " ", CONTACT_CHANNEL_PATTERN.sub("", str(value or ""))).strip(" ,，/／|｜·・;；")


def classify_order(order: dict[str, Any]) -> str:
    value = " ".join(
        str(order.get(key) or "")
        for key in ("order_type", "pickup_location", "dropoff_location", "remark", "fee_remark")
    )
    if re.search(r"(?:包车|包車|貸切|観光|fixed_tour)", value, re.I):
        return "charter"
    if any(pattern.search(value) for _, pattern in AIRPORT_PATTERNS) or re.search(r"(?:接机|接機|送机|送機|空港送迎)", value):
        return "airport_transfer"
    explicit = str(order.get("document_kind") or "").strip()
    if explicit in {"airport_transfer", "charter", "transfer"}:
        return explicit
    return "transfer"


def shift_date_time(date_value: Any, time_value: Any, minutes: int) -> dict[str, str]:
    date_text = str(date_value or "").strip()
    time_text = str(time_value or "").strip()
    try:
        base = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return {"date": date_text, "time": time_text, "at": ""}
    shifted = base + timedelta(minutes=minutes)
    return {
        "date": shifted.strftime("%Y-%m-%d"),
        "time": shifted.strftime("%H:%M"),
        "at": shifted.strftime("%Y-%m-%dT%H:%M:00"),
    }


def combine_date_time(date_value: Any, time_value: Any) -> str:
    shifted = shift_date_time(date_value, time_value, 0)
    return shifted["at"]


def default_applicant_slot(order: dict[str, Any]) -> int:
    stable_key = order.get("order_id") or order.get("id") or order.get("oid") or canonical_json(order)
    return int(sha256_text(str(stable_key))[:8], 16) % len(AIRPORT_APPLICANTS) + 1


def _legacy_daily_airport_arrival(order: dict[str, Any]) -> dict[str, str] | None:
    """Return the corrected arrival only for a provable, unpublished legacy +120m default."""
    if classify_order(order) != "airport_transfer" or not order.get("daily_import_group_key"):
        return None
    if str(order.get("end_time_source") or "") != "legacy_suggested_120m" or bool(order.get("end_time_confirmed")):
        return None
    if not order.get("order_date") or not order.get("start_time") or not order.get("end_time"):
        return None
    legacy = shift_date_time(order.get("order_date"), order.get("start_time"), 120)
    actual_end_date = str(order.get("end_date") or order.get("order_date") or "")
    if (actual_end_date, str(order.get("end_time") or "")) != (legacy["date"], legacy["time"]):
        return None
    return shift_date_time(order.get("order_date"), order.get("start_time"), 60)


def prepare_order_document_fields(
    conn: Any,
    group: dict[str, Any],
    *,
    repair_legacy_daily_defaults: bool = False,
) -> bool:
    """Persist defaults once. It never marks a location, applicant or price as confirmed."""
    changed = False
    for order in group.get("orders") or []:
        order_id = int(order.get("order_id") or order.get("id") or 0)
        if not order_id:
            continue
        kind = classify_order(order)
        pickup = str(order.get("pickup_location") or "").strip()
        dropoff = str(order.get("dropoff_location") or "").strip()
        pickup_source = str(order.get("pickup_source_text") or pickup).strip()
        dropoff_source = str(order.get("dropoff_source_text") or dropoff).strip()
        parsed_pickup = str(order.get("pickup_parsed_location") or normalize_airport_location(strip_contact_channels(pickup))).strip()
        parsed_dropoff = str(order.get("dropoff_parsed_location") or normalize_airport_location(strip_contact_channels(dropoff))).strip()
        pickup_suggested = str(order.get("pickup_suggested_location") or "").strip()
        dropoff_suggested = str(order.get("dropoff_suggested_location") or "").strip()
        if kind != "charter" and not order.get("pickup_location_confirmed"):
            normalized, changed_location = normalize_city_place(parsed_pickup, f"order:{order_id}:pickup")
            pickup_suggested = pickup_suggested or (normalized if changed_location else "")
            if pickup_suggested and pickup_suggested != parsed_pickup:
                pickup = pickup_suggested
        if kind != "charter" and not order.get("dropoff_location_confirmed"):
            normalized, changed_location = normalize_city_place(parsed_dropoff, f"order:{order_id}:dropoff")
            dropoff_suggested = dropoff_suggested or (normalized if changed_location else "")
            if dropoff_suggested and dropoff_suggested != parsed_dropoff:
                dropoff = dropoff_suggested
        suggested_arrival = _legacy_daily_airport_arrival(order) if repair_legacy_daily_defaults else None
        repair_legacy_arrival = bool(suggested_arrival)
        if kind == "airport_transfer" and order.get("order_date") and order.get("start_time") and not order.get("end_time"):
            suggested_arrival = shift_date_time(order.get("order_date"), order.get("start_time"), 60)
        slot = order.get("applicant_slot")
        if kind == "airport_transfer" and str(slot or "") not in {"1", "2", "3", "4"}:
            slot = default_applicant_slot(order)
        price_snapshot = order.get("price_snapshot_json")
        if not price_snapshot and order.get("price") not in (None, ""):
            price_snapshot = canonical_json({
                "source": "legacy_order_price",
                "suggested_total_jpy": order.get("price"),
                "confirmed": False,
            })
        conn.execute(
            """
            UPDATE orders
            SET document_kind = ?,
                applicant_slot = CASE
                    WHEN ? = 'airport_transfer' AND applicant_slot BETWEEN 1 AND 4 THEN applicant_slot
                    WHEN ? = 'airport_transfer' THEN ?
                    ELSE applicant_slot
                END,
                pickup_source_text = COALESCE(pickup_source_text, ?),
                dropoff_source_text = COALESCE(dropoff_source_text, ?),
                pickup_parsed_location = COALESCE(pickup_parsed_location, ?),
                dropoff_parsed_location = COALESCE(dropoff_parsed_location, ?),
                pickup_suggested_location = COALESCE(pickup_suggested_location, ?),
                dropoff_suggested_location = COALESCE(dropoff_suggested_location, ?),
                pickup_location = CASE WHEN pickup_location_confirmed = 0 AND ? <> '' THEN ? ELSE pickup_location END,
                dropoff_location = CASE WHEN dropoff_location_confirmed = 0 AND ? <> '' THEN ? ELSE dropoff_location END,
                end_date = CASE WHEN end_time IS NULL OR end_time = '' OR ? = 1 THEN COALESCE(?, end_date) ELSE end_date END,
                end_time = CASE WHEN end_time IS NULL OR end_time = '' OR ? = 1 THEN COALESCE(?, end_time) ELSE end_time END,
                end_time_source = CASE WHEN (end_time IS NULL OR end_time = '' OR ? = 1) AND ? IS NOT NULL THEN 'suggested_60m' ELSE end_time_source END,
                price_snapshot_json = COALESCE(price_snapshot_json, ?),
                updated_at = updated_at
            WHERE id = ? AND tenant_id = ?
            """,
            (
                kind, kind, kind, slot, pickup_source, dropoff_source, parsed_pickup, parsed_dropoff,
                pickup_suggested or None, dropoff_suggested or None,
                pickup_suggested, pickup_suggested, dropoff_suggested, dropoff_suggested,
                1 if repair_legacy_arrival else 0,
                suggested_arrival["date"] if suggested_arrival else None,
                1 if repair_legacy_arrival else 0,
                suggested_arrival["time"] if suggested_arrival else None,
                1 if repair_legacy_arrival else 0,
                suggested_arrival["time"] if suggested_arrival else None,
                price_snapshot,
                order_id, int(group.get("tenant_id") or 0),
            ),
        )
        order.update({
            "document_kind": kind,
            "applicant_slot": slot,
            "pickup_source_text": pickup_source,
            "dropoff_source_text": dropoff_source,
            "pickup_parsed_location": order.get("pickup_parsed_location") or parsed_pickup,
            "dropoff_parsed_location": order.get("dropoff_parsed_location") or parsed_dropoff,
            "pickup_suggested_location": pickup_suggested,
            "dropoff_suggested_location": dropoff_suggested,
            "pickup_location": pickup,
            "dropoff_location": dropoff,
            "end_date": suggested_arrival["date"] if suggested_arrival else order.get("end_date"),
            "end_time": suggested_arrival["time"] if suggested_arrival else order.get("end_time"),
            "end_time_source": "suggested_60m" if suggested_arrival else order.get("end_time_source"),
            "price_snapshot_json": price_snapshot,
        })
        changed = True
    return changed


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _order_snapshot(order: dict[str, Any]) -> dict[str, Any]:
    order_date = str(order.get("order_date") or "")
    pickup_time = str(order.get("start_time") or "")
    arrival = (
        {"date": str(order.get("end_date") or order_date), "time": str(order.get("end_time") or ""), "at": combine_date_time(order.get("end_date") or order_date, order.get("end_time"))}
        if order.get("end_time")
        else shift_date_time(order_date, pickup_time, 60)
    )
    kind = classify_order(order)
    slot = int(order.get("applicant_slot") or default_applicant_slot(order)) if kind == "airport_transfer" else None
    applicant_name = AIRPORT_APPLICANTS[slot - 1] if kind == "airport_transfer" and slot in (1, 2, 3, 4) else ""
    explicit_contract_party = str(order.get("agency_name") or "").strip()
    contract_party_name = explicit_contract_party or applicant_name
    end_time_source = str(order.get("end_time_source") or "")
    legacy_plus_120 = shift_date_time(order.get("order_date"), order.get("start_time"), 120) if order.get("order_date") and order.get("start_time") else None
    ambiguous_legacy_arrival = bool(
        kind == "airport_transfer"
        and order.get("daily_import_group_key")
        and not end_time_source
        and not bool(order.get("end_time_confirmed"))
        and legacy_plus_120
        and order.get("end_time")
        and (
            str(order.get("end_date") or order_date),
            str(order.get("end_time") or ""),
        ) == (legacy_plus_120["date"], legacy_plus_120["time"])
    )
    total_jpy = order.get("price")
    recommended_preview = False
    if total_jpy in (None, "") and order.get("daily_check_status") == "auto_passed":
        total_jpy = order.get("daily_effective_price")
        recommended_preview = total_jpy not in (None, "")
    price_snapshot_value = _json_object(order.get("price_snapshot_json"))
    if recommended_preview and not price_snapshot_value:
        price_snapshot_value = {
            "source": "recommended_preview",
            "rule_version": order.get("recommended_price_rule_version") or "",
            "rule_key": order.get("recommended_price_rule_key") or "",
            "match_basis": order.get("recommended_price_match_basis") or {},
        }
    fare_jpy = order.get("fare_jpy")
    if recommended_preview and fare_jpy in (None, ""):
        fare_jpy = total_jpy
    return {
        "order_id": int(order.get("order_id") or order.get("id") or 0),
        "oid": str(order.get("oid") or ""),
        "document_kind": kind,
        "business_date": order_date,
        "pickup_at": combine_date_time(order_date, pickup_time),
        "arrival_at": arrival["at"],
        "locations": {
            "pickup": {
                "raw": order.get("pickup_source_text") or order.get("pickup_location") or "",
                "parsed": order.get("pickup_parsed_location") or normalize_airport_location(order.get("pickup_location")),
                "suggested": order.get("pickup_suggested_location") or "",
                "confirmed": order.get("pickup_location") or "",
                "is_confirmed": bool(order.get("pickup_location_confirmed")),
            },
            "dropoff": {
                "raw": order.get("dropoff_source_text") or order.get("dropoff_location") or "",
                "parsed": order.get("dropoff_parsed_location") or normalize_airport_location(order.get("dropoff_location")),
                "suggested": order.get("dropoff_suggested_location") or "",
                "confirmed": order.get("dropoff_location") or "",
                "is_confirmed": bool(order.get("dropoff_location_confirmed")),
            },
        },
        "applicant_slot": slot,
        "applicant_slot_confirmed": bool(order.get("applicant_slot_confirmed")),
        "arrival_time_source": end_time_source,
        "arrival_time_confirmed": bool(order.get("end_time_confirmed")),
        "arrival_time_requires_review": ambiguous_legacy_arrival,
        "money": {
            "fare_jpy": fare_jpy,
            "service_fee_jpy": order.get("service_fee_jpy"),
            "advance_jpy": order.get("document_advance_jpy"),
            "toll_fee_jpy": order.get("toll_fee_jpy"),
            "parking_fee_jpy": order.get("parking_fee_jpy"),
            "total_jpy": total_jpy,
            "tax_included_confirmed": bool(order.get("tax_included_confirmed")),
            "price_confirmed": bool(order.get("price_confirmed")),
            "price_snapshot": price_snapshot_value,
        },
        "area_validation_status": str(order.get("area_validation_status") or "pending"),
        "run_confirmation_status": str(order.get("run_confirmation_status") or "pending"),
        "stopovers": list(order.get("printable_stopovers") or []),
        "agency_name": explicit_contract_party,
        "applicant_name": applicant_name if kind == "airport_transfer" else explicit_contract_party,
        "contract_party_name": contract_party_name,
        "contract_party_source": "agency_name" if explicit_contract_party else ("applicant_slot" if applicant_name else ""),
        "applicant_contact": order.get("guest_contact") or "",
    }


def _charter_days(
    order: dict[str, Any],
    snapshot_order: dict[str, Any],
    run_group_id: str,
) -> list[dict[str, Any]]:
    remark = _json_object(order.get("remark"))
    source = remark.get("fixed_tour") if isinstance(remark.get("fixed_tour"), dict) else remark
    raw_days = source.get("days") if isinstance(source, dict) else None
    if not isinstance(raw_days, list) or not raw_days:
        stops = source.get("stops") if isinstance(source, dict) else None
        raw_nodes = list(stops) if isinstance(stops, list) else []
        if not raw_nodes:
            raw_nodes = [
                {
                    "location": snapshot_order["locations"]["pickup"]["confirmed"],
                    "arrival_at": snapshot_order["pickup_at"],
                    "departure_at": snapshot_order["pickup_at"],
                },
                {
                    "location": snapshot_order["locations"]["dropoff"]["confirmed"],
                    "arrival_at": snapshot_order["arrival_at"],
                    "departure_at": snapshot_order["arrival_at"],
                },
            ]
        raw_days = [{"date": order.get("order_date"), "nodes": raw_nodes}]

    normalized_days: list[dict[str, Any]] = []
    last_day_index = len(raw_days) - 1
    order_id = snapshot_order["order_id"]
    for day_index, raw_day in enumerate(raw_days):
        day = raw_day if isinstance(raw_day, dict) else {}
        day_date = str(day.get("date") or shift_date_time(order.get("order_date"), "00:00", day_index * 1440)["date"])
        raw_nodes = day.get("nodes") if isinstance(day.get("nodes"), list) else []
        nodes: list[dict[str, Any]] = []
        last_node_index = len(raw_nodes) - 1
        for node_index, raw_node in enumerate(raw_nodes):
            node = raw_node if isinstance(raw_node, dict) else {"location": raw_node}
            location = str(node.get("location") or node.get("location_name") or node.get("planned_location") or "")
            arrival_at = str(node.get("arrival_at") or "") or combine_date_time(
                day_date, node.get("arrival_time") or node.get("default_arrival_time")
            )
            departure_at = str(node.get("departure_at") or "") or combine_date_time(
                day_date, node.get("departure_time") or node.get("default_departure_time")
            )
            node_type = str(node.get("node_type") or "")
            if node_type not in ROUTE_NODE_CONTRACT["node_types"]:
                if day_index == 0 and node_index == 0:
                    node_type = "pickup"
                elif day_index == last_day_index and node_index == last_node_index:
                    node_type = "dropoff"
                else:
                    node_type = "via"
            nodes.append({
                "route_node_id": str(node.get("route_node_id") or "").strip()
                or stable_id("node", run_group_id, order_id, "charter", day_index, node_index),
                "sequence_number": node_index + 1,
                "node_type": node_type,
                "location": location,
                "arrival_at": arrival_at,
                "departure_at": departure_at,
            })
        normalized_days.append({"date": day_date, "nodes": nodes})
    return normalized_days


def _route_nodes(
    group: dict[str, Any],
    snapshot_orders: list[dict[str, Any]],
    charter_contracts: list[dict[str, Any]],
    run_group_id: str,
    document_version_id: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    sequence = 1
    tenant_id = int(group.get("tenant_id") or 0)
    driver_id = int(group.get("driver_id") or 0)
    vehicle_id = int(group.get("vehicle_id") or 0)
    business_date = str(group.get("business_date") or "")
    first = snapshot_orders[0] if snapshot_orders else None
    last = snapshot_orders[-1] if snapshot_orders else None
    charter_by_order = {int(item["order_id"]): item for item in charter_contracts}

    def charter_boundary(item: dict[str, Any] | None, *, last_node: bool) -> str:
        if not item:
            return ""
        contract = charter_by_order.get(int(item["order_id"]))
        days = (contract or {}).get("days") or []
        if days:
            day = days[-1] if last_node else days[0]
            day_nodes = day.get("nodes") or []
            if day_nodes:
                node = day_nodes[-1] if last_node else day_nodes[0]
                candidate = str(
                    node.get("arrival_at" if last_node else "departure_at")
                    or node.get("departure_at" if last_node else "arrival_at")
                    or ""
                )
                if candidate:
                    return candidate
        return str(item.get("arrival_at" if last_node else "pickup_at") or "")

    first_at = charter_boundary(first, last_node=False)
    last_at = charter_boundary(last, last_node=True)
    garage = str(group.get("garage_location") or "車庫")
    garage_out_at = shift_date_time(first_at[:10] or business_date, first_at[11:16], -60)["at"] if first_at else ""
    if group.get("garage_out_time"):
        garage_out_at = combine_date_time(business_date, group.get("garage_out_time"))
    garage_in_at = shift_date_time(last_at[:10], last_at[11:16], 60)["at"] if last_at else ""
    if group.get("garage_in_time"):
        garage_in_at = combine_date_time(last_at[:10] or business_date, group.get("garage_in_time"))

    def append(
        node_type: str,
        order_id: int | None,
        location: str,
        arrival_at: str,
        departure_at: str,
        load_status: str,
        occurrence: Any = 0,
        *,
        node_id: str | None = None,
        node_date: str | None = None,
    ) -> None:
        nonlocal sequence
        nodes.append({
            "route_node_id": node_id or stable_id("node", run_group_id, order_id or 0, node_type, occurrence),
            "run_group_id": run_group_id,
            "document_version_id": document_version_id,
            "tenant_id": tenant_id,
            "driver_id": driver_id,
            "vehicle_id": vehicle_id,
            "business_date": node_date or business_date,
            "sequence_number": sequence,
            "order_id": order_id,
            "node_type": node_type,
            "planned_location": location,
            "planned_arrival_at": arrival_at,
            "planned_departure_at": departure_at,
            "load_status": load_status,
        })
        sequence += 1

    append(
        "garage_out", None, garage, "", garage_out_at, "empty",
        node_date=garage_out_at[:10] or business_date,
    )
    for item in snapshot_orders:
        order_id = item["order_id"]
        charter = charter_by_order.get(order_id)
        if charter:
            for day_index, day in enumerate(charter.get("days") or []):
                for node_index, node in enumerate(day.get("nodes") or []):
                    append(
                        node["node_type"], order_id, node["location"],
                        node["arrival_at"], node["departure_at"],
                        "boarding" if node["node_type"] == "pickup" else (
                            "alighting" if node["node_type"] == "dropoff" else "loaded"
                        ),
                        f"charter-{day_index}-{node_index}",
                        node_id=node["route_node_id"], node_date=day["date"],
                    )
            continue
        append("pickup", order_id, item["locations"]["pickup"]["confirmed"], item["pickup_at"], item["pickup_at"], "boarding")
        for via_index, place in enumerate(item.get("stopovers") or [], 1):
            append("via", order_id, str(place), "", "", "loaded", via_index)
        append("dropoff", order_id, item["locations"]["dropoff"]["confirmed"], item["arrival_at"], item["arrival_at"], "alighting")
    append(
        "garage_in", None, garage, garage_in_at, "", "empty",
        node_date=garage_in_at[:10] or business_date,
    )
    return nodes


def _apply_route_node_overrides(
    orders: list[dict[str, Any]],
    charter_contracts: list[dict[str, Any]],
    route_nodes: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> None:
    """Apply one persisted edit layer, then reflect it into both document views."""
    override_by_id = {str(item.get("route_node_id") or ""): item for item in overrides}
    for node in route_nodes:
        override = override_by_id.get(str(node.get("route_node_id") or ""))
        if not override:
            continue
        changed_fields = override.get("changed_fields")
        if not isinstance(changed_fields, list):
            changed_fields = _json_object(override.get("changed_fields_json")).get("fields") or []
        for field in ("planned_location", "planned_arrival_at", "planned_departure_at"):
            if field in changed_fields:
                node[field] = override.get(field) or ""
        node["location_confirmed"] = bool(override.get("location_confirmed"))

    order_by_id = {int(item.get("order_id") or 0): item for item in orders}
    for node in route_nodes:
        order = order_by_id.get(int(node.get("order_id") or 0))
        if not order:
            continue
        node_type = node.get("node_type")
        if node_type == "pickup":
            order["locations"]["pickup"]["confirmed"] = node.get("planned_location") or ""
            order["pickup_at"] = node.get("planned_departure_at") or node.get("planned_arrival_at") or ""
            if node.get("location_confirmed"):
                order["locations"]["pickup"]["is_confirmed"] = True
        elif node_type == "dropoff":
            order["locations"]["dropoff"]["confirmed"] = node.get("planned_location") or ""
            order["arrival_at"] = node.get("planned_arrival_at") or node.get("planned_departure_at") or ""
            if node.get("location_confirmed"):
                order["locations"]["dropoff"]["is_confirmed"] = True

    node_by_id = {str(node.get("route_node_id") or ""): node for node in route_nodes}
    for contract in charter_contracts:
        for day in contract.get("days") or []:
            for contract_node in day.get("nodes") or []:
                node = node_by_id.get(str(contract_node.get("route_node_id") or ""))
                if not node:
                    continue
                contract_node["location"] = node.get("planned_location") or ""
                contract_node["arrival_at"] = node.get("planned_arrival_at") or ""
                contract_node["departure_at"] = node.get("planned_departure_at") or ""


def build_document_snapshot(group: dict[str, Any], document_version_id: str | None = None) -> dict[str, Any]:
    tenant_id = int(group.get("tenant_id") or 0)
    business_date = str(group.get("business_date") or "")
    driver_id = int(group.get("driver_id") or 0)
    vehicle_id = int(group.get("vehicle_id") or 0)
    run_group_id = make_run_group_id(tenant_id, business_date, driver_id, vehicle_id)
    document_id = make_document_id(run_group_id)
    version_id = document_version_id or make_document_version_id()
    orders = [_order_snapshot(order) for order in group.get("orders") or []]
    airport_orders = [item for item in orders if item["document_kind"] == "airport_transfer"]
    charter_pairs = [
        (order, snapshot_order)
        for order, snapshot_order in zip(group.get("orders") or [], orders)
        if snapshot_order["document_kind"] == "charter"
    ]
    charter_contracts = [
        {
            "order_id": snapshot_order["order_id"],
            "passenger_pickup": snapshot_order["locations"]["pickup"]["confirmed"],
            "passenger_dropoff": snapshot_order["locations"]["dropoff"]["confirmed"],
            "operation_start_location": "車庫",
            "operation_end_location": "車庫",
            "days": _charter_days(order, snapshot_order, run_group_id),
        }
        for order, snapshot_order in charter_pairs
    ]
    route_nodes = _route_nodes(group, orders, charter_contracts, run_group_id, version_id)
    _apply_route_node_overrides(
        orders,
        charter_contracts,
        route_nodes,
        list(group.get("route_node_overrides") or []),
    )
    first_node = route_nodes[0] if route_nodes else {}
    last_node = route_nodes[-1] if route_nodes else {}
    field_overrides = group.get("document_field_overrides") or {}
    snapshot = {
        "schema_version": DOCUMENT_MODEL_VERSION,
        "document_id": document_id,
        "document_version_id": version_id,
        "run_group_id": run_group_id,
        "business_date": business_date,
        "driver": {
            "id": driver_id,
            # The formal document name belongs to the assignment's real driver.
            # Prefer the explicitly maintained print name, then fall back to the
            # driver archive name.  Never invent a placeholder for a legal PDF.
            "name": group.get("driver_print_name") or group.get("driver_name") or "",
            "office": group.get("driver_office") or "",
        },
        "vehicle": {
            "id": vehicle_id,
            "plate_number": group.get("plate_number") or "",
            "vehicle_type": group.get("vehicle_type") or "",
            "vehicle_type_code": group.get("vehicle_type_code") or "",
            "vehicle_group": group.get("vehicle_group") or "",
            "office": group.get("vehicle_office") or "",
            "permitted_business_area": group.get("vehicle_permitted_business_area") or "",
            "affiliation": group.get("vehicle_affiliation") or {},
        },
        "company": group.get("company") or {},
        "operations_manager": group.get("operations_manager") or (
            "朱英心" if "京都" in str(group.get("driver_office") or group.get("vehicle_office") or "") else "胡東鍇"
        ),
        "created_date": str(group.get("created_date") or business_date),
        "publication_status": "preview",
        "operation": {
            "start_location": first_node.get("planned_location") or "",
            "start_at": first_node.get("planned_departure_at") or "",
            "end_location": last_node.get("planned_location") or "",
            "end_at": last_node.get("planned_arrival_at") or "",
            "suggested": True,
        },
        "safety": {
            "waiting_place": field_overrides.get("operation:safety:waiting_place", group.get("safe_wait") or SAFETY_DEFAULTS["waiting_place"]),
            "attention_place": field_overrides.get("operation:safety:attention_place", group.get("safe_attention") or SAFETY_DEFAULTS["attention_place"]),
            "other_instruction": field_overrides.get("operation:safety:other_instruction", group.get("safe_other") or SAFETY_DEFAULTS["other_instruction"]),
        },
        "applicants": [{"slot": index + 1, "name": name, "contact": ""} for index, name in enumerate(AIRPORT_APPLICANTS)],
        "orders": orders,
        "airport_acceptance_pages": [airport_orders[index : index + 10] for index in range(0, len(airport_orders), 10)],
        "charter_contracts": charter_contracts,
        "route_nodes": route_nodes,
        "future_contracts": {
            "route_node": ROUTE_NODE_CONTRACT,
            "route_node_actual": ROUTE_NODE_ACTUAL_CONTRACT,
            "daily_inspection": DAILY_INSPECTION_CONTRACT,
        },
    }
    snapshot["publish_validation_issues"] = validate_document_snapshot(snapshot)
    snapshot["publish_ready"] = not snapshot["publish_validation_issues"]
    return snapshot


def validate_document_snapshot(snapshot: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    def require(value: Any, code: str) -> None:
        if value in (None, "", [], {}):
            issues.append(code)

    require(snapshot.get("driver", {}).get("id"), "driver_required")
    require(snapshot.get("driver", {}).get("name"), "driver_name_required")
    require(snapshot.get("vehicle", {}).get("id"), "vehicle_required")
    require(snapshot.get("vehicle", {}).get("plate_number"), "full_plate_number_required")
    require(snapshot.get("driver", {}).get("office"), "office_required")
    require(snapshot.get("operations_manager"), "operations_manager_required")
    for key in ("start_location", "start_at", "end_location", "end_at"):
        require(snapshot.get("operation", {}).get(key), f"operation_{key}_required")
    for key in ("waiting_place", "attention_place", "other_instruction"):
        require(snapshot.get("safety", {}).get(key), f"safe_{key}_required")
    for index, order in enumerate(snapshot.get("orders") or [], 1):
        prefix = f"order_{index}"
        require(order.get("pickup_at"), f"{prefix}_pickup_time_required")
        require(order.get("arrival_at"), f"{prefix}_arrival_time_required")
        if order.get("arrival_time_requires_review"):
            issues.append(f"{prefix}_arrival_time_source_confirmation_required")
        for side in ("pickup", "dropoff"):
            location = order.get("locations", {}).get(side, {})
            require(location.get("confirmed"), f"{prefix}_{side}_required")
            if not location.get("is_confirmed"):
                issues.append(f"{prefix}_{side}_confirmation_required")
        if order.get("run_confirmation_status") != "confirmed":
            issues.append(f"{prefix}_run_confirmation_required")
        if order.get("document_kind") == "airport_transfer":
            if order.get("applicant_slot") not in (1, 2, 3, 4):
                issues.append(f"{prefix}_applicant_slot_required")
            if not order.get("applicant_slot_confirmed"):
                issues.append(f"{prefix}_applicant_slot_confirmation_required")
        money = order.get("money") or {}
        require(money.get("total_jpy"), f"{prefix}_total_price_required")
        if not money.get("price_confirmed"):
            issues.append(f"{prefix}_price_confirmation_required")
        if not money.get("tax_included_confirmed"):
            issues.append(f"{prefix}_tax_confirmation_required")
        for key in ("fare_jpy", "service_fee_jpy", "advance_jpy"):
            if money.get(key) is None:
                issues.append(f"{prefix}_{key}_required")
        if order.get("area_validation_status") not in {"confirmed", "risk_acknowledged"}:
            issues.append(f"{prefix}_area_validation_required")
    return list(dict.fromkeys(issues))


def snapshot_sha256(snapshot: dict[str, Any]) -> str:
    return sha256_text(canonical_json(snapshot))


def snapshot_source_sha256(snapshot: dict[str, Any]) -> str:
    """Hash source content without per-generation version identifiers."""
    source = json.loads(canonical_json(snapshot))
    source.pop("document_version_id", None)
    for node in source.get("route_nodes") or []:
        node.pop("document_version_id", None)
    return sha256_text(canonical_json(source))


def upsert_document_batch(conn: Any, snapshot: dict[str, Any], status: str = "generated") -> None:
    conn.execute(
        """
        INSERT INTO dispatch_document_batches (
            tenant_id, document_id, run_group_id, business_date, driver_id, vehicle_id,
            status, current_document_version_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tenant_id, run_group_id) DO UPDATE SET
            status = excluded.status,
            current_document_version_id = excluded.current_document_version_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            snapshot["route_nodes"][0]["tenant_id"] if snapshot.get("route_nodes") else 0,
            snapshot["document_id"], snapshot["run_group_id"], snapshot["business_date"],
            snapshot["driver"]["id"], snapshot["vehicle"]["id"], status, snapshot["document_version_id"],
        ),
    )


def persist_route_nodes(conn: Any, snapshot: dict[str, Any]) -> None:
    for node in snapshot.get("route_nodes") or []:
        conn.execute(
            """
            INSERT OR REPLACE INTO dispatch_route_nodes (
                tenant_id, route_node_id, run_group_id, document_version_id, driver_id,
                vehicle_id, business_date, sequence_number, order_id, node_type,
                planned_location, planned_arrival_at, planned_departure_at, load_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(node.get(key) for key in (
                "tenant_id", "route_node_id", "run_group_id", "document_version_id", "driver_id",
                "vehicle_id", "business_date", "sequence_number", "order_id", "node_type",
                "planned_location", "planned_arrival_at", "planned_departure_at", "load_status",
            )),
        )


def record_document_event(conn: Any, snapshot: dict[str, Any], event_type: str, actor: dict[str, Any], event: dict[str, Any] | None = None) -> None:
    conn.execute(
        """
        INSERT INTO dispatch_document_events (
            tenant_id, document_id, document_version_id, event_type,
            actor_user_id, actor_role, actor_name, event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot["route_nodes"][0]["tenant_id"] if snapshot.get("route_nodes") else int(actor.get("tenant_id") or 0),
            snapshot["document_id"], snapshot.get("document_version_id"), event_type,
            int(actor.get("id") or 0) or None, actor.get("role"),
            actor.get("display_name") or actor.get("username"), canonical_json(event or {}),
        ),
    )


def future_data_contracts() -> dict[str, dict[str, Any]]:
    return {
        "route_node": ROUTE_NODE_CONTRACT,
        "route_node_actual": ROUTE_NODE_ACTUAL_CONTRACT,
        "daily_inspection": DAILY_INSPECTION_CONTRACT,
    }

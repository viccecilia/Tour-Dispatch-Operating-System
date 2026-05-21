import csv
import io
import json
import re
from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.location_service import (
    clean_text,
    extract_note_tokens,
    identify_vehicle_type,
    normalize_date_token,
    normalize_location_text,
    normalize_time_token,
)
from backend.services.order_service import create_order
from backend.services.order_number_service import build_order_oid, normalize_source_code, normalize_vehicle_type_code
from backend.services.tenant_context import get_current_tenant_id


DRAFT_FIELDS = [
    "oid",
    "raw_text",
    "source_type",
    "parse_status",
    "order_date",
    "end_date",
    "start_time",
    "end_time",
    "pickup_location",
    "dropoff_location",
    "order_type",
    "vehicle_type",
    "order_note_code",
    "order_source",
    "vehicle_class",
    "vehicle_type_code",
    "plate_short_code",
    "driver_code",
    "driver_language",
    "vehicle_color",
    "snow_tire",
    "passenger_count",
    "luggage_count",
    "guest_name",
    "guest_contact",
    "agency_name",
    "price",
    "price_rmb",
    "price_jpy",
    "fee_remark",
    "collection_amount_jpy",
    "parking_fee_jpy",
    "other_fee_jpy",
    "driver_salary_jpy",
    "remark",
    "parse_result_json",
]

EDITABLE_FIELDS = [
    "oid",
    "order_date",
    "end_date",
    "start_time",
    "end_time",
    "pickup_location",
    "dropoff_location",
    "order_type",
    "vehicle_type",
    "order_note_code",
    "order_source",
    "vehicle_class",
    "vehicle_type_code",
    "plate_short_code",
    "driver_code",
    "driver_language",
    "vehicle_color",
    "snow_tire",
    "passenger_count",
    "luggage_count",
    "guest_name",
    "guest_contact",
    "agency_name",
    "price",
    "price_rmb",
    "price_jpy",
    "fee_remark",
    "collection_amount_jpy",
    "parking_fee_jpy",
    "other_fee_jpy",
    "driver_salary_jpy",
    "remark",
    "parse_status",
]


def parse_text_to_draft(raw_text: str, source_type: str = "text") -> dict[str, Any]:
    raw_text = normalize_parser_input(raw_text)
    parsed = parse_chinese_order(raw_text)
    quality = analyze_parse_quality(raw_text, parsed)
    parse_status = "parsed" if _has_minimum_fields(parsed) else "failed"
    if not raw_text:
        parse_status = "failed"
    if parse_status == "failed":
        quality["confidence"] = min(float(quality["confidence"]), 0.35)
        quality["confidence_level"] = "low"
        quality["low_confidence"] = True
    parsed["raw_text"] = raw_text
    parsed["source_type"] = source_type
    parsed["parse_status"] = parse_status
    parsed["remark"] = _merge_remark(parsed.get("remark"), raw_text)
    parsed["parse_result_json"] = json.dumps(
        {
            "status": parse_status,
            "parsed": {key: value for key, value in parsed.items() if key != "parse_result_json"},
            "raw_text": raw_text,
            **quality,
            "manual_confirmation_required": True,
        },
        ensure_ascii=False,
    )
    return create_draft(parsed)


def parse_batch_text_to_drafts(raw_text: str, source_type: str = "text") -> list[dict[str, Any]]:
    """Split pasted operator text into order-sized lines and keep each raw line."""
    return [parse_text_to_draft(text, source_type) for text in split_batch_order_text(raw_text)]


def normalize_parser_input(raw_text: Any) -> str:
    text = clean_text(raw_text)
    if not text:
        return ""
    text = text.replace("=>", "->").replace("→", "->").replace("—", "-")
    text = re.sub(r"[【】]", " ", text)
    text = re.sub(r"\b(?:LINE|微信|Wechat|WeChat)\b[:：]?", " ", text, flags=re.IGNORECASE)
    lines = []
    for line in text.splitlines():
        line = _strip_chat_prefix(line)
        line = re.sub(r"^\s*[>｜|]+\s*", "", line)
        if line.strip():
            lines.append(line.strip())
    return clean_text("\n".join(lines))


def analyze_parse_quality(raw_text: str, parsed: dict[str, Any]) -> dict[str, Any]:
    important_fields = [
        "order_date",
        "start_time",
        "pickup_location",
        "dropoff_location",
        "order_type",
        "vehicle_type",
        "price",
    ]
    weights = {
        "order_date": 0.16,
        "start_time": 0.14,
        "pickup_location": 0.16,
        "dropoff_location": 0.16,
        "order_type": 0.12,
        "vehicle_type": 0.12,
        "price": 0.14,
    }
    missing = [field for field in important_fields if not parsed.get(field)]
    field_confidence = {
        field: _field_confidence(raw_text, field, parsed.get(field))
        for field in important_fields
    }
    confidence = sum(weights[field] * field_confidence[field] for field in important_fields)
    if not raw_text:
        confidence = 0
    elif len(raw_text) < 8:
        confidence = min(confidence, 0.4)
    warnings = []
    if missing:
        warnings.append("missing:" + ",".join(missing))
    if parsed.get("pickup_location") and parsed.get("pickup_location") == parsed.get("dropoff_location") and parsed.get("order_type") != "包车":
        warnings.append("same_pickup_dropoff")
        confidence -= 0.08
    if parsed.get("price") is None and re.search(r"\d{3,5}", raw_text):
        warnings.append("price_candidate_unconfirmed")
    confidence = round(max(0, min(confidence, 1)), 2)
    return {
        "confidence": confidence,
        "confidence_level": "high" if confidence >= 0.82 else "medium" if confidence >= 0.62 else "low",
        "low_confidence": confidence < 0.62,
        "field_confidence": field_confidence,
        "missing_fields": missing,
        "warnings": warnings,
        "diff_preview": _build_diff_preview(raw_text, parsed),
        "language": _detect_language(raw_text),
        "source_format": _detect_source_format(raw_text),
    }


def split_batch_order_text(raw_text: str) -> list[str]:
    text = normalize_parser_input(raw_text).replace("。", "。\n")
    text = re.sub(r"(?<!^)(?=(?:\[[^\]]+\]\s*)?(?:[^:\n：]{1,24}[:：]\s*)?\b\d{1,2}[./-]\d{1,2}\s)", "\n", text)
    text = re.sub(r"(?<!^)(?=(?:\[[^\]]+\]\s*)?(?:[^:\n：]{1,24}[:：]\s*)?\d{1,2}月\d{1,2}日?\s)", "\n", text)
    order_lines: list[str] = []
    customer_context: str | None = None
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            continue
        if _is_separator_or_caption(line):
            continue
        chunks = [chunk.strip() for chunk in re.split(r"(?<!^)(?=(?:\[[^\]]+\]\s*)?(?:[^:\n：]{1,24}[:：]\s*)?\b\d{1,2}[./-]\d{1,2}\s)", line) if chunk.strip()]
        for chunk in chunks:
            chunk = _strip_chat_prefix(chunk)
            if _looks_like_order_line(chunk):
                order_lines.append(_attach_customer_context(chunk, customer_context))
                continue
            if _looks_like_customer_line(chunk):
                customer_context = chunk.strip()
                continue
            if order_lines:
                order_lines[-1] = f"{order_lines[-1]} {chunk}".strip()
            else:
                order_lines.append(chunk)
    return [line for line in order_lines if line]


def parse_excel_to_drafts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        texts = [_row_to_text(row) for row in rows]
    else:
        csv_text = payload.get("csv") or payload.get("text") or payload.get("file_text") or ""
        texts = _csv_to_texts(csv_text)
    if not texts and str(payload.get("filename", "")).lower().endswith(".xlsx"):
        texts = [payload.get("raw_text") or "xlsx 文件入口已接收，请上传表格 rows 后解析"]
    return [parse_text_to_draft(text, "excel") for text in texts if clean_text(text)]


def parse_voice_to_draft(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("voice_text") or payload.get("text") or payload.get("mock_voice_text") or ""
    return parse_text_to_draft(text, "voice")


def list_drafts(status: str | None = None) -> list[dict[str, Any]]:
    sql = ["SELECT * FROM order_drafts WHERE tenant_id = ?"]
    params: list[Any] = [get_current_tenant_id()]
    if status:
        sql.append("AND parse_status = ?")
        params.append(status)
    sql.append("ORDER BY id DESC")
    with get_connection() as conn:
        return [_decode_draft(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def get_draft(draft_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM order_drafts WHERE id = ? AND tenant_id = ?", (_to_int(draft_id), get_current_tenant_id())).fetchone()
    return _decode_draft(row) if row else None


def update_draft(draft_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not get_draft(draft_id):
        return None
    data = {field: payload.get(field) for field in EDITABLE_FIELDS if field in payload}
    data = _normalize_numeric(data)
    if not data:
        return get_draft(draft_id)
    data["parse_result_json"] = json.dumps({"status": data.get("parse_status", "parsed"), "manual_update": data}, ensure_ascii=False)
    assignments = ", ".join(f"{field} = ?" for field in data)
    params = [data[field] for field in data]
    params.append(_to_int(draft_id))
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE order_drafts
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND tenant_id = ?
            """,
            [*params, get_current_tenant_id()],
        )
        conn.commit()
    return get_draft(draft_id)


def confirm_draft(draft_id: str) -> dict[str, Any] | None:
    draft = get_draft(draft_id)
    if not draft:
        return None
    if draft.get("confirmed_order_id"):
        return {"draft": draft, "order_id": draft["confirmed_order_id"], "already_confirmed": True}
    order = create_order(
        {
            "order_date": draft.get("order_date") or date.today().isoformat(),
            "end_date": draft.get("end_date") or draft.get("order_date") or date.today().isoformat(),
            "oid": draft.get("oid"),
            "start_time": draft.get("start_time"),
            "end_time": draft.get("end_time"),
            "pickup_location": draft.get("pickup_location") or "待确认起点",
            "dropoff_location": draft.get("dropoff_location") or "待确认终点",
            "order_type": draft.get("order_type"),
            "vehicle_type": draft.get("vehicle_type"),
            "order_note_code": draft.get("order_note_code"),
            "order_source": draft.get("order_source"),
            "vehicle_class": draft.get("vehicle_class"),
            "vehicle_type_code": draft.get("vehicle_type_code"),
            "plate_short_code": draft.get("plate_short_code"),
            "driver_code": draft.get("driver_code"),
            "driver_language": draft.get("driver_language"),
            "vehicle_color": draft.get("vehicle_color"),
            "snow_tire": draft.get("snow_tire"),
            "passenger_count": draft.get("passenger_count") or 0,
            "luggage_count": draft.get("luggage_count") or 0,
            "guest_name": draft.get("guest_name"),
            "guest_contact": draft.get("guest_contact"),
            "agency_name": draft.get("agency_name"),
            "price": draft.get("price"),
            "price_rmb": draft.get("price_rmb"),
            "price_jpy": draft.get("price_jpy"),
            "fee_remark": draft.get("fee_remark"),
            "collection_amount_jpy": draft.get("collection_amount_jpy"),
            "parking_fee_jpy": draft.get("parking_fee_jpy"),
            "other_fee_jpy": draft.get("other_fee_jpy"),
            "driver_salary_jpy": draft.get("driver_salary_jpy"),
            "remark": _merge_remark(draft.get("remark"), f"原始文本：{draft.get('raw_text') or ''}"),
            "dispatch_status": "unassigned",
            "settlement_status": "pending",
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE order_drafts
            SET parse_status = 'confirmed',
                confirmed_order_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND tenant_id = ?
            """,
            (order["id"], _to_int(draft_id), get_current_tenant_id()),
        )
        conn.commit()
    return {"draft": get_draft(draft_id), "order_id": order["id"], "order": order}


def discard_draft(draft_id: str) -> dict[str, Any] | None:
    draft = get_draft(draft_id)
    if not draft:
        return None
    remark = _merge_remark(draft.get("remark"), "草稿已废弃，原始文本保留。")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE order_drafts
            SET parse_status = 'failed',
                remark = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND tenant_id = ?
            """,
            (remark, _to_int(draft_id), get_current_tenant_id()),
        )
        conn.commit()
    return get_draft(draft_id)


def create_draft(data: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_numeric({field: data.get(field) for field in DRAFT_FIELDS if field in data})
    normalized["tenant_id"] = get_current_tenant_id()
    fields = list(normalized.keys())
    placeholders = ", ".join(["?"] * len(fields))
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO order_drafts ({', '.join(fields)}) VALUES ({placeholders})",
            [normalized[field] for field in fields],
        )
        draft_id = cursor.lastrowid
        oid = normalized.get("oid") or _build_draft_oid(conn, draft_id, normalized.get("order_date"))
        conn.execute(
            "UPDATE order_drafts SET oid = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (oid, draft_id),
        )
        conn.commit()
    draft = get_draft(str(draft_id))
    if not draft:
        raise ValueError("draft_create_failed")
    return draft


def parse_chinese_order(text: str) -> dict[str, Any]:
    raw = clean_text(text)
    parsed: dict[str, Any] = {}
    parsed["order_date"] = _extract_date(raw)
    parsed["end_date"] = parsed["order_date"]
    start_time, end_time = _extract_times(raw)
    parsed["start_time"] = start_time
    parsed["end_time"] = end_time
    with get_connection() as conn:
        pickup, dropoff, route_chain = _extract_route(conn, raw)
    parsed["pickup_location"] = pickup
    parsed["dropoff_location"] = dropoff
    parsed["order_type"] = _extract_order_type(raw)
    parsed["vehicle_type"] = identify_vehicle_type(raw)
    parsed["vehicle_class"] = parsed["vehicle_type"]
    parsed["vehicle_type_code"] = normalize_vehicle_type_code(parsed["vehicle_type"])
    parsed["order_note_code"] = _extract_order_note_code(raw)
    parsed["order_source"] = _extract_order_source(raw)
    parsed["vehicle_color"] = _extract_vehicle_color(raw)
    parsed["snow_tire"] = "雪" if "雪胎" in raw or re.search(r"\b雪\b", raw) else None
    parsed["passenger_count"] = _extract_count(raw, r"(\d+)\s*(?:人|位|名|客人)")
    parsed["luggage_count"] = _extract_count(raw, r"(\d+)\s*(?:箱|件行李|行李)")
    parsed["guest_name"] = _extract_guest_name(raw)
    parsed["guest_contact"] = _extract_phone(raw)
    parsed["agency_name"] = _extract_agency(raw)
    parsed["price"] = _extract_price(raw)
    parsed["price_rmb"] = parsed["price"]
    parsed["price_jpy"] = _extract_price_jpy(raw)
    parsed["collection_amount_jpy"] = _extract_fee(raw, r"代收\s*([0-9,]+)")
    parsed["parking_fee_jpy"] = _extract_fee(raw, r"停车费\s*([0-9,]+)")
    parsed["other_fee_jpy"] = _extract_other_fee(raw)
    notes, _ = extract_note_tokens(raw)
    parsed["fee_remark"] = "；".join(notes) if notes else None
    remark_parts = []
    if route_chain:
        remark_parts.append(f"路线链：{' -> '.join(route_chain)}")
    if notes:
        remark_parts.append("备注标签：" + "；".join(notes))
    remark_parts.append(raw)
    parsed["remark"] = "\n".join(remark_parts)
    return parsed


def _extract_order_note_code(text: str) -> str:
    match = re.search(r"订单备注代码[:：\s]*([DX])", text, re.IGNORECASE)
    if match:
        return normalize_source_code(match.group(1))
    if "老许" in text or "黄仁勋" in text:
        return "X"
    return "D"


def _is_separator_or_caption(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return True
    if set(compact) <= {"-", "—", "_", "=", "*"}:
        return True
    return compact in {"以上是包车订单", "以上是送迎订单", "包车订单", "送迎订单", "以上是包车订单。", "以上是送迎订单。"}


def _looks_like_order_line(text: str) -> bool:
    return bool(
        re.search(r"\b\d{1,2}[./-]\d{1,2}\b", text)
        or re.search(r"\d{1,2}月\d{1,2}日", text)
        or re.search(r"\b\d{6,8}\b", text)
    )


def _looks_like_customer_line(text: str) -> bool:
    if _looks_like_order_line(text):
        return False
    if any(token in text for token in ["包车", "接机", "送机", "接送", "单送", "往返", "机场", "酒店"]):
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fa5]", text)) and len(text) <= 40


def _attach_customer_context(order_text: str, customer_context: str | None) -> str:
    if not customer_context:
        return order_text
    if customer_context in order_text:
        return order_text
    return f"{order_text} 客户:{customer_context}"


def _strip_chat_prefix(text: str) -> str:
    value = clean_text(text)
    value = re.sub(r"^\s*\[[^\]]{1,30}\]\s*", "", value)
    value = re.sub(r"^\s*\d{1,2}[:：]\d{2}\s+", "", value)
    value = re.sub(r"^\s*[A-Za-z\u4e00-\u9fa5][A-Za-z0-9_\-\s\u4e00-\u9fa5]{0,22}\s+\d{1,2}[:：]\d{2}\s+", "", value)
    if not _looks_like_order_line(value):
        return value
    value = re.sub(r"^\s*[A-Za-z\u4e00-\u9fa5][A-Za-z0-9_\-\s\u4e00-\u9fa5]{0,22}[:：]\s*(?=\d{1,2}[./-]\d{1,2}|\d{1,2}月\d{1,2})", "", value)
    return value.strip()


def _extract_order_source(text: str) -> str | None:
    for label in ("大寅", "老许", "黄仁勋"):
        if label in text:
            return label
    return None


def _extract_vehicle_color(text: str) -> str | None:
    if "白" in text:
        return "白"
    if "黑" in text or "黒" in text:
        return "黑"
    return None


def _extract_date(text: str) -> str | None:
    if "今天" in text or "今日" in text:
        return date.today().isoformat()
    for pattern in [
        r"\b\d{8}\b",
        r"\b\d{6}\b",
        r"\b\d{4}[./\-年]\d{1,2}[./\-月]\d{1,2}日?\b",
        r"\b\d{1,2}[./\-月]\d{1,2}日?\b",
    ]:
        match = re.search(pattern, text)
        if match:
            normalized = normalize_date_token(match.group(0))
            if normalized:
                return normalized
    return None


def _extract_times(text: str) -> tuple[str | None, str | None]:
    work = re.sub(r"(?<!:)\b\d{1,2}[./\-月]\d{1,2}日?\b(?!:)", " ", text)
    work = re.sub(r"\b\d{6,8}\b", " ", work)
    matches = re.findall(r"\b(?:[01]?\d|2[0-3])[:：][0-5]\d\b", work)
    if not matches:
        work_no_notes = re.sub(r"（[^）]*）|\([^)]*\)", " ", work)
        for match in re.finditer(r"(?<![\d+*x×])(?:[01]\d|2[0-3])[0-5]\d(?![\dA-Za-z])", work_no_notes):
            before = work_no_notes[max(0, match.start() - 4) : match.start()]
            after = work_no_notes[match.end() : match.end() + 8]
            if any(token in before for token in ["座椅", "代收", "绿", "牌", "座"]):
                continue
            if any(token in after for token in ["日元", "円", "元"]):
                continue
            matches.append(match.group(0))
    if not matches:
        return None, None
    normalized = [normalize_time_token(match.replace("：", ":")) for match in matches]
    normalized = [item for item in normalized if item]
    if not normalized:
        return None, None
    return normalized[0], normalized[1] if len(normalized) > 1 else None


def _extract_route(conn, text: str) -> tuple[str | None, str | None, list[str]]:
    work = _strip_date_time_price(text)
    arrow_match = re.search(r"(.+?)\s*(?:->|→|到|至)\s*(.+)", work)
    if arrow_match:
        left = _clean_route_endpoint(arrow_match.group(1))
        right = _clean_route_endpoint(arrow_match.group(2))
        chain = [normalize_location_text(conn, left), normalize_location_text(conn, right)]
        return chain[0], chain[-1], chain

    chain = _extract_hyphen_route(conn, work)
    if len(chain) >= 2:
        return chain[0], chain[-1], chain

    for keyword in ("往返", "单送"):
        if keyword in work:
            left, right = work.split(keyword, 1)
            pickup = normalize_location_text(conn, _clean_route_endpoint(left))
            cleaned_right = _clean_route_endpoint(right)
            dropoff = normalize_location_text(conn, cleaned_right)
            if keyword == "往返" and (not cleaned_right or "接送" in right):
                dropoff = pickup
            return pickup or None, dropoff or None, [item for item in (pickup, dropoff) if item]

    match = re.search(r"(.{1,12}?)(接机|接送)(.{1,18})", work)
    if match:
        pickup = normalize_location_text(conn, _clean_route_endpoint(match.group(1)))
        dropoff = normalize_location_text(conn, _clean_route_endpoint(match.group(3)))
        return pickup or None, dropoff or None, [item for item in (pickup, dropoff) if item]

    match = re.search(r"(.{1,12}?)(送机)(.{1,18})", work)
    if match:
        pickup = normalize_location_text(conn, _clean_route_endpoint(match.group(1)))
        dropoff = normalize_location_text(conn, _clean_route_endpoint(match.group(3)))
        return pickup or None, dropoff or None, [item for item in (pickup, dropoff) if item]

    known = []
    for token in ["关西机场", "关西", "关空", "大阪市内", "大阪", "京都市内", "京都", "奈良", "宇治", "名古屋", "神户机场", "神户", "环球", "铃鹿", "大津", "胜尾寺", "美山", "龟岗", "龟冈", "新大阪"]:
        if token in work:
            loc = normalize_location_text(conn, token)
            if loc and loc not in known:
                known.append(loc)
    if len(known) >= 2:
        return known[0], known[-1], known
    if len(known) == 1:
        return known[0], None, known
    return None, None, []


def _extract_hyphen_route(conn, text: str) -> list[str]:
    route_text = re.sub(r"\s+", "", text)
    if "-" not in route_text:
        return []
    stop_at = re.search(r"(包车|接机|送机|接送|3代|10座|绿牌|绿|儿童座椅|￥|¥|\d{3,5})", route_text)
    if stop_at:
        route_text = route_text[: stop_at.start()]
    parts = [_clean_route_endpoint(part) for part in route_text.split("-")]
    chain = [normalize_location_text(conn, part) for part in parts if part]
    return [item for item in chain if item]


def _extract_order_type(text: str) -> str | None:
    if "包车" in text or "往返" in text:
        return "包车"
    if any(token in text for token in ["接机", "送机", "接送", "单送"]):
        return "送迎"
    return None


def _extract_count(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _extract_guest_name(text: str) -> str | None:
    match = re.search(r"([\u4e00-\u9fa5]{1,4}(?:先生|女士|小姐|太太))", text)
    if match:
        return match.group(1)
    ascii_tail = re.search(r"(?:\d{3,5}(?:\s*[+＋]\s*\d{3,5})?\s*(?:日元|円|jpy)?\s*)([A-Z][A-Za-z]+(?:[-\s][A-Z][A-Za-z]+){0,3})\s*$", text)
    if ascii_tail:
        return ascii_tail.group(1).strip()
    return None


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(?:\+?\d[\d -]{7,}\d)", text)
    return match.group(0).strip() if match else None


def _extract_agency(text: str) -> str | None:
    match = re.search(r"(?:旅行社|来源|社)[:：\s]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", text)
    return match.group(1) if match else None


def _extract_price(text: str) -> float | None:
    work = re.sub(r"\b\d{1,2}[./\-]\d{1,2}\b", " ", text)
    work = re.sub(r"\b(?:[01]?\d|2[0-3])[:：][0-5]\d\b", " ", work)
    candidates = []
    for match in re.finditer(r"(?:绿牌|绿|3代|10座|十座|海狮)\s*(\d{3,5})", work, re.IGNORECASE):
        candidates.append(int(match.group(1)))
    for match in re.finditer(r"(?<![\d*x×])(?:¥|￥)?\s*(\d{3,5})(?:\s*(?:元|日元|円|rmb|jpy))?", work, re.IGNORECASE):
        value = int(match.group(1))
        before = work[max(0, match.start() - 4) : match.start()]
        if "座椅" in before or "代收" in before:
            continue
        if value >= 300:
            candidates.append(value)
    return float(candidates[0]) if candidates else None


def _extract_price_jpy(text: str) -> float | None:
    match = re.search(r"(?:日元|円|JPY)\s*([0-9,]+)|([0-9,]+)\s*(?:日元|円|JPY)", text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    return float(value.replace(",", ""))


def _extract_fee(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _extract_other_fee(text: str) -> float | None:
    matches = re.findall(r"[+＋]\s*([0-9,]+)", text)
    if not matches:
        return None
    return float(sum(int(value.replace(",", "")) for value in matches))


def _strip_date_time_price(text: str) -> str:
    work = re.sub(r"\b\d{1,2}[./\-月]\d{1,2}日?\b", " ", text)
    work = re.sub(r"\b\d{6,8}\b", " ", work)
    work = re.sub(r"\b(?:[01]?\d|2[0-3])[:：.]?[0-5]\d\b", " ", work)
    work = re.sub(r"(?:¥|￥)?\d{3,5}(?:\s*(?:元|日元|円|rmb|jpy))?", " ", work, flags=re.IGNORECASE)
    work = re.sub(r"\s+", " ", work).strip()
    return work


def _clean_route_endpoint(value: str) -> str:
    value = clean_text(value)
    value = re.sub(r"^(以上是|包车订单|送迎订单|客户|客人|司机|导游|Ashwin Arora|Chris Lo)\s*", "", value, flags=re.IGNORECASE)
    value = re.split(r"(包车|送迎|接机|送机|接送|单送|3代|10座|绿牌|绿|儿童座椅|代收|备注|价格|[A-Z][A-Za-z]+)", value, maxsplit=1)[0]
    value = re.sub(r"\s+", "", value)
    return value.strip("- ")


def _has_minimum_fields(parsed: dict[str, Any]) -> bool:
    return bool(parsed.get("order_date") or parsed.get("start_time") or parsed.get("pickup_location") or parsed.get("dropoff_location"))


def _field_confidence(raw_text: str, field: str, value: Any) -> float:
    if value in ("", None):
        return 0.0
    text = raw_text.lower()
    if field == "order_date":
        return 0.95 if re.search(r"\d{1,4}[./\-年月]\d{1,2}", raw_text) or "今天" in raw_text or "今日" in raw_text else 0.65
    if field == "start_time":
        return 0.96 if re.search(r"\b(?:[01]?\d|2[0-3])[:：]?[0-5]\d\b", raw_text) else 0.62
    if field in {"pickup_location", "dropoff_location"}:
        return 0.9 if str(value) in raw_text or "->" in raw_text or "-" in raw_text or any(token in raw_text for token in ["接机", "送机", "单送", "往返"]) else 0.68
    if field == "order_type":
        return 0.95 if any(token in raw_text for token in ["包车", "接机", "送机", "接送", "单送", "往返"]) else 0.58
    if field == "vehicle_type":
        return 0.93 if any(token in text for token in ["3代", "三代", "10座", "十座", "alphard", "hiace", "海狮", "gl8"]) else 0.64
    if field == "price":
        return 0.9 if re.search(r"(?:¥|￥)?\s*\d{3,5}(?:\s*(?:元|円|日元|rmb|jpy))?", raw_text, re.IGNORECASE) else 0.55
    return 0.75


def _build_diff_preview(raw_text: str, parsed: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "order_date": "日期",
        "start_time": "开始时间",
        "end_time": "结束时间",
        "pickup_location": "起点",
        "dropoff_location": "终点",
        "order_type": "类型",
        "vehicle_type": "车型",
        "price": "价格",
        "guest_name": "客人",
        "guest_contact": "电话",
        "fee_remark": "费用备注",
    }
    return [
        {
            "field": field,
            "label": label,
            "parsed": parsed.get(field),
            "confidence": _field_confidence(raw_text, field, parsed.get(field)),
            "needs_review": parsed.get(field) in ("", None) or _field_confidence(raw_text, field, parsed.get(field)) < 0.7,
        }
        for field, label in labels.items()
    ]


def _detect_language(text: str) -> str:
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fa5]", text):
        return "zh"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "unknown"


def _detect_source_format(text: str) -> str:
    if re.search(r"^\s*\[[^\]]+\]", text, re.MULTILINE) or re.search(r"^[^:\n：]{1,24}[:：]\s*\d{1,2}[./-]\d{1,2}", text, re.MULTILINE):
        return "chat"
    if "," in text and "\n" in text:
        return "csv_like"
    return "plain_text"


def _merge_remark(left: Any, right: Any) -> str:
    parts = [str(value).strip() for value in (left, right) if str(value or "").strip()]
    return "\n".join(dict.fromkeys(parts))


def _normalize_numeric(data: dict[str, Any]) -> dict[str, Any]:
    for field in ("passenger_count", "luggage_count"):
        if field in data:
            data[field] = None if data[field] in ("", None) else int(data[field])
    for money_field in (
        "price",
        "price_rmb",
        "price_jpy",
        "collection_amount_jpy",
        "parking_fee_jpy",
        "other_fee_jpy",
        "driver_salary_jpy",
    ):
        if money_field in data:
            data[money_field] = None if data[money_field] in ("", None) else float(data[money_field])
    if "price" in data and "price_rmb" not in data and data.get("price") is not None:
        data["price_rmb"] = data["price"]
    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()
    return data


def _decode_draft(row) -> dict[str, Any]:
    draft = dict(row)
    raw = draft.get("parse_result_json")
    try:
        draft["parse_result"] = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        draft["parse_result"] = {}
    return draft


def _row_to_text(row: Any) -> str:
    if isinstance(row, dict):
        return " ".join(str(value) for value in row.values() if value not in ("", None))
    if isinstance(row, list):
        return " ".join(str(value) for value in row if value not in ("", None))
    return str(row)


def _csv_to_texts(csv_text: str) -> list[str]:
    if not csv_text.strip():
        return []
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return []
    return [" ".join(cell for cell in row if cell.strip()) for row in rows]


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_draft_oid(conn, draft_id: int, order_date: Any) -> str:
    resolved_date = str(order_date or date.today().isoformat())
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM order_drafts
        WHERE COALESCE(order_date, ?) = ?
          AND id <= ?
        """,
        (resolved_date, resolved_date, draft_id),
    ).fetchone()
    serial = int(row["count"] if row else 0) or draft_id
    draft = conn.execute(
        """
        SELECT order_note_code, order_source, vehicle_type, vehicle_type_code
        FROM order_drafts
        WHERE id = ?
        """,
        (draft_id,),
    ).fetchone()
    return build_order_oid(
        order_note_code=draft["order_note_code"] if draft else None,
        order_source=draft["order_source"] if draft else None,
        order_date=resolved_date,
        serial=serial,
        vehicle_type_code=draft["vehicle_type_code"] if draft else None,
        vehicle_type=draft["vehicle_type"] if draft else None,
        temporary=True,
    )

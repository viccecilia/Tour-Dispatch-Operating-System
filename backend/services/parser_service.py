import csv
import io
import json
import re
from datetime import date
from typing import Any

from backend.db.database import get_connection
from backend.services.order_service import create_order


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
    "passenger_count",
    "luggage_count",
    "guest_name",
    "guest_contact",
    "agency_name",
    "price",
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
    "passenger_count",
    "luggage_count",
    "guest_name",
    "guest_contact",
    "agency_name",
    "price",
    "remark",
    "parse_status",
]


def parse_text_to_draft(raw_text: str, source_type: str = "text") -> dict[str, Any]:
    raw_text = (raw_text or "").strip()
    parsed = parse_chinese_order(raw_text)
    parse_status = "parsed" if _has_minimum_fields(parsed) else "failed"
    if not raw_text:
        parse_status = "failed"
    parsed["raw_text"] = raw_text
    parsed["source_type"] = source_type
    parsed["parse_status"] = parse_status
    parsed["remark"] = _merge_remark(parsed.get("remark"), raw_text)
    parsed["parse_result_json"] = json.dumps(
        {"status": parse_status, "parsed": parsed, "raw_text": raw_text},
        ensure_ascii=False,
    )
    return create_draft(parsed)


def parse_excel_to_drafts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        texts = [_row_to_text(row) for row in rows]
    else:
        csv_text = payload.get("csv") or payload.get("text") or payload.get("file_text") or ""
        texts = _csv_to_texts(csv_text)
    if not texts and payload.get("filename", "").lower().endswith(".xlsx"):
        texts = [payload.get("raw_text") or "xlsx 文件入口已接收，需补充表格 rows 后解析"]
    return [parse_text_to_draft(text, "excel") for text in texts if text.strip()]


def parse_voice_to_draft(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("voice_text") or payload.get("text") or payload.get("mock_voice_text") or ""
    return parse_text_to_draft(text, "voice")


def list_drafts(status: str | None = None) -> list[dict[str, Any]]:
    sql = ["SELECT * FROM order_drafts"]
    params: list[Any] = []
    if status:
        sql.append("WHERE parse_status = ?")
        params.append(status)
    sql.append("ORDER BY id DESC")
    with get_connection() as conn:
        return [_decode_draft(row) for row in conn.execute(" ".join(sql), params).fetchall()]


def get_draft(draft_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM order_drafts WHERE id = ?", (_to_int(draft_id),)).fetchone()
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
            """,
            params,
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
            "pickup_location": draft.get("pickup_location") or "待补充起点",
            "dropoff_location": draft.get("dropoff_location") or "待补充终点",
            "order_type": draft.get("order_type"),
            "vehicle_type": draft.get("vehicle_type"),
            "passenger_count": draft.get("passenger_count") or 0,
            "luggage_count": draft.get("luggage_count") or 0,
            "guest_name": draft.get("guest_name"),
            "guest_contact": draft.get("guest_contact"),
            "agency_name": draft.get("agency_name"),
            "price": draft.get("price"),
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
            """,
            (order["id"], _to_int(draft_id)),
        )
        conn.commit()
    return {"draft": get_draft(draft_id), "order_id": order["id"], "order": order}


def discard_draft(draft_id: str) -> dict[str, Any] | None:
    draft = get_draft(draft_id)
    if not draft:
        return None
    remark = _merge_remark(draft.get("remark"), "草稿已作废，原始文本保留。")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE order_drafts
            SET parse_status = 'failed',
                remark = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (remark, _to_int(draft_id)),
        )
        conn.commit()
    return get_draft(draft_id)


def create_draft(data: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_numeric({field: data.get(field) for field in DRAFT_FIELDS if field in data})
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
    parsed: dict[str, Any] = {}
    parsed["order_date"] = _extract_date(text)
    parsed["end_date"] = parsed["order_date"]
    start_time, end_time = _extract_times(text)
    parsed["start_time"] = start_time
    parsed["end_time"] = end_time
    pickup, dropoff = _extract_route(text)
    parsed["pickup_location"] = pickup
    parsed["dropoff_location"] = dropoff
    parsed["order_type"] = _extract_order_type(text)
    parsed["vehicle_type"] = _extract_vehicle_type(text)
    parsed["passenger_count"] = _extract_count(text, r"(\d+)\s*(?:人|位|位客人|名)")
    parsed["luggage_count"] = _extract_count(text, r"(\d+)\s*(?:箱|件行李|件)")
    parsed["guest_name"] = _extract_guest_name(text)
    parsed["guest_contact"] = _extract_phone(text)
    parsed["agency_name"] = _extract_agency(text)
    parsed["price"] = _extract_price(text)
    parsed["remark"] = text
    return parsed


def _extract_date(text: str) -> str | None:
    current_year = date.today().year
    if "今天" in text or "今日" in text:
        return date.today().isoformat()
    match = re.search(r"(\d{1,2})[/-](\d{1,2})", text)
    if match:
        return f"{current_year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"
    match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if match:
        return f"{current_year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"
    return None


def _extract_times(text: str) -> tuple[str | None, str | None]:
    times = re.findall(r"(\d{1,2}:\d{2})", text)
    if not times:
        return None, None
    return times[0], times[1] if len(times) > 1 else None


def _extract_route(text: str) -> tuple[str | None, str | None]:
    arrow = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+)\s*(?:->|→|到|至)\s*([\u4e00-\u9fa5A-Za-z0-9]+)", text)
    if arrow:
        return arrow.group(1), arrow.group(2)
    pickup_words = ["成田机场", "成田", "羽田机场", "羽田", "关西机场", "大阪市内", "大阪", "东京站", "东京", "银座", "新宿", "京都", "酒店", "市内"]
    compact = re.search(r"(成田机场|成田|羽田机场|羽田|关西机场)(?:接机|送)(大阪市内|大阪|东京站|东京|银座|新宿|京都|酒店|市内)", text)
    if compact:
        return compact.group(1), compact.group(2)
    found = [word for word in pickup_words if word in text]
    if "接机" in text and found:
        return found[0], found[1] if len(found) > 1 else None
    if "送机" in text and found:
        return found[0], found[1] if len(found) > 1 else None
    return (found[0], found[1]) if len(found) >= 2 else (found[0], None) if found else (None, None)


def _extract_order_type(text: str) -> str | None:
    if "接机" in text:
        return "接机"
    if "送机" in text:
        return "送机"
    if "包车" in text:
        return "包车"
    if "机场" in text and "送" in text:
        return "送机"
    return None


def _extract_vehicle_type(text: str) -> str | None:
    for keyword in ["ALPHARD", "阿尔法", "丰田海狮", "海狮", "商务车", "中巴", "大巴"]:
        if keyword.lower() in text.lower():
            return keyword
    return None


def _extract_count(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _extract_guest_name(text: str) -> str | None:
    match = re.search(r"([\u4e00-\u9fa5]{1,4}(?:先生|女士|小姐))", text)
    return match.group(1) if match else None


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(?:\+?\d[\d -]{7,}\d)", text)
    return match.group(0).strip() if match else None


def _extract_agency(text: str) -> str | None:
    match = re.search(r"(?:旅行社|来源|社)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9]+)", text)
    return match.group(1) if match else None


def _extract_price(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|日元|円|JPY)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _has_minimum_fields(parsed: dict[str, Any]) -> bool:
    if not parsed.get("order_date") and (parsed.get("start_time") or parsed.get("pickup_location") or parsed.get("dropoff_location")):
        parsed["order_date"] = date.today().isoformat()
    return bool(parsed.get("order_date") or parsed.get("start_time") or parsed.get("pickup_location") or parsed.get("dropoff_location"))


def _merge_remark(left: Any, right: Any) -> str:
    parts = [str(value).strip() for value in (left, right) if str(value or "").strip()]
    return "\n".join(dict.fromkeys(parts))


def _normalize_numeric(data: dict[str, Any]) -> dict[str, Any]:
    for field in ("passenger_count", "luggage_count"):
        if field in data:
            data[field] = None if data[field] in ("", None) else int(data[field])
    if "price" in data:
        data["price"] = None if data["price"] in ("", None) else float(data["price"])
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
    date_text = resolved_date.replace("-", "")
    if len(date_text) != 8 or not date_text.isdigit():
        date_text = date.today().strftime("%Y%m%d")
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
    return f"{date_text}-{serial:03d}"

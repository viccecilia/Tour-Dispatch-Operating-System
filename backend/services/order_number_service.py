from __future__ import annotations

import re
from typing import Any


def normalize_source_code(value: Any = None, fallback: str = "D") -> str:
    text = str(value or fallback or "D").strip().upper()
    if text.startswith("X"):
        return "X"
    if text.startswith("D"):
        return "D"
    return (text[:1] or "D").upper()


def normalize_vehicle_type_code(*values: Any) -> str:
    text = " ".join(str(value or "") for value in values).lower()
    if any(token in text for token in ["3代", "三代", "alphard", "埃尔法", "阿尔法", "アルファード", "vellfire", "ヴェルファイア"]):
        return "A"
    if any(token in text for token in ["10座", "十座", "海狮", "海獅", "hiace", "ハイエース"]):
        return "H"
    if any(token in text for token in ["18座", "中巴", "マイクロバス"]):
        return "C"
    if any(token in text for token in ["23座", "考斯特", "coaster", "bus"]):
        return "B"
    if any(token in text for token in ["3代", "三代", "alphard", "埃尔法", "阿尔法", "vellfire", "威尔法"]):
        return "A"
    if any(token in text for token in ["10座", "十座", "海狮", "hiace"]):
        return "H"
    if any(token in text for token in ["18座", "中巴"]):
        return "C"
    if any(token in text for token in ["大巴", "巴士", "bus"]):
        return "B"
    return "A"


def plate_short_code(value: Any) -> str:
    chars = re.sub(r"[^0-9A-Za-z]", "", str(value or ""))
    return (chars[-4:] or "0000").upper()


def driver_short_code(name: Any = None, explicit_code: Any = None) -> str:
    explicit = re.sub(r"[^0-9A-Za-z]", "", str(explicit_code or "")).upper()
    if explicit:
        return explicit[:4]
    text = re.sub(r"\s+", "", str(name or ""))
    ascii_chars = "".join(ch for ch in text.upper() if "A" <= ch <= "Z")
    if ascii_chars:
        return ascii_chars[:4]
    return (text[:2] or "DR").upper()


def date_compact_yy(order_date: Any) -> str:
    text = str(order_date or "").replace("-", "")
    if len(text) == 8 and text.isdigit():
        return text[2:]
    if len(text) == 6 and text.isdigit():
        return text
    return "000000"


def build_order_oid(
    *,
    order_note_code: Any = None,
    order_source: Any = None,
    order_date: Any = None,
    serial: int = 1,
    plate_code: Any = None,
    driver_code: Any = None,
    driver_name: Any = None,
    vehicle_type_code: Any = None,
    vehicle_type: Any = None,
    temporary: bool = True,
) -> str:
    source = normalize_source_code(order_note_code or order_source)
    date_text = date_compact_yy(order_date)
    prefix = f"{source}{date_text}-{serial:04d}"
    if temporary:
        return f"{prefix}-TMP"
    plate = plate_short_code(plate_code)
    driver = driver_short_code(driver_name, driver_code)
    vehicle = str(vehicle_type_code or normalize_vehicle_type_code(vehicle_type)).strip().upper()[:1] or "A"
    return f"{prefix}-{plate}{driver}{vehicle}"


def split_existing_serial(oid: Any) -> int | None:
    match = re.search(r"^[A-Z]?(\d{6}|\d{8})-(\d{3,4})", str(oid or ""))
    return int(match.group(2)) if match else None

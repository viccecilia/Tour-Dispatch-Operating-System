from __future__ import annotations

import re
from typing import Any


ROLE_ACCOUNT_CODES = {
    "admin": "A1",
    "manager": "A1",
    "agency_admin": "A1",
    "customer_service": "B1",
    "service": "B1",
    "dispatcher": "B1",
    "operations_manager": "C1",
    "ops": "C1",
    "guide": "G1",
}


def _clean_code(value: Any, fallback: str = "") -> str:
    text = re.sub(r"[^0-9A-Za-z]", "", str(value or "")).upper()
    return text or fallback


def normalize_source_code(value: Any = None, fallback: str = "D") -> str:
    text = _clean_code(value, fallback)
    return (text[:5] or fallback).upper()


def normalize_org_code(value: Any = None, fallback: str = "D") -> str:
    text = normalize_source_code(value, fallback)
    if text in {"AGENCY", "PORTA", "PORTAL"}:
        return fallback
    return text


def normalize_account_code(value: Any = None, role: Any = None, fallback: str = "A1") -> str:
    raw = _clean_code(value)
    if re.fullmatch(r"[A-Z][0-9]", raw or ""):
        return raw
    role_key = str(role or "").strip().lower()
    return ROLE_ACCOUNT_CODES.get(role_key, fallback)


def actor_account_code(actor: dict[str, Any] | None, fallback: str = "A1") -> str:
    if not actor:
        return fallback
    return normalize_account_code(
        actor.get("operator_code") or actor.get("account_code") or actor.get("code"),
        actor.get("role") or actor.get("account_role"),
        fallback,
    )


def date_compact_yy(order_date: Any) -> str:
    text = str(order_date or "").replace("-", "").replace("/", "")
    if len(text) == 8 and text.isdigit():
        return text[2:]
    if len(text) == 6 and text.isdigit():
        return text
    return "000000"


def normalize_vehicle_type_label(*values: Any) -> str:
    raw_values = [str(value or "").strip() for value in values if str(value or "").strip()]
    if not raw_values:
        return ""
    text = " ".join(raw_values)
    lower = text.lower()
    compact = re.sub(r"\s+", "", text).upper()

    if any(token in compact for token in ("A-4", "A4", "4代", "四代", "四代阿尔法", "4代阿尔法")):
        return "A-4"
    if any(token in compact for token in ("A-3", "A3", "3代", "三代", "7座", "七座", "阿尔法", "埃尔法", "アルファード", "ヴェルファイア")):
        return "A-3"
    if any(token in lower for token in ("alphard", "vellfire")):
        return "A-3"
    if any(token in compact for token in ("H", "10座", "十座", "海狮", "海獅", "ハイエース", "グランエース")):
        return "H"
    if any(token in lower for token in ("hiace", "haice", "hice", "grandace")):
        return "H"
    return ""


def normalize_vehicle_type_code(*values: Any) -> str:
    label = normalize_vehicle_type_label(*values)
    if label.startswith("A-"):
        return "A"
    if label == "H":
        return "H"
    return "A"


def plate_short_code(value: Any) -> str:
    chars = re.sub(r"[^0-9A-Za-z]", "", str(value or ""))
    return (chars[-4:] or "0000").upper()


def driver_short_code(name: Any = None, explicit_code: Any = None) -> str:
    explicit = _clean_code(explicit_code)
    if explicit:
        return explicit[:4]
    text = re.sub(r"\s+", "", str(name or ""))
    ascii_chars = "".join(ch for ch in text.upper() if "A" <= ch <= "Z")
    if ascii_chars:
        return ascii_chars[:4]
    return (text[:2] or "DR").upper()


def build_public_order_oid(order_date: Any = None, serial: int = 1) -> str:
    return f"TF{date_compact_yy(order_date)}-{int(serial or 1):04d}"


def build_order_oid(
    *,
    order_note_code: Any = None,
    order_source: Any = None,
    order_date: Any = None,
    serial: int = 1,
    account_code: Any = None,
    account_role: Any = None,
    company_code: Any = None,
    agency_code: Any = None,
    plate_code: Any = None,
    driver_code: Any = None,
    driver_name: Any = None,
    vehicle_type_code: Any = None,
    vehicle_type: Any = None,
    temporary: bool = True,
) -> str:
    source = normalize_org_code(agency_code or company_code or order_note_code or order_source)
    account = normalize_account_code(account_code, account_role)
    prefix = f"{source}{date_compact_yy(order_date)}{account}-{int(serial or 1):04d}"
    if temporary:
        return prefix
    return build_execution_order_oid(
        prefix,
        plate_code=plate_code,
        driver_code=driver_code,
        driver_name=driver_name,
        vehicle_type_code=vehicle_type_code,
        vehicle_type=vehicle_type,
    )


def append_company_order_oid(
    base_oid: Any,
    *,
    company_code: Any,
    order_date: Any,
    account_code: Any = None,
    account_role: Any = None,
    serial: int = 1,
) -> str:
    base = _strip_execution_suffix(str(base_oid or "").strip())
    segment = build_order_oid(
        company_code=company_code,
        order_date=order_date,
        account_code=account_code,
        account_role=account_role,
        serial=serial,
        temporary=True,
    )
    if f"-{segment}" in f"-{base}":
        return base
    return f"{base}-{segment}" if base else segment


def build_execution_order_oid(
    base_oid: Any,
    *,
    plate_code: Any = None,
    driver_code: Any = None,
    driver_name: Any = None,
    vehicle_type_code: Any = None,
    vehicle_type: Any = None,
) -> str:
    base = _strip_execution_suffix(str(base_oid or "").strip())
    driver = driver_short_code(driver_name, driver_code)
    plate = plate_short_code(plate_code)
    vehicle = str(vehicle_type_code or normalize_vehicle_type_code(vehicle_type)).strip().upper()[:1] or "A"
    return f"{base}-{driver}{plate}{vehicle}" if base else f"{driver}{plate}{vehicle}"


def split_existing_serial(oid: Any) -> int | None:
    match = re.search(r"(?:^|-)[A-Z0-9]{1,5}\d{6}[A-Z]\d-(\d{4})(?:-|$)", str(oid or ""))
    return int(match.group(1)) if match else None


def _strip_execution_suffix(value: str) -> str:
    return re.sub(r"-[A-Z0-9]{2,8}\d{4}[A-Z]$", "", value)

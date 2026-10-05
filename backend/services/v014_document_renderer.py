from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.services.hotel_pool_service import normalize_city_place


A4_WIDTH = 595.276
A4_HEIGHT = 841.89

# V0.14 fixed carrier data. Database/config values always win; these values are
# only the official DAITORA fallback when the registered carrier is 株式会社大寅.
DAITORA_PROFILE = {
    "provider_suffix": "（大阪本社　京都営業所）",
    "osaka_address": "〒551-0013 大阪府大阪市大正区小林西2丁目10-3",
    "kyoto_address": "〒612-8448 京都府京都市伏見区竹田東小屋ノ内町95",
    "phone_office": "大阪本社",
    "phone_suffix": "（代表）",
    "area": "大阪市域交通圏 / 京都市域交通圏",
}

# The carrier block on every acceptance document is a statutory fixed profile.
# It must not inherit tenant/demo data (for example, Sakura Fleet KK).
FIXED_ACCEPTANCE_PROVIDER = {
    "name": "株式会社大寅（大阪本社　京都営業所）",
    "osaka_address": "〒551-0013 大阪府大阪市大正区小林西2丁目10-3",
    "kyoto_address": "〒612-8448 京都府京都市伏見区竹田東小屋ノ内町95",
    "phone": "大阪本社　06-6710-9861（代表）",
    "other": "安全統括　阪本 090-1483-4105",
    "area": "大阪市域交通圏・京都市域交通圏",
}

OFFICE_PROFILES = {
    "osaka": {"name": "大阪営業所", "manager": "胡東锴"},
    "kyoto": {"name": "京都営業所", "manager": "朱英心"},
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _clean(value: Any) -> str:
    text = _text(value)
    if re.fullmatch(r"(?:未入力|未確定|未設定|要確認|未確認|―|—)", text):
        return ""
    return text.replace("【仮】", "").strip()


def _japanese_office(value: Any) -> str:
    text = _clean(value)
    replacements = {
        "大阪营业所": "大阪営業所",
        "大阪營業所": "大阪営業所",
        "京都营业所": "京都営業所",
        "京都營業所": "京都営業所",
    }
    return replacements.get(text, text)


def _office_key(value: Any) -> str:
    text = _japanese_office(value)
    if "京都" in text:
        return "kyoto"
    if "大阪" in text:
        return "osaka"
    return ""


def _date_time(date_value: Any, time_value: Any) -> str:
    return "　".join(part for part in (_clean(date_value), _clean(time_value)) if part)


def _point(place: Any, date_value: Any, time_value: Any) -> str:
    return f"地点：{_clean(place)}\n日時：{_date_time(date_value, time_value)}"


def _money(value: Any) -> str:
    if value in (None, ""):
        return "未確定"
    try:
        return f"{float(value):,.0f}円"
    except (TypeError, ValueError):
        return _text(value)


def _order_identifier(order: dict[str, Any]) -> str:
    return _clean(order.get("oid")) or str(order.get("order_id") or "")


def _document_place(value: Any, stable_key: str) -> str:
    text = _clean(value)
    normalized, _ = normalize_city_place(text, stable_key)
    return _clean(normalized)


def _order_location(order: dict[str, Any], key: str) -> str:
    stable_key = "|".join(
        part
        for part in (_order_identifier(order), _clean(order.get("order_date")), key)
        if part
    )
    return _document_place(order.get(key), stable_key or key)


def _is_transfer(order: dict[str, Any]) -> bool:
    value = " ".join(
        _text(order.get(key))
        for key in ("order_type", "pickup_location", "dropoff_location")
    )
    return bool(re.search(r"接机|接機|送机|送機|迎え|送り|送迎|空港", value, re.I))


def application_method(order: dict[str, Any]) -> str:
    """Map internal acquisition channels to V0.14 formal application methods."""
    explicit = _clean(order.get("application_method"))
    source = explicit or _clean(order.get("order_source")) or _clean(order.get("source_channel"))
    normalized = source.lower()
    if re.search(r"電話|tel(?:ephone)?|phone", source, re.I):
        return "電話"
    if re.search(r"来店|店頭|walk[ -]?in", source, re.I):
        return "来店"
    if re.search(r"電子メール|e[ -]?mail|メール", source, re.I):
        return "電子メール"
    if (
        normalized
        or re.search(r"微信|wechat|line|whats(?:app|up)|kakao|網站|网站|網頁|网页|web", source, re.I)
    ):
        return "ウェブサイト"
    return "ウェブサイト"


def printable_instruction(order: dict[str, Any]) -> str:
    """Whitelist structured operational instructions; never print raw remarks."""
    values: list[str] = []
    flight = _clean(order.get("flight_number"))
    if flight:
        values.append(f"便名：{flight}")
    for key, label in (
        ("waiting_place", "待機場所"),
        ("attention_place", "注意箇所"),
        ("safety_instruction", "安全指示"),
        ("printable_operational_instruction", "指示事項"),
    ):
        value = _clean(order.get(key))
        if value:
            values.append(f"{label}：{value}")
    stopovers = order.get("printable_stopovers")
    if isinstance(stopovers, (list, tuple)):
        locations = [_clean(item) for item in stopovers if _clean(item)]
        if locations:
            values.append("立寄：" + " → ".join(locations))
    return "\n".join(values)


def _unique_orders(group: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, order in enumerate(group.get("orders") or []):
        key = _order_identifier(order) or f"row:{index}"
        if key in seen:
            continue
        seen.add(key)
        result.append(order)
    return result


def _company_profile(group: dict[str, Any]) -> dict[str, str]:
    source = group.get("company") or {}
    name = _clean(source.get("company_name")) or "株式会社大寅"
    is_daitora = "大寅" in name
    address_lines = [line.strip() for line in _text(source.get("address")).splitlines() if line.strip()]
    osaka = _clean(source.get("osaka_address"))
    kyoto = _clean(source.get("kyoto_address"))
    if not osaka and address_lines:
        osaka = address_lines[0]
    if not kyoto and len(address_lines) > 1:
        kyoto = address_lines[1]
    if is_daitora:
        osaka = osaka or DAITORA_PROFILE["osaka_address"]
        kyoto = kyoto or DAITORA_PROFILE["kyoto_address"]
    suffix = _clean(source.get("provider_suffix")) or (DAITORA_PROFILE["provider_suffix"] if is_daitora else "")
    area = _clean(source.get("business_area"))
    if not area:
        areas = []
        for order in group.get("orders") or []:
            value = _clean(order.get("operations_business_area"))
            if value and value not in areas:
                areas.append(value.replace("营业", "営業").replace("營業", "営業"))
        area = " / ".join(areas) or (DAITORA_PROFILE["area"] if is_daitora else "")
    phone = _clean(source.get("contact_phone"))
    phone_office = _clean(source.get("phone_office")) or (DAITORA_PROFILE["phone_office"] if is_daitora else "")
    phone_suffix = _clean(source.get("phone_suffix")) or (DAITORA_PROFILE["phone_suffix"] if is_daitora and phone else "")
    other = _clean(source.get("other_contact")) or _clean(source.get("contact_email")) or _clean(source.get("contact_name"))
    title = name + (suffix if suffix and suffix not in name else "")
    return {
        "name": name,
        "title": title,
        "osaka_address": osaka,
        "kyoto_address": kyoto,
        "address": _clean(source.get("address")),
        "phone": "　".join(part for part in (phone_office, phone) if part) + phone_suffix,
        "other": other,
        "area": area,
    }


def _office_profile(group: dict[str, Any]) -> dict[str, str]:
    office = _japanese_office(group.get("vehicle_office") or group.get("driver_office"))
    key = _office_key(office)
    default = OFFICE_PROFILES.get(key, {})
    return {
        "name": office or default.get("name", ""),
        "manager": _clean(group.get("operations_manager"))
        or default.get("manager", "")
        or _clean(group.get("document_actor_name")),
    }


def _garage(group: dict[str, Any], side: str) -> tuple[str, str]:
    place = (
        _clean(group.get(f"garage_{side}_location"))
        or _clean(group.get("garage_location"))
        or "車庫"
    )
    time = _clean(group.get(f"garage_{side}_time"))
    return place, time


def _operation_bounds(
    group: dict[str, Any], orders: list[dict[str, Any]], index: int
) -> dict[str, str]:
    order = orders[index]
    scope = _clean(order.get("operation_scope")) or "auto"
    date_value = _clean(order.get("order_date")) or _clean(group.get("business_date"))
    if scope in {"manual", "custom"}:
        return {
            "start_place": _order_location(order, "operation_start_location"),
            "start_date": _clean(order.get("operation_start_date")) or date_value,
            "start_time": _clean(order.get("operation_start_time")),
            "end_place": _order_location(order, "operation_end_location"),
            "end_date": _clean(order.get("operation_end_date")) or date_value,
            "end_time": _clean(order.get("operation_end_time")),
            "mode": scope,
        }
    if scope == "day":
        start_place, start_time = _garage(group, "out")
        end_place, end_time = _garage(group, "in")
        return {
            "start_place": start_place,
            "start_date": date_value,
            "start_time": start_time,
            "end_place": end_place,
            "end_date": date_value,
            "end_time": end_time,
            "mode": scope,
        }
    if index == 0:
        start_place, start_time = _garage(group, "out")
    else:
        previous = orders[index - 1]
        start_place = _order_location(previous, "dropoff_location")
        start_time = _clean(previous.get("end_time"))
    if index == len(orders) - 1:
        end_place, end_time = _garage(group, "in")
        end_date = date_value
    else:
        end_place = _order_location(order, "dropoff_location")
        end_time = _clean(order.get("end_time"))
        end_date = _clean(order.get("end_date")) or date_value
    return {
        "start_place": start_place,
        "start_date": date_value,
        "start_time": start_time,
        "end_place": end_place,
        "end_date": end_date,
        "end_time": end_time,
        "mode": "auto",
    }


def _acceptance_missing(vm: dict[str, Any]) -> list[str]:
    missing = []
    for key in (
        "pickup_place",
        "pickup_time",
        "dropoff_place",
        "dropoff_time",
        "operation_start_place",
        "operation_start_time",
        "operation_end_place",
        "operation_end_time",
        "provider_name",
    ):
        if not _clean(vm.get(key)):
            missing.append(key)
    if vm.get("fare") in (None, ""):
        missing.append("fare")
    return missing


def build_acceptance_view_model(
    group: dict[str, Any], order: dict[str, Any], index: int, order_count: int
) -> dict[str, Any]:
    orders = _unique_orders(group)
    bounds = _operation_bounds(group, orders, index)
    company = _company_profile(group)
    pickup_date = _clean(order.get("order_date")) or _clean(group.get("business_date"))
    dropoff_date = _clean(order.get("end_date")) or pickup_date
    total = order.get("price")
    fees = order.get("document_fee") if order.get("document_fee") not in (None, "") else 0
    try:
        fare = float(total) - float(fees) if total not in (None, "") else None
    except (TypeError, ValueError):
        fare = total
        fees = 0
    vm = {
        "company_name": company["name"],
        "provider_name": company["title"],
        "provider_osaka": company["osaka_address"],
        "provider_kyoto": company["kyoto_address"],
        "provider_address": company["address"],
        "provider_phone": company["phone"],
        "provider_other": company["other"],
        "provider_area": company["area"],
        "sequence": index + 1,
        "order_count": order_count,
        "order_number": _order_identifier(order),
        "date": pickup_date,
        "revision": int(order.get("run_revision") or 1),
        "applicant": _clean(order.get("agency_name")) or _clean(order.get("guest_name")),
        "applicant_phone": _clean(order.get("guest_contact")),
        "applicant_other": _clean(order.get("applicant_other_contact")),
        "method": application_method(order),
        "operation_start_place": bounds["start_place"],
        "operation_start_date": bounds["start_date"],
        "operation_start_time": bounds["start_time"],
        "operation_end_place": bounds["end_place"],
        "operation_end_date": bounds["end_date"],
        "operation_end_time": bounds["end_time"],
        "pickup_place": _order_location(order, "pickup_location"),
        "pickup_date": pickup_date,
        "pickup_time": _clean(order.get("start_time")),
        "dropoff_place": _order_location(order, "dropoff_location"),
        "dropoff_date": dropoff_date,
        "dropoff_time": _clean(order.get("end_time")),
        "fare": fare,
        "fees": fees,
        "total": total,
        "fee_label": "料金（ETC・駐車代 現収）" if _is_transfer(order) else "料金",
        "fee_detail": _clean(order.get("document_fee_detail")),
        "created_date": _clean(group.get("business_date")),
        "driver_name": _clean(group.get("driver_print_name")) or _clean(group.get("driver_name")),
        "plate_number": _clean(group.get("plate_number")),
        "scope": bounds["mode"],
    }
    vm["missing_fields"] = _acceptance_missing(vm)
    # Missing-field validation remains server-side; the generated document
    # itself must not print an English DRAFT label or watermark.
    vm["badge"] = ""
    return vm


def build_dispatch_view_model(group: dict[str, Any]) -> dict[str, Any]:
    orders = _unique_orders(group)
    company = _company_profile(group)
    office = _office_profile(group)
    garage_out, garage_out_time = _garage(group, "out")
    garage_in, garage_in_time = _garage(group, "in")
    rows = []
    for index, order in enumerate(orders, 1):
        applicant = _clean(order.get("agency_name")) or _clean(order.get("guest_name"))
        contact = _clean(order.get("guest_contact"))
        route = [f"乗車：{_order_location(order, 'pickup_location')}"]
        stopovers = order.get("printable_stopovers")
        if isinstance(stopovers, (list, tuple)):
            route.extend(
                f"立寄：{_document_place(item, f'{_order_identifier(order)}|stopover|{stop_index}')}"
                for stop_index, item in enumerate(stopovers)
                if _clean(item)
            )
        route.append(f"降車：{_order_location(order, 'dropoff_location')}")
        rows.append(
            {
                "sequence": index,
                "pickup_time": _clean(order.get("start_time")),
                "dropoff_time": _clean(order.get("end_time")),
                "route": "\n".join(route),
                "contract": "\n".join(
                    part for part in (f"氏名：{applicant}" if applicant else "", f"連絡：{contact}" if contact else "") if part
                ),
                "method": application_method(order),
                "instruction": printable_instruction(order) or "―",
                "order_number": _order_identifier(order),
            }
        )
    safety = {
        "waiting": _clean(group.get("safe_wait")),
        "attention": _clean(group.get("safe_attention")),
        "other": _clean(group.get("safe_other")),
    }
    for row in rows:
        if row["instruction"] != "―" and "便名：" in row["instruction"]:
            safety["other"] = "\n".join(part for part in (safety["other"], row["instruction"]) if part)
    vm = {
        "company_name": company["name"],
        "date": _clean(group.get("business_date")),
        "revision": max([int(order.get("run_revision") or 1) for order in orders] or [1]),
        "driver_name": _clean(group.get("driver_print_name")) or _clean(group.get("driver_name")),
        "plate_number": _clean(group.get("plate_number")),
        "office_name": office["name"],
        "manager": office["manager"],
        "created_date": _clean(group.get("business_date")),
        "garage_out": garage_out,
        "garage_out_time": garage_out_time,
        "garage_in": garage_in,
        "garage_in_time": garage_in_time,
        "rows": rows,
        "safety": safety,
    }
    missing = []
    for key in ("company_name", "driver_name", "plate_number", "office_name", "manager", "garage_out", "garage_out_time", "garage_in", "garage_in_time"):
        if not _clean(vm.get(key)):
            missing.append(key)
    vm["missing_fields"] = missing
    vm["badge"] = ""
    return vm


@dataclass
class _Cell:
    width: float
    text: str
    fill: str = ""
    bold: bool = False
    font: str = "value"
    size: float | None = None


class _Sheet:
    def __init__(self, canvas: Any, fonts: dict[str, str]):
        self.canvas = canvas
        self.fonts = fonts
        self.canvas.setStrokeColorRGB(0.21, 0.21, 0.21)
        self.canvas.setLineWidth(0.55)

    def _font(self, key: str, bold: bool = False) -> str:
        if bold:
            return self.fonts["bold"]
        return self.fonts.get(key, self.fonts["value"])

    def _wrap(self, text: Any, width: float, size: float, font: str) -> list[str]:
        value = str(text if text is not None else "")
        lines: list[str] = []
        for paragraph in value.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for character in paragraph:
                if self.canvas.stringWidth(current + character, font, size) > width and current:
                    lines.append(current)
                    current = character
                else:
                    current += character
            lines.append(current)
        return lines or [""]

    def text(
        self,
        value: Any,
        x: float,
        y: float,
        width: float = 539,
        size: float = 9,
        bold: bool = False,
        font_key: str = "value",
        color: str = "#161616",
    ) -> float:
        font = self._font(font_key, bold)
        lines = self._wrap(value, width, size, font)
        leading = size * 1.4
        self.canvas.setFont(font, size)
        self.canvas.setFillColor(color)
        for line_index, line in enumerate(lines):
            self.canvas.drawString(x, A4_HEIGHT - y - size - line_index * leading, line)
        return len(lines) * leading

    def centered(self, value: str, y: float, size: float = 18, bold: bool = True) -> None:
        font = self._font("label", bold)
        self.canvas.setFont(font, size)
        self.canvas.setFillColor("#161616")
        width = self.canvas.stringWidth(value, font, size)
        self.canvas.drawString((A4_WIDTH - width) / 2, A4_HEIGHT - y - size, value)

    def rect(self, x: float, y: float, width: float, height: float, fill: str = "") -> None:
        if fill:
            self.canvas.setFillColor(fill)
            self.canvas.rect(x, A4_HEIGHT - y - height, width, height, stroke=1, fill=1)
        else:
            self.canvas.rect(x, A4_HEIGHT - y - height, width, height, stroke=1, fill=0)

    def row(self, y: float, cells: list[_Cell], height: float | None = None, size: float = 9) -> float:
        line_heights = []
        for cell in cells:
            cell_size = cell.size or size
            font = self._font(cell.font, cell.bold)
            line_heights.append(len(self._wrap(cell.text, cell.width - 10, cell_size, font)) * cell_size * 1.4 + 10)
        row_height = height if height is not None else max(line_heights)
        x = 28.0
        for cell in cells:
            self.rect(x, y, cell.width, row_height, cell.fill)
            self.text(cell.text, x + 4, y + 3, cell.width - 8, cell.size or size, cell.bold, cell.font)
            x += cell.width
        return y + row_height

    def label(self, y: float, label: str, value: str, min_height: float = 0, size: float = 9) -> float:
        label_font = self._font("label", True)
        value_font = self._font("value", False)
        height = max(
            min_height,
            len(self._wrap(label, 97, size, label_font)) * size * 1.4 + 12,
            len(self._wrap(value, 422, size, value_font)) * size * 1.4 + 12,
        )
        return self.row(
            y,
            [
                _Cell(107, label, fill="#f3f3ef", bold=True, font="label"),
                _Cell(432, value, font="value"),
            ],
            height,
            size,
        )

    def watermark(self, badge: str) -> None:
        if not badge:
            return
        self.canvas.saveState()
        self.canvas.setFillColorRGB(0.42, 0.42, 0.38, alpha=0.07)
        self.canvas.translate(A4_WIDTH / 2, A4_HEIGHT / 2)
        self.canvas.rotate(32)
        self.canvas.setFont(self.fonts["bold"], 76)
        self.canvas.drawCentredString(0, 0, badge)
        self.canvas.restoreState()

    def footer(self, text: str, page_text: str, kind: str) -> None:
        self.text(text, 28, 803, 490, 7.3, font_key="label", color="#444444")
        self.text(page_text, 520, 803, 50, 7.3, font_key="label", color="#444444")
        self.text(kind, 28, 817, 539, 7.1, font_key="label", color="#666666")


def _provider_rows(vm: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("運送引受者", FIXED_ACCEPTANCE_PROVIDER["name"]),
        ("大阪　本社", FIXED_ACCEPTANCE_PROVIDER["osaka_address"]),
        ("京都営業所", FIXED_ACCEPTANCE_PROVIDER["kyoto_address"]),
        ("電 話 番 号", FIXED_ACCEPTANCE_PROVIDER["phone"]),
        ("その他連絡先", FIXED_ACCEPTANCE_PROVIDER["other"]),
        ("営 業 区 域", FIXED_ACCEPTANCE_PROVIDER["area"]),
    ]


def _draw_provider(sheet: _Sheet, vm: dict[str, Any], y: float) -> float:
    for index, (label, value) in enumerate(_provider_rows(vm)):
        size = 10 if index == 0 else 9.2
        sheet.canvas.setFont(sheet._font("value", index == 0), size)
        lines = sheet._wrap(value, 427, size, sheet._font("value", index == 0))
        height = max(27, len(lines) * size * 1.4 + 9)
        y = sheet.row(
            y,
            [
                _Cell(100, label, fill="#f3f3ef", bold=index == 0, font="label", size=9.2),
                _Cell(439, value, bold=index == 0, font="value", size=size),
            ],
            height,
            9.2,
        )
    return y


def _draw_acceptance(canvas: Any, fonts: dict[str, str], vm: dict[str, Any], packet_page: int, packet_total: int) -> None:
    sheet = _Sheet(canvas, fonts)
    sheet.text(vm["company_name"], 28, 17, 240, 9, True, "label")
    sheet.text(f"第 {vm['sequence']} 便 ／ {vm['order_count']} 件", 414, 15, 153, 10, True, "label")
    sheet.centered("運 送 引 受 書", 37, 21)
    sheet.text(
        f"{vm['order_number']} ／ {vm['date']} ／ R{vm['revision']}",
        28,
        69,
        401,
        8.4,
        font_key="label",
    )
    sheet.text(vm["badge"], 451, 69, 116, 8.4, True, "label")
    y = 87.0
    applicant_parts = []
    if vm["applicant"]:
        applicant_parts.append(f"氏名又は名称：{vm['applicant']}")
    if vm["applicant_phone"]:
        applicant_parts.append(f"電話番号：{vm['applicant_phone']}")
    if vm["applicant_other"]:
        applicant_parts.append(f"その他連絡先：{vm['applicant_other']}")
    applicant = "\n".join(applicant_parts)
    y = sheet.label(y, "運送の申込者", applicant, 65, 10)
    y = sheet.label(y, "申込方法", vm["method"], 31, 10)
    operation = (
        "【開始】" + _point(vm["operation_start_place"], vm["operation_start_date"], vm["operation_start_time"])
        + "\n【終了】" + _point(vm["operation_end_place"], vm["operation_end_date"], vm["operation_end_time"])
    )
    y = sheet.label(y, "運行の開始／終了\n地点及び日時", operation, 76, 9.4)
    pickup_dropoff = (
        "【乗車】" + _point(vm["pickup_place"], vm["pickup_date"], vm["pickup_time"])
        + "\n【降車】" + _point(vm["dropoff_place"], vm["dropoff_date"], vm["dropoff_time"])
    )
    y = sheet.label(y, "乗車／降車\n地点及び日時", pickup_dropoff, 76, 9.4)
    fare_lines = (
        f"運賃：{_money(vm['fare'])}\n"
        f"{vm['fee_label']}：{_money(vm['fees'])}\n"
        f"料金内訳：{vm['fee_detail']}\n"
        f"合計：{_money(vm['total'])}"
    )
    y = sheet.label(y, "運賃・料金", fare_lines, 75, 9.3)
    sheet.text("上記のとおり運送を引き受けます。", 28, y + 9, 350, 10, font_key="label")
    sheet.text(vm["created_date"], 410, y + 9, 157, 9, font_key="label")
    y += 31
    y = _draw_provider(sheet, vm, y)
    if y > 790:
        raise ValueError("acceptance_page_overflow")
    sheet.watermark(vm["badge"])
    sheet.footer(
        f"予定版 / R{vm['revision']} / {vm['date']}  {vm['driver_name']}  {vm['plate_number']}",
        f"{packet_page} / {packet_total}",
        "別記1参考様式 / 注文別・空欄は交付前に記入",
    )


def _dispatch_safety_text(vm: dict[str, Any]) -> str:
    safety = vm["safety"]
    return (
        f"待機場所：{safety['waiting']}\n"
        f"注意箇所：{safety['attention']}\n"
        f"その他指示事項：{safety['other']}"
    )


def _dispatch_header(sheet: _Sheet, vm: dict[str, Any], page: int, total: int, standard: bool) -> float:
    sheet.text(vm["company_name"], 28, 17, 240, 9, True, "label")
    page_label = "1 枚" if standard else f"{page} / {total} 頁"
    sheet.text(f"全日 {len(vm['rows'])} 件 ／ {page_label}", 399, 15, 168, 10, True, "label")
    sheet.centered("運 行 指 示 書", 37, 21)
    sheet.text(f"{vm['date']} ／ {vm['driver_name']} ／ R{vm['revision']}", 28, 69, 401, 8.4, font_key="label")
    sheet.text(vm["badge"], 451, 69, 116, 8.4, True, "label")
    y = 87.0
    y = sheet.row(y, [_Cell(79, "事業者名", "#f3f3ef", True, "label"), _Cell(206, vm["company_name"]), _Cell(79, "営業所名", "#f3f3ef", True, "label"), _Cell(175, vm["office_name"])], 26 if standard else 25, 9.2 if standard else 8.8)
    y = sheet.row(y, [_Cell(79, "運行管理者", "#f3f3ef", True, "label"), _Cell(206, vm["manager"]), _Cell(79, "作成年月日", "#f3f3ef", True, "label"), _Cell(175, vm["created_date"])], 26 if standard else 25, 9.2 if standard else 8.8)
    y = sheet.row(y, [_Cell(79, "運転者の氏名" if standard else "運転者", "#f3f3ef", True, "label"), _Cell(206, vm["driver_name"]), _Cell(79, "自動車登録番号" if standard else "車両番号", "#f3f3ef", True, "label"), _Cell(175, vm["plate_number"])], 26 if standard else 25, 9.1 if standard else 8.8)
    if standard:
        operation = (
            "【開始】" + _point(vm["garage_out"], vm["date"], vm["garage_out_time"])
            + "\n【終了】" + _point(vm["garage_in"], vm["date"], vm["garage_in_time"])
        )
        y = sheet.label(y, "全運行の開始／終了\n地点及び日時", operation, 66, 9.3)
    return y + 8


def _draw_signature(sheet: _Sheet, y: float, compact: bool) -> float:
    y = sheet.row(
        y,
        [
            _Cell(86, "運行管理者\n指示（印）", "#f3f3ef", font="label"),
            _Cell(183, ""),
            _Cell(86, "運転者\n確認（印）", "#f3f3ef", font="label"),
            _Cell(184, ""),
        ],
        39 if compact else 44,
        8.5 if compact else 9.2,
    )
    if not compact:
        y = sheet.row(
            y,
            [
                _Cell(86, "指示年月日", "#f3f3ef", font="label"),
                _Cell(183, "　年　月　日　時　分"),
                _Cell(86, "確認年月日", "#f3f3ef", font="label"),
                _Cell(184, "　年　月　日　時　分"),
            ],
            26,
            9,
        )
    return y


def _standard_row_cells(row: dict[str, Any]) -> list[_Cell]:
    return [
        _Cell(25, str(row["sequence"]), font="label"),
        _Cell(70, f"乗 {row['pickup_time']}\n降 {row['dropoff_time']}"),
        _Cell(222, row["route"]),
        _Cell(142, row["contract"]),
        _Cell(80, row["method"]),
    ]


def _compact_row_cells(row: dict[str, Any]) -> list[_Cell]:
    return [
        _Cell(34, str(row["sequence"]), font="label"),
        _Cell(66, f"乗 {row['pickup_time']}\n降 {row['dropoff_time']}"),
        _Cell(315, row["route"]),
        _Cell(124, row["instruction"]),
    ]


def _measure_row(sheet: _Sheet, cells: list[_Cell], size: float, minimum: float) -> float:
    heights = []
    for cell in cells:
        font = sheet._font(cell.font, cell.bold)
        heights.append(len(sheet._wrap(cell.text, cell.width - 10, size, font)) * size * 1.4 + 10)
    return max(minimum, *heights)


def _draw_dispatch_standard(canvas: Any, fonts: dict[str, str], vm: dict[str, Any], packet_page: int, packet_total: int) -> None:
    sheet = _Sheet(canvas, fonts)
    y = _dispatch_header(sheet, vm, 1, 1, True)
    headers = [
        _Cell(25, "便", "#eeeeeb", True, "label"),
        _Cell(70, "乗降時刻", "#eeeeeb", True, "label"),
        _Cell(222, "乗車・降車・立寄り地", "#eeeeeb", True, "label"),
        _Cell(142, "契約の相手方・連絡先", "#eeeeeb", True, "label"),
        _Cell(80, "配車依頼方法", "#eeeeeb", True, "label"),
    ]
    y = sheet.row(y, headers, 32, 8.7)
    rows = [_standard_row_cells(row) for row in vm["rows"]]
    sizes = [_measure_row(sheet, cells, 9.1, 47) for cells in rows]
    safety_text = _dispatch_safety_text(vm)
    safety_height = max(60, len(sheet._wrap(safety_text, 422, 9, sheet._font("value"))) * 12.6 + 12)
    available = 790 - y - safety_height - 70 - 29
    if sum(sizes) > available:
        raise ValueError("standard_dispatch_page_overflow")
    desired = min(106, available / max(len(rows), 1))
    expanded = [max(height, min(desired, height + 24)) for height in sizes]
    if sum(expanded) <= available:
        sizes = expanded
    for cells, height in zip(rows, sizes):
        y = sheet.row(y, cells, height, 9.1)
    y += 8
    y = sheet.label(y, "運行の安全確保\nに必要な事項", safety_text, safety_height, 9)
    y += 10
    y = _draw_signature(sheet, y, False)
    if y > 790:
        raise ValueError("standard_dispatch_page_overflow")
    sheet.watermark(vm["badge"])
    sheet.footer(
        f"予定版 / R{vm['revision']} / {vm['date']}  {vm['driver_name']}  {vm['plate_number']}",
        f"{packet_page} / {packet_total}",
        "別記2参考様式 / 全日一覧・空欄は指示前に記入 / 運行指示書 1/1",
    )


def _compact_page_fits(fonts: dict[str, str], vm: dict[str, Any], rows: list[dict[str, Any]], dense: bool) -> bool:
    from reportlab.pdfgen.canvas import Canvas
    from io import BytesIO

    canvas = Canvas(BytesIO(), pagesize=(A4_WIDTH, A4_HEIGHT))
    sheet = _Sheet(canvas, fonts)
    y = 87 + 25 * 3 + 7 + 24
    size = 7.15 if dense else 8.5
    for row in rows:
        y += _measure_row(sheet, _compact_row_cells(row), size, 32 if dense else 43)
    safety_text = _dispatch_safety_text(vm)
    safety_height = max(42 if dense else 52, len(sheet._wrap(safety_text, 422, size, sheet._font("value"))) * size * 1.35 + 9)
    y += 7 + safety_height + 7 + 39
    return y <= 790


def _draw_dispatch_compact(
    canvas: Any,
    fonts: dict[str, str],
    vm: dict[str, Any],
    rows: list[dict[str, Any]],
    page: int,
    total: int,
    dense: bool,
    packet_page: int,
    packet_total: int,
) -> None:
    sheet = _Sheet(canvas, fonts)
    y = _dispatch_header(sheet, vm, page, total, False)
    headers = [
        _Cell(34, "便", "#eeeeeb", True, "label"),
        _Cell(66, "乗降時刻", "#eeeeeb", True, "label"),
        _Cell(315, "乗車・降車・立寄り地", "#eeeeeb", True, "label"),
        _Cell(124, "指示・備考", "#eeeeeb", True, "label"),
    ]
    y = sheet.row(y, headers, 24, 8)
    size = 7.15 if dense else 8.5
    for row in rows:
        cells = _compact_row_cells(row)
        y = sheet.row(y, cells, _measure_row(sheet, cells, size, 32 if dense else 43), size)
    safety_text = _dispatch_safety_text(vm)
    safety_height = max(42 if dense else 52, len(sheet._wrap(safety_text, 422, size, sheet._font("value"))) * size * 1.35 + 9)
    y += 7
    y = sheet.label(y, "運行の安全確保\nに必要な事項", safety_text, safety_height, size)
    y += 7
    y = _draw_signature(sheet, y, True)
    if y > 790:
        raise ValueError("compact_dispatch_page_overflow")
    sheet.watermark(vm["badge"])
    sheet.footer(
        f"予定版 / R{vm['revision']} / {vm['date']}  {vm['driver_name']}  {vm['plate_number']}",
        f"{packet_page} / {packet_total}",
        f"別記2参考様式 / 連続頁・空欄は指示前に記入 / 運行指示書 {page}/{total}",
    )


def _dispatch_plan(fonts: dict[str, str], vm: dict[str, Any]) -> tuple[str, list[list[dict[str, Any]]]]:
    rows = vm["rows"]
    if len(rows) <= 7:
        return "standard", [rows]
    if len(rows) <= 10 and _compact_page_fits(fonts, vm, rows, True):
        return "dense", [rows]
    return "paged", [rows[index : index + 6] for index in range(0, len(rows), 6)]


def _load_reportlab(runtime_dir: Path) -> None:
    if "reportlab" in sys.modules:
        return
    venv_lib = runtime_dir / "trial" / "venv" / "lib"
    for site_packages in sorted(venv_lib.glob("python*/site-packages")):
        site_path = str(site_packages)
        if site_path not in sys.path:
            sys.path.insert(0, site_path)


def _register_fonts(jp_font_path: Path, sc_font_path: Path) -> dict[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if not jp_font_path.is_file() or not sc_font_path.is_file():
        raise ValueError("pdf_font_missing:NotoSansJP-VF.ttf/NotoSansSC-VF.ttf")
    fonts = {"label": "V014NotoSansJP", "value": "V014NotoSansSC", "bold": "V014NotoSansJP"}
    if fonts["label"] not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(fonts["label"], str(jp_font_path)))
    if fonts["value"] not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(fonts["value"], str(sc_font_path)))
    return fonts


def render_driver_packet(
    group: dict[str, Any],
    path: Path,
    *,
    runtime_dir: Path,
    jp_font_path: Path,
    sc_font_path: Path,
) -> int:
    """Render V0.14 acceptances first, followed by the all-day instruction."""
    _load_reportlab(runtime_dir)
    try:
        from reportlab.pdfgen import canvas as pdfcanvas
    except ImportError as exc:
        raise ValueError("pdf_dependency_missing:reportlab") from exc
    fonts = _register_fonts(jp_font_path, sc_font_path)
    orders = _unique_orders(group)
    if not orders:
        raise ValueError("run_document_has_no_orders")
    acceptance_models = [
        build_acceptance_view_model(group, order, index, len(orders))
        for index, order in enumerate(orders)
    ]
    dispatch_model = build_dispatch_view_model(group)
    dispatch_mode, dispatch_pages = _dispatch_plan(fonts, dispatch_model)
    total_pages = len(acceptance_models) + len(dispatch_pages)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = pdfcanvas.Canvas(str(path), pagesize=(A4_WIDTH, A4_HEIGHT), pageCompression=1)
    canvas.setTitle(path.stem)
    canvas.setAuthor("Tour Dispatch / V0.14")
    packet_page = 0
    for model in acceptance_models:
        packet_page += 1
        _draw_acceptance(canvas, fonts, model, packet_page, total_pages)
        canvas.showPage()
    for page_index, rows in enumerate(dispatch_pages, 1):
        packet_page += 1
        if dispatch_mode == "standard":
            _draw_dispatch_standard(canvas, fonts, dispatch_model, packet_page, total_pages)
        else:
            _draw_dispatch_compact(
                canvas,
                fonts,
                dispatch_model,
                rows,
                page_index,
                len(dispatch_pages),
                dispatch_mode == "dense",
                packet_page,
                total_pages,
            )
        canvas.showPage()
    canvas.save()
    return total_pages

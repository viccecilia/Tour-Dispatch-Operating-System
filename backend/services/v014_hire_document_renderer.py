from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable


A4_WIDTH = 595.276
A4_HEIGHT = 841.89
MARGIN = 28.0
CONTENT_WIDTH = 539.0
AIRPORT_ACCEPTANCE_LIMIT = 10
AIRPORT_DISPATCH_LIMIT = 4
APPLICANT_MARKS = {1: "①", 2: "②", 3: "③", 4: "④"}

PROVIDER_ROWS = (
    ("運送引受者", "株式会社大寅（大阪本社　京都営業所）"),
    ("大阪　本社", "〒551-0013 大阪府大阪市大正区小林西2丁目10-3"),
    ("京都営業所", "〒612-8448 京都府京都市伏見区竹田東小屋ノ内町95"),
    ("電 話 番 号", "大阪本社　06-6710-9861（代表）"),
    ("その他連絡先", "安全統括　阪本 090-1483-4105"),
    ("営 業 区 域", "大阪市域交通圏・京都市域交通圏"),
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _dt(value: Any) -> tuple[str, str]:
    text = _text(value)
    if not text:
        return "", ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        if "T" in text:
            date_value, time_value = text.split("T", 1)
            return date_value, time_value[:5]
        return text, ""
    return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")


def _money(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{int(float(value)):,}円"
    except (TypeError, ValueError):
        return _text(value)


def _location(order: dict[str, Any], side: str) -> str:
    return _text(order.get("locations", {}).get(side, {}).get("confirmed"))


def _applicant(snapshot: dict[str, Any], slot: Any) -> dict[str, Any]:
    for item in snapshot.get("applicants") or []:
        if item.get("slot") == slot:
            return item
    return {"slot": slot, "name": "", "contact": ""}


def _chunks(values: list[Any], size: int) -> list[list[Any]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _route_lines(contract: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for day_index, day in enumerate(contract.get("days") or [], 1):
        parts: list[str] = []
        for node in day.get("nodes") or []:
            _, arrival = _dt(node.get("arrival_at"))
            _, departure = _dt(node.get("departure_at"))
            time_value = departure or arrival
            value = " ".join(part for part in (time_value, _text(node.get("location"))) if part)
            if value:
                parts.append(value)
        lines.append(f"{day_index}日目（{_text(day.get('date'))}）　" + " → ".join(parts))
    return lines or [""]


def _contract_end_date(contract: dict[str, Any]) -> str:
    if contract.get("end_date"):
        return _text(contract.get("end_date"))
    days = list(contract.get("days") or [])
    return _text(days[-1].get("date")) if days else ""


@dataclass
class Cell:
    width: float
    text: str
    fill: str = ""
    bold: bool = False
    size: float | None = None
    align: str = "left"


class Sheet:
    def __init__(self, canvas: Any, fonts: dict[str, str]):
        self.canvas = canvas
        self.fonts = fonts
        self.canvas.setStrokeColor("#222222")
        self.canvas.setLineWidth(0.72)

    def font_for(self, value: Any, *, bold: bool = False) -> str:
        from reportlab.pdfbase import pdfmetrics

        primary = self.fonts["bold" if bold else "regular"]
        fallback = self.fonts.get("fallback_bold" if bold else "fallback_regular")
        if not fallback:
            return primary
        glyphs = pdfmetrics.getFont(primary).face.charToGlyph
        if any(ord(character) not in glyphs for character in str(value if value is not None else "")):
            return fallback
        return primary

    def wrap(self, value: Any, width: float, size: float, font: str) -> list[str]:
        lines: list[str] = []
        for paragraph in str(value if value is not None else "").split("\n"):
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for character in paragraph:
                if current and self.canvas.stringWidth(current + character, font, size) > width:
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
        width: float = CONTENT_WIDTH,
        size: float = 9,
        *,
        bold: bool = False,
        color: str = "#111111",
        align: str = "left",
    ) -> float:
        font = self.font_for(value, bold=bold)
        lines = self.wrap(value, width, size, font)
        leading = size * 1.32
        self.canvas.setFillColor(color)
        self.canvas.setFont(font, size)
        for index, line in enumerate(lines):
            baseline = A4_HEIGHT - y - size - index * leading
            if align == "center":
                start_x = x + (width - self.canvas.stringWidth(line, font, size)) / 2
            elif align == "right":
                start_x = x + width - self.canvas.stringWidth(line, font, size)
            else:
                start_x = x
            self.canvas.saveState()
            self.canvas.setFillColor(color)
            text_object = self.canvas.beginText(start_x, baseline)
            text_object.setFont(font, size)
            text_object.setTextRenderMode(0)
            text_object.textOut(line)
            self.canvas.drawText(text_object)
            self.canvas.restoreState()
        return len(lines) * leading

    def rect(self, x: float, y: float, width: float, height: float, fill: str = "") -> None:
        if fill:
            self.canvas.setFillColor(fill)
            self.canvas.rect(x, A4_HEIGHT - y - height, width, height, stroke=1, fill=1)
        else:
            self.canvas.rect(x, A4_HEIGHT - y - height, width, height, stroke=1, fill=0)

    def row(self, y: float, cells: Iterable[Cell], height: float | None = None, size: float = 9) -> float:
        items = list(cells)
        measured: list[float] = []
        for cell in items:
            cell_size = cell.size or size
            font = self.font_for(cell.text, bold=cell.bold)
            measured.append(len(self.wrap(cell.text, cell.width - 8, cell_size, font)) * cell_size * 1.32 + 8)
        row_height = height if height is not None else max(measured)
        x = MARGIN
        for cell in items:
            self.rect(x, y, cell.width, row_height, cell.fill)
            self.text(cell.text, x + 4, y + 3, cell.width - 8, cell.size or size, bold=cell.bold, align=cell.align)
            x += cell.width
        return y + row_height

    def cell(self, x: float, y: float, cell: Cell, height: float, size: float = 9) -> None:
        self.rect(x, y, cell.width, height, cell.fill)
        self.text(cell.text, x + 4, y + 3, cell.width - 8, cell.size or size, bold=cell.bold, align=cell.align)

    def label(self, y: float, label: str, value: str, min_height: float = 28, size: float = 9, label_width: float = 107) -> float:
        value_width = CONTENT_WIDTH - label_width
        label_lines = self.wrap(label, label_width - 8, size, self.font_for(label, bold=True))
        value_lines = self.wrap(value, value_width - 8, size, self.font_for(value))
        height = max(min_height, len(label_lines) * size * 1.32 + 8, len(value_lines) * size * 1.32 + 8)
        return self.row(y, [Cell(label_width, label, "#f2f2ef", True), Cell(value_width, value)], height, size)

    def document_header(
        self,
        title: str,
        meta: str = "",
        right: str = "",
        *,
        table_top: float = 82.0,
        company_label: str = "株式会社大寅　/　DAITORA",
    ) -> float:
        if company_label:
            self.text(company_label, MARGIN, 17, 260, 9.5, bold=True)
        if right:
            self.text(right, 365, 16, 202, 10.5, bold=True, align="right")
        self.text(title, 60, 35, A4_WIDTH - 120, 22, bold=True, align="center")
        if meta:
            self.text(meta, MARGIN, 66, CONTENT_WIDTH, 9.0)
        return table_top

    def footer(self, left: str, page: int, total: int) -> None:
        self.text(left, MARGIN, 812, 470, 7.1, color="#555555")
        self.text(f"{page} / {total}", 510, 812, 57, 7.1, color="#555555", align="right")


def _register_fonts(jp_font_path: Path) -> dict[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_dir = jp_font_path.parent
    paths = {
        "regular": font_dir / "NotoSansJP-Regular.ttf",
        "bold": font_dir / "NotoSansJP-Bold.ttf",
        "fallback_regular": font_dir / "NotoSansSC-Regular.ttf",
        "fallback_bold": font_dir / "NotoSansSC-Bold.ttf",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError("pdf_static_font_missing:" + ",".join(missing))
    fonts = {
        "regular": "V014HireJPRegular",
        "bold": "V014HireJPBold",
        "fallback_regular": "V014HireSCRegular",
        "fallback_bold": "V014HireSCBold",
    }
    for key, name in fonts.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(paths[key])))
    return fonts


def _provider(sheet: Sheet, y: float) -> float:
    for index, (label, value) in enumerate(PROVIDER_ROWS):
        y = sheet.row(y, [Cell(100, label, "#f2f2ef", index == 0, 9.0, "center"), Cell(439, value, "", index == 0, 9.3, "center")], 27, 9.0)
    return y


def _operation_parts(snapshot: dict[str, Any]) -> tuple[str, str]:
    operation = snapshot.get("operation") or {}
    start_date, start_time = _dt(operation.get("start_at"))
    end_date, end_time = _dt(operation.get("end_at"))
    return (
        f"地点　{_text(operation.get('start_location'))}\n日時　{start_date}　{start_time}",
        f"地点　{_text(operation.get('end_location'))}\n日時　{end_date}　{end_time}",
    )


def _draw_airport_applicants(sheet: Sheet, y: float, snapshot: dict[str, Any]) -> float:
    applicants = list(snapshot.get("applicants") or [])[:4]
    while len(applicants) < 4:
        applicants.append({"slot": len(applicants) + 1, "name": "", "contact": ""})
    for pair in ((applicants[0], applicants[2]), (applicants[1], applicants[3])):
        for side, item in enumerate(pair):
            x = MARGIN + side * 269
            name = _text(item.get("name"))
            if name == "WEBSITE":
                name = "WEBSITE（WeChat / Web 等）"
            slot = int(item.get("slot") or 0)
            sheet.cell(x, y, Cell(18, APPLICANT_MARKS.get(slot, str(slot)), "#f2f2ef", False, 8.0, "center"), 54, 8.0)
            labels = ("氏名・名称", "連絡方法等", "申込方法")
            values = (name, _text(item.get("contact")), "アプリ　電話　メール　Web　SNS　その他（　　）")
            for row_index, (label, value) in enumerate(zip(labels, values)):
                row_y = y + row_index * 18
                sheet.cell(x + 18, row_y, Cell(52, label, "#f2f2ef", True, 7.5), 18, 7.5)
                sheet.cell(x + 70, row_y, Cell(199 if side == 0 else 200, value, size=7.5), 18, 7.5)
        y += 54
    return y


def _draw_airport_acceptance(canvas: Any, fonts: dict[str, str], snapshot: dict[str, Any], orders: list[dict[str, Any]], acceptance_index: int, acceptance_total: int, page: int, total: int) -> None:
    sheet = Sheet(canvas, fonts)
    driver = snapshot.get("driver") or {}
    vehicle = snapshot.get("vehicle") or {}
    meta = f"{_text(snapshot.get('business_date'))}　/　{_text(driver.get('name'))}　/　{_text(vehicle.get('plate_number'))}"
    y = sheet.document_header("運送引受書", meta)
    y = _draw_airport_applicants(sheet, y, snapshot)
    start, end = _operation_parts(snapshot)
    y = sheet.row(y, [Cell(92, "運送の開始\n地点／日時", "#f2f2ef", True, 8.2), Cell(178, start, size=8.4), Cell(92, "運送の終了\n地点／日時", "#f2f2ef", True, 8.2), Cell(177, end, size=8.4)], 40, 8.2)
    headers = [Cell(26, "申込", "#eeeeeb", True, 7.0), Cell(70, "配車日時", "#eeeeeb", True, 7.0), Cell(100, "配車場所", "#eeeeeb", True, 7.0), Cell(20, "→", "#eeeeeb", True, 7.0, "center"), Cell(100, "降車場所", "#eeeeeb", True, 7.0), Cell(64, "到着日時", "#eeeeeb", True, 7.0), Cell(98, "運賃・料金・立替", "#eeeeeb", True, 7.0), Cell(63, "合計(税込)", "#eeeeeb", True, 7.0)]
    y = sheet.row(y, headers, 20, 7.0)
    for row_index in range(AIRPORT_ACCEPTANCE_LIMIT):
        if row_index < len(orders):
            order = orders[row_index]
            pickup_date, pickup_time = _dt(order.get("pickup_at"))
            arrival_date, arrival_time = _dt(order.get("arrival_at"))
            money = order.get("money") or {}
            advances = "・".join(name for name, value in (("P代", money.get("parking_fee_jpy")), ("高速代", money.get("toll_fee_jpy")), ("その他", money.get("advance_jpy"))) if value not in (None, "", 0, 0.0))
            detail = f"運賃 {_money(money.get('fare_jpy'))}\n料金 {_money(money.get('service_fee_jpy'))}\n立替：{advances}"
            row = [Cell(26, APPLICANT_MARKS.get(int(order.get("applicant_slot") or 0), str(order.get("applicant_slot") or "")), size=7.2, align="center"), Cell(70, f"{pickup_date}\n{pickup_time}", size=7.2), Cell(100, _location(order, "pickup"), size=7.15), Cell(20, "→", size=7.2, align="center"), Cell(100, _location(order, "dropoff"), size=7.15), Cell(64, f"{arrival_date}\n{arrival_time}", size=7.2), Cell(98, detail, size=6.85), Cell(63, _money(money.get("total_jpy")), size=7.2)]
        else:
            row = [Cell(width, "", size=7.0) for width in (26, 70, 100, 20, 100, 64, 98, 63)]
        y = sheet.row(y, row, 30, 7.0)
    y += 4
    sheet.text("上記のとおり運送を引き受けます。", MARGIN, y, 330, 9.0)
    sheet.text(f"作成日：{_text(snapshot.get('created_date') or snapshot.get('business_date'))}", 390, y, 177, 8.8, align="right")
    y += 21
    _provider(sheet, y)


def _draw_dispatch_header(sheet: Sheet, snapshot: dict[str, Any], count_text: str) -> float:
    driver = snapshot.get("driver") or {}
    vehicle = snapshot.get("vehicle") or {}
    meta = " / ".join(part for part in (_text(snapshot.get("business_date")), _text(driver.get("name")), _text(snapshot.get("route_code"))) if part)
    y = sheet.document_header("運 行 指 示 書", meta, count_text, table_top=87.0, company_label="株式会社大寅")
    y = sheet.row(y, [Cell(79, "事業者名", "#f2f2ef", True), Cell(206, "株式会社大寅"), Cell(79, "営業所名", "#f2f2ef", True), Cell(175, _text(driver.get("office")))], 26)
    y = sheet.row(y, [Cell(79, "運行管理者", "#f2f2ef", True), Cell(206, _text(snapshot.get("operations_manager"))), Cell(79, "作成年月日", "#f2f2ef", True), Cell(175, _text(snapshot.get("created_date") or snapshot.get("business_date")))], 26)
    y = sheet.row(y, [Cell(79, "運転者の氏名", "#f2f2ef", True), Cell(206, _text(driver.get("name"))), Cell(79, "自動車登録番号", "#f2f2ef", True), Cell(175, _text(vehicle.get("plate_number")))], 26)
    start, end = _operation_parts(snapshot)
    return sheet.label(y, "全運行の開始／終了\n地点及び日時", f"【開始】{start}\n【終了】{end}", 66, 8.7)


def _draw_safety_and_signatures(sheet: Sheet, snapshot: dict[str, Any], y: float, *, dates: bool) -> float:
    safety = snapshot.get("safety") or {}
    y = sheet.label(y, "運行の安全確保\nに必要な事項", f"待機場所：{_text(safety.get('waiting_place'))}\n注意箇所：{_text(safety.get('attention_place'))}\nその他指示事項：{_text(safety.get('other_instruction'))}", 60, 8.7)
    y += 10 if dates else 7
    signature_height = 44 if dates else 40
    signature_widths = (86, 183, 86, 184) if dates else (107, 163, 107, 162)
    y = sheet.row(y, [Cell(signature_widths[0], "運行管理者\n指示（印）", "#f2f2ef", True, 8.7), Cell(signature_widths[1], ""), Cell(signature_widths[2], "運転者\n確認（印）", "#f2f2ef", True, 8.7), Cell(signature_widths[3], "")], signature_height, 8.7)
    if dates:
        y = sheet.row(y, [Cell(86, "指示年月日", "#f2f2ef", True, 8.5), Cell(183, "　年　月　日　時　分", size=8.5), Cell(86, "確認年月日", "#f2f2ef", True, 8.5), Cell(184, "　年　月　日　時　分", size=8.5)], 26, 8.5)
    return y


def _draw_airport_dispatch(canvas: Any, fonts: dict[str, str], snapshot: dict[str, Any], orders: list[dict[str, Any]], dispatch_index: int, dispatch_total: int, page: int, total: int) -> None:
    sheet = Sheet(canvas, fonts)
    airport_count = sum(len(items) for items in snapshot.get("airport_acceptance_pages") or [])
    y = _draw_dispatch_header(sheet, snapshot, f"全日 {airport_count} 件 / {dispatch_index}枚目")
    y += 8
    y = sheet.row(y, [Cell(25, "便", "#eeeeeb", True, 7.8), Cell(70, "乗降時刻", "#eeeeeb", True, 7.8), Cell(222, "乗車・降車・立寄り地", "#eeeeeb", True, 7.8), Cell(142, "契約の相手方・連絡先", "#eeeeeb", True, 7.8), Cell(80, "配車依頼方法", "#eeeeeb", True, 7.8)], 32, 7.8)
    for index, order in enumerate(orders, 1 + (dispatch_index - 1) * AIRPORT_DISPATCH_LIMIT):
        _, pickup_time = _dt(order.get("pickup_at"))
        _, arrival_time = _dt(order.get("arrival_at"))
        route = f"乗車：{_location(order, 'pickup')}\n降車：{_location(order, 'dropoff')}"
        if order.get("stopovers"):
            route += "\n立寄：" + " → ".join(_text(item) for item in order["stopovers"])
        applicant = _applicant(snapshot, order.get("applicant_slot"))
        counterparty = _text(order.get("contract_party_name") or order.get("applicant_name") or applicant.get("name"))
        contact = _text(order.get("applicant_contact") or applicant.get("contact"))
        y = sheet.row(y, [Cell(25, str(index), size=8.2), Cell(70, f"乗 {pickup_time}\n降 {arrival_time}", size=8.2), Cell(222, route, size=8.35), Cell(142, f"氏名：{counterparty}\n連絡：{contact}", size=8.15), Cell(80, "ウェブサイト", size=8.15)], 71, 8.15)
    y += 8
    _draw_safety_and_signatures(sheet, snapshot, y, dates=True)
    driver = snapshot.get("driver") or {}
    vehicle = snapshot.get("vehicle") or {}
    footer = " / ".join(part for part in ("予定版", _text(snapshot.get("route_code") or "V0.14"), _text(snapshot.get("business_date")), _text(driver.get("name")), _text(vehicle.get("plate_number"))) if part)
    sheet.text(footer, MARGIN, 800, 470, 7.6)
    sheet.text("自動選定ホテルを含む計画案。実際の乗降地を要照合。・本機作成／押印・実際の交付は別途", MARGIN, 818, 500, 7.0, color="#555555")
    sheet.text(f"{dispatch_index} / {dispatch_total}", 510, 800, 57, 7.6, align="right")


def _charter_order(snapshot: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    for order in snapshot.get("orders") or []:
        if order.get("order_id") == contract.get("order_id"):
            return order
    return {}


def _draw_charter_acceptance(canvas: Any, fonts: dict[str, str], snapshot: dict[str, Any], contract: dict[str, Any], route_lines: list[str], continuation: int, continuation_total: int, page: int, total: int) -> None:
    sheet = Sheet(canvas, fonts)
    order = _charter_order(snapshot, contract)
    title = "運送引受書" if continuation == 1 else "運送引受書（続）"
    meta = " / ".join(part for part in (_text(snapshot.get("business_date")), _contract_end_date(contract)) if part)
    y = sheet.document_header(title, meta)
    applicant_name = _text(order.get("contract_party_name") or order.get("applicant_name") or order.get("agency_name"))
    y = sheet.label(y, "運送申込者", f"氏名・名称：{applicant_name}\n申込方法：ウェブサイト", 43, 8.7)
    start, end = _operation_parts(snapshot)
    y = sheet.row(y, [Cell(107, "運送の開始\n地点／日時", "#f2f2ef", True, 8.7), Cell(163, start, size=8.7), Cell(107, "運送の終了\n地点／日時", "#f2f2ef", True, 8.7), Cell(162, end, size=8.7)], 43, 8.7)
    route_height = 82 if continuation_total == 1 else 190
    y = sheet.label(y, "運行日程・経路", "\n".join(route_lines), route_height, 8.65)
    if continuation == continuation_total:
        money = order.get("money") or {}
        fee_lines = [f"運賃料金：{_money(money.get('total_jpy'))}"]
        if money.get("toll_fee_jpy") is None:
            fee_lines.append("高速通行料：実費精算")
        if money.get("parking_fee_jpy") is None:
            fee_lines.append("駐車料金：実費精算")
        y = sheet.label(y, "運賃料金", "\n".join(fee_lines), 49, 8.8)
        y += 5
        sheet.text("上記のとおり運送を引き受けます。", MARGIN, y, 330, 9.0)
        sheet.text(f"作成日：{_text(snapshot.get('created_date') or snapshot.get('business_date'))}", 390, y, 177, 8.8, align="right")
        y += 25
        _provider(sheet, y)
    driver = snapshot.get("driver") or {}
    vehicle = snapshot.get("vehicle") or {}
    footer = " / ".join(part for part in ("予定版", _text(snapshot.get("route_code") or "V0.14"), _text(snapshot.get("business_date")), _text(driver.get("name")), _text(vehicle.get("plate_number"))) if part)
    sheet.text(footer, MARGIN, 800, 470, 7.6)
    sheet.text("貸切・観光・一般・本機作成／押印・実際の交付は別途", MARGIN, 818, 500, 7.0, color="#555555")
    sheet.text(f"{continuation} / {continuation_total}", 510, 800, 57, 7.6, align="right")


def _draw_charter_dispatch(canvas: Any, fonts: dict[str, str], snapshot: dict[str, Any], contract: dict[str, Any], route_lines: list[str], continuation: int, continuation_total: int, page: int, total: int) -> None:
    sheet = Sheet(canvas, fonts)
    order = _charter_order(snapshot, contract)
    driver = snapshot.get("driver") or {}
    vehicle = snapshot.get("vehicle") or {}
    title = "運 行 指 示 書" if continuation == 1 else "運 行 指 示 書（続）"
    meta = " / ".join(part for part in (_text(driver.get("name")), _text(vehicle.get("plate_number")), _text(snapshot.get("business_date")), _contract_end_date(contract)) if part)
    y = sheet.document_header(title, meta)
    y = sheet.row(y, [Cell(107, "営業所", "#f2f2ef", True, 8.8), Cell(163, _text(driver.get("office")), size=8.8), Cell(107, "運行管理者", "#f2f2ef", True, 8.8), Cell(162, _text(snapshot.get("operations_manager")), size=8.8)], 25, 8.8)
    y = sheet.row(y, [Cell(107, "運転者", "#f2f2ef", True, 8.8), Cell(163, _text(driver.get("name")), size=8.8), Cell(107, "車両番号", "#f2f2ef", True, 8.8), Cell(162, _text(vehicle.get("plate_number")), size=8.8)], 25, 8.8)
    y = sheet.label(y, "運送申込者", _text(order.get("contract_party_name") or order.get("applicant_name") or order.get("agency_name")), 25, 8.8)
    start, end = _operation_parts(snapshot)
    y = sheet.row(y, [Cell(107, "全運行の開始\n地点／日時", "#f2f2ef", True, 8.7), Cell(163, start, size=8.7), Cell(107, "全運行の終了\n地点／日時", "#f2f2ef", True, 8.7), Cell(162, end, size=8.7)], 43, 8.7)
    route_height = 88 if continuation_total == 1 else 330
    y = sheet.label(y, "運行経路・指示事項", "\n".join(route_lines), route_height, 8.65)
    if continuation == continuation_total:
        y += 7
        _draw_safety_and_signatures(sheet, snapshot, y, dates=False)
    footer = " / ".join(part for part in ("予定版", _text(snapshot.get("route_code") or "V0.14"), _text(snapshot.get("business_date")), _text(driver.get("name")), _text(vehicle.get("plate_number"))) if part)
    sheet.text(footer, MARGIN, 800, 470, 7.6)
    sheet.text("貸切・観光・一般・本機作成／押印・実際の交付は別途", MARGIN, 818, 500, 7.0, color="#555555")
    sheet.text(f"{continuation} / {continuation_total}", 510, 800, 57, 7.6, align="right")


RenderJob = Callable[[Any, dict[str, str], int, int], None]


def _build_jobs(snapshot: dict[str, Any]) -> list[RenderJob]:
    jobs: list[RenderJob] = []
    airport_pages = [list(items) for items in snapshot.get("airport_acceptance_pages") or []]
    for acceptance_index, orders in enumerate(airport_pages, 1):
        jobs.append(lambda canvas, fonts, page, total, orders=orders, acceptance_index=acceptance_index: _draw_airport_acceptance(canvas, fonts, snapshot, orders, acceptance_index, len(airport_pages), page, total))
    all_airport_orders = [order for page_orders in airport_pages for order in page_orders]
    dispatch_pages = _chunks(all_airport_orders, AIRPORT_DISPATCH_LIMIT)
    for dispatch_index, orders in enumerate(dispatch_pages, 1):
        jobs.append(lambda canvas, fonts, page, total, orders=orders, dispatch_index=dispatch_index: _draw_airport_dispatch(canvas, fonts, snapshot, orders, dispatch_index, len(dispatch_pages), page, total))
    for contract in snapshot.get("charter_contracts") or []:
        lines = _route_lines(contract)
        acceptance_chunks = _chunks(lines, 5)
        for index, route_chunk in enumerate(acceptance_chunks, 1):
            jobs.append(lambda canvas, fonts, page, total, contract=contract, route_chunk=route_chunk, index=index: _draw_charter_acceptance(canvas, fonts, snapshot, contract, route_chunk, index, len(acceptance_chunks), page, total))
        dispatch_chunks = _chunks(lines, 8)
        for index, route_chunk in enumerate(dispatch_chunks, 1):
            jobs.append(lambda canvas, fonts, page, total, contract=contract, route_chunk=route_chunk, index=index: _draw_charter_dispatch(canvas, fonts, snapshot, contract, route_chunk, index, len(dispatch_chunks), page, total))
    return jobs


def render_hire_packet(snapshot: dict[str, Any], path: Path, *, jp_font_path: Path) -> int:
    """Render V0.14 hire acceptance and dispatch documents from one Phase 2A snapshot."""
    try:
        from reportlab.pdfgen import canvas as pdfcanvas
    except ImportError as exc:
        raise ValueError("pdf_dependency_missing:reportlab") from exc
    fonts = _register_fonts(jp_font_path)
    jobs = _build_jobs(snapshot)
    if not jobs:
        raise ValueError("hire_document_has_no_airport_or_charter_data")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = pdfcanvas.Canvas(str(path), pagesize=(A4_WIDTH, A4_HEIGHT), pageCompression=1)
    canvas.setTitle(path.stem)
    canvas.setAuthor("株式会社大寅 / Tour Dispatch V0.14")
    total = len(jobs)
    for page, job in enumerate(jobs, 1):
        job(canvas, fonts, page, total)
        canvas.showPage()
    canvas.save()
    return total


def render_hire_sample_packet(snapshot: dict[str, Any], path: Path, *, jp_font_path: Path) -> int:
    """Backward-compatible inspection helper used by the Phase 2B sample generator."""
    return render_hire_packet(snapshot, path, jp_font_path=jp_font_path)

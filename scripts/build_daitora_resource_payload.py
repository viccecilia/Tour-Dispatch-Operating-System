from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path


SOURCE_ROOT = Path(r"C:\Pang.S\车辆资料整理")
VEHICLE_CSV = SOURCE_ROOT / "车辆信息总表.csv"
DRIVER_CSV = SOURCE_ROOT / "司机信息表.csv"
FILES_ROOT = SOURCE_ROOT / "server_demo" / "files"
OUTPUT_PATH = Path("runtime/deploy/daitora_resource_payload.json")

HIDDEN_VEHICLE_CODES = {"7721", "3724", "7728"}
HIDDEN_DRIVER_NAMES = {
    "刘明海",
    "劉晟",
    "王爽",
    "楊増福",
    "滝澤雅禾",
    "富塚紀子",
    "陳鈴",
    "唐洋洲",
    "谷口（張）延瑾",
    "谷口延瑾",
    "福田弘一",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def era_to_iso(value: str | None) -> str:
    text = clean(value).replace(" ", "")
    if not text or text == "-":
        return ""
    match = re.search(r"([RrHh])(\d{1,2})(\d{2})(\d{2})", text)
    if match:
        era, y, m, d = match.groups()
        base = 2018 if era.upper() == "R" else 1988
        return f"{base + int(y):04d}-{int(m):02d}-{int(d):02d}"
    match = re.search(r"([RrHh])(\d{1,2})(\d{2})", text)
    if match:
        era, y, m = match.groups()
        base = 2018 if era.upper() == "R" else 1988
        return f"{base + int(y):04d}-{int(m):02d}-01"
    match = re.search(r"([RrHh])(\d{1,2})", text)
    if match:
        era, y = match.groups()
        base = 2018 if era.upper() == "R" else 1988
        return f"{base + int(y):04d}-01-01"
    match = re.search(r"令和\s*(\d{1,2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if match:
        year, month, day = match.groups()
        return f"{2018 + int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"平成\s*(\d{1,2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if match:
        year, month, day = match.groups()
        return f"{1988 + int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return ""


def iso_date(value: str | None) -> str:
    text = clean(value)
    if not text or text == "-":
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return era_to_iso(text)


def add_year(iso: str) -> str:
    if not iso:
        return ""
    current = datetime.strptime(iso, "%Y-%m-%d").date()
    try:
        return current.replace(year=current.year + 1).isoformat()
    except ValueError:
        return current.replace(year=current.year + 1, day=28).isoformat()


def infer_type_code(vehicle_type: str) -> str:
    lowered = vehicle_type.lower()
    if "hiace" in lowered or "ハイエース" in vehicle_type:
        return "H"
    if "alphard" in lowered or "アルファ" in vehicle_type or "ヴェルファ" in vehicle_type:
        return "A"
    if "nissan" in lowered:
        return "N"
    if "coaster" in lowered:
        return "C"
    return ""


def infer_seats(vehicle_type: str) -> int | None:
    lowered = vehicle_type.lower()
    if "hiace" in lowered or "nissan" in lowered or "ハイエース" in vehicle_type:
        return 10
    if "coaster" in lowered:
        return 18
    if "alphard" in lowered or "アルファ" in vehicle_type or "ヴェルファ" in vehicle_type:
        return 6
    return None


def split_dates(value: str | None) -> list[str]:
    dates = []
    for part in re.split(r"[/,、\s]+", clean(value)):
        parsed = era_to_iso(part)
        if parsed:
            dates.append(parsed)
    return sorted(set(dates))


def file_records_for(short_code: str, plate_number: str) -> list[dict[str, str]]:
    records: dict[tuple[str, str, str], dict[str, str]] = {}
    if not FILES_ROOT.exists():
        return []
    folders = [
        folder
        for folder in FILES_ROOT.iterdir()
        if folder.is_dir() and short_code in folder.name
    ]
    for folder in folders:
        for pdf in folder.glob("*.pdf"):
            name = pdf.name
            if "3ヶ月点検" in name:
                inspection_type = "inspection"
            elif "自動車檢查証記録事項" in name or "自動車検査証記録事項" in name or "自動車検査証" in name:
                inspection_type = "shaken"
            else:
                continue
            parsed = era_to_iso(name) or iso_date(name)
            if not parsed:
                continue
            key = (inspection_type, parsed, name)
            records[key] = {
                "inspection_type": inspection_type,
                "inspection_date": parsed,
                "source": "vehicle-docs",
                "note": name,
            }
    return sorted(records.values(), key=lambda item: (item["inspection_date"], item["inspection_type"], item["note"]))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_vehicles() -> list[dict[str, object]]:
    vehicles = []
    for row in read_csv(VEHICLE_CSV):
        short_code = clean(row.get("后四位"))
        if not short_code or short_code in HIDDEN_VEHICLE_CODES:
            continue
        plate_number = clean(row.get("车牌号"))
        vehicle_type = clean(row.get("车型")) or "vehicle"
        records = file_records_for(short_code, plate_number)
        for shaken_date in split_dates(row.get("車検日期")):
            records.append(
                {
                    "inspection_type": "shaken",
                    "inspection_date": shaken_date,
                    "source": "vehicle-ledger",
                    "note": "車検日期",
                }
            )
        for inspection_date in split_dates(row.get("3ヶ月点検日期")):
            records.append(
                {
                    "inspection_type": "inspection",
                    "inspection_date": inspection_date,
                    "source": "vehicle-ledger",
                    "note": "3ヶ月点検日期",
                }
            )
        deduped = {(r["inspection_type"], r["inspection_date"], r.get("note", "")): r for r in records}
        records = sorted(deduped.values(), key=lambda item: (item["inspection_date"], item["inspection_type"]))
        latest_shaken = max((r["inspection_date"] for r in records if r["inspection_type"] == "shaken"), default="")
        latest_any = max((r["inspection_date"] for r in records), default=latest_shaken)
        due = era_to_iso(row.get("车检到期"))
        if latest_shaken and (not due or due <= latest_shaken):
            due = add_year(latest_shaken)
        vehicles.append(
            {
                "plate_number": plate_number,
                "plate_short_code": short_code,
                "vehicle_type": vehicle_type,
                "vehicle_type_code": clean(row.get("型式")) or infer_type_code(vehicle_type),
                "vehicle_color": "",
                "vehicle_group": vehicle_type,
                "seat_count": infer_seats(vehicle_type),
                "status": "available",
                "maintenance_status": "",
                "last_inspection_date": latest_any,
                "shaken_due_date": due or add_year(latest_shaken),
                "inspection_expires_at": "",
                "insurance_due_date": "",
                "insurance_expires_at": "",
                "records": records,
            }
        )
    return vehicles


def initials(name: str) -> str:
    ascii_only = "".join(ch.upper() for ch in name if ch.isascii() and ch.isalpha())
    if ascii_only:
        return ascii_only[:6]
    return clean(name)[:6]


def build_drivers() -> list[dict[str, object]]:
    drivers = []
    for row in read_csv(DRIVER_CSV):
        name = clean(row.get("運転手名"))
        if not name or name in HIDDEN_DRIVER_NAMES:
            continue
        health_date = iso_date(row.get("健康诊断日期"))
        medical_expires = add_year(health_date)
        try:
            health_remaining = (datetime.strptime(medical_expires, "%Y-%m-%d").date() - date.today()).days if medical_expires else None
        except ValueError:
            health_remaining = None
        status_text = clean(row.get("状態"))
        active = status_text not in {"离职", "離職", "退职", "退職"}
        drivers.append(
            {
                "name": name,
                "phone": clean(row.get("携帯電話番号")),
                "status": "available" if active else "deleted",
                "driver_status": "available" if active else "deleted",
                "driver_code": initials(name),
                "office": clean(row.get("所属営業所")),
                "driver_external_id": clean(row.get("運転手ID")),
                "license_number": clean(row.get("免許番号")),
                "residence_status": clean(row.get("在留資格")),
                "residence_due_date": iso_date(row.get("再留期限有效日期")),
                "license_due_date": iso_date(row.get("免许有効期限")),
                "license_expires_at": iso_date(row.get("免许有効期限")),
                "health_check_due_date": health_date,
                "medical_check_expires_at": medical_expires,
                "health_check_remaining_days": health_remaining,
                "email": clean(row.get("メールアドレス")),
            }
        )
    return drivers


def main() -> None:
    payload = {
        "tenant_id": 8204,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "vehicles": build_vehicles(),
        "drivers": build_drivers(),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_PATH), "vehicles": len(payload["vehicles"]), "drivers": len(payload["drivers"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

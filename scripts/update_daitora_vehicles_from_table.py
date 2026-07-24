from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "runtime" / "wx_dispatch.sqlite3"
TENANT_ID = 529


def era_date(value: str, day_default: str = "01") -> str:
    raw = (value or "").strip().replace(" ", "")
    if not raw:
        return ""
    era = raw[0].upper()
    rest = raw[1:]
    if era == "R":
        year_base = 2018
    elif era == "H":
        year_base = 1988
    else:
        raise ValueError(f"unsupported era date: {value}")
    digits = "".join(ch for ch in rest if ch.isdigit())
    if len(digits) <= 2:
        year = year_base + int(digits)
        return f"{year:04d}-01-01"
    era_year = int(digits[:-4]) if len(digits) > 4 else int(digits[:-2])
    year = year_base + era_year
    if len(digits) >= 5:
        month = int(digits[-4:-2])
        day = int(digits[-2:])
    else:
        month = int(digits[-2:])
        day = int(day_default)
    return f"{year:04d}-{month:02d}-{day:02d}"


def vehicle_type_code(vehicle_type: str) -> str:
    text = vehicle_type.lower()
    if "ハイエース" in vehicle_type or "キャラバン" in vehicle_type or "hiace" in text:
        return "H"
    return "A"


VEHICLES = [
    {
        "plate": "なにわ330を1001",
        "type": "ハイエース",
        "color": "白",
        "first": "R5 07",
        "company": "R5 0710",
        "checks": ["R8 0114", "R8 0419"],
        "shaken_done": "R7 0708",
        "shaken_due": "R8 0709",
    },
    {
        "plate": "なにわ330い1027",
        "type": "ハイエース",
        "color": "黒",
        "first": "R6 02",
        "company": "R6 0301",
        "checks": ["R8 0320"],
        "shaken_done": "R8 0320",
        "shaken_due": "R8 0320",
    },
    {
        "plate": "なにわ300あ7886",
        "type": "ハイエース",
        "color": "白",
        "first": "R7 04",
        "company": "R7 0425",
        "checks": ["R8 0126"],
        "shaken_done": "R8 0809",
        "shaken_due": "R8 0809",
    },
    {
        "plate": "なにわ330う710",
        "type": "ヴェルファHV",
        "color": "黒",
        "first": "H29 04",
        "company": "R6 0207",
        "checks": ["R8 0204", "R8 0513"],
        "shaken_done": "R8 0204",
        "shaken_due": "R8 0219",
    },
    {
        "plate": "なにわ300あ6781",
        "type": "ヴェルファHV",
        "color": "黒",
        "first": "H29 03",
        "company": "R6 1105",
        "checks": ["R8 0226", "R8 0508"],
        "shaken_done": "R8 1027",
        "shaken_due": "R8 1104",
    },
    {
        "plate": "なにわ300あ7007",
        "type": "30系アルファード",
        "color": "黒",
        "first": "H27 10",
        "company": "R7 0212",
        "checks": ["R8 0212", "R8 0527"],
        "shaken_done": "R8 0212",
        "shaken_due": "R8 0211",
    },
    {
        "plate": "なにわ300あ7011",
        "type": "ヴェルファHV",
        "color": "黒",
        "first": "H28 12",
        "company": "R7 0213",
        "checks": ["R8 0206", "R8 0515"],
        "shaken_done": "R8 0206",
        "shaken_due": "R8 0212",
    },
    {
        "plate": "なにわ300あ7012",
        "type": "30系アルファード",
        "color": "黒",
        "first": "R2 08",
        "company": "R7 0213",
        "checks": ["R8 0209", "R8 0517"],
        "shaken_done": "R8 0209",
        "shaken_due": "R8 0212",
    },
    {
        "plate": "なにわ300あ7025",
        "type": "30系アルファード",
        "color": "白",
        "first": "R1 12",
        "company": "R7 0225",
        "checks": ["R8 0212", "R8 0520"],
        "shaken_done": "R8 0212",
        "shaken_due": "R8 0224",
    },
    {
        "plate": "なにわ300あ6832",
        "type": "30系アルファードHV",
        "color": "黒",
        "first": "R3 11",
        "company": "R6 1115",
        "checks": ["R8 0308", "R8 0616"],
        "shaken_done": "R7 1104",
        "shaken_due": "R8 1114",
    },
    {
        "plate": "なにわ300あ7495",
        "type": "30系アルファード",
        "color": "黒",
        "first": "H28 04",
        "company": "R7 0710",
        "checks": ["R8 0121", "R8 0425"],
        "shaken_done": "R7 0710",
        "shaken_due": "R8 0709",
    },
    {
        "plate": "なにわ300あ8298",
        "type": "30系アルファード",
        "color": "黒",
        "checks": [],
        "shaken_done": "R8 0609",
        "shaken_due": "R9 0609",
    },
    {
        "plate": "なにわ330あ719",
        "type": "ヴェルファHV",
        "color": "黒",
        "first": "R2 01",
        "company": "R7 0225",
        "checks": ["R8 0130", "R8 0514"],
        "shaken_done": "R8 0130",
        "shaken_due": "R8 0224",
    },
    {
        "plate": "なにわ300あ8256",
        "type": "30系アルファード",
        "color": "黒",
        "checks": [],
        "shaken_done": "R8 0525",
        "shaken_due": "R9 0525",
    },
    {
        "plate": "なにわ300あ8253",
        "type": "30系アルファード",
        "color": "白",
        "checks": [],
        "shaken_done": "R8 0525",
        "shaken_due": "R9 0525",
    },
    {
        "plate": "なにわ300あ7047",
        "type": "30系アルファード",
        "color": "黒",
        "first": "H27 08",
        "company": "R7 0304",
        "checks": ["R8 0303", "R8 0605"],
        "shaken_done": "R8 0303",
        "shaken_due": "R8 0303",
    },
    {
        "plate": "なにわ330い7707",
        "type": "40系アルファード",
        "color": "黒",
        "checks": [],
        "shaken_done": "R7 1223",
        "shaken_due": "R8 1223",
    },
    {
        "plate": "なにわ300あ7577",
        "type": "30系アルファード",
        "color": "黒",
        "first": "H29 06",
        "company": "R7 0805",
        "checks": ["R8 0410"],
        "shaken_done": "R7 0805",
        "shaken_due": "R8 0804",
    },
    {
        "plate": "なにわ300あ7286",
        "type": "30系アルファード",
        "color": "黒",
        "first": "H27 11",
        "company": "R7 0521",
        "checks": ["R8 0107", "R8 0514"],
        "shaken_done": "R7 0925",
        "shaken_due": "R8 0928",
    },
    {
        "plate": "なにわ300あ7312",
        "type": "ハイエース",
        "color": "銀",
        "first": "R2 01",
        "company": "R7 0529",
        "checks": ["R8 0106", "R8 0415", "R8 0706"],
        "shaken_done": "R8 0106",
        "shaken_due": "R9 0106",
    },
    {
        "plate": "なにわ300あ7621",
        "type": "ハイエース",
        "color": "白",
        "first": "R6 03",
        "company": "R7 0829",
        "checks": ["R8 0105", "R8 0313"],
        "shaken_done": "R7 0829",
        "shaken_due": "R8 0828",
    },
    {
        "plate": "なにわ300あ7634",
        "type": "ハイエース",
        "color": "白",
        "first": "R3 08",
        "company": "R7 0901",
        "checks": ["R8 0105", "R8 0401"],
        "shaken_done": "R7 0901",
        "shaken_due": "R8 0901",
    },
    {
        "plate": "なにわ300あ7689",
        "type": "ハイエース",
        "color": "白",
        "first": "R5 12",
        "company": "R7 0929",
        "checks": ["R8 0306"],
        "shaken_done": "R7 0929",
        "shaken_due": "R8 0929",
    },
    {
        "plate": "なにわ300あ6668",
        "type": "ハイエース",
        "color": "金",
        "first": "R5 11",
        "company": "R6 0805",
        "checks": ["R8 0127", "R8 0519"],
        "shaken_done": "R8 0804",
        "shaken_due": "R8 0804",
    },
    {
        "plate": "なにわ300あ8295",
        "type": "ハイエース",
        "color": "白",
        "checks": ["R8 0607"],
        "shaken_done": "R8 0607",
        "shaken_due": "R9 0608",
    },
    {
        "plate": "なにわ330う1007",
        "type": "キャラバン",
        "color": "黒",
        "checks": ["R8 0224"],
        "shaken_done": "R8 0224",
        "shaken_due": "R9 0224",
    },
    {
        "plate": "なにわ330か1008",
        "type": "キャラバン",
        "color": "黒",
        "checks": ["R8 0224", "R8 0511"],
        "shaken_done": "R8 0224",
        "shaken_due": "R9 0224",
    },
]


def last_digits(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-4:] if digits else ""


def next_inspection_due(checks: list[str], shaken_due: str) -> str:
    if not checks:
        return ""
    last = max(era_date(item) for item in checks)
    year, month, day = map(int, last.split("-"))
    month += 3
    while month > 12:
        year += 1
        month -= 12
    return f"{year:04d}-{month:02d}-{day:02d}"


def upsert_vehicle(conn: sqlite3.Connection, item: dict[str, object]) -> int:
    plate = str(item["plate"])
    first = era_date(str(item.get("first") or "")) if item.get("first") else None
    company = era_date(str(item.get("company") or "")) if item.get("company") else None
    checks = [era_date(value) for value in item.get("checks", [])]
    last_inspection = max(checks) if checks else None
    next_due = next_inspection_due(list(item.get("checks", [])), str(item.get("shaken_due") or "")) or None
    shaken_due = era_date(str(item.get("shaken_due") or "")) if item.get("shaken_due") else None
    seats = 10 if item["type"] in {"ハイエース", "キャラバン"} else 7
    code = vehicle_type_code(str(item["type"]))
    plate_short = last_digits(plate)
    existing = conn.execute(
        """
        SELECT id
        FROM vehicles
        WHERE tenant_id = ? AND (plate_number = ? OR plate_no = ? OR plate_short_code = ?)
        ORDER BY CASE WHEN plate_number = ? THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        (TENANT_ID, plate, plate, plate_short, plate),
    ).fetchone()
    values = {
        "plate_no": plate,
        "plate_number": plate,
        "vehicle_type": item["type"],
        "vehicle_type_code": code,
        "plate_short_code": plate_short,
        "vehicle_color": item["color"],
        "seat_count": seats,
        "seats": seats,
        "status": "available",
        "maintenance_status": "normal",
        "first_registration_date": first,
        "company_registration_date": company,
        "last_inspection_date": last_inspection,
        "next_inspection_due_date": next_due,
        "inspection_expires_at": next_due,
        "shaken_due_date": shaken_due,
    }
    if existing:
        vehicle_id = int(existing["id"])
        assignments = ", ".join(f"{key} = ?" for key in values)
        conn.execute(
            f"UPDATE vehicles SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*values.values(), vehicle_id),
        )
    else:
        keys = ["tenant_id", *values.keys()]
        placeholders = ", ".join("?" for _ in keys)
        conn.execute(
            f"INSERT INTO vehicles ({', '.join(keys)}, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP)",
            (TENANT_ID, *values.values()),
        )
        vehicle_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    conn.execute(
        "DELETE FROM vehicle_inspection_records WHERE tenant_id = ? AND vehicle_id = ?",
        (TENANT_ID, vehicle_id),
    )
    for check in checks:
        conn.execute(
            """
            INSERT INTO vehicle_inspection_records (
                tenant_id, vehicle_id, inspection_type, inspection_date, source, note, updated_at
            )
            VALUES (?, ?, 'inspection', ?, 'daitora_2026_table', '3个月点检', CURRENT_TIMESTAMP)
            """,
            (TENANT_ID, vehicle_id, check),
        )
    if item.get("shaken_done"):
        conn.execute(
            """
            INSERT INTO vehicle_inspection_records (
                tenant_id, vehicle_id, inspection_type, inspection_date, source, note, updated_at
            )
            VALUES (?, ?, 'shaken', ?, 'daitora_2026_table', '车检', CURRENT_TIMESTAMP)
            """,
            (TENANT_ID, vehicle_id, era_date(str(item["shaken_done"]))),
        )
    return vehicle_id


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}")
    backup = DB_PATH.with_name(f"{DB_PATH.stem}_before_daitora_vehicle_update_{datetime.now():%Y%m%d_%H%M%S}.sqlite3")
    shutil.copy2(DB_PATH, backup)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        plates = {item["plate"] for item in VEHICLES}
        with conn:
            vehicle_ids = [upsert_vehicle(conn, item) for item in VEHICLES]
            placeholders = ", ".join("?" for _ in plates)
            conn.execute(
                f"""
                UPDATE vehicles
                SET status = 'deleted',
                    maintenance_status = 'retired',
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ?
                  AND plate_number NOT IN ({placeholders})
                """,
                (TENANT_ID, *plates),
            )
        active_count = conn.execute(
            "SELECT COUNT(*) AS total FROM vehicles WHERE tenant_id = ? AND status != 'deleted'",
            (TENANT_ID,),
        ).fetchone()["total"]
        print(f"backup={backup}")
        print(f"upserted={len(vehicle_ids)} active={active_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

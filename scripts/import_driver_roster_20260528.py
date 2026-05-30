from __future__ import annotations

from collections import Counter
import datetime as dt
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import hash_password  # noqa: E402


DB_PATHS = [
    ROOT_DIR / "runtime" / "wx_dispatch.sqlite3",
    ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3",
]

# Fields:
# external_id, office, name, license_due, license_no, residence_status,
# residence_due, health_due, health_remaining_days, phone, email
ROSTER = [
    ("12225", "\u672c\u793e", "\u59da\u535a", "20271217", "621003655831", "\u7279\u5b9a46\u53f7", "20261212", "20250904", 99, "090-6058-7891", ""),
    ("12232", "\u672c\u793e", "\u674e\u529b", "20280525", "639802801030", "\u6c38\u4f4f\u8005", "20280818", "20250709", 42, "080-4238-1388", ""),
    ("12266", "\u672c\u793e", "\u4e07\u5f37", "20280816", "621606151630", "", "20260329", "20260311", 287, "070-2303-6669", ""),
    ("12257", "\u672c\u793e", "\u590f\u5929\u5ffb", "20280324", "621606286300", "\u6c38\u4f4f\u8005", "20241205", "20250901", 96, "080-4034-1775", ""),
    ("12276", "\u672c\u793e", "\u5468\u4f1d\u6ce2", "20270112", "620807749110", "\u6c38\u4f4f\u8005", "20280608", "20260119", 236, "090-9613-8613", ""),
    ("12256", "\u672c\u793e", "\u59dc\u5c0f\u6d9b", "20281008", "540200072842", "\u6c38\u4f4f\u8005", "20300830", "20260227", 275, "070-8508-9919", ""),
    ("12314", "\u4eac\u90fd\u55b6\u696d\u6240", "\u9ad8\u5f18\u5f3a", "20290602", "611901171530", "\u6c38\u4f4f\u8005", "20290401", "20260303", 279, "080-4867-0502", "2279abqy@gmail.com"),
    ("12325", "\u672c\u793e", "\u674e\u6210\u5fd7", "20290904", "621203896240", "\u6c38\u4f4f\u8005", "20280303", "20250904", 99, "080-4647-9188", ""),
    ("12306", "\u672c\u793e", "\u738b\u5553\u8d85", "20270706", "622105430700", "\u6c38\u4f4f\u8005", "20320128", "20260109", 226, "090-4273-9895", ""),
    ("12293", "\u672c\u793e", "\u5442\u96f2\u9f8d", "20280724", "501201004210", "\u6c38\u4f4f\u8005", "20260522", "20250806", 70, "080-2952-0888", ""),
    ("12251", "\u672c\u793e", "\u5148\u5c71\u6b66\u5fd7", "20280208", "629401872360", "\u65e5\u672c\u306e\u56fd\u7c4d", "", "20260308", 284, "090-7486-8828", ""),
    ("12289", "\u4eac\u90fd\u55b6\u696d\u6240", "\u767d\u77f3\u8ce2\u5fd7", "20270828", "621704881351", "\u6c38\u4f4f\u8005", "20301207", "20260310", 286, "070-2015-1485", "shiraishikenji728@gmail.com"),
    ("12341", "\u4eac\u90fd\u55b6\u696d\u6240", "\u5c71\u4e0b\u6d0b\u5b50", "20291130", "620902148413", "\u6c38\u4f4f\u8005", "20280126", "20250528", 0, "080-5328-6390", ""),
    ("12241", "\u4eac\u90fd\u55b6\u696d\u6240", "\u6731\u82f1\u5fc3", "20280710", "641700648690", "\u65e5\u672c\u4eba\u306e\u914d\u5076\u8005\u7b49", "20250904", "20251117", 173, "080-4566-0980", ""),
    ("12252", "\u672c\u793e", "\u8bb8\u6d77\u9f99", "20261221", "621805623090", "\u6c38\u4f4f\u8005", "20281216", "20260311", 287, "080-3111-6688", ""),
    ("12262", "\u672c\u793e", "\u5f35\u9298", "20271218", "620003022910", "\u6c38\u4f4f\u8005", "20260618", "20251207", 193, "080-4978-1170", ""),
    ("12328", "\u672c\u793e", "\u738b\u654f", "20290413", "621608015790", "\u65e5\u672c\u4eba\u306e\u914d\u5076\u8005\u7b49", "20271121", "20260323", 299, "090-9982-6098", ""),
    ("12203", "\u672c\u793e", "\u5cb8\u7530\u535a\u5149", "20290626", "628116647111", "\u65e5\u672c\u306e\u56fd\u7c4d", "", "20260420", 327, "080-3223-2454", ""),
    ("12346", "\u672c\u793e", "\u738b\u723d", "20260712", "621105256350", "\u6c38\u4f4f\u8005", "20300928", "20250414", -44, "070-1730-2084", ""),
    ("12230", "\u672c\u793e", "\u91d1\u8c37\u52c7\u8f1d", "20271221", "531400379970", "\u65e5\u672c\u306e\u56fd\u7c4d", "", "20250711", 44, "080-6366-6777", ""),
    ("12324", "\u672c\u793e", "\u5289\u665f", "20270825", "621704110190", "\u5b9a\u4f4f\u8005", "20280714", "20260321", 297, "070-7589-4639", ""),
    ("12231", "\u672c\u793e", "\u5510\u6d0b\u6d32", "20280602", "621700911380", "\u6c38\u4f4f\u8005", "20410805", "20250804", 68, "090-3281-6298", ""),
    ("12308", "\u672c\u793e", "\u694a\u6b63\u5143", "20270705", "621600556560", "\u6c38\u4f4f\u8005", "20310611", "2026029", 277, "090-4290-1058", ""),
    ("12320", "\u672c\u793e", "\u9673\u9234", "20280930", "621405439560", "\u6c38\u4f4f\u8005", "20321026", "20260108", 225, "080-4234-6276", ""),
    ("12311", "\u672c\u793e", "\u90dd\u5b97\u7af9", "20270510", "621507195640", "\u6c38\u4f4f\u8005", "20300224", "20251007", 132, "080-8346-3810", ""),
    ("12351", "\u672c\u793e", "\u90b5\u9cf4", "20290622", "618708096452", "\u6c38\u4f4f\u8005", "20290205", "20250714", 47, "080-5636-5922", "2029/2/5"),
    ("12310", "\u672c\u793e", "\u97d3\u671d\u65b0", "20290704", "621605361070", "\u6c38\u4f4f\u8005", "20251121", "20250828", 92, "070-2637-7966", "2026/11/21"),
    ("12327", "\u672c\u793e", "\u694a\u5897\u798f", "20291212", "62140042831", "\u6c38\u4f4f\u8005", "20300921", "20250411", -47, "070-1828-6888", ""),
    ("12283", "\u672c\u793e", "\u5176\u582f", "20280228", "440905034530", "\u6c38\u4f4f\u8005", "20290901", "20250905", 100, "080-3545-0199", ""),
    ("12315", "\u672c\u793e", "\u694a\u5065\u6ce2", "20270901", "631303020600", "\u6c38\u4f4f\u8005\u306e\u914d\u5076\u8005\u7b49", "20270410", "20250822", 86, "080-2450-2988", ""),
    ("12279", "\u672c\u793e", "\u674e\u5409\u6b66", "20270809", "611202367321", "\u6c38\u4f4f\u8005\u306e\u914d\u5076\u8005\u7b49", "20250417", "20260130", 247, "080-3034-7888", ""),
    ("12302", "\u672c\u793e", "\u8c37\u53e3\uff08\u5f35\uff09\u5ef6\u747e", "20290426", "649401350420", "\u6c38\u4f4f\u8005", "20280202", "20251126", 182, "080-4768-0127", ""),
    ("12355", "\u672c\u793e", "\u798f\u7530\u5f18\u4e00", "20300610", "620708130980", "\u65e5\u672c\u306e\u56fd\u7c4d", "", "20251010", 135, "090-8523-5658", ""),
    ("12316", "\u672c\u793e", "\u5f35\u6c38", "20290802", "621904517000", "\u6c38\u4f4f\u8005", "20310221", "20260212", 260, "080-2543-3838", ""),
    ("12344", "\u672c\u793e", "\u8d99\u6893\u7476", "20290505", "622005693990", "\u65e5\u672c\u4eba\u306e\u914d\u5076\u8005\u7b49", "20301205", "20260509", 346, "080-8296-2017", ""),
    ("12342", "\u672c\u793e", "\u6edd\u6fa4\u96c5\u79be", "20291104", "301707356051", "\u65e5\u672c\u7c4d", "", "20250630", 33, "070-9188-5588", ""),
    ("12291", "\u672c\u793e", "\u675c\u4f9d\u8ed2", "20290119", "621100778371", "\u6c38\u4f4f\u8005", "20280210", "20251112", 168, "090-8525-9979", ""),
    ("12334", "\u672c\u793e", "\u738b\u5049\u5175", "20261119", "620802117971", "\u6c38\u4f4f\u8005", "20301208", "20260311", 287, "070-8976-5430", ""),
    ("12332", "\u672c\u793e", "\u674e\u6ca2\u6d69", "20290422", "621603829910", "\u6c38\u4f4f\u8005", "20280330", "20260327", 303, "080-4237-5207", ""),
    ("12358", "\u672c\u793e", "\u683e\u51b2", "20290804", "621700653150", "\u6c38\u4f4f\u8005", "20310912", "20260512", 349, "080-3821-7822", ""),
    ("12358", "\u672c\u793e", "\u5468\u653f", "20290608", "621803599290", "\u6c38\u4f4f\u8005", "20300628", "20250513", -15, "080-4182-6999", ""),
]


def normalize_phone(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def parse_date(value: str) -> str | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    if "/" in text:
        parts = [int(part) for part in text.split("/") if part]
        if len(parts) == 3:
            return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    digits = normalize_phone(text)
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) == 7:
        return f"{digits[:4]}-{digits[4:6]}-{int(digits[6:]):02d}"
    return None


def find_user_by_phone(conn: sqlite3.Connection, normalized: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE tenant_id = 1
          AND (
              REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
              OR REPLACE(REPLACE(REPLACE(COALESCE(username, ''), '-', ''), ' ', ''), '+', '') = ?
          )
        ORDER BY is_active DESC, id ASC
        LIMIT 1
        """,
        (normalized, normalized),
    ).fetchone()


def unique_username(conn: sqlite3.Connection, normalized: str, current_user_id: int | None = None) -> str:
    username = normalized
    suffix = 1
    while True:
        row = conn.execute("SELECT id FROM users WHERE tenant_id = 1 AND username = ?", (username,)).fetchone()
        if not row or (current_user_id and int(row["id"]) == int(current_user_id)):
            return username
        suffix += 1
        username = f"{normalized}-{suffix}"


def find_driver(
    conn: sqlite3.Connection,
    normalized: str,
    external_id: str,
    external_id_counts: Counter[str],
) -> sqlite3.Row | None:
    existing = conn.execute(
        """
        SELECT *
        FROM drivers
        WHERE tenant_id = 1
          AND REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (normalized,),
    ).fetchone()
    if existing or not external_id or external_id_counts[external_id] != 1:
        return existing
    return conn.execute(
        "SELECT * FROM drivers WHERE tenant_id = 1 AND driver_external_id = ? ORDER BY id ASC LIMIT 1",
        (external_id,),
    ).fetchone()


def import_db(path: Path, external_id_counts: Counter[str]) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    phones: list[str] = []
    upserted = 0
    for (
        external_id,
        office,
        name,
        license_due,
        license_no,
        residence_status,
        residence_due,
        health_due,
        health_remaining,
        phone,
        email,
    ) in ROSTER:
        normalized = normalize_phone(phone)
        if not normalized:
            continue
        phones.append(normalized)
        existing = find_driver(conn, normalized, external_id, external_id_counts)
        payload = {
            "name": name,
            "phone": phone,
            "office": office,
            "driver_external_id": external_id,
            "license_due_date": parse_date(license_due),
            "license_expires_at": parse_date(license_due),
            "license_number": license_no,
            "residence_status": residence_status,
            "residence_due_date": parse_date(residence_due),
            "health_check_due_date": parse_date(health_due),
            "medical_check_expires_at": parse_date(health_due),
            "health_check_remaining_days": health_remaining,
            "email": email if "@" in email else None,
            "status": "available",
            "driver_status": "available",
        }
        if existing:
            driver_id = int(existing["id"])
            driver_code = existing["driver_code"]
            conn.execute(
                """
                UPDATE drivers
                SET name = :name,
                    phone = :phone,
                    office = :office,
                    driver_external_id = :driver_external_id,
                    license_due_date = :license_due_date,
                    license_expires_at = :license_expires_at,
                    license_number = :license_number,
                    residence_status = :residence_status,
                    residence_due_date = :residence_due_date,
                    health_check_due_date = :health_check_due_date,
                    medical_check_expires_at = :medical_check_expires_at,
                    health_check_remaining_days = :health_check_remaining_days,
                    email = :email,
                    status = :status,
                    driver_status = :driver_status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id AND tenant_id = 1
                """,
                {**payload, "id": driver_id},
            )
        else:
            driver_code = None
            cursor = conn.execute(
                """
                INSERT INTO drivers (
                    tenant_id, name, phone, office, driver_external_id,
                    license_due_date, license_expires_at, license_number,
                    residence_status, residence_due_date,
                    health_check_due_date, medical_check_expires_at,
                    health_check_remaining_days, email, status, driver_status, updated_at
                )
                VALUES (
                    1, :name, :phone, :office, :driver_external_id,
                    :license_due_date, :license_expires_at, :license_number,
                    :residence_status, :residence_due_date,
                    :health_check_due_date, :medical_check_expires_at,
                    :health_check_remaining_days, :email, :status, :driver_status, CURRENT_TIMESTAMP
                )
                """,
                payload,
            )
            driver_id = int(cursor.lastrowid)
        user = find_user_by_phone(conn, normalized)
        password = normalized[-6:]
        if user:
            username = unique_username(conn, normalized, int(user["id"]))
            conn.execute(
                """
                UPDATE users
                SET username = ?,
                    password_hash = ?,
                    role = 'driver',
                    display_name = ?,
                    phone = ?,
                    profile_type = 'driver',
                    profile_id = ?,
                    is_active = 1,
                    password_changed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = 1 AND id = ?
                """,
                (username, hash_password(password), name, phone, driver_id, user["id"]),
            )
            user_id = int(user["id"])
        else:
            username = unique_username(conn, normalized)
            conn.execute(
                """
                INSERT INTO users (
                    tenant_id, username, password_hash, role, display_name, phone,
                    profile_type, profile_id, wx_bind_status, is_active,
                    password_changed_at, updated_at
                )
                VALUES (1, ?, ?, 'driver', ?, ?, 'driver', ?, 'unbound', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (username, hash_password(password), name, phone, driver_id),
            )
            user_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        conn.execute(
            """
            UPDATE drivers
            SET user_id = ?, driver_code = COALESCE(driver_code, ?), updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = 1 AND id = ?
            """,
            (user_id, driver_code, driver_id),
        )
        upserted += 1

    placeholders = ",".join("?" for _ in phones)
    conn.execute(
        f"""
        UPDATE drivers
        SET status = 'deleted', driver_status = 'deleted', updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = 1
          AND REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') NOT IN ({placeholders})
        """,
        phones,
    )
    conn.execute(
        f"""
        UPDATE users
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = 1
          AND profile_type = 'driver'
          AND REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), '-', ''), ' ', ''), '+', '') NOT IN ({placeholders})
        """,
        phones,
    )
    conn.commit()
    active = conn.execute(
        "SELECT COUNT(*) AS c FROM drivers WHERE tenant_id = 1 AND COALESCE(status, '') != 'deleted'"
    ).fetchone()["c"]
    accounts = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE tenant_id = 1 AND profile_type = 'driver' AND is_active = 1"
    ).fetchone()["c"]
    print(f"{path}: upserted={upserted} active_drivers={active} active_driver_accounts={accounts}")
    conn.close()


def main() -> None:
    external_id_counts = Counter(item[0] for item in ROSTER if item[0])
    for path in DB_PATHS:
        import_db(path, external_id_counts)


if __name__ == "__main__":
    main()

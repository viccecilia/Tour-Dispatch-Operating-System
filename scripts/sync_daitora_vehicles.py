from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.resource_library_service import list_resource_library


DB_PATH = "runtime/wx_dispatch.sqlite3"
TARGET_TENANT_ID = 1


def vehicle_type_code(name: str) -> str:
    text = (name or "").lower()
    if "hiace" in text or "ハイエース" in text:
        return "hiace"
    if "alphard" in text or "アルファ" in text:
        return "alphard"
    if "coaster" in text or "コースター" in text:
        return "coaster"
    return "vehicle"


def seat_count(name: str) -> int:
    code = vehicle_type_code(name)
    if code == "hiace":
        return 10
    if code == "alphard":
        return 6
    if code == "coaster":
        return 20
    return 0


def main() -> None:
    library = list_resource_library()
    rows = library.get("vehicles") or []
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    synced = 0
    skipped = 0
    with conn:
        for item in rows:
            plate = (item.get("plate_number") or "").strip()
            suffix = (item.get("suffix") or "").strip()
            if not plate:
                skipped += 1
                continue
            vtype = (item.get("vehicle_type") or "").strip()
            code = vehicle_type_code(vtype)
            seats = seat_count(vtype)
            existing = conn.execute(
                """
                SELECT id FROM vehicles
                WHERE tenant_id = ?
                  AND (
                    plate_number = ?
                    OR plate_no = ?
                    OR (plate_short_code <> '' AND plate_short_code = ?)
                  )
                LIMIT 1
                """,
                (TARGET_TENANT_ID, plate, plate, suffix),
            ).fetchone()
            payload = {
                "tenant_id": TARGET_TENANT_ID,
                "plate_number": plate,
                "plate_no": plate,
                "vehicle_type": vtype or code,
                "seat_count": seats,
                "seats": seats,
                "status": "available",
                "plate_short_code": suffix,
                "vehicle_type_code": code,
                "vehicle_color": "",
                "updated_at": now,
            }
            if existing:
                conn.execute(
                    """
                    UPDATE vehicles
                    SET plate_number = ?, plate_no = ?, vehicle_type = ?, seat_count = ?, seats = ?,
                        status = CASE WHEN COALESCE(status, '') IN ('deleted', 'retired') THEN status ELSE 'available' END,
                        plate_short_code = ?, vehicle_type_code = ?, updated_at = ?
                    WHERE tenant_id = ? AND id = ?
                    """,
                    (
                        payload["plate_number"],
                        payload["plate_no"],
                        payload["vehicle_type"],
                        payload["seat_count"],
                        payload["seats"],
                        payload["plate_short_code"],
                        payload["vehicle_type_code"],
                        payload["updated_at"],
                        TARGET_TENANT_ID,
                        existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO vehicles (
                        tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status,
                        plate_short_code, vehicle_type_code, vehicle_color,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["tenant_id"],
                        payload["plate_no"],
                        payload["plate_number"],
                        payload["vehicle_type"],
                        payload["seats"],
                        payload["seat_count"],
                        payload["status"],
                        payload["plate_short_code"],
                        payload["vehicle_type_code"],
                        payload["vehicle_color"],
                        now,
                        now,
                    ),
                )
            synced += 1
    print({"tenant_id": TARGET_TENANT_ID, "synced": synced, "skipped": skipped, "library_summary": library.get("summary")})


if __name__ == "__main__":
    main()

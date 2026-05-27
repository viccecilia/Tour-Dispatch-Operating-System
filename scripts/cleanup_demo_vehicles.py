import os
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    from backend.config import DB_PATH

    db_path = Path(os.environ.get("WX_DISPATCH_DB", DB_PATH)).resolve()
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        before = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        rows = conn.execute(
            """
            SELECT id, COALESCE(NULLIF(plate_number, ''), plate_no, '') AS plate
            FROM vehicles
            WHERE tenant_id = 1
            """
        ).fetchall()
        delete_ids = [row["id"] for row in rows if not str(row["plate"] or "").startswith("なにわ")]
        if delete_ids:
            placeholders = ",".join(["?"] * len(delete_ids))
            conn.execute(f"DELETE FROM vehicles WHERE id IN ({placeholders})", delete_ids)
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        plates = [
            row[0]
            for row in conn.execute(
                "SELECT COALESCE(NULLIF(plate_number, ''), plate_no, '') FROM vehicles WHERE tenant_id = 1 ORDER BY id"
            ).fetchall()
        ]

    print(f"database={db_path}")
    print(f"vehicles_before={before}")
    print(f"vehicles_deleted={len(delete_ids)}")
    print(f"vehicles_after={after}")
    print("remaining_plates=" + ", ".join(plates))


if __name__ == "__main__":
    main()

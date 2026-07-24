from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import DB_PATH, RUNTIME_DIR
from backend.db.database import get_connection


ORDER_RUNTIME_TABLES = [
    "driver_evidence_uploads",
    "driver_expense_reports",
    "driver_reports",
    "driver_workflow_events",
    "location_logs",
    "incidents",
    "agency_order_change_requests",
    "auction_bids",
    "auction_listings",
    "assignments",
    "order_drafts",
    "orders",
    "travel_agency_guide_events",
    "travel_agency_marketplace_quotes",
    "travel_agency_marketplace_drafts",
    "travel_agency_orders",
    "travel_agency_audit_logs",
    "notifications",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset TourFlow test order runtime data while preserving drivers, vehicles, accounts, and company records.")
    parser.add_argument("--yes", action="store_true", help="Actually clear data. Without this flag the script only prints counts.")
    parser.add_argument("--no-backup", action="store_true", help="Skip sqlite backup before clearing.")
    args = parser.parse_args()

    before = table_counts()
    if not args.yes:
        print_report("dry_run", before, None)
        return

    backup_path = None if args.no_backup else backup_database()
    clear_tables()
    after = table_counts()
    print_report("cleared", before, after, backup_path)


def backup_database() -> Path:
    backup_dir = RUNTIME_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pre_reset_orders_{stamp}_{DB_PATH.name}"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def clear_tables() -> None:
    with get_connection() as conn:
        existing = existing_tables(conn)
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in ORDER_RUNTIME_TABLES:
            if table in existing:
                conn.execute(f"DELETE FROM {table}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()


def table_counts() -> dict[str, int]:
    with get_connection() as conn:
        existing = existing_tables(conn)
        return {
            table: int(conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
            for table in ORDER_RUNTIME_TABLES
            if table in existing
        }


def existing_tables(conn) -> set[str]:
    return {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }


def print_report(status: str, before: dict[str, int], after: dict[str, int] | None, backup_path: Path | None = None) -> None:
    print(f"status={status}")
    if backup_path:
        print(f"backup={backup_path}")
    print("table,before,after")
    for table, count in before.items():
        next_count = "" if after is None else after.get(table, 0)
        print(f"{table},{count},{next_count}")


if __name__ == "__main__":
    main()

import argparse
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


TRANSACTION_TABLES = [
    "audit_logs",
    "data_anomaly_scans",
    "notifications",
    "workflow_runs",
    "usage_events",
    "location_logs",
    "driver_reports",
    "assignments",
    "order_drafts",
    "incidents",
    "orders",
]

COUNT_TABLES = [
    "tenants",
    "users",
    "departments",
    "teams",
    "operator_profiles",
    "drivers",
    "vehicles",
    "agencies",
    "locations",
    "orders",
    "assignments",
    "order_drafts",
    "driver_reports",
    "audit_logs",
    "notifications",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a clean WX Dispatch trial database.")
    parser.add_argument(
        "--output",
        default=str(ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"),
        help="Trial database path. Defaults to runtime/trial/wx_dispatch_trial.sqlite3",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output file if it already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.overwrite:
        raise SystemExit(f"trial database already exists: {output}. Use --overwrite to replace it.")
    if output.exists():
        output.unlink()

    os.environ["WX_DISPATCH_DB"] = str(output)
    os.environ.setdefault("WX_DISPATCH_DEMO_MODE", "false")
    os.environ.setdefault("WX_DISPATCH_RESET_DEMO_ON_START", "false")

    from backend.db.database import get_connection, init_db, table_counts

    init_db(seed=True)
    with get_connection() as conn:
        for table in TRANSACTION_TABLES:
            if _table_exists(conn, table):
                conn.execute(f"DELETE FROM {table}")
        conn.commit()

    print(f"trial_database={output}")
    print(table_counts([table for table in COUNT_TABLES if _table_exists_in_runtime(table)]))
    print("trial_database_ready=true")


def _table_exists(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone() is not None


def _table_exists_in_runtime(table: str) -> bool:
    from backend.db.database import get_connection

    with get_connection() as conn:
        return _table_exists(conn, table)


if __name__ == "__main__":
    main()

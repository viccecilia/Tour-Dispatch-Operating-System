import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from backend.app.config import DB_PATH
from backend.db.database import init_db, table_counts
import demo_seed


TABLES = [
    "users",
    "drivers",
    "vehicles",
    "agencies",
    "locations",
    "orders",
    "assignments",
    "order_drafts",
    "driver_reports",
    "driver_evidence_uploads",
    "driver_workflow_events",
    "driver_expense_reports",
    "location_logs",
    "notifications",
]


def main() -> None:
    # Keep resource master data (drivers, vehicles, agencies, locations) intact.
    # demo_seed only clears runtime transaction tables and then loads recent real orders.
    init_db(seed=True)
    demo_seed.main()
    print(f"database={DB_PATH}")
    print(table_counts(TABLES))


if __name__ == "__main__":
    main()

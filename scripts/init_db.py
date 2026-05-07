from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import DB_PATH
from backend.db.database import init_db, table_counts


def main() -> None:
    init_db(seed=True)
    counts = table_counts(["users", "drivers", "vehicles", "agencies", "orders", "assignments", "order_drafts", "driver_reports"])
    print(f"database={DB_PATH}")
    print(counts)


if __name__ == "__main__":
    main()

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import BACKUP_DIR, DB_PATH, ensure_runtime_dirs


def main() -> None:
    ensure_runtime_dirs()
    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"wx_dispatch_{timestamp}.sqlite3"
    try:
        with sqlite3.connect(DB_PATH) as source, sqlite3.connect(backup_file) as target:
            source.backup(target)
    except sqlite3.Error:
        shutil.copy2(DB_PATH, backup_file)
    journal_file = backup_file.with_name(f"{backup_file.name}-journal")
    if journal_file.exists():
        try:
            journal_file.unlink()
        except PermissionError:
            pass
    print(backup_file)


if __name__ == "__main__":
    main()

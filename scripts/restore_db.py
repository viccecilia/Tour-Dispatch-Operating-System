import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import DB_PATH, ensure_runtime_dirs


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/restore_db.py <backup_file>")
    backup_file = Path(sys.argv[1]).resolve()
    if not backup_file.exists():
        raise SystemExit(f"backup not found: {backup_file}")
    ensure_runtime_dirs()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, DB_PATH)
    print(f"restored {backup_file} -> {DB_PATH}")


if __name__ == "__main__":
    main()

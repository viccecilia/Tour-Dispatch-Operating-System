import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRIAL_DB = ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"
BACKUP_DIR = ROOT_DIR / "runtime" / "backups" / "trial"


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not TRIAL_DB.exists():
        raise SystemExit(f"trial database not found: {TRIAL_DB}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"wx_dispatch_trial_{timestamp}.sqlite3"
    shutil.copy2(TRIAL_DB, backup_path)
    print(f"trial_backup={backup_path}")
    print("trial_backup_ready=true")


if __name__ == "__main__":
    main()

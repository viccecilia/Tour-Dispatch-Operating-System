import argparse
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRIAL_DB = ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore the internal-test trial SQLite database.")
    parser.add_argument("backup_file", help="Path to a trial backup sqlite3 file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backup_path = Path(args.backup_file).resolve()
    if not backup_path.exists():
        raise SystemExit(f"backup not found: {backup_path}")
    TRIAL_DB.parent.mkdir(parents=True, exist_ok=True)
    if TRIAL_DB.exists():
        TRIAL_DB.unlink()
    shutil.copy2(backup_path, TRIAL_DB)
    print(f"trial_restored={TRIAL_DB}")
    print("trial_restore_ready=true")


if __name__ == "__main__":
    main()

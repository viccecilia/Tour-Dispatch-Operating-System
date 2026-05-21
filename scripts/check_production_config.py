import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import (  # noqa: E402
    BACKUP_DIR,
    BASE_URL,
    DB_PATH,
    DEMO_MODE,
    HOST,
    JWT_SECRET,
    LOG_DIR,
    PORT,
    RESET_DEMO_ON_START,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check WX Dispatch production runtime configuration.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when production blockers are found.")
    args = parser.parse_args()

    checks = [
        ("host_configured", bool(HOST), f"host={HOST}"),
        ("port_configured", isinstance(PORT, int) and PORT > 0, f"port={PORT}"),
        ("base_url_configured", BASE_URL.startswith(("http://", "https://")), f"base_url={BASE_URL}"),
        ("database_path_configured", bool(DB_PATH), f"db={DB_PATH}"),
        ("log_dir_configured", bool(LOG_DIR), f"log_dir={LOG_DIR}"),
        ("backup_dir_configured", bool(BACKUP_DIR), f"backup_dir={BACKUP_DIR}"),
        ("demo_mode_disabled", DEMO_MODE is False, f"demo_mode={DEMO_MODE}"),
        ("reset_demo_disabled", RESET_DEMO_ON_START is False, f"reset_demo_on_start={RESET_DEMO_ON_START}"),
        ("jwt_secret_changed", JWT_SECRET != "wx-dispatch-demo-secret-change-me", "jwt_secret=***"),
        ("jwt_secret_length", len(JWT_SECRET) >= 24, "jwt_secret_length>=24"),
    ]

    failed = []
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            failed.append(name)

    if failed:
        print("production_config_blockers=" + ",".join(failed))
        if args.strict:
            raise SystemExit(1)
    else:
        print("production_config_ready=true")


if __name__ == "__main__":
    main()

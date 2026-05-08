import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import BASE_URL, DB_PATH


BASE = os.environ.get("WX_DISPATCH_BASE_URL", BASE_URL).rstrip("/")


def main() -> None:
    checks = [
        ("database", check_database),
        ("api", lambda: request_json("/api/ping").get("ok") is True),
        ("dashboard", lambda: request_text("/dashboard").startswith("<!doctype html>")),
        ("parser", lambda: "drafts" in request_json("/api/parser/drafts")),
        ("dispatch", lambda: "orders" in request_json("/api/dispatch/unassigned-orders")),
        ("calendar", lambda: request_json("/api/calendar/dispatch?view=day").get("ok") is True),
        ("driver", lambda: "assignments" in request_json("/api/driver/assignments?driver_id=1")),
    ]
    failed = []
    for name, fn in checks:
        try:
            ok = bool(fn())
        except Exception as exc:  # noqa: BLE001 - health output should show any runtime failure.
            ok = False
            print(f"[FAIL] {name}: {exc}")
        if ok:
            print(f"[OK] {name}")
        else:
            if name not in [item[0] for item in failed]:
                print(f"[FAIL] {name}")
            failed.append((name, "failed"))
    if failed:
        raise SystemExit(1)


def check_database() -> bool:
    return DB_PATH.exists() and DB_PATH.stat().st_size > 0


def request_json(path: str) -> dict:
    data = request_text(path)
    return json.loads(data)


def request_text(path: str) -> str:
    url = f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {body}") from exc


if __name__ == "__main__":
    main()

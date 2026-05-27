import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRIAL_DB = Path(os.environ.get("WX_DISPATCH_TRIAL_DB", ROOT_DIR / "runtime" / "trial" / "wx_dispatch_trial.sqlite3")).resolve()
BASE_URL = os.environ.get("WX_DISPATCH_TRIAL_BASE_URL", os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")).rstrip("/")
WEB_URL = os.environ.get("WX_DISPATCH_WEB_URL", "").rstrip("/")
TOKEN = ""


def main() -> None:
    checks = [
        ("trial_database", check_trial_database),
        ("api_ping", lambda: request_json("/api/ping").get("ok") is True),
        ("login_api", login),
        ("driver_api", lambda: "assignments" in request_json("/api/driver/assignments?driver_id=1")),
        ("dispatch_api", lambda: "orders" in request_json("/api/dispatch/unassigned-orders")),
        ("finance_api_admin", lambda: "orders" in request_json("/api/finance/ledger")),
    ]
    if WEB_URL:
        checks.append(("web_admin", lambda: request_text_url(WEB_URL, token=False) != ""))
    else:
        print("[SKIP] web_admin: set WX_DISPATCH_WEB_URL to check deployed React admin")

    failed = []
    for name, fn in checks:
        try:
            ok = bool(fn())
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"[FAIL] {name}: {exc}")
        if ok:
            print(f"[OK] {name}")
        else:
            print(f"[FAIL] {name}")
            failed.append(name)
    if failed:
        raise SystemExit(1)


def check_trial_database() -> bool:
    if not TRIAL_DB.exists() or TRIAL_DB.stat().st_size <= 0:
        return False
    with sqlite3.connect(TRIAL_DB) as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        drivers = conn.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
        vehicles = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    return users > 0 and drivers > 0 and vehicles >= 0


def request_json(path: str) -> dict:
    return json.loads(request_text(path))


def request_text(path: str) -> str:
    return request_text_url(f"{BASE_URL}{path}", token=True)


def request_text_url(url: str, token: bool = True) -> str:
    headers = {}
    if token and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {body}") from exc


def login() -> bool:
    global TOKEN
    payload = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        TOKEN = json.loads(response.read().decode("utf-8"))["token"]
    return bool(TOKEN)


if __name__ == "__main__":
    main()

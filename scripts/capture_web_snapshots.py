import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT_ROUND = os.environ.get("WX_DISPATCH_UI_ROUND", "R055")
FRONTEND_URL = os.environ.get("WX_DISPATCH_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
BACKEND_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
OUTPUT_DIR = ROOT_DIR / "docs" / "ui_snapshots" / SNAPSHOT_ROUND

PAGES = [
    ("dashboard", "web-dashboard.png"),
    ("dispatch", "web-dispatch.png"),
    ("calendar", "web-calendar.png"),
    ("driver-monitor", "web-driver-monitor.png"),
    ("finance", "web-finance.png"),
    ("analytics", "web-analytics.png"),
    ("automation", "web-automation.png"),
    ("settings", "web-settings.png"),
]


def login_token() -> str:
    payload = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
    request = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    token = data.get("token")
    if not token:
        raise RuntimeError("Login did not return token")
    return token


def wait_for_frontend() -> None:
    last_error = None
    for _ in range(20):
      try:
          with urllib.request.urlopen(FRONTEND_URL, timeout=3) as response:
              if response.status < 500:
                  return
      except Exception as exc:  # noqa: BLE001 - this is a startup probe.
          last_error = exc
      time.sleep(0.5)
    raise RuntimeError(f"Frontend is not reachable at {FRONTEND_URL}: {last_error}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wait_for_frontend()
    token = login_token()
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto(FRONTEND_URL, wait_until="domcontentloaded")
        page.evaluate("token => window.localStorage.setItem('wx_dispatch_token', token)", token)
        page.reload(wait_until="networkidle")

        for route, filename in PAGES:
            url = f"{FRONTEND_URL}/#{route}"
            target = OUTPUT_DIR / filename
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(300)
            page.screenshot(path=str(target), full_page=True)
            captured.append(str(target.relative_to(ROOT_DIR)))

        browser.close()

    print(json.dumps({"round": SNAPSHOT_ROUND, "output_dir": str(OUTPUT_DIR), "captured": captured}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - command output should show actionable reason.
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise

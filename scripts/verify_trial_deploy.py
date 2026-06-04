import argparse
import json
import shlex
import subprocess
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WEB_URL = "https://admin-trial.taxi-airport.jp"
DEFAULT_API_URL = "https://api-trial.taxi-airport.jp"
EXPECTED_TRIAL_DB = "runtime/trial/wx_dispatch_trial.sqlite3"


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "script" and attr_map.get("src"):
            self.assets.append(attr_map["src"] or "")
        if tag == "link" and attr_map.get("href"):
            self.assets.append(attr_map["href"] or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify TourFlow trial deployment after cloud upload.")
    parser.add_argument("--web-url", default=DEFAULT_WEB_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--remote-host", default="ubuntu@133.167.79.170")
    parser.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "tourflow_sakura_vps_ed25519"))
    parser.add_argument("--skip-remote", action="store_true", help="Skip SSH-based server checks.")
    args = parser.parse_args()

    checks = [
        ("api_ping", lambda: check_api_ping(args.api_url)),
        ("web_bundle_points_to_trial_api", lambda: check_web_bundle(args.web_url, args.api_url)),
        ("local_frontend_default_api", check_local_frontend_default_api),
        ("miniapp_dispatch_default_api", lambda: check_miniapp_api(ROOT_DIR / "miniapp_dispatch" / "utils" / "api.js")),
        ("miniapp_agency_default_api", lambda: check_miniapp_api(ROOT_DIR / "miniapp_agency" / "utils" / "api.js")),
        ("cloud_platform_login", lambda: check_platform_login(args.api_url)),
        ("cloud_carrier_admin_login", lambda: check_dispatch_mobile_login(args.api_url, "SKR-08070010000", "Test123456")),
        ("cloud_driver_login", lambda: check_dispatch_mobile_login(args.api_url, "SKR-08070010101", "Test123456")),
        ("cloud_agency_portal_login", lambda: check_agency_login(args.api_url, "AGA2026", "Test123456")),
        ("cloud_agency_guide_login", lambda: check_agency_login(args.api_url, "080-7101-0101", "Test123456")),
    ]
    if not args.skip_remote:
        checks.extend(
            [
                ("remote_api_env_is_trial", lambda: check_remote_env(args.remote_host, args.ssh_key)),
                ("remote_trial_db_has_accounts", lambda: check_remote_trial_db(args.remote_host, args.ssh_key)),
            ]
        )

    failed = []
    for name, fn in checks:
        try:
            detail = fn()
            ok = bool(detail)
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail = str(exc)
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            failed.append(name)

    if failed:
        print("trial_deploy_blockers=" + ",".join(failed))
        raise SystemExit(1)
    print("trial_deploy_ready=true")


def check_api_ping(api_url: str) -> str:
    payload = get_json(f"{api_url.rstrip('/')}/api/ping")
    if payload.get("ok") is not True:
        raise RuntimeError(f"unexpected ping payload: {payload}")
    return "api ping ok"


def check_web_bundle(web_url: str, api_url: str) -> str:
    web_url = web_url.rstrip("/")
    html = get_text(web_url + "/")
    parser = AssetParser()
    parser.feed(html)
    js_assets = [asset for asset in parser.assets if asset.endswith(".js")]
    if not js_assets:
        raise RuntimeError("no bundled js asset found")
    found_api = False
    found_origin_bug = False
    for asset in js_assets:
        asset_url = asset if asset.startswith("http") else f"{web_url}/{asset.lstrip('/')}"
        text = get_text(asset_url)
        found_api = found_api or api_url in text
        found_origin_bug = found_origin_bug or "window.location.origin" in text
    if not found_api:
        raise RuntimeError(f"bundle does not contain {api_url}")
    if found_origin_bug:
        raise RuntimeError("bundle still contains window.location.origin API fallback")
    return "hosted bundle contains trial API and no origin fallback"


def check_local_frontend_default_api() -> str:
    text = (ROOT_DIR / "frontend" / "src" / "services" / "apiClient.ts").read_text(encoding="utf-8")
    required = ['"http://127.0.0.1:18765"', '"https://api-trial.taxi-airport.jp"', "window.location.hostname"]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("missing " + ", ".join(missing))
    if "window.location.origin" in text:
        raise RuntimeError("apiClient.ts must not use window.location.origin as cloud API")
    return "frontend default API split is explicit"


def check_miniapp_api(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "https://api-trial.taxi-airport.jp" not in text:
        raise RuntimeError(f"{path} missing trial API")
    if "http://127.0.0.1:18765" not in text:
        raise RuntimeError(f"{path} missing local API for devtools")
    return f"{path.parent.parent.name} has trial and local API constants"


def check_platform_login(api_url: str) -> str:
    payload = post_json(f"{api_url.rstrip('/')}/api/auth/login", {"username": "admin", "password": "admin123"})
    if not payload.get("token"):
        raise RuntimeError("missing token")
    return "admin login ok"


def check_dispatch_mobile_login(api_url: str, login: str, password: str) -> str:
    payload = post_json(
        f"{api_url.rstrip('/')}/api/dispatch-mobile/login",
        {"login": login, "username": login, "password": password, "client_type": "miniapp"},
    )
    if not payload.get("token"):
        raise RuntimeError("missing token")
    return f"{login} login ok"


def check_agency_login(api_url: str, portal_code: str, password: str) -> str:
    payload = post_json(f"{api_url.rstrip('/')}/api/agency-portal/login", {"portal_code": portal_code, "password": password})
    if not payload.get("token") and not payload.get("agency_token"):
        raise RuntimeError("missing agency token")
    return f"{portal_code} login ok"


def check_remote_env(remote_host: str, ssh_key: str) -> str:
    command = (
        "cd /home/ubuntu/tourflow && "
        "printf 'db=' && WX_DISPATCH_ENV=trial python3 - <<'PY'\n"
        "from backend.config import DB_PATH, TRIAL_MODE, DEMO_MODE\n"
        "print(str(DB_PATH) + ' trial=' + str(TRIAL_MODE) + ' demo=' + str(DEMO_MODE))\n"
        "PY"
    )
    output = ssh(remote_host, ssh_key, command)
    if EXPECTED_TRIAL_DB not in output.replace("\\", "/"):
        raise RuntimeError(output)
    return output.strip().replace("\n", " ")


def check_remote_trial_db(remote_host: str, ssh_key: str) -> str:
    command = (
        "cd /home/ubuntu/tourflow && WX_DISPATCH_ENV=trial python3 - <<'PY'\n"
        "import sqlite3\n"
        "from backend.config import DB_PATH\n"
        "conn = sqlite3.connect(DB_PATH)\n"
        "cur = conn.cursor()\n"
        "users = cur.execute(\"SELECT COUNT(*) FROM users WHERE username IN ('SKR-08070010000','SKR-08070010101','admin')\").fetchone()[0]\n"
        "agencies = cur.execute(\"SELECT COUNT(*) FROM travel_agency_accounts WHERE password_seed='Test123456'\").fetchone()[0]\n"
        "print(f'db={DB_PATH} users={users} agency_accounts={agencies}')\n"
        "PY"
    )
    output = ssh(remote_host, ssh_key, command)
    if "users=3" not in output or "agency_accounts=" not in output:
        raise RuntimeError(output)
    return output.strip()


def ssh(remote_host: str, ssh_key: str, remote_command: str) -> str:
    completed = subprocess.run(
        ["ssh", "-i", ssh_key, remote_host, "bash -lc " + shlex.quote(remote_command)],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def get_json(url: str) -> dict:
    return json.loads(get_text(url))


def get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "tourflow-deploy-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {body}") from exc


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "tourflow-deploy-check/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {body}") from exc


if __name__ == "__main__":
    main()

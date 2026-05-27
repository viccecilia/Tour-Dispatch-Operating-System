import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from exc


def main() -> None:
    global TOKEN
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    target_date = date.today().isoformat()
    payload = request("GET", f"/api/attendance/daily?{urllib.parse.urlencode({'date': target_date})}")
    required_summary = {"total_drivers", "departed", "returned", "sleep_risk", "missing_report", "average_constraint_hours"}
    missing_summary = required_summary - set(payload.get("summary", {}))
    if missing_summary:
        raise AssertionError(f"attendance summary missing keys: {sorted(missing_summary)}")
    if not isinstance(payload.get("rows"), list):
        raise AssertionError("attendance rows must be a list")
    for row in payload["rows"]:
        for key in ["vehicle_plate", "driver_name", "depart_call_time", "depart_time", "return_time", "return_call_time", "constraint_hours", "sleep_risk_level"]:
            if key not in row:
                raise AssertionError(f"attendance row missing key: {key}")
    print(
        json.dumps(
            {
                "date": payload.get("date"),
                "row_count": len(payload.get("rows", [])),
                "summary": payload.get("summary"),
                "sample": payload.get("rows", [])[:2],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

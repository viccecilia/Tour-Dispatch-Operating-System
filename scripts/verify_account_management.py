import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import get_connection, init_db
from backend.services.auth_service import phone_password_tail


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")


def request(method: str, path: str, payload: dict | None = None, token: str = "") -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            result = json.loads(body) if body else {}
            result["_status"] = response.status
            return result
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError:
            result = {"error": body}
        result["_status"] = exc.code
        return result


def assert_ok(name: str, condition: bool, detail: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def phone_tail(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())[-6:]


def prepare_driver(phone: str, suffix: str) -> int:
    init_db(seed=True)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO drivers (tenant_id, name, phone, status, driver_status, updated_at)
            VALUES (1, ?, ?, 'available', 'available', CURRENT_TIMESTAMP)
            """,
            (f"R071测试司机{suffix}", phone),
        )
        conn.commit()
        return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])


def main() -> None:
    tail_cases = {
        "08046447554": "447554",
        "080-4644-7554": "447554",
        "090-6058-7891": "587891",
        "090 6058 7891": "587891",
    }
    for phone, expected in tail_cases.items():
        assert_ok(f"phone_tail_{phone}", phone_tail(phone) == expected, {"phone": phone, "expected": expected, "actual": phone_tail(phone)})
        assert_ok(
            f"canonical_phone_password_tail_{phone}",
            phone_password_tail(phone) == expected,
            {"phone": phone, "expected": expected, "actual": phone_password_tail(phone)},
        )

    suffix = str(int(time.time()))[-6:]
    phones = {
        "dispatcher": f"090-81-{suffix}",
        "ops": f"090-82-{suffix}",
        "driver": f"090-83-{suffix}",
    }
    driver_id = prepare_driver(phones["driver"], suffix)

    admin_login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    assert_ok("admin_login", admin_login.get("_status") == 200 and admin_login.get("token"), admin_login)
    admin_token = admin_login["token"]

    overview = request("GET", "/api/accounts/overview", token=admin_token)
    assert_ok("admin_overview", overview.get("_status") == 200 and "roles" in overview, overview)

    dispatcher = request(
        "POST",
        "/api/accounts",
        {"role": "dispatcher", "display_name": f"R071调度{suffix}", "phone": phones["dispatcher"]},
        token=admin_token,
    )
    ops = request(
        "POST",
        "/api/accounts",
        {"role": "operations_manager", "display_name": f"R071运行{suffix}", "phone": phones["ops"]},
        token=admin_token,
    )
    driver = request(
        "POST",
        "/api/accounts",
        {"role": "driver", "display_name": f"R071司机{suffix}", "phone": phones["driver"]},
        token=admin_token,
    )
    assert_ok("create_dispatcher", dispatcher.get("_status") == 201 and dispatcher["account"]["role"] == "dispatcher", dispatcher)
    assert_ok("create_ops", ops.get("_status") == 201 and ops["account"]["role"] == "operations_manager", ops)
    assert_ok("create_driver", driver.get("_status") == 201 and int(driver["account"]["profile_id"]) == driver_id, driver)

    missing_driver = request(
        "POST",
        "/api/accounts",
        {"role": "driver", "display_name": "No Driver", "phone": f"090-84-{suffix}"},
        token=admin_token,
    )
    assert_ok("driver_must_match_phone", missing_driver.get("_status") == 400 and missing_driver.get("error") == "driver_phone_not_preloaded", missing_driver)

    dispatcher_login = request(
        "POST",
        "/api/auth/login-phone",
        {"phone": phones["dispatcher"], "password": phone_tail(phones["dispatcher"]), "client_type": "web"},
    )
    ops_login = request(
        "POST",
        "/api/auth/login-phone",
        {"phone": phones["ops"], "password": phone_tail(phones["ops"]), "client_type": "web"},
    )
    assert_ok("dispatcher_login_tail", dispatcher_login.get("_status") == 200, dispatcher_login)
    assert_ok("ops_login_tail", ops_login.get("_status") == 200, ops_login)

    dispatcher_overview = request("GET", "/api/accounts/overview", token=dispatcher_login["token"])
    ops_overview = request("GET", "/api/accounts/overview", token=ops_login["token"])
    assert_ok("dispatcher_no_account_management", dispatcher_overview.get("_status") == 403, dispatcher_overview)
    assert_ok("ops_no_account_management", ops_overview.get("_status") == 403, ops_overview)

    admin_finance = request("GET", "/api/finance/summary", token=admin_token)
    dispatcher_finance = request("GET", "/api/finance/summary", token=dispatcher_login["token"])
    ops_finance = request("GET", "/api/finance/summary", token=ops_login["token"])
    assert_ok("admin_finance", admin_finance.get("_status") == 200, admin_finance)
    assert_ok("dispatcher_no_finance", dispatcher_finance.get("_status") == 403, dispatcher_finance)
    assert_ok("ops_no_finance", ops_finance.get("_status") == 403, ops_finance)

    bind = request(
        "POST",
        "/api/auth/login-phone",
        {
            "phone": phones["dispatcher"],
            "password": phone_tail(phones["dispatcher"]),
            "wx_openid": f"wx_r071_{suffix}",
            "client_type": "dispatch_miniapp",
        },
    )
    assert_ok("miniapp_wechat_bind", bind.get("_status") == 200 and bind["user"]["wx_bind_status"] == "bound", bind)

    reset = request("POST", f"/api/accounts/{dispatcher['account']['id']}/reset-password", token=admin_token)
    assert_ok("reset_password", reset.get("_status") == 200, reset)
    unbind = request("POST", f"/api/accounts/{dispatcher['account']['id']}/unbind-wechat", token=admin_token)
    assert_ok("unbind_wechat", unbind.get("_status") == 200 and unbind["account"]["wx_bind_status"] == "unbound", unbind)

    role_update = request(
        "PUT",
        f"/api/accounts/{ops['account']['id']}",
        {"role": "dispatcher"},
        token=admin_token,
    )
    assert_ok("role_update", role_update.get("_status") == 200 and role_update["account"]["role"] == "dispatcher", role_update)

    disable = request("POST", f"/api/accounts/{dispatcher['account']['id']}/disable", token=admin_token)
    assert_ok("disable_account", disable.get("_status") == 200 and not disable["account"]["is_active"], disable)
    disabled_login = request(
        "POST",
        "/api/auth/login-phone",
        {"phone": phones["dispatcher"], "password": phone_tail(phones["dispatcher"]), "client_type": "web"},
    )
    assert_ok("disabled_cannot_login", disabled_login.get("_status") == 401, disabled_login)

    overview_after = request("GET", "/api/accounts/overview", token=admin_token)
    role_names = {item["role"] for item in overview_after.get("roles", [])}
    assert_ok("overview_role_cards", {"admin", "dispatcher", "operations_manager", "driver"}.issubset(role_names), overview_after)

    with get_connection() as conn:
        audit_count = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM audit_logs
            WHERE action IN ('account_create', 'account_update', 'account_disable', 'password_reset', 'wechat_unbind')
              AND created_at >= datetime('now', '-10 minutes')
            """
        ).fetchone()["c"]
    assert_ok("account_audit_logs", audit_count >= 5, audit_count)

    print(
        json.dumps(
            {
                "ok": True,
                "created": {
                    "dispatcher": dispatcher["account"]["id"],
                    "operations_manager": ops["account"]["id"],
                    "driver": driver["account"]["id"],
                },
                "driver_id": driver_id,
                "role_cards": sorted(role_names),
                "audit_count": audit_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

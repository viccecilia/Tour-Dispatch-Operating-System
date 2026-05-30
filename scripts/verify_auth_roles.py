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

from backend.db.database import get_connection, hash_password, init_db


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


def assert_true(name: str, condition: bool, detail: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def prepare_profiles() -> dict:
    init_db(seed=True)
    suffix = str(int(time.time()))[-6:]
    phones = {
        "driver": f"090-70-{suffix}",
        "driver_other": f"090-71-{suffix}",
        "dispatcher": f"090-72-{suffix}",
        "ops": f"090-73-{suffix}",
        "admin": f"090-74-{suffix}",
    }
    with get_connection() as conn:
        for key in ("driver", "driver_other"):
            conn.execute(
                """
                INSERT INTO drivers (tenant_id, name, phone, status, driver_status, updated_at)
                VALUES (1, ?, ?, 'available', 'available', CURRENT_TIMESTAMP)
                """,
                (f"R070验证司机-{key}-{suffix}", phones[key]),
            )
        for role, key, name in [
            ("dispatcher", "dispatcher", "R070验证调度"),
            ("operations_manager", "ops", "R070验证运行管理"),
            ("admin", "admin", "R070验证管理"),
        ]:
            username = f"r070_{role}_{suffix}"
            conn.execute(
                """
                INSERT INTO users (
                    tenant_id, username, password_hash, role, display_name, phone,
                    is_active, wx_bind_status, updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, 0, 'unbound', CURRENT_TIMESTAMP)
                """,
                (username, hash_password("inactive"), role, name, phones[key]),
            )
            user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute(
                """
                INSERT INTO operator_profiles (tenant_id, user_id, title, phone, invite_status, updated_at)
                VALUES (1, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                """,
                (user_id, role, phones[key]),
            )
        conn.commit()
        driver = conn.execute("SELECT * FROM drivers WHERE phone = ?", (phones["driver"],)).fetchone()
        other_driver = conn.execute("SELECT * FROM drivers WHERE phone = ?", (phones["driver_other"],)).fetchone()
    return {"phones": phones, "driver_id": driver["id"], "other_driver_id": other_driver["id"], "suffix": suffix}


def register(phone: str, role: str, password: str, wx_openid: str = "", client_type: str = "web") -> dict:
    return request(
        "POST",
        "/api/auth/register",
        {
            "phone": phone,
            "password": password,
            "role": role,
            "wx_openid": wx_openid,
            "client_type": client_type,
        },
    )


def main() -> None:
    setup = prepare_profiles()
    phones = setup["phones"]

    ping = request("GET", "/api/ping")
    assert_true("ping", ping.get("ok") is True, ping)

    unknown = register("099-0000-0000", "driver", "pass123", "wx_unknown", "driver_miniapp")
    assert_true("unknown_phone_rejected", unknown.get("_status") == 400 and unknown.get("error") == "driver_phone_not_preloaded", unknown)

    driver_reg = register(phones["driver"], "driver", "driverPass1", "wx_driver_1", "driver_miniapp")
    assert_true("driver_register", driver_reg.get("_status") == 201 and driver_reg["user"]["role"] == "driver", driver_reg)
    assert_true("driver_profile_bound", int(driver_reg["user"]["profile_id"]) == int(setup["driver_id"]), driver_reg)

    driver_login = request("POST", "/api/auth/login-phone", {"phone": phones["driver"], "password": "driverPass1", "wx_openid": "wx_driver_1", "client_type": "driver_miniapp"})
    assert_true("driver_login_same_wechat", driver_login.get("_status") == 200, driver_login)
    mismatch = request("POST", "/api/auth/login-phone", {"phone": phones["driver"], "password": "driverPass1", "wx_openid": "wx_other", "client_type": "driver_miniapp"})
    assert_true("driver_wechat_mismatch", mismatch.get("_status") == 401 and mismatch.get("error") == "wechat_binding_mismatch", mismatch)

    dispatcher_reg = register(phones["dispatcher"], "dispatcher", "dispatcherPass1", "wx_dispatcher_1", "dispatch_miniapp")
    ops_reg = register(phones["ops"], "operations_manager", "opsPass1", "wx_ops_1", "dispatch_miniapp")
    admin_reg = register(phones["admin"], "admin", "adminPass1", "", "web")
    assert_true("dispatcher_register", dispatcher_reg.get("_status") == 201 and dispatcher_reg["user"]["role"] == "dispatcher", dispatcher_reg)
    assert_true("ops_register", ops_reg.get("_status") == 201 and ops_reg["user"]["role"] == "operations_manager", ops_reg)
    assert_true("admin_register", admin_reg.get("_status") == 201 and admin_reg["user"]["role"] == "admin", admin_reg)

    web_admin_login = request("POST", "/api/auth/login-phone", {"phone": phones["admin"], "password": "adminPass1", "client_type": "web"})
    assert_true("web_admin_without_wechat", web_admin_login.get("_status") == 200, web_admin_login)

    admin_token = web_admin_login["token"]
    dispatcher_token = dispatcher_reg["token"]
    ops_token = ops_reg["token"]
    driver_token = driver_login["token"]

    admin_finance = request("GET", "/api/finance/summary", token=admin_token)
    dispatcher_finance = request("GET", "/api/finance/summary", token=dispatcher_token)
    ops_finance = request("GET", "/api/finance/summary", token=ops_token)
    assert_true("admin_finance_allowed", admin_finance.get("_status") == 200, admin_finance)
    assert_true("dispatcher_finance_forbidden", dispatcher_finance.get("_status") == 403, dispatcher_finance)
    assert_true("ops_finance_forbidden", ops_finance.get("_status") == 403, ops_finance)

    ops_drivers = request("GET", "/api/resources/drivers", token=ops_token)
    ops_locations = request("GET", "/api/fleet/latest-locations", token=ops_token)
    assert_true("ops_resources_allowed", ops_drivers.get("_status") == 200 and "drivers" in ops_drivers, ops_drivers)
    assert_true("ops_map_allowed", ops_locations.get("_status") == 200, ops_locations)

    own_profile = request("GET", f"/api/driver/profile?driver_id={setup['other_driver_id']}", token=driver_token)
    assert_true("driver_forced_to_own_profile", int(own_profile.get("driver", {}).get("id") or 0) == int(setup["driver_id"]), own_profile)
    assert_true("driver_profile_no_price", "price" not in json.dumps(own_profile, ensure_ascii=False).lower(), own_profile)

    reset = request("POST", "/api/auth/admin/reset-password", {"user_id": dispatcher_reg["user"]["id"]}, token=admin_token)
    assert_true("password_reset", reset.get("_status") == 200, reset)
    tail = "".join(ch for ch in phones["dispatcher"] if ch.isdigit())[-6:]
    dispatcher_tail_login = request("POST", "/api/auth/login-phone", {"phone": phones["dispatcher"], "password": tail, "wx_openid": "wx_dispatcher_1", "client_type": "dispatch_miniapp"})
    assert_true("password_reset_login", dispatcher_tail_login.get("_status") == 200, dispatcher_tail_login)

    unbound = request("POST", "/api/auth/admin/unbind-wechat", {"user_id": driver_reg["user"]["id"]}, token=admin_token)
    assert_true("admin_unbind_wechat", unbound.get("_status") == 200 and unbound["user"]["wx_bind_status"] == "unbound", unbound)
    rebound = request("POST", "/api/auth/login-phone", {"phone": phones["driver"], "password": "driverPass1", "wx_openid": "wx_driver_2", "client_type": "driver_miniapp"})
    assert_true("driver_rebind_wechat", rebound.get("_status") == 200 and rebound["user"]["wx_bind_status"] == "bound", rebound)

    with get_connection() as conn:
        audit_count = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM audit_logs
            WHERE action IN ('register_bind', 'wechat_bind', 'wechat_binding_mismatch', 'wechat_unbind', 'password_reset')
            """
        ).fetchone()["c"]
    assert_true("audit_written", audit_count >= 5, audit_count)

    print(
        json.dumps(
            {
                "ok": True,
                "driver_user": driver_reg["user"]["id"],
                "dispatcher_user": dispatcher_reg["user"]["id"],
                "ops_user": ops_reg["user"]["id"],
                "admin_user": admin_reg["user"]["id"],
                "wechat_mismatch_status": mismatch.get("_status"),
                "audit_count": audit_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

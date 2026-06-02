from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.database import get_connection, hash_password, init_db  # noqa: E402
from backend.services.auth_service import company_login_name  # noqa: E402
from backend.services.company_registration_service import create_company_registration, list_company_registrations  # noqa: E402
from backend.services.tenant_context import set_current_tenant_id  # noqa: E402
from backend.services.travel_agency_service import ROLE_MATRIX, ensure_travel_agency_schema  # noqa: E402


PASSWORD = "Test123456"
AGENCY_PORTAL_PASSWORD = "Test123456"
RESULT_PATH = ROOT / "runtime" / "task_results" / "TEST_ACCOUNTS.json"
REPORT_PATH = ROOT / "runtime" / "task_results" / "TEST_ACCOUNTS.md"

CARRIERS = [
    {
        "code": "SKR",
        "name": "Sakura Fleet",
        "registered_name": "Sakura Fleet KK",
        "representative_name": "Ken Sato",
        "phone": "080-7001-0000",
        "address": "Osaka Chuo 1-1-1",
        "bank": "MUFG Bank",
        "branch": "Osaka",
        "account": "7001001",
        "drivers": [
            ("SKR-D01", "Ken Sato", "080-7001-0101"),
            ("SKR-D02", "Aki Tanaka", "080-7001-0102"),
            ("SKR-D03", "Ryo Suzuki", "080-7001-0103"),
        ],
    },
    {
        "code": "KEX",
        "name": "Kansai Express",
        "registered_name": "Kansai Express KK",
        "representative_name": "Aki Tanaka",
        "phone": "080-7002-0000",
        "address": "Kyoto Shimogyo 2-2-2",
        "bank": "SMBC",
        "branch": "Kyoto",
        "account": "7002001",
        "drivers": [
            ("KEX-D01", "Yuki Mori", "080-7002-0101"),
            ("KEX-D02", "Hiro Ito", "080-7002-0102"),
            ("KEX-D03", "Nao Kato", "080-7002-0103"),
        ],
    },
    {
        "code": "TYO",
        "name": "Tokyo Premium",
        "registered_name": "Tokyo Premium KK",
        "representative_name": "Yu Takahashi",
        "phone": "080-7003-0000",
        "address": "Tokyo Minato 3-3-3",
        "bank": "Mizuho Bank",
        "branch": "Tokyo",
        "account": "7003001",
        "drivers": [
            ("TYO-D01", "Shun Watanabe", "080-7003-0101"),
            ("TYO-D02", "Mai Kobayashi", "080-7003-0102"),
            ("TYO-D03", "Ren Yamada", "080-7003-0103"),
        ],
    },
]

AGENCIES = [
    {
        "code": "AGA",
        "name": "Toyo Holiday Travel",
        "registered_name": "Toyo Holiday Travel KK",
        "portal_code": "AGA2026",
        "representative_name": "Hanako Yamada",
        "contact": "A Manager",
        "phone": "080-7101-0000",
        "address": "Osaka Kita 4-4-4",
        "bank": "MUFG Bank",
        "branch": "Umeda",
        "account": "7101001",
        "guides": [
            ("AGA-G01", "Mico Yamamoto", "080-7101-0101"),
            ("AGA-G02", "Naomi Kuroda", "080-7101-0102"),
            ("AGA-G03", "Sho Hayashi", "080-7101-0103"),
        ],
    },
    {
        "code": "AGB",
        "name": "Fuji Tour Travel",
        "registered_name": "Fuji Tour Travel KK",
        "portal_code": "AGB2026",
        "representative_name": "Makoto Fujiwara",
        "contact": "B Manager",
        "phone": "080-7102-0000",
        "address": "Tokyo Shinjuku 5-5-5",
        "bank": "SMBC",
        "branch": "Shinjuku",
        "account": "7102001",
        "guides": [
            ("AGB-G01", "Gayun Lee", "080-7102-0101"),
            ("AGB-G02", "Emily Childers", "080-7102-0102"),
            ("AGB-G03", "Mahesh Patil", "080-7102-0103"),
        ],
    },
    {
        "code": "AGC",
        "name": "Keihan International Travel",
        "registered_name": "Keihan International KK",
        "portal_code": "AGC2026",
        "representative_name": "Ryo Kobayashi",
        "contact": "C Manager",
        "phone": "080-7103-0000",
        "address": "Kyoto Nakagyo 6-6-6",
        "bank": "Resona Bank",
        "branch": "Kyoto",
        "account": "7103001",
        "guides": [
            ("AGC-G01", "Noki Shi", "080-7103-0101"),
            ("AGC-G02", "Donghan Yang", "080-7103-0102"),
            ("AGC-G03", "Mina Okada", "080-7103-0103"),
        ],
    },
]


def main() -> None:
    init_db(seed=True)
    ensure_travel_agency_schema()
    set_current_tenant_id(1)

    carrier_accounts = []
    agency_accounts = []

    for carrier in CARRIERS:
        with get_connection() as conn:
            tenant_id = ensure_tenant(conn, carrier["code"], carrier["name"])
            web_accounts = [
                ensure_user(conn, tenant_id, f"{carrier['code']}-admin", "admin", f"{carrier['name']} Admin", carrier["phone"]),
                ensure_user(conn, tenant_id, f"{carrier['code']}-dispatch", "dispatcher", f"{carrier['name']} Dispatcher", bump_phone(carrier["phone"], 1)),
                ensure_user(conn, tenant_id, f"{carrier['code']}-ops", "operations_manager", f"{carrier['name']} Operations", bump_phone(carrier["phone"], 2)),
            ]
            drivers = []
            management_login = company_login_name(carrier["phone"], carrier["code"], carrier["name"])
            dispatch_login = company_login_name(bump_phone(carrier["phone"], 1), carrier["code"], carrier["name"])
            operations_login = company_login_name(bump_phone(carrier["phone"], 2), carrier["code"], carrier["name"])
            for driver_code, driver_name, phone in carrier["drivers"]:
                driver_id = ensure_driver(conn, tenant_id, driver_code, driver_name, phone)
                username = company_login_name(phone, carrier["code"], carrier["name"])
                ensure_user(conn, tenant_id, username, "driver", driver_name, phone, profile_type="driver", profile_id=driver_id)
                drivers.append({"driver_code": driver_code, "name": driver_name, "phone": phone, "login": username, "password": PASSWORD})
            conn.commit()
        ensure_company_registration("carrier", carrier)
        carrier_accounts.append(
            {
                "company_code": carrier["code"],
                "company_name": carrier["name"],
                "tenant_id": tenant_id,
                "management_account": {"login": management_login, "legacy_login": f"{carrier['code']}-admin", "password": PASSWORD, "role": "admin"},
                "dispatch_account": {"login": dispatch_login, "legacy_login": f"{carrier['code']}-dispatch", "password": PASSWORD, "role": "dispatcher"},
                "operations_account": {"login": operations_login, "legacy_login": f"{carrier['code']}-ops", "password": PASSWORD, "role": "operations_manager"},
                "drivers": drivers,
                "user_ids": web_accounts,
            }
        )

    for agency in AGENCIES:
        with get_connection() as conn:
            agency_id = ensure_agency(conn, agency)
            company_id = ensure_travel_agency_company(conn, agency)
            owner = ensure_travel_agency_account(conn, company_id, "agency_owner", f"{agency['code']} Owner", agency["phone"])
            cs = ensure_travel_agency_account(conn, company_id, "agency_customer_service", f"{agency['code']} Customer Service", bump_phone(agency["phone"], 1))
            finance = ensure_travel_agency_account(conn, company_id, "agency_finance", f"{agency['code']} Finance", bump_phone(agency["phone"], 2))
            guide_accounts = []
            for guide_code, guide_name, phone in agency["guides"]:
                guide_id = ensure_travel_agency_guide(conn, company_id, guide_code, guide_name, phone)
                account_id = ensure_travel_agency_account(conn, company_id, "agency_guide", guide_name, phone)
                guide_accounts.append({"guide_code": guide_code, "name": guide_name, "phone": phone, "login": phone, "password_seed": phone[-4:], "guide_id": guide_id, "account_id": account_id})
            conn.commit()
        ensure_company_registration("agency", agency)
        agency_accounts.append(
            {
                "agency_code": agency["code"],
                "agency_name": agency["name"],
                "agency_id": agency_id,
                "portal_code": agency["portal_code"],
                "portal_password": AGENCY_PORTAL_PASSWORD,
                "travel_agency_company_id": company_id,
                "management_account": {"login": agency["phone"], "password_seed": agency["phone"][-4:], "role": "agency_owner", "account_id": owner},
                "customer_service_account": {"login": bump_phone(agency["phone"], 1), "password_seed": bump_phone(agency["phone"], 1)[-4:], "role": "agency_customer_service", "account_id": cs},
                "finance_account": {"login": bump_phone(agency["phone"], 2), "password_seed": bump_phone(agency["phone"], 2)[-4:], "role": "agency_finance", "account_id": finance},
                "guide_accounts": guide_accounts,
            }
        )

    result = {
        "platform_admin": {"login": "admin", "password": "admin123"},
        "default_carrier_password": PASSWORD,
        "carrier_accounts": carrier_accounts,
        "agency_portal_accounts": agency_accounts,
        "notes": [
            "车公司 Web 账号写入 users 表，可用用户名和 Test123456 登录。",
            "车公司司机账号写入 drivers + users 表，登录名格式为 公司代码-手机号数字。",
            "旅行社门户使用登录代码 + 密码登录；输入登录代码后页面会识别旅行社名称。",
            "旅行社内部财务/客服/管理/导游账号写入 travel_agency_accounts 表，password_seed 为手机号后四位；当前如未做旅行社内部账号登录页，这些账号先作为权限与数据结构测试用。",
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"json": str(RESULT_PATH), "report": str(REPORT_PATH)}, ensure_ascii=False, indent=2))


def ensure_company_registration(company_type: str, data: dict[str, Any]) -> None:
    existing = list_company_registrations({"keyword": data["code"], "company_type": company_type})
    if existing:
        return
    create_company_registration(
        {
            "company_type": company_type,
            "company_code": data["code"],
            "company_name": data["name"],
            "registered_name": data["registered_name"],
            "representative_name": data["representative_name"],
            "address": data["address"],
            "contact_name": data.get("contact") or data["representative_name"],
            "contact_phone": data["phone"],
            "bank_name": data["bank"],
            "bank_branch": data["branch"],
            "bank_account_type": "ordinary",
            "bank_account_number": data["account"],
            "bank_account_holder": data["registered_name"],
            "status": "approved",
        }
    )


def ensure_tenant(conn, code: str, name: str) -> int:
    row = conn.execute("SELECT id FROM tenants WHERE slug = ?", (code,)).fetchone()
    if row:
        conn.execute("UPDATE tenants SET name = ?, status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, row["id"]))
        return int(row["id"])
    cursor = conn.execute("INSERT INTO tenants (name, slug, status, updated_at) VALUES (?, ?, 'active', CURRENT_TIMESTAMP)", (name, code))
    return int(cursor.lastrowid)


def ensure_user(
    conn,
    tenant_id: int,
    username: str,
    role: str,
    display_name: str,
    phone: str,
    profile_type: str | None = None,
    profile_id: int | None = None,
) -> int:
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        user_id = int(row["id"])
        conn.execute(
            """
            UPDATE users
            SET tenant_id = ?, password_hash = ?, role = ?, display_name = ?, phone = ?,
                profile_type = ?, profile_id = ?, is_active = 1, must_change_password = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (tenant_id, hash_password(PASSWORD), role, display_name, phone, profile_type, profile_id, user_id),
        )
        return user_id
    cursor = conn.execute(
        """
        INSERT INTO users (
            tenant_id, username, password_hash, role, display_name, phone,
            profile_type, profile_id, is_active, must_change_password, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, CURRENT_TIMESTAMP)
        """,
        (tenant_id, username, hash_password(PASSWORD), role, display_name, phone, profile_type, profile_id),
    )
    return int(cursor.lastrowid)


def ensure_driver(conn, tenant_id: int, driver_code: str, name: str, phone: str) -> int:
    row = conn.execute("SELECT id FROM drivers WHERE tenant_id = ? AND driver_code = ?", (tenant_id, driver_code)).fetchone()
    if row:
        driver_id = int(row["id"])
        conn.execute(
            """
            UPDATE drivers
            SET name = ?, phone = ?, status = 'available', driver_status = 'active',
                driver_language = 'JP/CN', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (name, phone, driver_id, tenant_id),
        )
        return driver_id
    cursor = conn.execute(
        """
        INSERT INTO drivers (tenant_id, name, phone, status, driver_status, driver_code, driver_language, updated_at)
        VALUES (?, ?, ?, 'available', 'active', ?, 'JP/CN', CURRENT_TIMESTAMP)
        """,
        (tenant_id, name, phone, driver_code),
    )
    return int(cursor.lastrowid)


def ensure_agency(conn, agency: dict[str, Any]) -> int:
    row = conn.execute("SELECT id FROM agencies WHERE tenant_id = 1 AND agency_code = ?", (agency["code"],)).fetchone()
    if row:
        agency_id = int(row["id"])
        conn.execute(
            """
            UPDATE agencies
            SET company_name = ?, name = ?, address = ?, contact_name = ?, contact_phone = ?,
                responsible_person = ?, portal_code = ?, portal_password_hash = ?,
                portal_password_updated_at = CURRENT_TIMESTAMP, is_portal_enabled = 1,
                status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = 1
            """,
            (agency["name"], agency["name"], agency["address"], agency["contact"], agency["phone"], agency["representative_name"], agency["portal_code"], hash_portal_password(AGENCY_PORTAL_PASSWORD), agency_id),
        )
        return agency_id
    cursor = conn.execute(
        """
        INSERT INTO agencies (
            tenant_id, agency_code, company_name, name, address, contact_name, contact_phone,
            responsible_person, status, portal_code, portal_password_hash,
            portal_password_updated_at, is_portal_enabled, updated_at
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
        """,
        (agency["code"], agency["name"], agency["name"], agency["address"], agency["contact"], agency["phone"], agency["representative_name"], agency["portal_code"], hash_portal_password(AGENCY_PORTAL_PASSWORD)),
    )
    return int(cursor.lastrowid)


def hash_portal_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_travel_agency_company(conn, agency: dict[str, Any]) -> int:
    row = conn.execute("SELECT id FROM travel_agency_companies WHERE tenant_id = 1 AND company_code = ?", (agency["code"],)).fetchone()
    if row:
        company_id = int(row["id"])
        conn.execute(
            """
            UPDATE travel_agency_companies
            SET company_name = ?, master_phone = ?, master_display_name = ?, status = 'active',
                must_change_password = 0, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = 1 AND id = ?
            """,
            (agency["name"], agency["phone"], agency["contact"], company_id),
        )
        return company_id
    cursor = conn.execute(
        """
        INSERT INTO travel_agency_companies (
            tenant_id, company_code, company_name, master_phone, master_display_name,
            status, must_change_password, wx_bind_required, settings_json, updated_at
        )
        VALUES (1, ?, ?, ?, ?, 'active', 0, 0, '{}', CURRENT_TIMESTAMP)
        """,
        (agency["code"], agency["name"], agency["phone"], agency["contact"]),
    )
    return int(cursor.lastrowid)


def ensure_travel_agency_account(conn, company_id: int, role: str, display_name: str, phone: str) -> int:
    row = conn.execute(
        "SELECT id FROM travel_agency_accounts WHERE tenant_id = 1 AND company_id = ? AND role = ? AND phone = ?",
        (company_id, role, phone),
    ).fetchone()
    permissions = json.dumps(ROLE_MATRIX[role], ensure_ascii=False)
    seed = phone[-4:]
    if row:
        account_id = int(row["id"])
        conn.execute(
            """
            UPDATE travel_agency_accounts
            SET display_name = ?, password_seed = ?, must_change_password = 0,
                permissions_json = ?, status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = 1
            """,
            (display_name, seed, permissions, account_id),
        )
        return account_id
    cursor = conn.execute(
        """
        INSERT INTO travel_agency_accounts (
            tenant_id, company_id, role, display_name, phone, password_seed,
            must_change_password, permissions_json, status, updated_at
        )
        VALUES (1, ?, ?, ?, ?, ?, 0, ?, 'active', CURRENT_TIMESTAMP)
        """,
        (company_id, role, display_name, phone, seed, permissions),
    )
    return int(cursor.lastrowid)


def ensure_travel_agency_guide(conn, company_id: int, guide_code: str, name: str, phone: str) -> int:
    row = conn.execute(
        "SELECT id FROM travel_agency_guides WHERE tenant_id = 1 AND company_id = ? AND certificate_no = ?",
        (company_id, guide_code),
    ).fetchone()
    if row:
        guide_id = int(row["id"])
        conn.execute(
            """
            UPDATE travel_agency_guides
            SET name = ?, phone = ?, languages = 'JP/CN/EN', status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = 1
            """,
            (name, phone, guide_id),
        )
        return guide_id
    cursor = conn.execute(
        """
        INSERT INTO travel_agency_guides (
            tenant_id, company_id, name, phone, languages, certificate_no, status, updated_at
        )
        VALUES (1, ?, ?, ?, 'JP/CN/EN', ?, 'active', CURRENT_TIMESTAMP)
        """,
        (company_id, name, phone, guide_code),
    )
    return int(cursor.lastrowid)


def bump_phone(phone: str, offset: int) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    next_digits = str(int(digits) + offset).zfill(len(digits))
    return f"{next_digits[:3]}-{next_digits[3:7]}-{next_digits[7:]}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# TourFlow 测试账户",
        "",
        "版本：2026-06-01  ",
        "目标：本地和云端使用同一套测试账户，便于 3 人以上协同测试。",
        "",
        "## 访问地址",
        "",
        "| 端口 | 本地 Web | 云端 Web |",
        "| --- | --- | --- |",
        "| 平台总控 / 车公司 Web | `http://127.0.0.1:5173/` | `https://admin-trial.taxi-airport.jp/` |",
        "| 旅行社 Web | `http://127.0.0.1:5173/#agency-portal` | `https://admin-trial.taxi-airport.jp/#agency-portal` |",
        "| 本地 API / 云端 API | `http://127.0.0.1:18765` | `https://api-trial.taxi-airport.jp` |",
        "",
        "## 平台总控 Web",
        "",
        "| 入口 | 登录名 | 密码 |",
        "| --- | --- | --- |",
        f"| 平台总控 Web | `{result['platform_admin']['login']}` | `{result['platform_admin']['password']}` |",
        "",
        "## 车公司端 Web 账号",
        "",
        "登录页如果显示“公司账号”，优先使用 `公司代码-手机号数字` 格式。旧用户名保留用于兼容 `/api/auth/login`。",
        "",
        "| 公司代码 | 公司名 | 管理账号 | 调度账号 | 运行管理账号 | 旧管理账号 | 旧调度账号 | 旧运行管理账号 | 密码 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for carrier in result["carrier_accounts"]:
        lines.append(
            f"| {carrier['company_code']} | {carrier['company_name']} | `{carrier['management_account']['login']}` | `{carrier['dispatch_account']['login']}` | `{carrier['operations_account']['login']}` | `{carrier['management_account'].get('legacy_login', '')}` | `{carrier['dispatch_account'].get('legacy_login', '')}` | `{carrier['operations_account'].get('legacy_login', '')}` | `{result['default_carrier_password']}` |"
        )
    lines.extend(
        [
            "",
            "## 车公司端小程序账号",
            "",
            "小程序目录：`miniapp_dispatch/`  ",
            "登录方式：公司管理、调度、运行管理、司机统一从车公司小程序登录页进入，后端按账号角色分配页面和权限。",
            "",
            "| 公司代码 | 管理账号 | 调度账号 | 运行管理账号 | 密码 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for carrier in result["carrier_accounts"]:
        lines.append(
            f"| {carrier['company_code']} | `{carrier['management_account']['login']}` | `{carrier['dispatch_account']['login']}` | `{carrier['operations_account']['login']}` | `{result['default_carrier_password']}` |"
        )
    lines.extend(["", "## 车公司司机账号", "", "| 公司 | 司机代码 | 司机名 | 电话 | 登录名 | 密码 |", "| --- | --- | --- | --- | --- | --- |"])
    for carrier in result["carrier_accounts"]:
        for driver in carrier["drivers"]:
            lines.append(f"| {carrier['company_code']} | {driver['driver_code']} | {driver['name']} | {driver['phone']} | `{driver['login']}` | `{driver['password']}` |")
    lines.extend(
        [
            "",
            "## 旅行社端 Web 账号",
            "",
            "旅行社 Web 入口：  ",
            "本地：`http://127.0.0.1:5173/#agency-portal`  ",
            "云端：`https://admin-trial.taxi-airport.jp/#agency-portal`",
            "",
            "| 旅行社代码 | 旅行社名 | 登录代码 | 密码 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for agency in result["agency_portal_accounts"]:
        lines.append(f"| {agency['agency_code']} | {agency['agency_name']} | `{agency['portal_code']}` | `{agency['portal_password']}` |")
    lines.extend(["", "登录方式：打开 `#agency-portal`，输入上表“登录代码”，页面会显示旅行社名称，再输入密码登录。登录后可在“设置”里修改密码。"])
    lines.extend(
        [
            "",
            "## 旅行社端小程序账号",
            "",
            "小程序目录：`miniapp_agency/`  ",
            "登录方式：当前 MVP 推荐继续使用旅行社 `portal code + 密码` 登录，先保证 Web 和小程序共用同一旅行社租户数据。",
            "",
            "| 旅行社代码 | 登录代码 | 密码 |",
            "| --- | --- | --- |",
        ]
    )
    for agency in result["agency_portal_accounts"]:
        lines.append(f"| {agency['agency_code']} | `{agency['portal_code']}` | `{agency['portal_password']}` |")
    lines.extend(["", "## 旅行社内部权限账号规划", "", "这些账号用于旅行社内部权限测试：管理、客服、财务、导游。若要在云端启用，需要执行云端测试账号同步。", "", "| 旅行社 | 管理账号 | 客服账号 | 财务账号 | 导游账号 |", "| --- | --- | --- | --- | --- |"])
    for agency in result["agency_portal_accounts"]:
        guides = "；".join(f"`{g['login']}` / `{g['password_seed']}` {g['name']}" for g in agency["guide_accounts"])
        lines.append(
            f"| {agency['agency_code']} | `{agency['management_account']['login']}` / `{agency['management_account']['password_seed']}` | `{agency['customer_service_account']['login']}` / `{agency['customer_service_account']['password_seed']}` | `{agency['finance_account']['login']}` / `{agency['finance_account']['password_seed']}` | {guides} |"
        )
    lines.extend(
        [
            "",
            "## 是否统一旅行社和车公司小程序入口",
            "",
            "建议分两步：",
            "",
            "1. MVP 阶段继续保留两个小程序目录：",
            "   - `miniapp_dispatch/`：车公司管理、调度、运行管理、司机。",
            "   - `miniapp_agency/`：旅行社管理、客服、财务、导游。",
            "2. 稳定后再做统一入口：",
            "   - 新增一个统一登录页。",
            "   - 登录后根据账号归属和角色跳转到旅行社端或车公司端。",
            "   - 底层接口仍按端口隔离，避免旅行社权限误触车公司调度、司机、运行管理流程。",
            "",
            "结论：有必要统一入口，但不建议现在合并业务代码。先统一登录体验，保留两套业务端页面和权限边界。",
            "",
            "## 云端同步确认项",
            "",
            "同步云端测试账户会写入云端测试数据库，执行前需要明确确认：",
            "",
            "1. 只补齐或更新测试账户，不清理订单数据。",
            "2. 不做生产数据修改。",
            "3. 不 Git push。",
            "4. 不上传小程序。",
            "5. 如云端 API 需要重启，只重启测试环境 API 服务。",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

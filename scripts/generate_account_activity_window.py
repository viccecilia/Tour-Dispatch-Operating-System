from __future__ import annotations

import argparse
import html
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import DB_PATH  # noqa: E402
from backend.db.database import get_connection  # noqa: E402

OUT = ROOT / "runtime" / "task_results" / "account_activity_window.html"
FRONTEND_PUBLIC_OUT = ROOT / "frontend" / "public" / "activity-window" / "index.html"
TEST_ACCOUNTS_JSON = ROOT / "runtime" / "task_results" / "TEST_ACCOUNTS.json"
SERVER_SNAPSHOT = ROOT / "runtime" / "task_results" / "server_wx_dispatch_snapshot.sqlite3"
TRIAL_DB = ROOT / "runtime" / "trial" / "wx_dispatch_trial.sqlite3"
REMOTE_DB = "/home/ubuntu/tourflow/runtime/trial/wx_dispatch_trial.sqlite3"
SSH_KEY = Path.home() / ".ssh" / "tourflow_sakura_vps_ed25519"
SSH_TARGET = "ubuntu@133.167.79.170"


def main() -> None:
    args = parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_PUBLIC_OUT.parent.mkdir(parents=True, exist_ok=True)
    data = collect_sources(args.source, args.fetch_server)
    html_text = render_html(data)
    OUT.write_text(html_text, encoding="utf-8")
    FRONTEND_PUBLIC_OUT.write_text(html_text, encoding="utf-8")
    print(OUT)
    print(FRONTEND_PUBLIC_OUT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate account activity window HTML.")
    parser.add_argument("--source", choices=["local", "server", "both"], default="both")
    parser.add_argument("--no-fetch-server", dest="fetch_server", action="store_false")
    parser.set_defaults(fetch_server=True)
    return parser.parse_args()


def collect_sources(source: str, fetch_server: bool) -> dict[str, Any]:
    sources: list[tuple[str, Path | None]] = []
    if source in {"local", "both"}:
        sources.append(("local", Path(DB_PATH)))
    if source in {"server", "both"}:
        snapshot = fetch_server_snapshot() if fetch_server else SERVER_SNAPSHOT
        if snapshot.exists():
            sources.append(("server", snapshot))

    tenants: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []

    for source_name, db_path in sources:
        try:
            collected = collect_activity(source_name, db_path)
            tenants.extend(collected["tenants"])
            users.extend(collected["users"])
            events.extend(collected["events"])
            records.extend(collected["records"])
            source_status.append({"source": source_name, "ok": True, "path": str(db_path)})
        except Exception as exc:  # pragma: no cover - visible in generated page
            source_status.append({"source": source_name, "ok": False, "path": str(db_path), "error": str(exc)})

    users = enrich_users(users)
    events.sort(key=lambda item: (item.get("time") or "", item.get("id") or 0), reverse=True)
    records.sort(key=lambda item: (item.get("time") or "", item.get("id") or 0), reverse=True)
    return {
        "generated_at": now_label(),
        "sources": source_status,
        "tenants": tenants,
        "users": users,
        "events": events,
        "records": records,
        "login_guide": load_login_guide(),
    }


def fetch_server_snapshot() -> Path:
    SERVER_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    if not SSH_KEY.exists():
        return SERVER_SNAPSHOT
    if SERVER_SNAPSHOT.exists():
        SERVER_SNAPSHOT.unlink()
    subprocess.run(
        ["scp", "-i", str(SSH_KEY), f"{SSH_TARGET}:{REMOTE_DB}", str(SERVER_SNAPSHOT)],
        check=True,
    )
    return SERVER_SNAPSHOT


def collect_activity(source_name: str, db_path: Path | None) -> dict[str, Any]:
    conn = open_connection(source_name, db_path)
    try:
        tenants = with_source(rows(conn, "SELECT id, name, slug FROM tenants ORDER BY id"), source_name)
        users = with_source(user_rows(conn), source_name)
        events = []
        events.extend(order_events(conn, source_name))
        events.extend(draft_events(conn, source_name))
        events.extend(auction_events(conn, source_name))
        events.extend(notification_events(conn, source_name))
        events.extend(dispatch_mobile_audit_events(conn, source_name))
        events.extend(audit_log_events(conn, source_name))
        records = []
        records.extend(order_records(conn, source_name))
        records.extend(draft_records(conn, source_name))
        records.extend(auction_records(conn, source_name))
        records.extend(assignment_records(conn, source_name))
        return {"tenants": tenants, "users": users, "events": events, "records": records}
    finally:
        conn.close()


def open_connection(source_name: str, db_path: Path | None) -> sqlite3.Connection:
    if source_name == "local" and db_path == Path(DB_PATH):
        conn = get_connection()
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def user_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(conn, "users"):
        return []
    return rows(
        conn,
        """
        SELECT
          u.id,
          u.tenant_id,
          t.name AS tenant_name,
          t.slug AS tenant_code,
          u.username,
          u.display_name,
          u.role,
          u.phone,
          u.profile_type,
          u.profile_id,
          u.is_active,
          u.last_login_at,
          u.created_at,
          u.updated_at
        FROM users u
        LEFT JOIN tenants t ON t.id = u.tenant_id
        ORDER BY u.tenant_id, u.role, u.id
        """,
    )


def enrich_users(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for user in users:
        tenant = user.get("tenant_name") or user.get("tenant_code") or f"tenant-{user.get('tenant_id')}"
        role = str(user.get("role") or "")
        username = str(user.get("username") or "")
        scope = "平台总后台" if username == "admin" or role == "platform" else "公司端口"
        inner = {
            "admin": "管理",
            "dispatcher": "调度",
            "operations_manager": "运行管理",
            "driver": "司机",
        }.get(role, role or "未分类")
        enriched.append(
            {
                **user,
                "scope_level": scope,
                "company_port": tenant,
                "company_inner_level": inner,
                "search": " ".join(
                    str(v or "")
                    for v in [user.get("username"), user.get("display_name"), role, tenant, scope, inner]
                ).lower(),
            }
        )
    return enriched


def order_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    return [
        event(
            row,
            source=source,
            kind="order",
            action="订单更新",
            entity=row.get("oid") or f"order-{row.get('id')}",
            status=row.get("dispatch_status") or row.get("execution_status") or "-",
            actor=row.get("updated_by_dispatcher") or row.get("created_by_dispatcher") or "-",
            account=row.get("updated_by_dispatcher_code") or row.get("created_by_dispatcher_code") or "-",
            time=row.get("updated_at") or row.get("created_at"),
            detail=route_detail(row),
        )
        for row in select_orders(conn, limit=2000)
    ]


def draft_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "order_drafts"):
        return []
    return [
        event(
            row,
            source=source,
            kind="draft",
            action="草稿更新",
            entity=row.get("oid") or f"draft-{row.get('id')}",
            status=row.get("parse_status") or "-",
            actor=row.get("updated_by_dispatcher") or row.get("created_by_dispatcher") or "-",
            account=row.get("updated_by_dispatcher_code") or row.get("created_by_dispatcher_code") or "-",
            time=row.get("updated_at") or row.get("created_at"),
            detail=route_detail(row),
        )
        for row in select_drafts(conn, limit=2000)
    ]


def auction_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "auction_listings"):
        return []
    result = []
    for row in select_auctions(conn, limit=2000):
        claimed = row.get("status") in {"claimed", "sold"}
        buyer = row.get("buyer_name") or row.get("buyer_code") or "-"
        seller = row.get("tenant_name") or row.get("tenant_code") or "-"
        action = "大厅成交" if claimed else "发布大厅"
        actor = buyer if claimed else (row.get("published_by_name") or seller)
        account = row.get("buyer_code") if claimed else row.get("tenant_code")
        detail = f"{route_detail(row)} · 发布方 {seller} · 接单方 {buyer} · 当前价 {money(row.get('current_bid_jpy'))}"
        result.append(
            event(
                row,
                source=source,
                kind="auction",
                action=action,
                entity=row.get("listing_code") or row.get("oid") or f"listing-{row.get('id')}",
                status=row.get("status") or "-",
                actor=actor,
                account=account,
                time=row.get("updated_at") or row.get("sold_at") or row.get("published_at"),
                detail=detail,
            )
        )
    return result


def notification_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "notifications"):
        return []
    return [
        event(
            row,
            source=source,
            kind="notification",
            action=f"通知:{row.get('notification_type') or 'system'}",
            entity=row.get("title") or f"notification-{row.get('id')}",
            status=row.get("status") or "-",
            actor=row.get("target_role") or "全部",
            account=row.get("target_role") or "-",
            time=row.get("updated_at") or row.get("created_at"),
            detail=row.get("body") or "",
        )
        for row in rows(
            conn,
            """
            SELECT n.*, t.name AS tenant_name, t.slug AS tenant_code
            FROM notifications n
            LEFT JOIN tenants t ON t.id = n.tenant_id
            ORDER BY COALESCE(n.updated_at, n.created_at) DESC, n.id DESC
            LIMIT 2000
            """,
        )
    ]


def dispatch_mobile_audit_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "dispatch_mobile_audit_logs"):
        return []
    return [
        event(
            row,
            source=source,
            kind="mobile_audit",
            action=row.get("action") or "mobile_action",
            entity=f"{row.get('entity_type') or '-'} {row.get('entity_id') or ''}".strip(),
            status="audit",
            actor=row.get("dispatcher_name") or "-",
            account=row.get("dispatcher_code") or str(row.get("dispatcher_id") or "-"),
            time=row.get("created_at"),
            detail=row.get("summary") or row.get("source_path") or "",
        )
        for row in rows(
            conn,
            """
            SELECT a.*, t.name AS tenant_name, t.slug AS tenant_code
            FROM dispatch_mobile_audit_logs a
            LEFT JOIN tenants t ON t.id = a.tenant_id
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT 2000
            """,
        )
    ]


def audit_log_events(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "audit_logs"):
        return []
    cols = columns(conn, "audit_logs")
    sql = f"SELECT {', '.join(cols)} FROM audit_logs ORDER BY id DESC LIMIT 2000"
    return [
        event(
            row,
            source=source,
            kind="audit",
            action=row.get("action") or row.get("action_type") or "audit",
            entity=f"{row.get('entity_type') or row.get('target_type') or '-'} {row.get('entity_id') or row.get('target_id') or ''}".strip(),
            status=row.get("status") or "audit",
            actor=row.get("actor_name") or row.get("username") or row.get("actor") or "-",
            account=row.get("actor_id") or row.get("user_id") or "-",
            time=row.get("created_at") or row.get("timestamp") or row.get("updated_at"),
            detail=row.get("summary") or row.get("description") or row.get("details") or "",
        )
        for row in rows(conn, sql)
    ]


def order_records(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    return [
        record(
            row,
            source=source,
            kind="order",
            title=row.get("oid") or f"order-{row.get('id')}",
            status=row.get("dispatch_status") or row.get("execution_status") or "-",
            owner=row.get("created_by_dispatcher_code") or row.get("created_by_dispatcher") or "-",
            time=row.get("updated_at") or row.get("created_at"),
            detail=route_detail(row),
            price=money(row.get("price_jpy") or row.get("price")),
        )
        for row in select_orders(conn, limit=5000)
    ]


def draft_records(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    return [
        record(
            row,
            source=source,
            kind="draft",
            title=row.get("oid") or f"draft-{row.get('id')}",
            status=row.get("parse_status") or "-",
            owner=row.get("created_by_dispatcher_code") or row.get("created_by_dispatcher") or "-",
            time=row.get("updated_at") or row.get("created_at"),
            detail=route_detail(row),
            price=money(row.get("price_jpy") or row.get("price")),
        )
        for row in select_drafts(conn, limit=5000)
    ]


def auction_records(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    return [
        record(
            row,
            source=source,
            kind="auction",
            title=row.get("listing_code") or row.get("oid") or f"listing-{row.get('id')}",
            status=row.get("status") or "-",
            owner=f"发布方 {row.get('tenant_name') or '-'} / 接单方 {row.get('buyer_name') or '-'}",
            time=row.get("updated_at") or row.get("published_at"),
            detail=route_detail(row),
            price=f"起拍 {money(row.get('start_price_jpy'))} / 当前 {money(row.get('current_bid_jpy'))} / 一口价 {money(row.get('buyout_price_jpy'))}",
        )
        for row in select_auctions(conn, limit=5000)
    ]


def assignment_records(conn: sqlite3.Connection, source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, "assignments"):
        return []
    return [
        record(
            row,
            source=source,
            kind="assignment",
            title=row.get("oid") or f"assignment-{row.get('id')}",
            status=row.get("execution_status") or row.get("status") or "-",
            owner=f"{row.get('driver_name') or row.get('driver_id') or '-'} / {row.get('vehicle_name') or row.get('vehicle_id') or '-'}",
            time=row.get("updated_at") or row.get("created_at"),
            detail=route_detail(row),
            price="",
        )
        for row in rows(
            conn,
            """
            SELECT
              a.*,
              t.name AS tenant_name,
              t.slug AS tenant_code,
              o.oid,
              o.order_date,
              o.start_time,
              o.pickup_location,
              o.dropoff_location,
              d.name AS driver_name,
              v.plate_no AS vehicle_name
            FROM assignments a
            LEFT JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
            LEFT JOIN tenants t ON t.id = a.tenant_id
            LEFT JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
            LEFT JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
            ORDER BY COALESCE(a.updated_at, a.created_at) DESC, a.id DESC
            LIMIT 5000
            """,
        )
    ]


def select_orders(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "orders"):
        return []
    return rows(
        conn,
        f"""
        SELECT o.*, t.name AS tenant_name, t.slug AS tenant_code
        FROM orders o
        LEFT JOIN tenants t ON t.id = o.tenant_id
        WHERE COALESCE(o.is_deleted, 0) = 0
        ORDER BY COALESCE(o.updated_at, o.created_at) DESC, o.id DESC
        LIMIT {int(limit)}
        """,
    )


def select_drafts(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "order_drafts"):
        return []
    return rows(
        conn,
        f"""
        SELECT d.*, t.name AS tenant_name, t.slug AS tenant_code
        FROM order_drafts d
        LEFT JOIN tenants t ON t.id = d.tenant_id
        ORDER BY COALESCE(d.updated_at, d.created_at) DESC, d.id DESC
        LIMIT {int(limit)}
        """,
    )


def select_auctions(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "auction_listings"):
        return []
    return rows(
        conn,
        f"""
        SELECT
          l.*,
          l.seller_tenant_id AS tenant_id,
          seller.name AS tenant_name,
          seller.slug AS tenant_code,
          buyer.name AS buyer_name,
          buyer.slug AS buyer_code,
          o.oid,
          o.order_date,
          o.start_time,
          o.pickup_location,
          o.dropoff_location
        FROM auction_listings l
        LEFT JOIN orders o ON o.id = l.order_id
        LEFT JOIN tenants seller ON seller.id = l.seller_tenant_id
        LEFT JOIN tenants buyer ON buyer.id = l.buyer_tenant_id
        ORDER BY COALESCE(l.updated_at, l.sold_at, l.published_at) DESC, l.id DESC
        LIMIT {int(limit)}
        """,
    )


def event(
    row: dict[str, Any],
    *,
    source: str,
    kind: str,
    action: str,
    entity: Any,
    status: Any,
    actor: Any,
    account: Any,
    time: Any,
    detail: str,
) -> dict[str, Any]:
    item = base_item(row, source, kind, entity, status, actor, account, time, detail)
    item["action"] = str(action or "-")
    item["search"] = search_blob(item, item["action"])
    return item


def record(
    row: dict[str, Any],
    *,
    source: str,
    kind: str,
    title: Any,
    status: Any,
    owner: Any,
    time: Any,
    detail: str,
    price: str,
) -> dict[str, Any]:
    item = base_item(row, source, kind, title, status, owner, owner, time, detail)
    item["price"] = price
    item["search"] = search_blob(item, price)
    return item


def base_item(
    row: dict[str, Any],
    source: str,
    kind: str,
    entity: Any,
    status: Any,
    actor: Any,
    account: Any,
    time: Any,
    detail: str,
) -> dict[str, Any]:
    tenant = row.get("tenant_name") or row.get("tenant_code") or f"tenant-{row.get('tenant_id')}"
    tenant_code = row.get("tenant_code") or ""
    return {
        "id": row.get("id"),
        "source": source,
        "source_label": "本地" if source == "local" else "服务器",
        "kind": kind,
        "entity": str(entity or "-"),
        "status": str(status or "-"),
        "actor": str(actor or "-"),
        "account": str(account or "-"),
        "tenant_id": row.get("tenant_id"),
        "tenant": tenant,
        "tenant_code": tenant_code,
        "scope_level": activity_scope_level(kind, tenant_code, tenant),
        "company_port": tenant,
        "company_inner_level": activity_inner_level(kind, actor, account),
        "time": str(time or ""),
        "detail": detail,
    }


def activity_scope_level(kind: str, tenant_code: str, tenant: str) -> str:
    code = str(tenant_code or "").lower()
    name = str(tenant or "").lower()
    if kind == "audit" and (code in {"", "admin", "platform"} or "platform" in name):
        return "平台总后台"
    return "公司端口"


def activity_inner_level(kind: str, actor: Any, account: Any) -> str:
    text = f"{actor or ''} {account or ''}".lower()
    if "driver" in text or kind == "assignment":
        return "司机/车辆"
    if "agency" in text:
        return "旅行社"
    if kind in {"order", "draft"}:
        return "调度/订单"
    if kind == "auction":
        return "订单大厅"
    if kind == "notification":
        return "通知"
    if kind in {"audit", "mobile_audit"}:
        return "审计/平台"
    return "公司动作"


def route_detail(row: dict[str, Any]) -> str:
    return f"{row.get('order_date') or '-'} {row.get('start_time') or ''} · {row.get('pickup_location') or '-'} -> {row.get('dropoff_location') or '-'}"


def search_blob(item: dict[str, Any], extra: Any = "") -> str:
    return " ".join(str(v or "") for v in [*item.values(), extra]).lower()


def with_source(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [{**item, "source": source} for item in items]


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    sql = "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?"
    return bool(conn.execute(sql, (table,)).fetchone())


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    return f"¥{amount:,.0f}" if amount else "-"


def normalize_phone_login(login: str) -> str:
    text = str(login or "").strip()
    if "-" in text and text[:3].isalpha():
        text = text.split("-", 1)[1]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or text


def phone_last6(login: str) -> str:
    digits = "".join(ch for ch in str(login or "") if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else ""


def load_login_guide() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if TEST_ACCOUNTS_JSON.exists():
        try:
            payload = json.loads(TEST_ACCOUNTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

    platform_admin = payload.get("platform_admin") or {"login": "admin", "password": "admin123"}
    carrier_accounts = []
    carrier_drivers = []
    for item in payload.get("carrier_accounts", []):
        management = item.get("management_account") or {}
        dispatch = item.get("dispatch_account") or {}
        operations = item.get("operations_account") or {}
        carrier_accounts.append(
            {
                "company_code": item.get("company_code") or "",
                "company_name": item.get("company_name") or "",
                "management_login": normalize_phone_login(management.get("login") or ""),
                "dispatch_login": normalize_phone_login(dispatch.get("login") or ""),
                "operations_login": normalize_phone_login(operations.get("login") or ""),
                "password_rule": "手机号后 6 位",
            }
        )
        for driver in item.get("drivers", []):
            login = normalize_phone_login(driver.get("login") or driver.get("phone") or "")
            carrier_drivers.append(
                {
                    "company_code": item.get("company_code") or "",
                    "driver_code": driver.get("driver_code") or "",
                    "name": driver.get("name") or "",
                    "login": login,
                    "password": phone_last6(login),
                }
            )

    agency_portals = []
    agency_staff = []
    agency_guides = []
    for item in payload.get("agency_portal_accounts", []):
        agency_portals.append(
            {
                "agency_code": item.get("agency_code") or "",
                "agency_name": item.get("agency_name") or "",
                "portal_code": item.get("portal_code") or "",
                "portal_password": item.get("portal_password") or "",
            }
        )
        management = item.get("management_account") or {}
        service = item.get("customer_service_account") or {}
        finance = item.get("finance_account") or {}
        agency_staff.append(
            {
                "agency_code": item.get("agency_code") or "",
                "management": management.get("login") or "",
                "customer_service": service.get("login") or "",
                "finance": finance.get("login") or "",
                "password": management.get("password") or service.get("password") or finance.get("password") or "",
            }
        )
        for guide in item.get("guide_accounts", []):
            agency_guides.append(
                {
                    "agency_code": item.get("agency_code") or "",
                    "name": guide.get("name") or "",
                    "login": guide.get("login") or "",
                    "password": guide.get("password") or "",
                }
            )

    dynamic = collect_dynamic_carrier_accounts()

    existing_codes = {item["company_code"] for item in carrier_accounts if item.get("company_code")}
    for item in dynamic["carrier_accounts"]:
        if item.get("company_code") not in existing_codes:
            carrier_accounts.append(item)
            existing_codes.add(item.get("company_code"))

    existing_driver_keys = {(item["company_code"], item["login"]) for item in carrier_drivers if item.get("company_code") and item.get("login")}
    for item in dynamic["carrier_drivers"]:
        key = (item.get("company_code"), item.get("login"))
        if key not in existing_driver_keys:
            carrier_drivers.append(item)
            existing_driver_keys.add(key)

    return {
        "urls": [
            {"platform": "平台总后台 / 车公司 Web", "local": "http://127.0.0.1:5173/", "server": "https://admin-trial.taxi-airport.jp/"},
            {"platform": "旅行社 Web", "local": "http://127.0.0.1:5173/#agency-portal", "server": "https://admin-trial.taxi-airport.jp/#agency-portal"},
            {"platform": "Activity Window", "local": "http://127.0.0.1:18768/account_activity_window.html", "server": "https://admin-trial.taxi-airport.jp/activity-window/"},
            {"platform": "API", "local": "http://127.0.0.1:18765", "server": "https://api-trial.taxi-airport.jp"},
        ],
        "platform_admin": platform_admin,
        "carrier_accounts": carrier_accounts,
        "carrier_drivers": carrier_drivers,
        "agency_portals": agency_portals,
        "agency_staff": agency_staff,
        "agency_guides": agency_guides,
        "notes": [
            "平台总后台账号只在 Web 总后台使用，不用于小程序登录。",
            "车公司管理 / 调度 / 运行管理 / 司机账号现统一为手机号数字登录，不再带公司前缀，初始密码为手机号后 6 位。",
            "旅行社 Portal 仍使用门户代码登录；旅行社内部账号和导游账号按当前测试表使用。",
        ],
    }


def collect_dynamic_carrier_accounts() -> dict[str, list[dict[str, Any]]]:
    carrier_accounts: list[dict[str, Any]] = []
    carrier_drivers: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_drivers: set[tuple[str, str]] = set()

    # Prefer the trial miniapp DB because it carries the current Yuzu/Daitora
    # accounts, then supplement it with the freshly fetched server snapshot and
    # the legacy local DB used by older web tools.
    for db_path in [TRIAL_DB, SERVER_SNAPSHOT, Path(DB_PATH)]:
        if not db_path.exists():
            continue
        try:
            dynamic = collect_dynamic_carrier_accounts_from_db(db_path)
        except Exception:
            continue

        for item in dynamic["carrier_accounts"]:
            code = item.get("company_code") or ""
            if code and code not in seen_codes:
                carrier_accounts.append(item)
                seen_codes.add(code)

        for item in dynamic["carrier_drivers"]:
            key = (item.get("company_code") or "", item.get("login") or "")
            if key[0] and key[1] and key not in seen_drivers:
                carrier_drivers.append(item)
                seen_drivers.add(key)

    return {"carrier_accounts": carrier_accounts, "carrier_drivers": carrier_drivers}


def collect_dynamic_carrier_accounts_from_db(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if not table_exists(conn, "users"):
            return {"carrier_accounts": [], "carrier_drivers": []}

        registrations: list[dict[str, Any]] = []
        registered_tenants: set[int] = set()

        if table_exists(conn, "company_registrations"):
            registrations = rows(
                conn,
                """
                SELECT tenant_id, company_code, company_name, contact_phone
                FROM company_registrations
                WHERE company_type = 'carrier' AND status = 'approved' AND tenant_id IS NOT NULL
                ORDER BY id
                """,
            )
            registered_tenants = {int(row.get("tenant_id")) for row in registrations if row.get("tenant_id") is not None}

        if table_exists(conn, "tenants"):
            params = tuple(registered_tenants)
            excluded = ",".join("?" for _ in params) or "NULL"
            registrations.extend(
                rows(
                    conn,
                    f"""
                    SELECT t.id AS tenant_id, t.slug AS company_code, t.name AS company_name, '' AS contact_phone
                    FROM tenants t
                    WHERE t.id NOT IN ({excluded})
                      AND EXISTS (
                        SELECT 1 FROM users u
                        WHERE u.tenant_id = t.id
                          AND u.role IN ('admin', 'dispatcher', 'operations_manager', 'driver')
                      )
                    ORDER BY t.id
                    """,
                    params,
                )
            )

        carrier_accounts: list[dict[str, Any]] = []
        carrier_drivers: list[dict[str, Any]] = []

        for reg in registrations:
            tenant_id = reg.get("tenant_id")
            if tenant_id is None:
                continue
            company_code = reg.get("company_code") or f"T{tenant_id}"
            company_name = reg.get("company_name") or company_code

            # Avoid an old single-user Daitora tenant leaking into the account
            # window when the current Daitora miniapp tenant is DTR/8204.
            if str(company_code).lower() == "daitora" and int(tenant_id) != 8204:
                continue

            role_rows = rows(
                conn,
                """
                SELECT username, display_name, role, phone, is_active
                FROM users
                WHERE tenant_id = ?
                ORDER BY CASE role
                  WHEN 'admin' THEN 1
                  WHEN 'dispatcher' THEN 2
                  WHEN 'operations_manager' THEN 3
                  WHEN 'driver' THEN 4
                  ELSE 9 END, is_active DESC, id ASC
                """,
                (tenant_id,),
            )
            if not role_rows:
                continue

            driver_rows = [row for row in role_rows if row.get("role") == "driver" and row.get("username")]
            manager_rows = [row for row in role_rows if row.get("role") in {"admin", "dispatcher", "operations_manager"}]
            if not driver_rows and not manager_rows:
                continue

            by_role: dict[str, dict[str, Any]] = {}
            for row in role_rows:
                role = row.get("role") or ""
                if role not in by_role and row.get("is_active"):
                    by_role[role] = row
                elif role not in by_role:
                    by_role[role] = row

            admin_login = normalize_phone_login((by_role.get("admin") or {}).get("username") or reg.get("contact_phone") or "")
            dispatch_login = normalize_phone_login((by_role.get("dispatcher") or {}).get("username") or "")
            operations_login = normalize_phone_login((by_role.get("operations_manager") or {}).get("username") or "")

            carrier_accounts.append(
                {
                    "company_code": company_code,
                    "company_name": company_name,
                    "management_login": admin_login,
                    "dispatch_login": dispatch_login,
                    "operations_login": operations_login,
                    "password_rule": "固定密码 447554" if company_code == "DTR" else "phone last 6 digits",
                }
            )

            for index, row in enumerate(driver_rows[:12], start=1):
                login = normalize_phone_login(row.get("username") or row.get("phone") or "")
                carrier_drivers.append(
                    {
                        "company_code": company_code,
                        "driver_code": f"{company_code}-D{index:02d}",
                        "name": row.get("display_name") or row.get("phone") or "",
                        "login": login,
                        "password": phone_last6(login),
                    }
                )

        return {"carrier_accounts": carrier_accounts, "carrier_drivers": carrier_drivers}
    finally:
        conn.close()

def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    generated_at = html.escape(str(data.get("generated_at") or ""))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TourFlow 全账号动作窗口</title>
  <style>
    :root {{ --bg:#eef3f8; --panel:#fff; --line:#d7e2ef; --text:#102033; --muted:#65758b; --blue:#246bfe; --green:#0f8a78; --amber:#b7791f; --violet:#6d28d9; --red:#d93445; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, "Microsoft YaHei", Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:24px 28px 16px; background:#10233f; color:#fff; }}
    h1 {{ margin:0; font-size:26px; }}
    header p {{ margin:8px 0 0; color:#c7d5e8; }}
    main {{ padding:18px 24px 32px; }}
    .guide,.tabs,.filters,.kpis,.table-wrap,.users,.matrix {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; box-shadow:0 18px 45px rgba(16,32,51,.08); }}
    .guide {{ margin-bottom:14px; padding:16px; }}
    .guide h2 {{ margin:0 0 8px; font-size:18px; }}
    .guide p {{ margin:0 0 12px; color:var(--muted); }}
    .guide-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .guide-block {{ border:1px solid #e3ebf5; border-radius:10px; padding:12px; background:#fbfdff; overflow:auto; }}
    .guide-block h3 {{ margin:0 0 8px; font-size:14px; }}
    .guide table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    .guide th,.guide td {{ padding:8px 8px; border-bottom:1px solid #edf2f7; text-align:left; vertical-align:top; white-space:nowrap; }}
    .guide th {{ background:#f7faff; color:#52637a; }}
    .guide code {{ font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background:#f1f5f9; padding:1px 5px; border-radius:6px; }}
    .guide ul {{ margin:8px 0 0 18px; color:var(--muted); }}
    .tabs {{ display:flex; gap:8px; padding:8px; margin-bottom:12px; }}
    .tab {{ border:0; border-radius:9px; padding:10px 14px; background:#f3f7fc; color:#52637a; font-weight:900; cursor:pointer; }}
    .tab.active {{ color:#fff; background:var(--blue); }}
    .filters {{ padding:14px; display:grid; grid-template-columns:1.5fr repeat(7, minmax(120px, 1fr)); gap:10px; position:sticky; top:0; z-index:5; }}
    input,select {{ width:100%; height:38px; border:1px solid var(--line); border-radius:9px; padding:0 11px; font-weight:700; color:var(--text); background:#fff; }}
    .kpis {{ margin:14px 0; padding:14px; display:grid; grid-template-columns:repeat(6, 1fr); gap:10px; }}
    .kpi {{ padding:12px; border-radius:10px; background:#f7faff; border:1px solid #e1e9f5; }}
    .kpi span {{ display:block; color:var(--muted); font-size:12px; font-weight:800; }}
    .kpi b {{ display:block; margin-top:6px; font-size:24px; }}
    .matrix {{ margin-bottom:14px; padding:14px; display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
    .node {{ border:1px solid #e1e9f5; background:#f8fbff; border-radius:10px; padding:12px; }}
    .node b {{ display:block; font-size:15px; }}
    .node small {{ display:block; margin-top:6px; color:var(--muted); line-height:1.5; }}
    .layout {{ display:grid; grid-template-columns:1fr 340px; gap:14px; align-items:start; }}
    .table-wrap {{ overflow:auto; max-height:calc(100vh - 340px); }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ padding:10px 12px; border-bottom:1px solid #edf2f7; text-align:left; vertical-align:top; }}
    th {{ background:#f7faff; color:#52637a; font-size:12px; position:sticky; top:0; z-index:2; }}
    tr:hover {{ background:#f8fbff; }}
    .badge {{ display:inline-flex; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:900; background:#edf4ff; color:#255ac7; white-space:nowrap; }}
    .scope {{ background:#eef2ff; color:#3730a3; }}
    .inner {{ background:#fff7ed; color:#9a3412; }}
    .auction {{ background:#ecfdf5; color:var(--green); }}
    .notification {{ background:#fff7ed; color:var(--amber); }}
    .mobile_audit,.audit {{ background:#f5f3ff; color:var(--violet); }}
    .order {{ background:#eff6ff; color:#1d4ed8; }}
    .draft {{ background:#fefce8; color:#a16207; }}
    .assignment {{ background:#f0fdfa; color:#0f766e; }}
    .detail {{ color:var(--muted); line-height:1.45; max-width:560px; }}
    .users {{ padding:14px; max-height:calc(100vh - 340px); overflow:auto; }}
    .users h2 {{ margin:0 0 10px; font-size:15px; }}
    .user {{ padding:9px 0; border-bottom:1px solid #edf2f7; }}
    .user b {{ display:block; }}
    .user small {{ color:var(--muted); line-height:1.5; }}
    .muted {{ color:var(--muted); }}
    @media (max-width:1200px) {{ .filters,.kpis,.layout,.guide-grid {{ grid-template-columns:1fr; }} .table-wrap,.users {{ max-height:none; }} }}
  </style>
</head>
<body>
  <header>
    <h1>全账号动作可视化窗口</h1>
    <p>生成时间：{generated_at} · 覆盖订单、订单大厅、通知、移动端审计与平台审计，并附上登录入口与测试账号矩阵。</p>
  </header>
  <main>
    <section class="guide">
      <h2>登录入口与测试账号</h2>
      <p>这里放的是当前测试环境常用入口。车公司手机号账号按新规则展示为纯数字登录名，不再带公司前缀。</p>
      <div class="guide-grid" id="guide"></div>
    </section>
    <section class="tabs">
      <button class="tab active" data-view="records">业务对象</button>
      <button class="tab" data-view="events">动作流水</button>
    </section>
    <section class="filters">
      <input id="q" placeholder="搜索订单 / 公司 / 账号 / 动作 / 路线" />
      <select id="source"><option value="">全部来源</option><option value="local">本地</option><option value="server">服务器</option></select>
      <select id="scope"><option value="">全部层级</option></select>
      <select id="company"><option value="">全部公司端口</option></select>
      <select id="inner"><option value="">全部公司内层级</option></select>
      <select id="account"><option value="">全部账号/人员</option></select>
      <select id="kind"><option value="">全部动作类型</option></select>
      <select id="time"><option value="">全部时间</option><option value="today">今天</option><option value="3d">最近 3 天</option><option value="7d">最近 7 天</option></select>
    </section>
    <section class="kpis" id="kpis"></section>
    <section class="matrix" id="matrix"></section>
    <section class="layout">
      <div class="table-wrap">
        <table>
          <thead id="head"></thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <aside class="users">
        <h2>账号列表</h2>
        <div id="users"></div>
      </aside>
    </section>
  </main>
  <script>
    const DATA = {payload};
    const $ = id => document.getElementById(id);
    const state = {{ view:'records', q:'', source:'', scope:'', company:'', inner:'', account:'', kind:'', time:'' }};
    const kinds = {{ order:'订单', draft:'订单草稿', auction:'订单大厅', assignment:'派车任务', notification:'通知', mobile_audit:'移动端审计', audit:'平台审计' }};
    const esc = v => String(v ?? '').replace(/[&<>"']/g, s => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[s]));
    const unique = arr => [...new Set(arr.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'zh-CN'));
    const sourceLabel = v => v === 'server' ? '服务器' : '本地';
    function currentData() {{ return state.view === 'events' ? DATA.events : DATA.records; }}
    function itemScope(e) {{ return e.scope_level || '公司端口'; }}
    function itemCompany(e) {{ return e.company_port || e.tenant || '-'; }}
    function itemInner(e) {{ return e.company_inner_level || '公司动作'; }}
    function userScope(u) {{ return u.scope_level || ((u.username === 'admin') ? '平台总后台' : '公司端口'); }}
    function userCompany(u) {{ return u.company_port || u.tenant_name || u.tenant_code || '-'; }}
    function userInner(u) {{ return u.company_inner_level || u.role || '-'; }}
    function resetSelect(id, values, label, formatter=(x)=>x) {{
      const el = $(id), old = el.value;
      el.innerHTML = `<option value="">${{label}}</option>`;
      values.forEach(v => {{ const o=document.createElement('option'); o.value=v; o.textContent=formatter(v); el.appendChild(o); }});
      el.value = values.includes(old) ? old : '';
      state[id] = el.value;
    }}
    function refreshOptions() {{
      const all = currentData();
      resetSelect('scope', unique(all.map(itemScope)), '全部层级');
      resetSelect('company', unique(all.map(itemCompany)), '全部公司端口');
      resetSelect('inner', unique(all.map(itemInner)), '全部公司内层级');
      resetSelect('account', unique(all.map(e => e.account).concat(all.map(e => e.actor))), '全部账号/人员');
      resetSelect('kind', unique(all.map(e => e.kind)), '全部动作类型', v => kinds[v] || v);
    }}
    ['q','source','scope','company','inner','account','kind','time'].forEach(id => $(id).addEventListener('input', () => {{ state[id] = $(id).value; render(); }}));
    document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {{ state.view = btn.dataset.view; document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === btn)); refreshOptions(); render(); }}));
    function afterTime(e) {{
      if (!state.time || !e.time) return true;
      const d = new Date(String(e.time).replace(' ', 'T'));
      if (Number.isNaN(d.getTime())) return true;
      const days = state.time === 'today' ? 1 : state.time === '3d' ? 3 : 7;
      return new Date() - d <= days * 86400000;
    }}
    function filtered() {{
      const q = state.q.trim().toLowerCase();
      return currentData().filter(e =>
        (!q || String(e.search || '').includes(q)) &&
        (!state.source || e.source === state.source) &&
        (!state.scope || itemScope(e) === state.scope) &&
        (!state.company || itemCompany(e) === state.company) &&
        (!state.inner || itemInner(e) === state.inner) &&
        (!state.account || e.account === state.account || e.actor === state.account) &&
        (!state.kind || e.kind === state.kind) &&
        afterTime(e)
      );
    }}
    function filteredUsers() {{
      const q = state.q.trim().toLowerCase();
      return (DATA.users || []).filter(u =>
        (!q || String(u.search || '').includes(q)) &&
        (!state.source || u.source === state.source) &&
        (!state.scope || userScope(u) === state.scope) &&
        (!state.company || userCompany(u) === state.company) &&
        (!state.inner || userInner(u) === state.inner) &&
        (!state.account || u.username === state.account || u.display_name === state.account)
      );
    }}
    function renderKpis(items) {{
      const by = k => items.filter(e => e.kind === k).length;
      const defs = [
        ['当前结果', items.length],
        ['平台动作', items.filter(e => itemScope(e) === '平台总后台').length],
        ['公司端口', unique(items.map(itemCompany)).length],
        ['订单/草稿', by('order') + by('draft')],
        ['大厅/派车', by('auction') + by('assignment')],
        ['审计/通知', by('audit') + by('mobile_audit') + by('notification')]
      ];
      $('kpis').innerHTML = defs.map(x => `<div class="kpi"><span>${{esc(x[0])}}</span><b>${{x[1]}}</b></div>`).join('');
    }}
    function renderMatrix(items) {{
      const groups = new Map();
      items.forEach(e => {{
        const key = `${{itemScope(e)}}||${{itemCompany(e)}}||${{itemInner(e)}}`;
        groups.set(key, (groups.get(key) || 0) + 1);
      }});
      $('matrix').innerHTML = [...groups.entries()].sort((a,b)=>b[1]-a[1]).slice(0,12).map(([key,count]) => {{
        const [scope, company, inner] = key.split('||');
        return `<div class="node"><b>${{esc(company)}} <span class="badge">${{count}}</span></b><small><span class="badge scope">${{esc(scope)}}</span> <span class="badge inner">${{esc(inner)}}</span></small></div>`;
      }}).join('') || '<div class="node"><b>暂无数据</b><small>当前筛选条件下没有可显示的动作。</small></div>';
    }}
    function renderGuide() {{
      const guide = DATA.login_guide || {{}};
      const block = (title, head, rows) => `
        <div class="guide-block">
          <h3>${{esc(title)}}</h3>
          <table>
            <thead><tr>${{head.map(x => `<th>${{esc(x)}}</th>`).join('')}}</tr></thead>
            <tbody>${{rows.join('') || '<tr><td colspan="99" class="muted">暂无</td></tr>'}}</tbody>
          </table>
        </div>`;
      const urlRows = (guide.urls || []).map(item => `<tr><td>${{esc(item.platform)}}</td><td><code>${{esc(item.local)}}</code></td><td><code>${{esc(item.server)}}</code></td></tr>`);
      const platformRows = [guide.platform_admin ? `<tr><td>平台总后台</td><td><code>${{esc(guide.platform_admin.login)}}</code></td><td><code>${{esc(guide.platform_admin.password)}}</code></td></tr>` : ''];
      const carrierRows = (guide.carrier_accounts || []).map(item => `<tr><td>${{esc(item.company_code)}}</td><td>${{esc(item.company_name)}}</td><td><code>${{esc(item.management_login)}}</code></td><td><code>${{esc(item.dispatch_login)}}</code></td><td><code>${{esc(item.operations_login)}}</code></td><td>${{esc(item.password_rule)}}</td></tr>`);
      const driverRows = (guide.carrier_drivers || []).map(item => `<tr><td>${{esc(item.company_code)}}</td><td>${{esc(item.driver_code)}}</td><td>${{esc(item.name)}}</td><td><code>${{esc(item.login)}}</code></td><td><code>${{esc(item.password)}}</code></td></tr>`);
      const portalRows = (guide.agency_portals || []).map(item => `<tr><td>${{esc(item.agency_code)}}</td><td>${{esc(item.agency_name)}}</td><td><code>${{esc(item.portal_code)}}</code></td><td><code>${{esc(item.portal_password)}}</code></td></tr>`);
      const agencyRows = (guide.agency_staff || []).map(item => `<tr><td>${{esc(item.agency_code)}}</td><td><code>${{esc(item.management)}}</code></td><td><code>${{esc(item.customer_service)}}</code></td><td><code>${{esc(item.finance)}}</code></td><td><code>${{esc(item.password)}}</code></td></tr>`);
      const guideRows = (guide.agency_guides || []).map(item => `<tr><td>${{esc(item.agency_code)}}</td><td>${{esc(item.name)}}</td><td><code>${{esc(item.login)}}</code></td><td><code>${{esc(item.password)}}</code></td></tr>`);
      $('guide').innerHTML = [
        block('访问地址', ['端口', '本地', '服务器'], urlRows),
        block('平台总后台', ['入口', '登录名', '密码'], platformRows),
        block('车公司管理 / 调度 / 运行管理', ['公司', '公司名', '管理', '调度', '运行管理', '初始密码'], carrierRows),
        block('司机账号', ['公司', '司机代码', '姓名', '登录名', '初始密码'], driverRows),
        block('旅行社 Portal', ['旅行社', '名称', '门户代码', '密码'], portalRows),
        block('旅行社内部账号', ['旅行社', '管理', '客服', '财务', '密码'], agencyRows),
        block('旅行社导游', ['旅行社', '姓名', '登录名', '密码'], guideRows),
        `<div class="guide-block"><h3>说明</h3><ul>${{(guide.notes || []).map(x => `<li>${{esc(x)}}</li>`).join('')}}</ul></div>`
      ].join('');
    }}
    function renderHead() {{
      $('head').innerHTML = state.view === 'events'
        ? '<tr><th>来源</th><th>层级</th><th>公司端口</th><th>公司内层级</th><th>时间</th><th>账号/人员</th><th>类型</th><th>动作</th><th>对象</th><th>状态</th><th>详情</th></tr>'
        : '<tr><th>来源</th><th>层级</th><th>公司端口</th><th>公司内层级</th><th>时间</th><th>类型</th><th>业务对象</th><th>状态</th><th>归属人员</th><th>金额</th><th>详情</th></tr>';
    }}
    function renderRows(items) {{
      $('rows').innerHTML = items.slice(0, 1500).map(e => state.view === 'events' ? `<tr>
        <td><span class="badge">${{esc(sourceLabel(e.source))}}</span></td><td><span class="badge scope">${{esc(itemScope(e))}}</span></td><td><b>${{esc(itemCompany(e))}}</b><br><span class="muted">${{esc(e.tenant_code || '')}}</span></td><td><span class="badge inner">${{esc(itemInner(e))}}</span></td>
        <td>${{esc(e.time || '-')}}</td><td><b>${{esc(e.actor || '-')}}</b><br><span class="muted">${{esc(e.account || '-')}}</span></td><td><span class="badge ${{e.kind}}">${{esc(kinds[e.kind] || e.kind)}}</span></td><td>${{esc(e.action || '-')}}</td><td><b>${{esc(e.entity || '-')}}</b></td><td>${{esc(e.status || '-')}}</td><td class="detail">${{esc(e.detail || '')}}</td>
      </tr>` : `<tr>
        <td><span class="badge">${{esc(sourceLabel(e.source))}}</span></td><td><span class="badge scope">${{esc(itemScope(e))}}</span></td><td><b>${{esc(itemCompany(e))}}</b><br><span class="muted">${{esc(e.tenant_code || '')}}</span></td><td><span class="badge inner">${{esc(itemInner(e))}}</span></td>
        <td>${{esc(e.time || '-')}}</td><td><span class="badge ${{e.kind}}">${{esc(kinds[e.kind] || e.kind)}}</span></td><td><b>${{esc(e.entity || '-')}}</b></td><td>${{esc(e.status || '-')}}</td><td>${{esc(e.actor || '-')}}</td><td>${{esc(e.price || '')}}</td><td class="detail">${{esc(e.detail || '')}}</td>
      </tr>`).join('') || '<tr><td colspan="11" class="muted">当前筛选条件下没有数据。</td></tr>';
    }}
    function renderUsers() {{
      const users = filteredUsers();
      $('users').innerHTML = users.map(u => `<div class="user"><b>${{esc(u.display_name || u.username || '-')}}</b><small>${{esc(sourceLabel(u.source))}} · ${{esc(userScope(u))}} · ${{esc(userCompany(u))}} · ${{esc(userInner(u))}}<br>${{esc(u.username || '-')}} · ${{u.is_active ? '启用' : '停用'}} · 最近登录 ${{esc(u.last_login_at || '-')}}</small></div>`).join('') || '<div class="muted">没有符合条件的账号</div>';
    }}
    function render() {{
      const items = filtered();
      renderHead();
      renderKpis(items);
      renderMatrix(items);
      renderRows(items);
      renderUsers();
    }}
    renderGuide();
    refreshOptions();
    render();
  </script>
</body>
</html>"""


if __name__ == "__main__":
    main()

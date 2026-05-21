import json
from typing import Any

from backend.db.database import get_connection
from backend.services.tenant_context import get_current_tenant_id


SENSITIVE_KEYS = {"password", "password_hash", "token", "authorization", "secret"}


def ensure_audit_schema() -> None:
    with get_connection() as conn:
        _ensure_audit_tables(conn)
        conn.commit()


def record_audit(
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    actor: str | None = None,
    source_path: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    ensure_audit_schema()
    diff = _diff(before, after)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO audit_logs (
                tenant_id, actor, action, entity_type, entity_id, summary,
                before_json, after_json, diff_json, source_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                get_current_tenant_id(),
                actor or "system",
                action,
                entity_type,
                "" if entity_id is None else str(entity_id),
                summary or _summary(action, entity_type, entity_id, diff),
                _json(before),
                _json(after),
                _json(diff),
                source_path,
            ),
        )
        conn.commit()
        return _get_audit_log(conn, cursor.lastrowid) or {"id": cursor.lastrowid}


def list_audit_logs(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_audit_schema()
    params = params or {}
    clauses = ["tenant_id = ?"]
    values: list[Any] = [get_current_tenant_id()]
    for field in ("action", "entity_type", "entity_id", "actor"):
        value = params.get(field)
        if value:
            clauses.append(f"{field} = ?")
            values.append(str(value))
    keyword = params.get("keyword")
    if keyword:
        clauses.append("(summary LIKE ? OR action LIKE ? OR entity_type LIKE ? OR actor LIKE ?)")
        like = f"%{keyword}%"
        values.extend([like, like, like, like])
    limit = _limit(params.get("limit"), default=100, maximum=500)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM audit_logs
            WHERE {" AND ".join(clauses)}
            ORDER BY id DESC
            LIMIT ?
            """,
            [*values, limit],
        ).fetchall()
    return [_decode_log(row) for row in rows]


def get_entity_history(entity_type: str, entity_id: Any, limit: int = 100) -> list[dict[str, Any]]:
    return list_audit_logs(
        {
            "entity_type": entity_type,
            "entity_id": "" if entity_id is None else str(entity_id),
            "limit": limit,
        }
    )


def scan_data_anomalies() -> dict[str, Any]:
    ensure_audit_schema()
    issues: list[dict[str, Any]] = []
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        _append_count_issue(
            conn,
            issues,
            code="missing_price",
            severity="medium",
            title="Orders missing price",
            sql="""
                SELECT id, oid, order_date, pickup_location, dropoff_location
                FROM orders
                WHERE tenant_id = ? AND COALESCE(is_deleted, 0) = 0
                  AND (price IS NULL OR price = 0)
                ORDER BY order_date DESC, id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        _append_count_issue(
            conn,
            issues,
            code="assigned_without_active_assignment",
            severity="high",
            title="Assigned orders without active assignment",
            sql="""
                SELECT o.id, o.oid, o.order_date, o.pickup_location, o.dropoff_location
                FROM orders o
                LEFT JOIN assignments a
                  ON a.order_id = o.id AND a.status = 'active' AND a.tenant_id = o.tenant_id
                WHERE o.tenant_id = ? AND COALESCE(o.is_deleted, 0) = 0
                  AND o.dispatch_status = 'assigned'
                  AND a.id IS NULL
                ORDER BY o.order_date DESC, o.id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        _append_count_issue(
            conn,
            issues,
            code="active_assignment_order_not_assigned",
            severity="high",
            title="Active assignments whose order is not assigned",
            sql="""
                SELECT a.id AS assignment_id, o.id, o.oid, o.dispatch_status, o.order_date
                FROM assignments a
                JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
                WHERE a.tenant_id = ? AND a.status = 'active'
                  AND COALESCE(o.is_deleted, 0) = 0
                  AND COALESCE(o.dispatch_status, '') != 'assigned'
                ORDER BY a.id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        _append_count_issue(
            conn,
            issues,
            code="active_assignment_missing_resource",
            severity="medium",
            title="Active assignments missing driver or vehicle",
            sql="""
                SELECT id AS assignment_id, order_id, driver_id, vehicle_id
                FROM assignments
                WHERE tenant_id = ? AND status = 'active'
                  AND (driver_id IS NULL OR driver_id = 0 OR vehicle_id IS NULL OR vehicle_id = 0)
                ORDER BY id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        _append_count_issue(
            conn,
            issues,
            code="open_incidents",
            severity="medium",
            title="Open incidents still need attention",
            sql="""
                SELECT id, order_id, severity, title, created_at
                FROM incidents
                WHERE tenant_id = ? AND status = 'open'
                ORDER BY id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        _append_count_issue(
            conn,
            issues,
            code="failed_parser_drafts",
            severity="low",
            title="Failed parser drafts preserved for review",
            sql="""
                SELECT id, oid, raw_text, created_at
                FROM order_drafts
                WHERE tenant_id = ? AND parse_status = 'failed'
                ORDER BY id DESC
                LIMIT 30
            """,
            params=(tenant_id,),
        )
        scan = {
            "issue_count": sum(issue["count"] for issue in issues),
            "category_count": len([issue for issue in issues if issue["count"] > 0]),
            "issues": issues,
        }
        cursor = conn.execute(
            """
            INSERT INTO data_anomaly_scans (tenant_id, scan_type, issue_count, result_json)
            VALUES (?, 'governance', ?, ?)
            """,
            (tenant_id, scan["issue_count"], _json(scan)),
        )
        conn.commit()
        scan["scan_id"] = cursor.lastrowid
    record_audit(
        "data_anomaly_scan",
        "governance",
        scan.get("scan_id"),
        after={"issue_count": scan["issue_count"], "category_count": scan["category_count"]},
        actor="system",
        source_path="/api/audit/scan",
        summary=f"Data anomaly scan found {scan['issue_count']} issues",
    )
    return scan


def list_anomaly_scans(limit: int = 20) -> list[dict[str, Any]]:
    ensure_audit_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM data_anomaly_scans
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (get_current_tenant_id(), _limit(limit, default=20, maximum=100)),
        ).fetchall()
    scans = []
    for row in rows:
        item = dict(row)
        item["result"] = _loads(item.pop("result_json", None)) or {}
        scans.append(item)
    return scans


def _ensure_audit_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            actor TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            summary TEXT,
            before_json TEXT,
            after_json TEXT,
            diff_json TEXT,
            source_path TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_anomaly_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            scan_type TEXT NOT NULL DEFAULT 'governance',
            issue_count INTEGER NOT NULL DEFAULT 0,
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _append_count_issue(conn, issues: list[dict[str, Any]], code: str, severity: str, title: str, sql: str, params: tuple[Any, ...]) -> None:
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    issues.append({"code": code, "severity": severity, "title": title, "count": len(rows), "examples": rows})


def _diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if before is None and after is None:
        return {}
    before = before or {}
    after = after or {}
    keys = sorted(set(before) | set(after))
    result: dict[str, dict[str, Any]] = {}
    for key in keys:
        if key in SENSITIVE_KEYS:
            continue
        left = before.get(key)
        right = after.get(key)
        if left != right:
            result[key] = {"before": _sanitize(left), "after": _sanitize(right)}
    return result


def _summary(action: str, entity_type: str, entity_id: Any, diff: dict[str, Any]) -> str:
    changed = ", ".join(list(diff.keys())[:6])
    suffix = f": {changed}" if changed else ""
    return f"{action} {entity_type} {entity_id or ''}{suffix}".strip()


def _get_audit_log(conn, log_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,)).fetchone()
    return _decode_log(row) if row else None


def _decode_log(row) -> dict[str, Any]:
    item = dict(row)
    item["before"] = _loads(item.pop("before_json", None))
    item["after"] = _loads(item.pop("after_json", None))
    item["diff"] = _loads(item.pop("diff_json", None)) or {}
    return item


def _json(value: Any) -> str:
    return json.dumps(_sanitize(value), ensure_ascii=False, sort_keys=True)


def _loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str) and len(value) > 800:
        return value[:800] + "...[truncated]"
    return value


def _limit(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))

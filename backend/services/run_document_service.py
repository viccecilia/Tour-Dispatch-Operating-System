from __future__ import annotations

import json
import re
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.config import RUNTIME_DIR
from backend.db.database import get_connection
from backend.services.notification_service import create_notification
from backend.services.order_number_service import driver_short_code, normalize_source_code, plate_short_code
from backend.services.tariff_service import recommend_route_fare
from backend.services.tenant_context import get_current_tenant_id
from backend.services.auth_account_service import supabase_enabled
from backend.services.document_model_service import (
    build_document_snapshot,
    canonical_json,
    make_run_group_id,
    make_document_version_id,
    persist_route_nodes,
    prepare_order_document_fields,
    record_document_event,
    sha256_file,
    shift_date_time,
    snapshot_source_sha256,
    upsert_document_batch,
)


class DriverAccountPreflightError(ValueError):
    def __init__(self, blocked: list[dict[str, Any]]):
        super().__init__("driver_account_preflight_failed")
        self.blocked = blocked


EDITABLE_FIELDS = {
    "order_date",
    "start_time",
    "operations_business_area",
    "order_type",
    "pickup_location",
    "dropoff_location",
    "price",
}
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
JP_FONT_PATH = FONT_DIR / "NotoSansJP-VF.ttf"
SC_FONT_PATH = FONT_DIR / "NotoSansSC-VF.ttf"
# Bump this whenever the formal PDF layout or fixed rendering rules change.
# It prevents a previously generated file from being reused after a template fix.
DOCUMENT_RENDERER_VERSION = "v014-hire-phase2c3-shared-10-job-pages-20261012-1"


def _optional_coalesce_expr(
    sources: list[tuple[str, set[str], tuple[str, ...]]], result_name: str
) -> str:
    expressions = []
    for alias, columns, candidates in sources:
        expressions.extend(f"NULLIF({alias}.{column}, '')" for column in candidates if column in columns)
    if not expressions:
        return f"'' AS {result_name}"
    return f"COALESCE({', '.join(expressions)}, '') AS {result_name}"


def group_key(business_date: Any, driver_id: Any, vehicle_id: Any) -> str:
    return f"{business_date}:{int(driver_id)}:{int(vehicle_id)}"


def parse_group_key(value: Any) -> tuple[str, int, int]:
    parts = str(value or "").split(":")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        raise ValueError("invalid_run_group")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[0]):
        raise ValueError("invalid_run_group_date")
    return parts[0], int(parts[1]), int(parts[2])


def list_run_groups(business_date: str | None = None, tenant_id: int | None = None) -> list[dict[str, Any]]:
    tenant = int(tenant_id or get_current_tenant_id())
    values: list[Any] = [tenant]
    where = ""
    if business_date:
        where = "AND o.order_date = ?"
        values.append(str(business_date)[:10])
    with closing(get_connection()) as conn:
        driver_columns = {row["name"] for row in conn.execute("PRAGMA table_info(drivers)").fetchall()}
        vehicle_columns = {row["name"] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
        driver_print_expr = _optional_coalesce_expr(
            [("d", driver_columns, ("print_name", "document_name", "japanese_display_name"))],
            "driver_print_name",
        )
        vehicle_office_expr = _optional_coalesce_expr(
            [("v", vehicle_columns, ("office", "office_name"))], "vehicle_office"
        )
        manager_expr = _optional_coalesce_expr(
            [
                ("v", vehicle_columns, ("operations_manager", "manager_name")),
                ("d", driver_columns, ("operations_manager", "manager_name")),
            ],
            "operations_manager",
        )
        garage_expr = _optional_coalesce_expr(
            [
                ("v", vehicle_columns, ("garage_name", "garage_address", "garage_location")),
                ("d", driver_columns, ("garage_name", "garage_address", "garage_location")),
            ],
            "garage_location",
        )
        garage_out_time_expr = _optional_coalesce_expr(
            [
                ("v", vehicle_columns, ("garage_out_time",)),
                ("d", driver_columns, ("garage_out_time",)),
            ],
            "garage_out_time",
        )
        garage_in_time_expr = _optional_coalesce_expr(
            [
                ("v", vehicle_columns, ("garage_in_time",)),
                ("d", driver_columns, ("garage_in_time",)),
            ],
            "garage_in_time",
        )
        rows = conn.execute(
            f"""
            SELECT a.id AS assignment_id, a.order_id, a.driver_id, a.vehicle_id,
                   o.oid, o.order_date, o.end_date, o.start_time, o.end_time,
                   o.daily_import_group_key,
                   o.operations_business_area, o.order_type, o.order_note_code, o.order_source,
                   o.pickup_location, o.dropoff_location, o.price, o.price_jpy, o.fee_remark,
                   o.agency_name, o.guest_name, o.guest_contact, o.flight_number, o.source_channel,
                   o.passenger_count, o.luggage_count, o.remark,
                   o.document_kind, o.applicant_slot, o.applicant_slot_confirmed,
                   o.pickup_source_text, o.dropoff_source_text,
                   o.pickup_parsed_location, o.dropoff_parsed_location,
                   o.pickup_suggested_location, o.dropoff_suggested_location,
                   o.pickup_location_confirmed, o.dropoff_location_confirmed,
                   o.fare_jpy, o.service_fee_jpy, o.document_advance_jpy,
                   o.toll_fee_jpy, o.parking_fee_jpy, o.price_confirmed,
                   o.tax_included_confirmed, o.price_snapshot_json,
                   o.area_validation_status,
                   o.end_time_source, o.end_time_confirmed,
                   o.run_confirmation_status, o.run_confirmed_at,
                   o.run_confirmed_by_user_id, o.run_confirmed_by, o.run_revision,
                   d.name AS driver_name, d.driver_code, d.office AS driver_office,
                   {driver_print_expr}, {vehicle_office_expr}, {manager_expr},
                   {garage_expr}, {garage_out_time_expr}, {garage_in_time_expr},
                   v.plate_number, v.vehicle_type, v.seat_count
            FROM assignments a
            JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
            JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
            JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
            WHERE a.tenant_id = ? AND a.status = 'active'
              AND COALESCE(o.is_deleted, 0) = 0 {where}
            ORDER BY o.order_date, d.name, v.plate_number, o.start_time, a.id
            """,
            values,
        ).fetchall()
        documents = conn.execute(
            """
            SELECT * FROM driver_run_documents
            WHERE tenant_id = ?
            ORDER BY business_date, driver_id, vehicle_id, version DESC
            """,
            (tenant,),
        ).fetchall()
        override_rows = conn.execute(
            "SELECT * FROM dispatch_route_node_overrides WHERE tenant_id = ? ORDER BY id",
            (tenant,),
        ).fetchall()
        field_override_rows = conn.execute(
            "SELECT run_group_id, field_id, value_text FROM dispatch_document_field_overrides WHERE tenant_id = ? ORDER BY id",
            (tenant,),
        ).fetchall()
        company_row = conn.execute(
            """
            SELECT COALESCE(NULLIF(registered_name, ''), company_name) AS company_name,
                   address, contact_name, contact_phone, contact_email, business_license_number
            FROM company_registrations
            WHERE tenant_id = ? OR (managing_tenant_id = ? AND company_type = 'carrier')
            ORDER BY CASE status WHEN 'approved' THEN 0 WHEN 'active' THEN 1 ELSE 2 END, id DESC
            LIMIT 1
            """,
            (tenant, tenant),
        ).fetchone()
        tenant_row = conn.execute("SELECT name FROM tenants WHERE id = ?", (tenant,)).fetchone()
    company = dict(company_row) if company_row else {"company_name": (tenant_row["name"] if tenant_row else "株式会社大寅"), "address": "", "contact_name": "", "contact_phone": "", "contact_email": "", "business_license_number": ""}
    latest: dict[str, dict[str, Any]] = {}
    for raw in documents:
        doc = dict(raw)
        key = group_key(doc["business_date"], doc["driver_id"], doc["vehicle_id"])
        latest.setdefault(key, doc)
    overrides_by_group: dict[str, list[dict[str, Any]]] = {}
    for raw in override_rows:
        item = dict(raw)
        try:
            decoded = json.loads(item.get("changed_fields_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = {}
        item["changed_fields"] = decoded.get("fields") if isinstance(decoded, dict) else []
        overrides_by_group.setdefault(str(item.get("run_group_id") or ""), []).append(item)
    field_overrides_by_group: dict[str, dict[str, str]] = {}
    for raw in field_override_rows:
        item = dict(raw)
        field_overrides_by_group.setdefault(str(item.get("run_group_id") or ""), {})[
            str(item.get("field_id") or "")
        ] = str(item.get("value_text") or "")
    grouped: dict[str, dict[str, Any]] = {}
    for raw in rows:
        item = dict(raw)
        item["printable_stopovers"] = _printable_stopovers_from_route_note(item)
        item["area_warning"], item["area_route"] = _area_review_from_route_note(item)
        recommendation = recommend_route_fare(
            item.get("pickup_location"),
            item.get("dropoff_location"),
            item.get("order_type"),
            item.get("vehicle_type"),
            item.get("remark"),
            item.get("seat_count"),
        )
        item["recommended_price"] = recommendation.get("amount") if recommendation else None
        item["recommended_price_label"] = recommendation.get("label") if recommendation else ""
        key = group_key(item["order_date"], item["driver_id"], item["vehicle_id"])
        group = grouped.setdefault(
            key,
            {
                "key": key,
                "tenant_id": tenant,
                "business_date": item["order_date"],
                "driver_id": item["driver_id"],
                "vehicle_id": item["vehicle_id"],
                "driver_name": item.get("driver_name") or "未定司机",
                "driver_print_name": item.get("driver_print_name") or "",
                "driver_code": item.get("driver_code") or "",
                "driver_office": item.get("driver_office") or "",
                "vehicle_office": item.get("vehicle_office") or "",
                "operations_manager": item.get("operations_manager") or "",
                "garage_location": item.get("garage_location") or "",
                "garage_out_time": item.get("garage_out_time") or "",
                "garage_in_time": item.get("garage_in_time") or "",
                "plate_number": item.get("plate_number") or "",
                "vehicle_type": item.get("vehicle_type") or "",
                "seat_count": item.get("seat_count"),
                "company": company,
                "orders": [],
            },
        )
        group["orders"].append(item)
    result = []
    for key, group in grouped.items():
        run_group_id = make_run_group_id(
            group["tenant_id"], group["business_date"], group["driver_id"], group["vehicle_id"]
        )
        group["route_node_overrides"] = overrides_by_group.get(run_group_id, [])
        group["document_field_overrides"] = field_overrides_by_group.get(run_group_id, {})
        total = len(group["orders"])
        confirmed = sum(1 for order in group["orders"] if order.get("run_confirmation_status") == "confirmed")
        state = "confirmed" if confirmed == total and total else ("confirming" if confirmed else "pending")
        doc = latest.get(key)
        current_hash = _source_hash(group)
        document_status = (doc or {}).get("status") or "none"
        if doc and doc.get("source_hash") != current_hash:
            document_status = "stale"
        validation_issues = _validate_group(group, require_complete=True)
        if document_status == "generated":
            workflow_status, workflow_text = "pdf_pending", "PDF 待确认"
        elif document_status == "reviewed":
            workflow_status, workflow_text = "ready", "可发布"
        elif document_status == "published":
            workflow_status, workflow_text = "published", "已发布"
        elif validation_issues:
            workflow_status, workflow_text = "needs_data", f"{len(validation_issues)} 项待补"
        else:
            workflow_status, workflow_text = "draft_ready", "待审核"
        group.update(
            {
                "order_count": total,
                "confirmed_count": confirmed,
                "pending_count": total - confirmed,
                "confirmation_status": state,
                "confirmation_text": f"{confirmed}/{total} 已确认",
                "latest_document": _public_document(doc) if doc else None,
                "document_status": document_status,
                "workflow_status": workflow_status,
                "workflow_status_text": workflow_text,
                "validation_issues": validation_issues,
            }
        )
        result.append(group)
    return result


def confirm_order(order_id: Any, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    _require_operations_actor(actor)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    order_id_int = int(order_id)
    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "运行管理")
    updates = {key: payload.get(key) for key in EDITABLE_FIELDS if key in payload}
    pdf_edit = bool(payload.get("pdf_edit"))
    required = {
        "order_date": "日付", "start_time": "時刻", "operations_business_area": "営業区域",
        "order_type": "運送種別", "pickup_location": "乗車地", "dropoff_location": "降車地", "price": "運賃",
    }
    missing = [label for key, label in required.items() if key not in updates or _missing_confirm_value(key, updates.get(key))]
    if missing and not pdf_edit:
        raise ValueError("確認できません。未入力：" + "、".join(missing))
    if pdf_edit and not updates:
        raise ValueError("変更する項目がありません")
    with closing(get_connection()) as conn:
        before = conn.execute("SELECT * FROM orders WHERE tenant_id = ? AND id = ?", (tenant, order_id_int)).fetchone()
        if not before:
            raise ValueError("order_not_found")
        assignment = conn.execute(
            "SELECT driver_id, vehicle_id FROM assignments WHERE tenant_id = ? AND order_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (tenant, order_id_int),
        ).fetchone()
        if not assignment:
            raise ValueError("order_not_assigned")
        changed = any(_normalized(before[key]) != _normalized(value) for key, value in updates.items())
        if updates:
            clauses = [f"{key} = ?" for key in updates]
            values = [_db_value(key, updates[key]) for key in updates]
            if "pickup_location" in updates:
                clauses.append("pickup_location_confirmed = 1")
            if "dropoff_location" in updates:
                clauses.append("dropoff_location_confirmed = 1")
            if "price" in updates and _normalized(before["price"]) != _normalized(updates["price"]):
                clauses.extend(
                    [
                        "price_confirmed = 0",
                        "price_confirmed_by_user_id = NULL",
                        "price_confirmed_by = NULL",
                        "price_confirmed_at = NULL",
                    ]
                )
            if (
                "start_time" in updates
                and str(before["end_time_source"] or "") == "suggested_60m"
                and not int(before["end_time_confirmed"] or 0)
            ):
                shifted = shift_date_time(updates.get("order_date") or before["order_date"], updates["start_time"], 60)
                clauses.extend(["end_date = ?", "end_time = ?"])
                values.extend([shifted["date"], shifted["time"]])
            if changed:
                clauses.append("run_revision = COALESCE(run_revision, 1) + 1")
            conn.execute(
                f"UPDATE orders SET {', '.join(clauses)}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
                [*values, tenant, order_id_int],
            )
        if pdf_edit:
            conn.execute(
                """
                UPDATE orders
                SET run_confirmation_status = 'pending', run_confirmed_at = NULL,
                    run_confirmed_by_user_id = NULL, run_confirmed_by = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (tenant, order_id_int),
            )
        else:
            conn.execute(
                """
                UPDATE orders
                SET run_confirmation_status = 'confirmed', run_confirmed_at = CURRENT_TIMESTAMP,
                    run_confirmed_by_user_id = ?, run_confirmed_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (actor_id, actor_name, tenant, order_id_int),
            )
        if changed:
            _mark_group_stale(conn, tenant, str(before["order_date"]), assignment["driver_id"], assignment["vehicle_id"])
            new_date = str(updates.get("order_date") or before["order_date"])
            if new_date != str(before["order_date"]):
                _mark_group_stale(conn, tenant, new_date, assignment["driver_id"], assignment["vehicle_id"])
        conn.commit()
        row = conn.execute("SELECT * FROM orders WHERE tenant_id = ? AND id = ?", (tenant, order_id_int)).fetchone()
    return dict(row)


def mark_order_changed(
    order_id: Any,
    before: dict[str, Any],
    after: dict[str, Any],
    tenant_id: int | None = None,
    *,
    force: bool = False,
) -> bool:
    if not before or not after:
        return False
    changed = force or any(_normalized(before.get(key)) != _normalized(after.get(key)) for key in EDITABLE_FIELDS)
    if not changed:
        return False
    tenant = int(tenant_id or after.get("tenant_id") or get_current_tenant_id())
    with closing(get_connection()) as conn:
        assignments = conn.execute(
            "SELECT driver_id, vehicle_id FROM assignments WHERE tenant_id = ? AND order_id = ? AND status = 'active'",
            (tenant, int(order_id)),
        ).fetchall()
        conn.execute(
            """
            UPDATE orders SET run_confirmation_status = 'pending', run_confirmed_at = NULL,
                run_confirmed_by_user_id = NULL, run_confirmed_by = NULL,
                run_revision = COALESCE(run_revision, 1) + 1, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant, int(order_id)),
        )
        for assignment in assignments:
            _mark_group_stale(conn, tenant, str(before.get("order_date") or after.get("order_date")), assignment["driver_id"], assignment["vehicle_id"])
            if after.get("order_date") != before.get("order_date"):
                _mark_group_stale(conn, tenant, str(after.get("order_date")), assignment["driver_id"], assignment["vehicle_id"])
        conn.commit()
    return True


def mark_run_group_stale(
    business_date: Any,
    driver_id: Any,
    vehicle_id: Any,
    tenant_id: int | None = None,
) -> None:
    """Invalidate the existing packet for an assignment group without a renderer change."""
    tenant = int(tenant_id or get_current_tenant_id())
    with closing(get_connection()) as conn:
        _mark_group_stale(conn, tenant, str(business_date), int(driver_id), int(vehicle_id))
        conn.commit()


def generate_run_document(group_value: Any, actor: dict[str, Any]) -> dict[str, Any]:
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    with closing(get_connection()) as conn:
        locked = conn.execute(
            """
            SELECT 1
            WHERE EXISTS (
                SELECT 1 FROM driver_run_documents
                WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
                  AND status = 'published'
            ) OR EXISTS (
                SELECT 1 FROM assignments a
                JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
                WHERE a.tenant_id = ? AND o.order_date = ? AND a.driver_id = ? AND a.vehicle_id = ?
                  AND a.status = 'active'
                  AND (a.published_at IS NOT NULL OR a.execution_status <> 'draft')
            )
            LIMIT 1
            """,
            (tenant, date_value, driver_id, vehicle_id, tenant, date_value, driver_id, vehicle_id),
        ).fetchone()
        prepare_order_document_fields(conn, group, repair_legacy_daily_defaults=not bool(locked))
        conn.commit()
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    errors = _validate_group(group, require_complete=False)
    if errors:
        raise ValueError("PDFを生成できません：" + "、".join(errors))
    group["document_actor_name"] = str(actor.get("display_name") or actor.get("username") or "運行管理者")
    source_hash = _source_hash(group)
    with closing(get_connection()) as conn:
        existing = conn.execute(
            """
            SELECT * FROM driver_run_documents
            WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
              AND source_hash = ? AND status IN ('generated', 'reviewed', 'published')
            ORDER BY version DESC LIMIT 1
            """,
            (tenant, date_value, driver_id, vehicle_id, source_hash),
        ).fetchone()
        if existing and Path(existing["file_path"]).is_file():
            return _public_document(dict(existing))
        version = int(
            conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM driver_run_documents WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?",
                (tenant, date_value, driver_id, vehicle_id),
            ).fetchone()[0]
        )
        previous = conn.execute(
            """
            SELECT document_version_id FROM driver_run_documents
            WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
            ORDER BY version DESC LIMIT 1
            """,
            (tenant, date_value, driver_id, vehicle_id),
        ).fetchone()
    document_version_id = make_document_version_id()
    snapshot = build_document_snapshot(group, document_version_id)
    snapshot["renderer_version"] = DOCUMENT_RENDERER_VERSION
    source_hash = snapshot_source_sha256(snapshot)
    output_dir = RUNTIME_DIR / "uploads" / "run_documents" / str(tenant) / date_value
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _document_stem(group)
    file_name = f"{stem}-V{version}.pdf"
    output_path = (output_dir / file_name).resolve()
    page_count = _render_pdf(snapshot, output_path)
    pdf_sha256 = sha256_file(output_path)
    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "运行管理")
    url = f"/api/run-documents/file?document_id="
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE driver_run_documents
            SET status = 'stale', lifecycle_status = 'superseded',
                stale_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ? AND status IN ('generated', 'reviewed')
            """,
            (tenant, date_value, driver_id, vehicle_id),
        )
        cursor = conn.execute(
            """
            INSERT INTO driver_run_documents (
                tenant_id, business_date, driver_id, vehicle_id, version, status, source_hash,
                file_name, file_path, file_url, page_count, created_by_user_id, created_by,
                document_id, document_version_id, run_group_id, lifecycle_status, document_kind,
                snapshot_json, source_sha256, pdf_sha256, supersedes_document_version_id
            ) VALUES (?, ?, ?, ?, ?, 'generated', ?, ?, ?, '', ?, ?, ?, ?, ?, ?, 'generated',
                      'run_packet', ?, ?, ?, ?)
            """,
            (
                tenant, date_value, driver_id, vehicle_id, version, source_hash,
                file_name, str(output_path), page_count, actor_id, actor_name,
                snapshot["document_id"], snapshot["document_version_id"], snapshot["run_group_id"],
                canonical_json(snapshot), source_hash, pdf_sha256,
                previous["document_version_id"] if previous else None,
            ),
        )
        doc_id = cursor.lastrowid
        url = f"/api/run-documents/file?document_id={doc_id}"
        conn.execute("UPDATE driver_run_documents SET file_url = ? WHERE id = ?", (url, doc_id))
        upsert_document_batch(conn, snapshot, "generated")
        persist_route_nodes(conn, snapshot)
        record_document_event(
            conn, snapshot, "generated", actor,
            {"version_number": version, "source_sha256": source_hash, "pdf_sha256": pdf_sha256},
        )
        conn.commit()
        row = conn.execute("SELECT * FROM driver_run_documents WHERE id = ?", (doc_id,)).fetchone()
    return _public_document(dict(row))


def _editable_node_preview(snapshot: dict[str, Any]) -> dict[str, Any]:
    order_kind = {
        int(order.get("order_id") or 0): str(order.get("document_kind") or "")
        for order in snapshot.get("orders") or []
    }
    nodes = []
    for node in snapshot.get("route_nodes") or []:
        node_type = str(node.get("node_type") or "")
        order_id = int(node.get("order_id") or 0)
        nodes.append(
            {
                "field_id": f"route_node:{node.get('route_node_id')}:planned_location",
                "route_node_id": node.get("route_node_id"),
                "run_group_id": node.get("run_group_id"),
                "document_version_id": node.get("document_version_id"),
                "sequence_number": node.get("sequence_number"),
                "order_id": order_id or None,
                "document_kind": order_kind.get(order_id, "operation"),
                "node_type": node_type,
                "planned_location": node.get("planned_location") or "",
                "planned_arrival_at": node.get("planned_arrival_at") or "",
                "planned_departure_at": node.get("planned_departure_at") or "",
                "load_status": node.get("load_status") or "",
                "editable_arrival": node_type not in {"garage_out", "pickup"},
                "editable_departure": node_type not in {"garage_in", "dropoff"},
                "document_references": ["acceptance", "dispatch"],
            }
        )
    return {
        "document_id": snapshot.get("document_id"),
        "document_version_id": snapshot.get("document_version_id"),
        "run_group_id": snapshot.get("run_group_id"),
        "business_date": snapshot.get("business_date"),
        "source_sha256": snapshot_source_sha256(snapshot),
        "document_revision": snapshot.get("document_version_id"),
        "document_fields": [
            {"field_id": "operation:safety:waiting_place", "label": "待機場所", "value": (snapshot.get("safety") or {}).get("waiting_place") or "", "editable": True},
            {"field_id": "operation:safety:attention_place", "label": "注意箇所", "value": (snapshot.get("safety") or {}).get("attention_place") or "", "editable": True},
            {"field_id": "operation:safety:other_instruction", "label": "安全指示", "value": (snapshot.get("safety") or {}).get("other_instruction") or "", "editable": True},
            {"field_id": "company:office", "label": "営業所", "value": (snapshot.get("driver") or {}).get("office") or "", "editable": False},
        ] + [field for order in snapshot.get("orders") or [] for field in (
            {"field_id": f"order:{order.get('order_id')}:contract_party_name", "order_id": order.get("order_id"), "label": "合同方", "value": order.get("contract_party_name") or order.get("applicant_name") or "", "editable": True},
            {"field_id": f"order:{order.get('order_id')}:applicant_contact", "order_id": order.get("order_id"), "label": "联系方式", "value": order.get("applicant_contact") or "", "editable": True},
            {"field_id": f"order:{order.get('order_id')}:price_jpy", "order_id": order.get("order_id"), "label": "费用（日元）", "value": order.get("money", {}).get("total_jpy"), "editable": True, "input_type": "number"},
        )],
        "nodes": nodes,
        "validation_issues": list(snapshot.get("publish_validation_issues") or []),
    }


def _route_timing_issues(snapshot: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    def parsed(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            issues.append("invalid_datetime")
            return None

    previous: datetime | None = None
    for node in sorted(snapshot.get("route_nodes") or [], key=lambda item: int(item.get("sequence_number") or 0)):
        if not str(node.get("planned_location") or "").strip():
            issues.append(f"route_node_location_missing:{node.get('route_node_id')}")
        arrival = parsed(node.get("planned_arrival_at"))
        departure = parsed(node.get("planned_departure_at"))
        if arrival and departure and departure < arrival:
            issues.append(f"segment_time_order:{node.get('route_node_id')}")
        event_start = arrival or departure
        event_end = departure or arrival
        if previous and event_start and event_start < previous:
            issues.append(f"route_time_order:{node.get('route_node_id')}")
        if event_end:
            previous = event_end
    return list(dict.fromkeys(issues))


def get_run_document_preview(group_value: Any, actor: dict[str, Any]) -> dict[str, Any]:
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    snapshot = build_document_snapshot(group, "draft-preview")
    preview = _editable_node_preview(snapshot)
    preview["validation_issues"] = list(dict.fromkeys(preview["validation_issues"] + _route_timing_issues(snapshot)))
    return preview


def update_run_document_node(group_value: Any, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    """Persist one editable node layer without mutating a published snapshot."""
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    snapshot = build_document_snapshot(group, "draft-node-edit")
    expected_source_hash = str(payload.get("expected_source_hash") or "").strip()
    current_source_hash = snapshot_source_sha256(snapshot)
    if expected_source_hash and expected_source_hash != current_source_hash:
        raise ValueError("document_revision_conflict")
    route_node_id = str(payload.get("route_node_id") or "").strip()
    node = next((item for item in snapshot.get("route_nodes") or [] if item.get("route_node_id") == route_node_id), None)
    if not node:
        raise ValueError("route_node_not_found")
    allowed = ("planned_location", "planned_arrival_at", "planned_departure_at")
    changes = {field: str(payload.get(field) or "").strip() for field in allowed if field in payload}
    if not changes:
        raise ValueError("route_node_no_changes")
    for field in ("planned_arrival_at", "planned_departure_at"):
        if changes.get(field):
            try:
                datetime.fromisoformat(changes[field].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"invalid_datetime:{field}") from exc
    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "运行管理")
    existing_override = next(
        (item for item in group.get("route_node_overrides") or [] if item.get("route_node_id") == route_node_id),
        {},
    )
    changed_fields = list(dict.fromkeys([*(existing_override.get("changed_fields") or []), *changes.keys()]))
    changed_fields_json = canonical_json({"fields": changed_fields})
    values = {field: changes.get(field, node.get(field) or "") for field in allowed}
    location_confirmed = 1 if "planned_location" in changes and bool(changes["planned_location"]) else int(node.get("location_confirmed") or 0)
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO dispatch_route_node_overrides (
                tenant_id, run_group_id, route_node_id, planned_location,
                planned_arrival_at, planned_departure_at, location_confirmed,
                changed_fields_json, updated_by_user_id, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, run_group_id, route_node_id) DO UPDATE SET
                planned_location = excluded.planned_location,
                planned_arrival_at = excluded.planned_arrival_at,
                planned_departure_at = excluded.planned_departure_at,
                location_confirmed = excluded.location_confirmed,
                changed_fields_json = excluded.changed_fields_json,
                updated_by_user_id = excluded.updated_by_user_id,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                tenant, snapshot["run_group_id"], route_node_id,
                values["planned_location"], values["planned_arrival_at"], values["planned_departure_at"],
                location_confirmed, changed_fields_json, actor_id, actor_name,
            ),
        )
        if node.get("order_id"):
            conn.execute(
                """
                UPDATE orders
                SET run_confirmation_status = 'pending', run_confirmed_at = NULL,
                    run_confirmed_by_user_id = NULL, run_confirmed_by = NULL,
                    run_revision = COALESCE(run_revision, 1) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (tenant, int(node["order_id"])),
            )
        _mark_group_stale(conn, tenant, date_value, driver_id, vehicle_id)
        conn.commit()
    refreshed = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not refreshed:
        raise ValueError("run_group_not_found")
    updated_snapshot = build_document_snapshot(refreshed, make_document_version_id())
    preview = _editable_node_preview(updated_snapshot)
    preview["validation_issues"] = list(dict.fromkeys(preview["validation_issues"] + _route_timing_issues(updated_snapshot)))
    with closing(get_connection()) as conn:
        record_document_event(
            conn,
            updated_snapshot,
            "route_node_edited",
            actor,
            {"route_node_id": route_node_id, "changed_fields": list(changes)},
        )
        conn.commit()
    return preview


def update_run_document_field(group_value: Any, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    """Persist one whitelisted non-route field in the canonical draft."""
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    snapshot = build_document_snapshot(group, "draft-field-edit")
    expected_source_hash = str(payload.get("expected_source_hash") or "").strip()
    if expected_source_hash and expected_source_hash != snapshot_source_sha256(snapshot):
        raise ValueError("document_revision_conflict")
    field_id = str(payload.get("field_id") or "").strip()
    raw_value = payload.get("value")
    value = "" if raw_value is None else str(raw_value).strip()
    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "运行管理")
    safety_fields = {
        "operation:safety:waiting_place",
        "operation:safety:attention_place",
        "operation:safety:other_instruction",
    }
    order_match = re.fullmatch(r"order:(\d+):(contract_party_name|applicant_contact|price_jpy)", field_id)
    affected_order_ids: list[int]
    with closing(get_connection()) as conn:
        if field_id in safety_fields:
            if len(value) > 1000:
                raise ValueError("document_field_value_too_long")
            conn.execute(
                """
                INSERT INTO dispatch_document_field_overrides (
                    tenant_id, run_group_id, field_id, value_text, updated_by_user_id, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, run_group_id, field_id) DO UPDATE SET
                    value_text = excluded.value_text,
                    updated_by_user_id = excluded.updated_by_user_id,
                    updated_by = excluded.updated_by,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (tenant, snapshot["run_group_id"], field_id, value, actor_id, actor_name),
            )
            affected_order_ids = [int(order["order_id"]) for order in snapshot.get("orders") or []]
        elif order_match:
            order_id = int(order_match.group(1))
            field_name = order_match.group(2)
            if not any(int(order.get("order_id") or 0) == order_id for order in snapshot.get("orders") or []):
                raise ValueError("document_field_order_not_found")
            if field_name == "price_jpy":
                try:
                    numeric_value = float(value)
                except ValueError as exc:
                    raise ValueError("document_field_invalid_price") from exc
                if numeric_value < 0:
                    raise ValueError("document_field_invalid_price")
                conn.execute(
                    """
                    UPDATE orders SET price = ?, price_jpy = ?, price_confirmed = 0,
                        price_confirmed_by_user_id = NULL, price_confirmed_by = NULL,
                        price_confirmed_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE tenant_id = ? AND id = ?
                    """,
                    (numeric_value, numeric_value, tenant, order_id),
                )
            else:
                if len(value) > 240:
                    raise ValueError("document_field_value_too_long")
                column = "agency_name" if field_name == "contract_party_name" else "guest_contact"
                conn.execute(
                    f"UPDATE orders SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
                    (value, tenant, order_id),
                )
            affected_order_ids = [order_id]
        else:
            raise ValueError("document_field_not_editable")
        for order_id in affected_order_ids:
            conn.execute(
                """
                UPDATE orders SET run_confirmation_status = 'pending', run_confirmed_at = NULL,
                    run_confirmed_by_user_id = NULL, run_confirmed_by = NULL,
                    run_revision = COALESCE(run_revision, 1) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (tenant, order_id),
            )
        _mark_group_stale(conn, tenant, date_value, driver_id, vehicle_id)
        conn.commit()
    refreshed = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not refreshed:
        raise ValueError("run_group_not_found")
    updated_snapshot = build_document_snapshot(refreshed, make_document_version_id())
    preview = _editable_node_preview(updated_snapshot)
    preview["validation_issues"] = list(dict.fromkeys(preview["validation_issues"] + _route_timing_issues(updated_snapshot)))
    with closing(get_connection()) as conn:
        record_document_event(conn, updated_snapshot, "document_field_edited", actor, {"field_id": field_id})
        conn.commit()
    return preview


def review_run_document(group_value: Any, actor: dict[str, Any]) -> dict[str, Any]:
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    errors = _validate_group(group, require_complete=True)
    if errors:
        raise ValueError("公開前の必須項目が不足しています：" + "、".join(errors))
    current_hash = _source_hash(group)
    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "運行管理者")
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT * FROM driver_run_documents
            WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
              AND source_hash = ? AND status IN ('generated', 'reviewed')
            ORDER BY version DESC LIMIT 1
            """,
            (tenant, date_value, driver_id, vehicle_id, current_hash),
        ).fetchone()
        if not row or not Path(row["file_path"]).is_file():
            raise ValueError("確認対象の最新 PDF がありません。先に PDF を生成して開いてください")
        conn.execute(
            """
            UPDATE driver_run_documents
            SET status = 'reviewed', reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by_user_id = ?, reviewed_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
            """,
            (actor_id, actor_name, tenant, row["id"]),
        )
        conn.commit()
        reviewed = conn.execute("SELECT * FROM driver_run_documents WHERE tenant_id = ? AND id = ?", (tenant, row["id"])).fetchone()
    return _public_document(dict(reviewed))


def publish_run_documents(group_values: list[Any], actor: dict[str, Any]) -> list[dict[str, Any]]:
    _require_operations_actor(actor)
    if not group_values:
        raise ValueError("公開する運行グループを選択してください")
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    actor_name = str(actor.get("display_name") or actor.get("username") or "運行管理者")
    documents = []
    for value in group_values:
        date_value, driver_id, vehicle_id = parse_group_key(value)
        group = _find_group(date_value, driver_id, vehicle_id, tenant)
        if not group:
            raise ValueError("run_group_not_found")
        errors = _validate_group(group, require_complete=True)
        if errors:
            raise ValueError("公開前の必須項目が不足しています：" + "、".join(errors))
        current_hash = _source_hash(group)
        with closing(get_connection()) as conn:
            row = conn.execute(
                """
                SELECT * FROM driver_run_documents
                WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
                  AND source_hash = ? AND status = 'reviewed'
                ORDER BY version DESC LIMIT 1
                """,
                (tenant, date_value, driver_id, vehicle_id, current_hash),
            ).fetchone()
        if not row or not Path(row["file_path"]).is_file():
            raise ValueError("PDF が未確認です。PDF を開き、運行管理者が確認してから公開してください")
        documents.append(_public_document(dict(row)))
    # Validate every selected document first, then validate all driver accounts.
    # Both checks happen before the first write so a batch can never be partly
    # published when one reviewed PDF or account mapping is invalid.
    group_driver_ids = sorted({int(doc["driver_id"]) for doc in documents})
    blocked = _driver_account_preflight(tenant, group_driver_ids)
    if blocked:
        raise DriverAccountPreflightError(blocked)
    with closing(get_connection()) as conn:
        for doc in documents:
            conn.execute(
                """
                UPDATE driver_run_documents
                SET status = 'published', published_at = CURRENT_TIMESTAMP,
                    published_by_user_id = ?, published_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
                """,
                (int(actor.get("id") or 0) or None, actor_name, tenant, doc["id"]),
            )
            conn.execute(
                """
                UPDATE assignments
                SET execution_status = CASE WHEN execution_status = 'draft' THEN 'assigned' ELSE execution_status END,
                    published_by_user_id = ?, published_by_name = ?,
                    published_at = COALESCE(published_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND driver_id = ? AND vehicle_id = ? AND status = 'active'
                  AND order_id IN (
                    SELECT id FROM orders WHERE tenant_id = ? AND order_date = ? AND COALESCE(is_deleted, 0) = 0
                  )
                """,
                (
                    int(actor.get("id") or 0) or None, actor_name, tenant,
                    doc["driver_id"], doc["vehicle_id"], tenant, doc["business_date"],
                ),
            )
            conn.execute(
                """
                UPDATE orders SET execution_status = CASE WHEN execution_status = 'draft' THEN 'assigned' ELSE execution_status END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND order_date = ? AND id IN (
                    SELECT order_id FROM assignments
                    WHERE tenant_id = ? AND driver_id = ? AND vehicle_id = ? AND status = 'active'
                )
                """,
                (tenant, doc["business_date"], tenant, doc["driver_id"], doc["vehicle_id"]),
            )
        conn.commit()
        rows = conn.execute(
            f"SELECT * FROM driver_run_documents WHERE tenant_id = ? AND id IN ({','.join('?' for _ in documents)}) ORDER BY id",
            [tenant, *[doc["id"] for doc in documents]],
        ).fetchall()
    published = [_public_document(dict(row)) for row in rows]
    for doc in published:
        revised = int(doc.get("version") or 1) > 1
        create_notification(
            {
                "tenant_id": tenant,
                "notification_type": "run_document_updated" if revised else "run_document_published",
                "title": f"{doc['business_date']} 運行書類が{'更新' if revised else '公開'}されました",
                "body": f"運送引受書・運行指示書 V{doc['version']} を確認してください。",
                "priority": "high",
                "target_role": "driver",
                "link": "/pages/driver/index",
                "source_type": "driver_run_document",
                "source_id": f"{doc['driver_id']}:run-document:{doc['id']}",
            }
        )
    return published


def _driver_account_preflight(tenant: int, driver_ids: list[int]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    with closing(get_connection()) as conn:
        for driver_id in driver_ids:
            row = conn.execute(
                """
                SELECT d.id AS driver_id, d.name AS driver_name, d.user_id,
                       u.id AS account_id, u.role, u.profile_type, u.profile_id,
                       u.is_active, u.supabase_user_id
                FROM drivers d
                LEFT JOIN users u ON u.id = d.user_id AND u.tenant_id = d.tenant_id
                WHERE d.tenant_id = ? AND d.id = ?
                """,
                (tenant, driver_id),
            ).fetchone()
            reason = ""
            if not row:
                reason = "driver_not_found"
            elif not row["account_id"]:
                reason = "driver_account_missing"
            elif not row["is_active"]:
                reason = "driver_account_inactive"
            elif row["role"] != "driver" or row["profile_type"] != "driver":
                reason = "driver_account_role_mismatch"
            elif int(row["profile_id"] or 0) != int(driver_id):
                reason = "driver_account_profile_mismatch"
            elif supabase_enabled() and not str(row["supabase_user_id"] or ""):
                reason = "driver_supabase_identity_missing"
            if reason:
                blocked.append(
                    {
                        "driver_id": driver_id,
                        "driver_name": row["driver_name"] if row else "",
                        "account_id": row["account_id"] if row else None,
                        "reason": reason,
                    }
                )
    return blocked


def review_and_publish_run_document(group_value: Any, actor: dict[str, Any]) -> dict[str, Any]:
    """Review the current source-hash PDF, publish it, and return the next group."""
    _require_operations_actor(actor)
    date_value, _, _ = parse_group_key(group_value)
    reviewed = review_run_document(group_value, actor)
    published = publish_run_documents([group_value], actor)[0]
    groups = list_run_groups(date_value, int(actor.get("tenant_id") or get_current_tenant_id()))
    next_group_key = None
    if groups:
        current_index = next((index for index, item in enumerate(groups) if item["key"] == str(group_value)), -1)
        ordered = groups[current_index + 1:] + groups[:max(current_index, 0)]
        next_group_key = next(
            (item["key"] for item in ordered if item.get("document_status") != "published"),
            None,
        )
    return {
        "document": published,
        "reviewed_document_id": reviewed.get("id"),
        "next_group_key": next_group_key,
    }


def list_driver_run_documents(driver_id: Any, tenant_id: int | None = None) -> list[dict[str, Any]]:
    tenant = int(tenant_id or get_current_tenant_id())
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT d.*, v.plate_number
            FROM driver_run_documents d
            LEFT JOIN vehicles v ON v.id = d.vehicle_id AND v.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.driver_id = ? AND d.status = 'published'
              AND d.id = (
                SELECT d2.id FROM driver_run_documents d2
                WHERE d2.tenant_id = d.tenant_id AND d2.business_date = d.business_date
                  AND d2.driver_id = d.driver_id AND d2.vehicle_id = d.vehicle_id
                  AND d2.status = 'published'
                ORDER BY d2.version DESC LIMIT 1
              )
            ORDER BY d.business_date DESC, d.version DESC
            """,
            (tenant, int(driver_id)),
        ).fetchall()
    return [_public_document(dict(row)) for row in rows]


def resolve_run_document(document_id: Any, user: dict[str, Any]) -> Path | None:
    tenant = int(user.get("tenant_id") or get_current_tenant_id())
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM driver_run_documents WHERE tenant_id = ? AND id = ?", (tenant, int(document_id))).fetchone()
    if not row:
        return None
    if user.get("role") == "driver":
        if int(user.get("profile_id") or 0) != int(row["driver_id"]) or row["status"] != "published":
            return None
    elif user.get("role") not in {"admin", "dispatcher", "operations_manager"}:
        return None
    path = Path(row["file_path"]).resolve()
    allowed = (RUNTIME_DIR / "uploads" / "run_documents").resolve()
    try:
        path.relative_to(allowed)
    except ValueError:
        return None
    return path if path.is_file() else None


def _find_group(date_value: str, driver_id: int, vehicle_id: int, tenant: int) -> dict[str, Any] | None:
    return next((g for g in list_run_groups(date_value, tenant) if g["driver_id"] == driver_id and g["vehicle_id"] == vehicle_id), None)


def _printable_stopovers_from_route_note(order: dict[str, Any]) -> list[str]:
    """Adapt the parser's structured route marker for the unchanged V0.14 renderer."""
    text = str(order.get("fee_remark") or "")
    match = re.search(r"完整路线[:：]\s*([^；;\n]+)", text)
    if not match:
        return []
    nodes = [node.strip() for node in re.split(r"\s*(?:->|→)\s*", match.group(1)) if node.strip()]
    if len(nodes) <= 2:
        return []
    pickup = str(order.get("pickup_location") or "").strip()
    dropoff = str(order.get("dropoff_location") or "").strip()
    if nodes[0] == pickup and nodes[-1] == dropoff:
        return nodes[1:-1]
    return nodes[1:-1]


def _area_review_from_route_note(order: dict[str, Any]) -> tuple[bool, str]:
    match = re.search(r"区域确认[:：]\s*([^；;\n]+)", str(order.get("fee_remark") or ""))
    return (True, match.group(1).strip()) if match else (False, "")


def _validate_group(group: dict[str, Any], require_complete: bool = True) -> list[str]:
    errors = []
    if not group.get("driver_name"): errors.append("運転者が未設定です")
    if not group.get("plate_number"): errors.append("車両の完全な登録番号がありません")
    company = group.get("company") or {}
    if not company.get("company_name"): errors.append("事業者名が未設定です")
    if not group.get("orders"): errors.append("運行注文がありません")
    if not require_complete:
        return errors
    if not group.get("driver_office"): errors.append("営業所が未設定です")
    for index, item in enumerate(group.get("orders") or [], 1):
        for key, label in (("order_date", "日付"), ("start_time", "時刻"), ("operations_business_area", "営業区域"), ("order_type", "運送種別"), ("pickup_location", "乗車地"), ("dropoff_location", "降車地"), ("price", "運賃")):
            if _missing_confirm_value(key, item.get(key)): errors.append(f"第{index}件の{label}がありません")
    return errors


def _mark_group_stale(conn: Any, tenant: int, date_value: str, driver_id: int, vehicle_id: int) -> None:
    conn.execute(
        """
        UPDATE driver_run_documents
        SET status = 'stale', lifecycle_status = 'superseded',
            stale_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
          AND status IN ('generated', 'reviewed')
        """,
        (tenant, date_value, driver_id, vehicle_id),
    )
    conn.execute(
        """
        UPDATE driver_run_documents
        SET lifecycle_status = 'superseded', stale_at = COALESCE(stale_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
          AND status = 'published'
        """,
        (tenant, date_value, driver_id, vehicle_id),
    )


def _source_hash(group: dict[str, Any]) -> str:
    snapshot = build_document_snapshot(group, "source-hash")
    snapshot["renderer_version"] = DOCUMENT_RENDERER_VERSION
    return snapshot_source_sha256(snapshot)


def _document_stem(group: dict[str, Any]) -> str:
    first = group["orders"][0]
    source = normalize_source_code(first.get("order_note_code") or first.get("order_source"), "D")
    date_code = str(group["business_date"]).replace("-", "")[2:]
    oid = str(first.get("oid") or "")
    serial_match = re.search(r"-(\d{4})(?:-|$)", oid)
    serial = serial_match.group(1) if serial_match else f"{int(first.get('order_id') or 0):04d}"[-4:]
    plate = plate_short_code(group.get("plate_number"))
    driver = driver_short_code(group.get("driver_name"), group.get("driver_code"))
    return f"{source}{date_code}{serial}-{plate}{driver}"


def _render_pdf(group_or_snapshot: dict[str, Any], path: Path) -> int:
    from backend.services.v014_hire_document_renderer import render_hire_packet

    snapshot = (
        group_or_snapshot
        if group_or_snapshot.get("schema_version")
        else build_document_snapshot(group_or_snapshot, group_or_snapshot.get("document_version_id"))
    )
    snapshot["renderer_version"] = DOCUMENT_RENDERER_VERSION
    return render_hire_packet(snapshot, path, jp_font_path=JP_FONT_PATH)


def _render_pdf_legacy(group: dict[str, Any], path: Path) -> int:
    """Previous server-designed table renderer, retained only for rollback diagnostics."""
    # The Trial service intentionally stays on the system Python.  PDF wheels
    # live in a runtime-owned venv so they can be upgraded without modifying
    # the operating-system Python installation.
    if "reportlab" not in sys.modules:
        venv_lib = RUNTIME_DIR / "trial" / "venv" / "lib"
        for site_packages in sorted(venv_lib.glob("python*/site-packages")):
            site_path = str(site_packages)
            if site_path not in sys.path:
                sys.path.insert(0, site_path)
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("pdf_dependency_missing:reportlab") from exc
    if not JP_FONT_PATH.is_file() or not SC_FONT_PATH.is_file():
        raise ValueError("pdf_font_missing:NotoSansJP-VF.ttf/NotoSansSC-VF.ttf")
    jp_font_name = "NotoSansJP"
    sc_font_name = "NotoSansSC"
    if jp_font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(jp_font_name, str(JP_FONT_PATH)))
    if sc_font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(sc_font_name, str(SC_FONT_PATH)))
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("JP", parent=styles["BodyText"], fontName=jp_font_name, fontSize=9, leading=13)
    value_normal = ParagraphStyle("CJKValue", parent=normal, fontName=sc_font_name)
    title = ParagraphStyle("JPTitle", parent=normal, fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=5 * mm)
    small = ParagraphStyle("JPSmall", parent=normal, fontSize=8, leading=11)
    value_small = ParagraphStyle("CJKValueSmall", parent=value_normal, fontSize=8, leading=11)
    story = []
    orders = group["orders"]
    company = group.get("company") or {}
    for index, order in enumerate(orders, 1):
        acceptance_code = f"{_document_stem(group)}-01-{index}"
        story.extend([
            Paragraph("運送引受書", title),
            Paragraph(f"文書番号：{acceptance_code}", small), Spacer(1, 3 * mm),
            _field_table([
                ("事業者名", company.get("company_name") or "-"),
                ("事業者住所", company.get("address") or "-"),
                ("事業者連絡先", company.get("contact_phone") or "-"),
                ("許可番号", company.get("business_license_number") or "-"),
                ("運送申込者", order.get("agency_name") or order.get("guest_name") or "-"),
                ("申込方法", _pdf_application_method(order)),
                ("運行日", order.get("order_date")), ("配車時刻", order.get("start_time")),
                ("営業区域", _japanese_area(order.get("operations_business_area") or group.get("driver_office") or "未設定")),
                ("運送種別", _japanese_order_type(order.get("order_type"))),
                ("運送開始", _date_time_place(order.get("order_date"), order.get("start_time"), order.get("pickup_location"))),
                ("運送終了", _date_time_place(order.get("end_date") or order.get("order_date"), order.get("end_time"), order.get("dropoff_location"))),
                ("乗車地", order.get("pickup_location")), ("降車地", order.get("dropoff_location")),
                ("運賃", _money(order.get("price"))), ("注文番号", order.get("oid")),
                ("旅客氏名", order.get("guest_name") or "-"), ("連絡先", order.get("guest_contact") or "-"),
                ("運転者", group.get("driver_name")), ("車両番号", group.get("plate_number")),
                ("備考", _pdf_document_instruction(order)),
            ], normal, value_normal, colors, Table, TableStyle, mm),
            Spacer(1, 8 * mm), Paragraph("運送内容を確認し、上記のとおり引き受けます。", normal),
            Spacer(1, 18 * mm), Paragraph("運行管理者確認：____________________　運転者確認：____________________", normal),
        ])
        story.append(PageBreak())
    instruction_code = f"{_document_stem(group)}-02"
    story.extend([
        Spacer(1, 8 * mm),
        Paragraph("運行指示書", title),
        Paragraph(f"文書番号：{instruction_code}", small),
        Spacer(1, 2 * mm),
        _field_table([
            ("事業者名", company.get("company_name") or "-"),
            ("運行日", group.get("business_date")), ("営業区域", _japanese_area(group.get("driver_office") or _first_area(orders))),
            ("運転者", group.get("driver_name")), ("車両番号", group.get("plate_number")),
            ("車種", group.get("vehicle_type") or "-"), ("運行管理者", _japanese_operator_name(group.get("document_actor_name") or orders[0].get("run_confirmed_by"))),
        ], normal, value_normal, colors, Table, TableStyle, mm),
        Spacer(1, 5 * mm), Paragraph("当日運行明細", ParagraphStyle("section", parent=normal, fontSize=12, leading=17)),
    ])
    rows = [[Paragraph(x, small) for x in ("No.", "時刻", "注文番号", "運行経路", "種別", "運賃", "便名・文書指示")]]
    for index, order in enumerate(orders, 1):
        rows.append([Paragraph(str(value), value_small) for value in (
            index, order.get("start_time") or "-", order.get("oid") or order.get("order_id"),
            f"{order.get('pickup_location') or '-'} → {order.get('dropoff_location') or '-'}",
            _japanese_order_type(order.get("order_type")), _money(order.get("price")),
            _pdf_document_instruction(order),
        )])
    detail = Table(rows, colWidths=[10*mm, 16*mm, 27*mm, 52*mm, 18*mm, 20*mm, 37*mm], repeatRows=1, splitByRow=1)
    detail.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), jp_font_name), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF6")),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#8A98A8")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(detail)
    story.extend([
        Spacer(1, 8 * mm),
        Paragraph("安全運行指示：運行前点呼、車両点検、休憩の確保及び運行変更時の運行管理者への報告を徹底すること。", normal),
        Spacer(1, 10 * mm),
        Paragraph("指示・確認欄：運行管理者 ____________________　運転者 ____________________", normal),
    ])
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=15*mm, bottomMargin=15*mm, title=path.stem, author="Tour Dispatch")
    page_total = {"value": 0}

    class NumberedCanvas(pdfcanvas.Canvas):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._saved_page_states: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._saved_page_states)
            page_total["value"] = total
            instruction_total = max(1, total - len(orders))
            for state in self._saved_page_states:
                self.__dict__.update(state)
                current = self.getPageNumber()
                self.setFont(jp_font_name, 8)
                footer_text = f"{group['business_date']}  {group['driver_name']}  {group['plate_number']}  - {current}/{total} -"
                if current > len(orders):
                    footer_text += f"  運行指示書 {current - len(orders)}/{instruction_total}"
                self.drawCentredString(A4[0] / 2, 8 * mm, footer_text)
                super().showPage()
            super().save()

    doc.build(story, canvasmaker=NumberedCanvas)
    return page_total["value"]


def _field_table(items: list[tuple[str, Any]], label_style: Any, value_style: Any, colors: Any, Table: Any, TableStyle: Any, mm: Any) -> Any:
    from reportlab.platypus import Paragraph
    rows = [[Paragraph(str(label), label_style), Paragraph(str(value if value not in (None, "") else "-"), value_style)] for label, value in items]
    table = Table(rows, colWidths=[48*mm, 124*mm], splitByRow=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "NotoSansJP"), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F6FA")),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#9AA6B2")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _public_document(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row: return None
    safe = dict(row)
    try:
        snapshot = json.loads(str(safe.get("snapshot_json") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        snapshot = {}
    safe["renderer_version"] = snapshot.get("renderer_version") or DOCUMENT_RENDERER_VERSION
    safe.pop("file_path", None)
    safe.pop("snapshot_json", None)
    return safe


def _require_operations_actor(actor: dict[str, Any]) -> None:
    if str(actor.get("role") or "") not in {"admin", "dispatcher", "operations_manager"}:
        raise ValueError("運行書類を操作する権限がありません")


def _normalized(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _db_value(key: str, value: Any) -> Any:
    if key == "price":
        text = str(value or "").strip()
        return float(text) if text else None
    return str(value or "").strip()


def _missing_confirm_value(key: str, value: Any) -> bool:
    text = str(value if value is not None else "").strip()
    if text in {"", "未设定", "未設定", "待确认", "待確認", "地点待补", "地点待補"}:
        return True
    if key == "price":
        try:
            return float(text) <= 0
        except ValueError:
            return True
    return False


def _money(value: Any) -> str:
    if value in (None, ""): return "-"
    try: return f"¥{float(value):,.0f}"
    except (TypeError, ValueError): return str(value)


def _pdf_application_method(order: dict[str, Any]) -> str:
    """Return only formal application-source fields allowed in the document."""
    from backend.services.v014_document_renderer import application_method

    return application_method(order)


def _pdf_document_instruction(order: dict[str, Any]) -> str:
    """Whitelist formal document instructions; never copy raw operational remarks."""
    from backend.services.v014_document_renderer import printable_instruction

    return printable_instruction(order) or "-"


def _date_time_place(date_value: Any, time_value: Any, place_value: Any) -> str:
    parts = [str(value).strip() for value in (date_value, time_value, place_value) if value not in (None, "") and str(value).strip()]
    return " ".join(parts) or "-"


def _first_area(orders: list[dict[str, Any]]) -> str:
    return next((str(item.get("operations_business_area")) for item in orders if item.get("operations_business_area")), "未設定")


def _japanese_order_type(value: Any) -> str:
    text = str(value or "").strip()
    return {
        "接机": "空港迎え",
        "接機": "空港迎え",
        "送机": "空港送り",
        "送機": "空港送り",
        "包车": "貸切",
        "包車": "貸切",
        "单送": "片道送迎",
        "單送": "片道送迎",
        "往返": "往復送迎",
        "往復": "往復送迎",
        "待确认": "要確認",
        "待確認": "要確認",
    }.get(text, text or "-")


def _japanese_area(value: Any) -> str:
    text = str(value or "").strip()
    replacements = {
        "营业区域": "営業区域",
        "營業區域": "営業区域",
        "营业所": "営業所",
        "營業所": "営業所",
        "未设定": "未設定",
        "大阪": "大阪",
        "京都": "京都",
        "神户": "神戸",
        "神戶": "神戸",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text or "未設定"


def _japanese_operator_name(value: Any) -> str:
    text = str(value or "").strip()
    return {
        "运行管理": "運行管理",
        "运行管理员": "運行管理者",
        "运营管理": "運行管理",
    }.get(text, text or "-")

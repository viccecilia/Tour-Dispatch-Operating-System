from __future__ import annotations

import json
import re
import sys
from contextlib import closing
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.app.config import RUNTIME_DIR
from backend.db.database import get_connection
from backend.services.notification_service import create_notification
from backend.services.order_number_service import driver_short_code, normalize_source_code, plate_short_code
from backend.services.tariff_service import diagnose_route_fare, price_snapshot
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
from backend.services.hotel_pool_service import normalize_city_place
from backend.services.dispatch_service import reassign_orders


class DriverAccountPreflightError(ValueError):
    def __init__(self, blocked: list[dict[str, Any]]):
        super().__init__("driver_account_preflight_failed")
        self.blocked = blocked


class DailyGroupPreflightError(ValueError):
    def __init__(self, issues: list[dict[str, Any]]):
        super().__init__("daily_group_preflight_failed")
        self.issues = issues


EDITABLE_FIELDS = {
    "order_date",
    "end_date",
    "start_time",
    "end_time",
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
DOCUMENT_RENDERER_VERSION = "v014-hire-document-workbench-10job-20261017-7-provider-profile"


def _optional_coalesce_expr(
    sources: list[tuple[str, set[str], tuple[str, ...]]], result_name: str
) -> str:
    expressions = []
    for alias, columns, candidates in sources:
        expressions.extend(f"NULLIF({alias}.{column}, '')" for column in candidates if column in columns)
    if not expressions:
        return f"'' AS {result_name}"
    return f"COALESCE({', '.join(expressions)}, '') AS {result_name}"


def _vehicle_quote_context(conn: Any, vehicle_id: Any) -> dict[str, Any]:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}

    def expression(alias: str, candidates: tuple[str, ...]) -> str:
        existing = [f"NULLIF({column}, '')" for column in candidates if column in columns]
        return f"COALESCE({', '.join(existing)}, '') AS {alias}" if existing else f"'' AS {alias}"

    row = conn.execute(
        f"""
        SELECT id,
               {expression('plate_number', ('plate_number', 'plate_no'))},
               {expression('vehicle_type', ('vehicle_type',))},
               {expression('vehicle_type_code', ('vehicle_type_code',))},
               {expression('vehicle_group', ('vehicle_group',))},
               {expression('vehicle_office', ('document_office_name', 'office', 'office_name', 'branch', 'sales_office'))},
               {expression('vehicle_permitted_business_area', ('permitted_business_area', 'operations_business_area', 'business_area', 'license_area', 'operating_area', 'permit_area'))},
               {('seat_count' if 'seat_count' in columns else ('seats' if 'seats' in columns else 'NULL'))} AS seat_count
        FROM vehicles
        WHERE id = ?
        """,
        (int(vehicle_id),),
    ).fetchone()
    return dict(row) if row else {}


def _diagnose_order_quote(order: dict[str, Any], vehicle: dict[str, Any]) -> dict[str, Any]:
    return diagnose_route_fare(
        order.get("pickup_location"),
        order.get("dropoff_location"),
        order.get("order_type"),
        vehicle.get("vehicle_type"),
        order.get("remark"),
        vehicle.get("seat_count"),
        vehicle_office=vehicle.get("vehicle_office"),
        plate_number=vehicle.get("plate_number"),
        vehicle_type_code=vehicle.get("vehicle_type_code"),
        vehicle_group=vehicle.get("vehicle_group"),
        permitted_business_area=vehicle.get("vehicle_permitted_business_area"),
        pickup_source_text=order.get("pickup_source_text"),
        dropoff_source_text=order.get("dropoff_source_text"),
        start_time=order.get("start_time"),
        end_time=order.get("end_time"),
        business_date=order.get("order_date"),
    )


def _daily_order_check(order: dict[str, Any]) -> dict[str, Any]:
    assessment = order.get("area_assessment") or {}
    missing_labels = []
    for key, label in (
        ("order_date", "日期"),
        ("start_time", "配车时间"),
        ("order_type", "订单类别"),
        ("pickup_location", "上车地点"),
        ("dropoff_location", "下车地点"),
    ):
        if _missing_confirm_value(key, order.get(key)):
            missing_labels.append(label)
    effective_area = order.get("operations_business_area") or order.get("suggested_business_area") or ""
    stored_price = order.get("price")
    effective_price = stored_price if not _missing_confirm_value("price", stored_price) else order.get("recommended_price")
    try:
        snapshot = json.loads(str(order.get("price_snapshot_json") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        snapshot = {}

    status = "auto_passed"
    label = "自动核对通过"
    issues: list[str] = []
    if missing_labels or not effective_area:
        status, label = "missing", "资料缺失"
        issues = missing_labels + ([] if effective_area else ["营业区域"])
    elif assessment.get("status") == "risk":
        status, label = "area_risk", "营业区域风险"
        issues = [str(assessment.get("label") or "营业区域风险")]
    elif assessment.get("status") != "passed":
        status, label = "missing", "营业所／许可待核对"
        issues = [str(assessment.get("label") or "营业区域待核对")]
    elif effective_price in (None, "") or _missing_confirm_value("price", effective_price):
        status, label = "price_pending", "价格待确认"
        issues = ["没有已保存金额或可用推荐价"]
    elif snapshot.get("source") == "manual_override" and str(order.get("run_confirmation_status") or "") != "confirmed":
        status, label = "manual_recheck", "人工修改后待复核"
        issues = ["人工金额尚未重新确认"]
    return {
        "daily_check_status": status,
        "daily_check_label": label,
        "daily_check_issues": issues,
        "daily_effective_price": effective_price,
        "daily_effective_business_area": effective_area,
    }


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
            [("v", vehicle_columns, ("document_office_name", "office", "office_name", "branch", "sales_office"))],
            "vehicle_office",
        )
        vehicle_permit_area_expr = _optional_coalesce_expr(
            [
                (
                    "v",
                    vehicle_columns,
                    (
                        "permitted_business_area",
                        "operations_business_area",
                        "business_area",
                        "license_area",
                        "operating_area",
                        "permit_area",
                    ),
                )
            ],
            "vehicle_permitted_business_area",
        )
        vehicle_type_code_expr = _optional_coalesce_expr(
            [("v", vehicle_columns, ("vehicle_type_code",))], "vehicle_type_code"
        )
        vehicle_group_expr = _optional_coalesce_expr(
            [("v", vehicle_columns, ("vehicle_group",))], "vehicle_group"
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
                   {driver_print_expr}, {vehicle_office_expr}, {vehicle_permit_area_expr},
                   {vehicle_type_code_expr}, {vehicle_group_expr}, {manager_expr},
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
        price_diagnostic = _diagnose_order_quote(item, item)
        affiliation = price_diagnostic.get("affiliation") or {}
        item["recommended_price"] = price_diagnostic.get("amount")
        item["recommended_price_label"] = price_diagnostic.get("label") or ""
        item["recommended_price_rule_version"] = price_diagnostic.get("rule_version") or ""
        item["recommended_price_rule_key"] = price_diagnostic.get("key") or ""
        item["recommended_price_reason"] = price_diagnostic.get("reason") or ""
        item["recommended_price_match_basis"] = price_diagnostic.get("match_basis") or {}
        item["recommended_order_category"] = price_diagnostic.get("order_category") or "unknown"
        item["area_assessment"] = price_diagnostic.get("area_assessment") or {}
        item["vehicle_affiliation"] = affiliation
        item["suggested_business_area"] = affiliation.get("suggested_business_area") or ""
        item.update(_daily_order_check(item))
        key = group_key(item["order_date"], item["driver_id"], item["vehicle_id"])
        group = grouped.setdefault(
            key,
            {
                "key": key,
                "tenant_id": tenant,
                "business_date": item["order_date"],
                "driver_id": item["driver_id"],
                "vehicle_id": item["vehicle_id"],
                "driver_name": item.get("driver_name") or "",
                "driver_print_name": item.get("driver_print_name") or "",
                "driver_code": item.get("driver_code") or "",
                "driver_office": item.get("driver_office") or "",
                "vehicle_office": item.get("vehicle_office") or "",
                "vehicle_permitted_business_area": item.get("vehicle_permitted_business_area") or "",
                "vehicle_affiliation": item.get("vehicle_affiliation") or {},
                "suggested_business_area": item.get("suggested_business_area") or "",
                "operations_manager": item.get("operations_manager") or "",
                "garage_location": item.get("garage_location") or "",
                "garage_out_time": item.get("garage_out_time") or "",
                "garage_in_time": item.get("garage_in_time") or "",
                "plate_number": item.get("plate_number") or "",
                "vehicle_type": item.get("vehicle_type") or "",
                "vehicle_type_code": item.get("vehicle_type_code") or "",
                "vehicle_group": item.get("vehicle_group") or "",
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
        office_key = str((group.get("vehicle_affiliation") or {}).get("office_key") or "")
        if not group.get("operations_manager"):
            group["operations_manager"] = {"osaka": "胡東鍇", "kyoto": "朱英心"}.get(office_key, "")
            group["operations_manager_source"] = "office_default" if group["operations_manager"] else "missing"
        else:
            group["operations_manager_source"] = "vehicle_or_driver_archive"
        confirmed = sum(1 for order in group["orders"] if order.get("run_confirmation_status") == "confirmed")
        auto_checked = sum(1 for order in group["orders"] if order.get("daily_check_status") == "auto_passed")
        pending_checks = total - auto_checked
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
                "auto_checked_count": auto_checked,
                "pending_check_count": pending_checks,
                "auto_check_text": f"自动核对 {auto_checked} · 待处理 {pending_checks}",
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
    location_source_inputs: dict[str, str] = {}
    for field_name, node_role in (("pickup_location", "pickup"), ("dropoff_location", "dropoff")):
        if field_name not in updates:
            continue
        raw_location = str(updates.get(field_name) or "").strip()
        normalized_location, was_normalized = normalize_city_place(
            raw_location,
            f"daily-order:{order_id_int}:{node_role}",
            include_supplemental=True,
        )
        if was_normalized:
            location_source_inputs[field_name] = raw_location
            updates[field_name] = normalized_location
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
        vehicle_context = _vehicle_quote_context(conn, assignment["vehicle_id"])
        effective_order = dict(before)
        effective_order.update(updates)
        price_diagnostic = _diagnose_order_quote(effective_order, vehicle_context)
        changed = any(_normalized(before[key]) != _normalized(value) for key, value in updates.items())
        existing_price_snapshot: dict[str, Any] = {}
        try:
            existing_price_snapshot = json.loads(str(before["price_snapshot_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            existing_price_snapshot = {}
        quote_context_changed = any(
            key in updates and _normalized(before[key]) != _normalized(updates[key])
            for key in (
                "price",
                "order_date",
                "start_time",
                "order_type",
                "pickup_location",
                "dropoff_location",
            )
        )
        refresh_price_snapshot = (
            "price" in updates
            and (
                quote_context_changed
                or not existing_price_snapshot.get("rule_version")
            )
        )
        if updates:
            clauses = [f"{key} = ?" for key in updates]
            values = [_db_value(key, updates[key]) for key in updates]
            if "pickup_location" in updates:
                clauses.append("pickup_location_confirmed = 1")
                if _normalized(before["pickup_location"]) != _normalized(updates["pickup_location"]):
                    clauses.append("pickup_source_text = ?")
                    values.append(location_source_inputs.get("pickup_location", str(updates["pickup_location"] or "")))
            if "dropoff_location" in updates:
                clauses.append("dropoff_location_confirmed = 1")
                if _normalized(before["dropoff_location"]) != _normalized(updates["dropoff_location"]):
                    clauses.append("dropoff_source_text = ?")
                    values.append(location_source_inputs.get("dropoff_location", str(updates["dropoff_location"] or "")))
            if "operations_business_area" in updates and not _missing_confirm_value(
                "operations_business_area", updates.get("operations_business_area")
            ):
                # Selecting the business area in the formal order-confirmation
                # step is the operator's explicit acknowledgement.  Persist it
                # separately so an old parser note cannot keep showing a stale
                # "area needs confirmation" warning forever.
                clauses.append("area_validation_status = 'confirmed'")
            if "price" in updates and _normalized(before["price"]) != _normalized(updates["price"]):
                clauses.extend(
                    [
                        "price_confirmed = 0",
                        "price_confirmed_by_user_id = NULL",
                        "price_confirmed_by = NULL",
                        "price_confirmed_at = NULL",
                    ]
                )
            if refresh_price_snapshot:
                clauses.append("price_snapshot_json = ?")
                values.append(
                    json.dumps(
                        price_snapshot(
                            price_diagnostic,
                            updates.get("price"),
                            vehicle_id=assignment["vehicle_id"],
                        ),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
            if (
                "start_time" in updates
                and str(before["end_time_source"] or "") == "suggested_60m"
                and not int(before["end_time_confirmed"] or 0)
            ):
                shifted = shift_date_time(updates.get("order_date") or before["order_date"], updates["start_time"], 60)
                clauses.extend(["end_date = ?", "end_time = ?"])
                values.extend([shifted["date"], shifted["time"]])
            if "end_time" in updates:
                clauses.extend(["end_time_source = 'manual'", "end_time_confirmed = 1"])
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


def reassign_daily_group(group_value: Any, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    """Change one daily draft group to another real driver/vehicle without publishing it."""
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    new_driver_id = int(payload.get("driver_id") or driver_id)
    new_vehicle_id = int(payload.get("vehicle_id") or vehicle_id)
    if new_driver_id == driver_id and new_vehicle_id == vehicle_id:
        return {"success": True, "reused": True, "group_key": group_value, "updated_order_ids": []}
    order_ids = [int(item.get("order_id") or 0) for item in group.get("orders") or []]
    if not order_ids or any(not item for item in order_ids):
        raise ValueError("daily_group_orders_missing")
    result = reassign_orders(
        order_ids,
        new_driver_id,
        new_vehicle_id,
        actor=actor,
        notify_driver=False,
        publish_assignment=False,
    )
    if not result.get("success"):
        return result
    mark_run_group_stale(date_value, driver_id, vehicle_id, tenant)
    mark_run_group_stale(date_value, new_driver_id, new_vehicle_id, tenant)
    return {
        **result,
        "reused": False,
        "group_key": group_key(date_value, new_driver_id, new_vehicle_id),
        "previous_group_key": group_value,
    }


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
    source_sha256 = snapshot_source_sha256(snapshot)
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
                "business_date": node.get("business_date") or snapshot.get("business_date") or "",
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
    preview = {
        "document_id": snapshot.get("document_id"),
        "document_version_id": snapshot.get("document_version_id"),
        "run_group_id": snapshot.get("run_group_id"),
        "business_date": snapshot.get("business_date"),
        "source_sha256": source_sha256,
        "document_revision": source_sha256,
        "document_fields": [
            {"field_id": "operation:safety:waiting_place", "label": "待機場所", "value": (snapshot.get("safety") or {}).get("waiting_place") or "", "editable": True},
            {"field_id": "operation:safety:attention_place", "label": "注意箇所", "value": (snapshot.get("safety") or {}).get("attention_place") or "", "editable": True},
            {"field_id": "operation:safety:other_instruction", "label": "安全指示", "value": (snapshot.get("safety") or {}).get("other_instruction") or "", "editable": True},
            {"field_id": "company:office", "label": "営業所", "value": (snapshot.get("driver") or {}).get("office") or "", "editable": False},
        ] + [field for order in snapshot.get("orders") or [] for field in (
            {"field_id": f"order:{order.get('order_id')}:contract_party_name", "order_id": order.get("order_id"), "label": "合同方", "value": order.get("contract_party_name") or order.get("applicant_name") or "", "editable": True},
            {"field_id": f"order:{order.get('order_id')}:applicant_contact", "order_id": order.get("order_id"), "label": "联系方式", "value": order.get("applicant_contact") or "", "editable": True},
            {"field_id": f"order:{order.get('order_id')}:price_jpy", "order_id": order.get("order_id"), "label": "合计（日元）", "value": order.get("money", {}).get("total_jpy"), "editable": True, "input_type": "number"},
            {"field_id": f"order:{order.get('order_id')}:fare_jpy", "order_id": order.get("order_id"), "label": "运价（日元）", "value": order.get("money", {}).get("fare_jpy"), "editable": True, "input_type": "number"},
            {"field_id": f"order:{order.get('order_id')}:service_fee_jpy", "order_id": order.get("order_id"), "label": "料金（日元）", "value": order.get("money", {}).get("service_fee_jpy"), "editable": True, "input_type": "number"},
            {"field_id": f"order:{order.get('order_id')}:advance_jpy", "order_id": order.get("order_id"), "label": "其他立替（日元）", "value": order.get("money", {}).get("advance_jpy"), "editable": True, "input_type": "number"},
            {"field_id": f"order:{order.get('order_id')}:toll_fee_jpy", "order_id": order.get("order_id"), "label": "高速费（日元）", "value": order.get("money", {}).get("toll_fee_jpy"), "editable": True, "input_type": "number"},
            {"field_id": f"order:{order.get('order_id')}:parking_fee_jpy", "order_id": order.get("order_id"), "label": "停车费（日元）", "value": order.get("money", {}).get("parking_fee_jpy"), "editable": True, "input_type": "number"},
        )],
        "nodes": nodes,
        "validation_issues": list(snapshot.get("publish_validation_issues") or []),
    }
    preview["document_views"] = _document_workbench_views(snapshot, preview["document_fields"], nodes)
    preview["page_plan"] = preview["document_views"].get("page_plan") or []
    preview["template_version"] = DOCUMENT_RENDERER_VERSION
    return preview


def _document_workbench_views(
    snapshot: dict[str, Any],
    document_fields: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the data-driven mobile rendering model used by both document tabs.

    The renderer and the workbench consume the same airport page plan.  Cells
    carry stable ids so zooming, paging, and sorting cannot redirect an edit to
    a different order.
    """
    field_by_id = {str(item.get("field_id") or ""): item for item in document_fields}
    nodes_by_order: dict[int, list[dict[str, Any]]] = {}
    operation_nodes: list[dict[str, Any]] = []
    for node in nodes:
        order_id = int(node.get("order_id") or 0)
        (nodes_by_order.setdefault(order_id, []) if order_id else operation_nodes).append(node)

    def cell(
        label: str,
        value: Any,
        field_id: str = "",
        *,
        order_id: int | None = None,
        route_node_id: str = "",
        input_type: str = "text",
        editable: bool | None = None,
    ) -> dict[str, Any]:
        existing = field_by_id.get(field_id) or {}
        actual_value = existing.get("value") if field_id in field_by_id else value
        can_edit = bool(existing.get("editable")) if editable is None else bool(editable)
        if isinstance(actual_value, float) and actual_value.is_integer():
            display_value = str(int(actual_value))
        else:
            display_value = "" if actual_value is None else str(actual_value)
        return {
            "label": label,
            "value": actual_value,
            "display_value": display_value,
            "field_id": field_id,
            "order_id": order_id,
            "route_node_id": route_node_id,
            "input_type": existing.get("input_type") or input_type,
            "editable": can_edit,
        }

    def node_cell(node: dict[str, Any] | None, key: str, label: str, *, input_type: str = "text") -> dict[str, Any]:
        item = node or {}
        value = item.get(key) or ""
        editable = True
        if key == "planned_arrival_at":
            editable = bool(item.get("editable_arrival"))
        elif key == "planned_departure_at":
            editable = bool(item.get("editable_departure"))
        return cell(
            label,
            value,
            f"route_node:{item.get('route_node_id')}:{key}" if item.get("route_node_id") else "",
            order_id=item.get("order_id"),
            route_node_id=str(item.get("route_node_id") or ""),
            input_type=input_type,
            editable=editable and bool(item.get("route_node_id")),
        )

    order_by_id = {int(item.get("order_id") or 0): item for item in snapshot.get("orders") or []}

    def task(order: dict[str, Any], sequence: int) -> dict[str, Any]:
        order_id = int(order.get("order_id") or 0)
        order_nodes = nodes_by_order.get(order_id) or []
        pickup = next((item for item in order_nodes if item.get("node_type") == "pickup"), None)
        dropoff = next((item for item in reversed(order_nodes) if item.get("node_type") == "dropoff"), None)
        route_text = " → ".join(
            str(value) for value in (
                (pickup or {}).get("planned_location"),
                (dropoff or {}).get("planned_location"),
            ) if value
        )
        return {
            "sequence": sequence,
            "order_id": order_id,
            "document_kind": order.get("document_kind") or "airport_transfer",
            "route_text": route_text,
            "cells": {
                "pickup_time": node_cell(pickup, "planned_departure_at", "配車時刻", input_type="datetime"),
                "pickup_location": node_cell(pickup, "planned_location", "乗車地"),
                "dropoff_time": node_cell(dropoff, "planned_arrival_at", "到着予定", input_type="datetime"),
                "dropoff_location": node_cell(dropoff, "planned_location", "降車地"),
                "contract_party": cell(
                    "契約相手", order.get("contract_party_name") or order.get("applicant_name") or "",
                    f"order:{order_id}:contract_party_name", order_id=order_id,
                ),
                "contact": cell(
                    "連絡先", order.get("applicant_contact") or "",
                    f"order:{order_id}:applicant_contact", order_id=order_id,
                ),
                "price": cell(
                    "運賃・料金", (order.get("money") or {}).get("total_jpy"),
                    f"order:{order_id}:price_jpy", order_id=order_id, input_type="number",
                ),
                "fare": cell(
                    "運賃", (order.get("money") or {}).get("fare_jpy"),
                    f"order:{order_id}:fare_jpy", order_id=order_id, input_type="number",
                ),
                "service_fee": cell(
                    "料金", (order.get("money") or {}).get("service_fee_jpy"),
                    f"order:{order_id}:service_fee_jpy", order_id=order_id, input_type="number",
                ),
                "advance": cell(
                    "その他立替", (order.get("money") or {}).get("advance_jpy"),
                    f"order:{order_id}:advance_jpy", order_id=order_id, input_type="number",
                ),
                "toll_fee": cell(
                    "高速代", (order.get("money") or {}).get("toll_fee_jpy"),
                    f"order:{order_id}:toll_fee_jpy", order_id=order_id, input_type="number",
                ),
                "parking_fee": cell(
                    "駐車代", (order.get("money") or {}).get("parking_fee_jpy"),
                    f"order:{order_id}:parking_fee_jpy", order_id=order_id, input_type="number",
                ),
            },
        }

    airport_pages: list[dict[str, Any]] = []
    sequence = 1
    for page_index, page_orders in enumerate(snapshot.get("airport_acceptance_pages") or [], 1):
        tasks = []
        for order in page_orders:
            tasks.append(task(order, sequence))
            sequence += 1
        airport_pages.append({
            "page_index": page_index,
            "order_ids": [item["order_id"] for item in tasks],
            "tasks": tasks,
        })

    charter_pages: list[dict[str, Any]] = []
    for contract_index, contract in enumerate(snapshot.get("charter_contracts") or [], 1):
        order_id = int(contract.get("order_id") or 0)
        order = order_by_id.get(order_id) or {"order_id": order_id, "document_kind": "charter"}
        for day_index, day in enumerate(contract.get("days") or [], 1):
            day_nodes = [
                item for item in nodes_by_order.get(order_id, [])
                if str(item.get("business_date") or "") == str(day.get("date") or "")
            ]
            route_rows = []
            for node_index, node in enumerate(day_nodes, 1):
                route_rows.append({
                    "sequence": node_index,
                    "route_node_id": node.get("route_node_id"),
                    "location": node_cell(node, "planned_location", "地点"),
                    "arrival": node_cell(node, "planned_arrival_at", "到着", input_type="datetime"),
                    "departure": node_cell(node, "planned_departure_at", "出発", input_type="datetime"),
                })
            charter_pages.append({
                "page_index": len(charter_pages) + 1,
                "contract_index": contract_index,
                "day_index": day_index,
                "day_date": day.get("date") or snapshot.get("business_date"),
                "order_ids": [order_id],
                "tasks": [task(order, contract_index)],
                "route_rows": route_rows,
            })

    pages = airport_pages or charter_pages
    total_pages = len(pages)
    for page in pages:
        page["page_total"] = total_pages

    company = snapshot.get("company") or {}
    operation = snapshot.get("operation") or {}
    safety = snapshot.get("safety") or {}
    common = {
        "business_date": snapshot.get("business_date") or "",
        "driver": snapshot.get("driver") or {},
        "vehicle": snapshot.get("vehicle") or {},
        "company": company,
        "operations_manager": snapshot.get("operations_manager") or "",
        "operation": operation,
        "applicants": snapshot.get("applicants") or [],
        "safety": {
            "waiting_place": cell("待機場所", safety.get("waiting_place") or "", "operation:safety:waiting_place"),
            "attention_place": cell("注意箇所", safety.get("attention_place") or "", "operation:safety:attention_place"),
            "other_instruction": cell("安全指示", safety.get("other_instruction") or "", "operation:safety:other_instruction"),
        },
    }
    page_plan = [
        {"page_index": page["page_index"], "order_ids": page.get("order_ids") or []}
        for page in pages
    ]
    return {
        "template_version": DOCUMENT_RENDERER_VERSION,
        "page_plan": page_plan,
        "acceptance": {**common, "title": "運送引受書", "pages": pages},
        "dispatch": {**common, "title": "運行指示書", "pages": pages},
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


def patch_run_document_draft(group_value: Any, payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist a whitelisted set of workbench cell edits.

    No PDF is rendered here.  A retry whose values are already current is a
    safe no-op even if it carries the source hash from before the first save.
    """
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    snapshot = build_document_snapshot(group, "draft-batch-edit")
    preview_before = _editable_node_preview(snapshot)
    raw_patches = payload.get("patches")
    if not isinstance(raw_patches, list) or not raw_patches:
        raise ValueError("document_patch_empty")
    if len(raw_patches) > 100:
        raise ValueError("document_patch_too_large")

    node_by_id = {
        str(item.get("route_node_id") or ""): item
        for item in snapshot.get("route_nodes") or []
    }
    order_ids = {int(item.get("order_id") or 0) for item in snapshot.get("orders") or []}
    field_value_by_id = {
        str(item.get("field_id") or ""): item.get("value")
        for item in preview_before.get("document_fields") or []
    }
    safety_fields = {
        "operation:safety:waiting_place",
        "operation:safety:attention_place",
        "operation:safety:other_instruction",
    }
    normalized_patches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_patch in raw_patches:
        if not isinstance(raw_patch, dict):
            raise ValueError("document_patch_invalid")
        field_id = str(raw_patch.get("field_id") or "").strip()
        if not field_id or field_id in seen:
            raise ValueError("document_patch_duplicate_field" if field_id else "document_patch_field_missing")
        seen.add(field_id)
        raw_value = raw_patch.get("value")
        value = "" if raw_value is None else str(raw_value).strip()
        route_match = re.fullmatch(
            r"route_node:([^:]+):(planned_location|planned_arrival_at|planned_departure_at)",
            field_id,
        )
        order_match = re.fullmatch(
            r"order:(\d+):(contract_party_name|applicant_contact|price_jpy|fare_jpy|service_fee_jpy|advance_jpy|toll_fee_jpy|parking_fee_jpy)",
            field_id,
        )
        if route_match:
            route_node_id, field_name = route_match.groups()
            node = node_by_id.get(route_node_id)
            if not node:
                raise ValueError("route_node_not_found")
            if field_name in {"planned_arrival_at", "planned_departure_at"} and value:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"invalid_datetime:{field_name}") from exc
            if field_name == "planned_location" and value:
                value, _ = normalize_city_place(value, route_node_id, include_supplemental=True)
            current_value = str(node.get(field_name) or "").strip()
            normalized_patches.append({
                "kind": "node", "field_id": field_id, "route_node_id": route_node_id,
                "field_name": field_name, "value": value, "current_value": current_value,
                "order_id": int(node.get("order_id") or 0) or None,
            })
        elif field_id in safety_fields:
            if len(value) > 1000:
                raise ValueError("document_field_value_too_long")
            normalized_patches.append({
                "kind": "safety", "field_id": field_id, "value": value,
                "current_value": "" if field_value_by_id.get(field_id) is None else str(field_value_by_id.get(field_id)).strip(),
            })
        elif order_match:
            order_id = int(order_match.group(1))
            field_name = order_match.group(2)
            if order_id not in order_ids:
                raise ValueError("document_field_order_not_found")
            if field_name in {"price_jpy", "fare_jpy", "service_fee_jpy", "advance_jpy", "toll_fee_jpy", "parking_fee_jpy"}:
                if value:
                    try:
                        numeric_value = float(value)
                    except ValueError as exc:
                        raise ValueError("document_field_invalid_price") from exc
                    if numeric_value < 0:
                        raise ValueError("document_field_invalid_price")
                else:
                    numeric_value = None
                stored_value: Any = numeric_value
            else:
                if len(value) > 240:
                    raise ValueError("document_field_value_too_long")
                stored_value = value
            current_raw = field_value_by_id.get(field_id)
            current_value = "" if current_raw is None else str(current_raw).strip()
            if field_name.endswith("_jpy"):
                def canonical_number(raw: Any) -> str:
                    if raw is None or str(raw).strip() == "":
                        return ""
                    try:
                        return format(Decimal(str(raw).strip()).normalize(), "f")
                    except InvalidOperation:
                        return str(raw).strip()
                comparable_value = canonical_number(stored_value)
                comparable_current = canonical_number(current_value)
            else:
                comparable_value = "" if stored_value is None else str(stored_value)
                comparable_current = current_value
            normalized_patches.append({
                "kind": "order", "field_id": field_id, "field_name": field_name,
                "value": stored_value, "raw_value": value, "current_value": comparable_current,
                "comparable_value": comparable_value, "order_id": order_id,
            })
        else:
            raise ValueError("document_field_not_editable")

    # Preserve the established airport rule in the canonical draft layer: only
    # an explicitly auto-suggested arrival follows a changed pickup time.  A
    # manually overridden drop-off node or an unknown/explicit source is never
    # rewritten.
    order_by_id = {int(item.get("order_id") or 0): item for item in snapshot.get("orders") or []}
    requested_ids = {item["field_id"] for item in normalized_patches}
    for item in list(normalized_patches):
        if item.get("kind") != "node" or item.get("field_name") != "planned_departure_at" or not item.get("order_id"):
            continue
        pickup_node = node_by_id.get(str(item.get("route_node_id") or "")) or {}
        order = order_by_id.get(int(item["order_id"])) or {}
        if pickup_node.get("node_type") != "pickup" or order.get("document_kind") != "airport_transfer":
            continue
        if order.get("arrival_time_source") != "suggested_60m" or bool(order.get("arrival_time_confirmed")):
            continue
        dropoff = next(
            (node for node in snapshot.get("route_nodes") or [] if int(node.get("order_id") or 0) == int(item["order_id"]) and node.get("node_type") == "dropoff"),
            None,
        )
        if not dropoff or not item.get("value"):
            continue
        dropoff_id = str(dropoff.get("route_node_id") or "")
        dropoff_field_id = f"route_node:{dropoff_id}:planned_arrival_at"
        if dropoff_field_id in requested_ids:
            continue
        existing_dropoff_override = next(
            (override for override in group.get("route_node_overrides") or [] if str(override.get("route_node_id") or "") == dropoff_id),
            {},
        )
        existing_changed_fields = existing_dropoff_override.get("changed_fields") or []
        if "planned_arrival_at" in existing_changed_fields and "auto_suggested_arrival" not in existing_changed_fields:
            continue
        shifted = shift_date_time(str(item["value"])[:10], str(item["value"])[11:16], 60)["at"]
        normalized_patches.append({
            "kind": "node", "field_id": dropoff_field_id, "route_node_id": dropoff_id,
            "field_name": "planned_arrival_at", "value": shifted,
            "current_value": str(dropoff.get("planned_arrival_at") or "").strip(),
            "order_id": int(item["order_id"]), "derived": True,
        })

    def comparable(item: dict[str, Any], key: str) -> str:
        value = item.get(key)
        return "" if value is None else str(value)

    changed = [
        item for item in normalized_patches
        if comparable(item, "comparable_value" if "comparable_value" in item else "value")
        != comparable(item, "current_value")
    ]
    current_source_hash = snapshot_source_sha256(snapshot)
    expected_source_hash = str(payload.get("expected_source_hash") or "").strip()
    if expected_source_hash and expected_source_hash != current_source_hash and changed:
        raise ValueError("document_revision_conflict")
    if not changed:
        preview_before["saved_patch_count"] = 0
        preview_before["idempotent_replay"] = True
        return preview_before

    actor_id = int(actor.get("id") or 0) or None
    actor_name = str(actor.get("display_name") or actor.get("username") or "运行管理")
    node_changes: dict[str, dict[str, Any]] = {}
    derived_arrival_nodes: set[str] = set()
    explicit_arrival_nodes: set[str] = set()
    affected_order_ids: set[int] = set()
    for item in changed:
        if item["kind"] == "node":
            bucket = node_changes.setdefault(item["route_node_id"], {})
            bucket[item["field_name"]] = item["value"]
            if item["field_name"] == "planned_arrival_at":
                (derived_arrival_nodes if item.get("derived") else explicit_arrival_nodes).add(item["route_node_id"])
            if item.get("order_id"):
                affected_order_ids.add(int(item["order_id"]))
        elif item["kind"] == "order":
            affected_order_ids.add(int(item["order_id"]))

    with closing(get_connection()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            for route_node_id, changes in node_changes.items():
                node = node_by_id[route_node_id]
                existing_override = next(
                    (item for item in group.get("route_node_overrides") or [] if item.get("route_node_id") == route_node_id),
                    {},
                )
                changed_fields = list(dict.fromkeys([*(existing_override.get("changed_fields") or []), *changes.keys()]))
                if route_node_id in derived_arrival_nodes and "auto_suggested_arrival" not in changed_fields:
                    changed_fields.append("auto_suggested_arrival")
                if route_node_id in explicit_arrival_nodes:
                    changed_fields = [field for field in changed_fields if field != "auto_suggested_arrival"]
                values = {
                    field: changes.get(field, node.get(field) or "")
                    for field in ("planned_location", "planned_arrival_at", "planned_departure_at")
                }
                location_confirmed = (
                    1 if "planned_location" in changes and bool(changes["planned_location"])
                    else int(node.get("location_confirmed") or 0)
                )
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
                        location_confirmed, canonical_json({"fields": changed_fields}), actor_id, actor_name,
                    ),
                )
            for item in changed:
                if item["kind"] == "safety":
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
                        (tenant, snapshot["run_group_id"], item["field_id"], item["value"], actor_id, actor_name),
                    )
                elif item["kind"] == "order":
                    if item["field_name"] == "price_jpy":
                        conn.execute(
                            """
                            UPDATE orders SET price = ?, price_jpy = ?, price_confirmed = 0,
                                price_confirmed_by_user_id = NULL, price_confirmed_by = NULL,
                                price_confirmed_at = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE tenant_id = ? AND id = ?
                            """,
                            (item["value"], item["value"], tenant, item["order_id"]),
                        )
                    elif item["field_name"] in {"fare_jpy", "service_fee_jpy", "advance_jpy", "toll_fee_jpy", "parking_fee_jpy"}:
                        column = "document_advance_jpy" if item["field_name"] == "advance_jpy" else item["field_name"]
                        conn.execute(
                            f"""
                            UPDATE orders SET {column} = ?, price_confirmed = 0,
                                price_confirmed_by_user_id = NULL, price_confirmed_by = NULL,
                                price_confirmed_at = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE tenant_id = ? AND id = ?
                            """,
                            (item["value"], tenant, item["order_id"]),
                        )
                    else:
                        column = "agency_name" if item["field_name"] == "contract_party_name" else "guest_contact"
                        conn.execute(
                            f"UPDATE orders SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
                            (item["value"], tenant, item["order_id"]),
                        )
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
        except Exception:
            conn.rollback()
            raise

    refreshed = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not refreshed:
        raise ValueError("run_group_not_found")
    updated_snapshot = build_document_snapshot(refreshed, make_document_version_id())
    preview = _editable_node_preview(updated_snapshot)
    preview["validation_issues"] = list(dict.fromkeys(preview["validation_issues"] + _route_timing_issues(updated_snapshot)))
    preview["saved_patch_count"] = len(changed)
    preview["idempotent_replay"] = False
    with closing(get_connection()) as conn:
        record_document_event(
            conn, updated_snapshot, "document_draft_patched", actor,
            {"field_ids": [item["field_id"] for item in changed], "client_request_id": str(payload.get("client_request_id") or "")[:120]},
        )
        conn.commit()
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


def _prepare_published_pdf(row: dict[str, Any], published_at: datetime, actor: dict[str, Any]) -> dict[str, Any]:
    """Render a formal file without overwriting the reviewed preview artifact."""
    try:
        source_snapshot = json.loads(str(row.get("snapshot_json") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("公開対象 PDF の文書スナップショットを読み込めません") from exc
    if not str((source_snapshot.get("driver") or {}).get("name") or "").strip():
        raise ValueError("公開前の必須項目が不足しています：運転者の正式文書名が未設定です")

    # Publication metadata changes the visible formal PDF only.  The immutable
    # business-content snapshot and its source hash remain unchanged.
    final_snapshot = json.loads(canonical_json(source_snapshot))
    final_snapshot["publication_status"] = "published"
    final_snapshot["created_date"] = published_at.date().isoformat()
    final_snapshot["published_at"] = published_at.isoformat(timespec="seconds")
    final_snapshot["published_by"] = str(actor.get("display_name") or actor.get("username") or "運行管理者")

    preview_path = Path(str(row.get("file_path") or "")).resolve()
    final_path = preview_path.with_name(f"{preview_path.stem}-published{preview_path.suffix}")
    temporary_path = final_path.with_name(f"{final_path.stem}.publishing{final_path.suffix}")
    temporary_path.unlink(missing_ok=True)
    try:
        page_count = _render_pdf(final_snapshot, temporary_path)
        pdf_sha256 = sha256_file(temporary_path)
        temporary_path.replace(final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return {
        "source_snapshot": source_snapshot,
        "file_name": final_path.name,
        "file_path": str(final_path),
        "page_count": page_count,
        "pdf_sha256": pdf_sha256,
        "created_date": final_snapshot["created_date"],
        "published_at": final_snapshot["published_at"],
    }


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
        documents.append(dict(row))
    # Validate every selected document first, then validate all driver accounts.
    # Both checks happen before the first write so a batch can never be partly
    # published when one reviewed PDF or account mapping is invalid.
    group_driver_ids = sorted({int(doc["driver_id"]) for doc in documents})
    blocked = _driver_account_preflight(tenant, group_driver_ids)
    if blocked:
        raise DriverAccountPreflightError(blocked)
    published_at = datetime.now().astimezone()
    prepared: list[dict[str, Any]] = []
    try:
        for doc in documents:
            prepared.append(_prepare_published_pdf(doc, published_at, actor))
        with closing(get_connection()) as conn:
            for doc, formal in zip(documents, prepared):
                conn.execute(
                    """
                    UPDATE driver_run_documents
                    SET status = 'published', lifecycle_status = 'published', published_at = ?,
                        published_by_user_id = ?, published_by = ?, file_name = ?, file_path = ?,
                        page_count = ?, pdf_sha256 = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE tenant_id = ? AND id = ?
                    """,
                    (
                        formal["published_at"], int(actor.get("id") or 0) or None, actor_name,
                        formal["file_name"], formal["file_path"], formal["page_count"],
                        formal["pdf_sha256"], tenant, doc["id"],
                    ),
                )
                record_document_event(
                    conn,
                    formal["source_snapshot"],
                    "published",
                    actor,
                    {
                        "published_at": formal["published_at"],
                        "created_date": formal["created_date"],
                        "source_sha256": doc.get("source_sha256") or doc.get("source_hash"),
                        "pdf_sha256": formal["pdf_sha256"],
                    },
                )
                conn.execute(
                """
                UPDATE assignments
                SET execution_status = CASE WHEN execution_status = 'draft' THEN 'assigned' ELSE execution_status END,
                    published_by_user_id = ?, published_by_name = ?,
                    published_at = COALESCE(published_at, ?), updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND driver_id = ? AND vehicle_id = ? AND status = 'active'
                  AND order_id IN (
                    SELECT id FROM orders WHERE tenant_id = ? AND order_date = ? AND COALESCE(is_deleted, 0) = 0
                  )
                """,
                (
                    int(actor.get("id") or 0) or None, actor_name, formal["published_at"], tenant,
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
    except Exception:
        for formal in prepared:
            Path(formal["file_path"]).unlink(missing_ok=True)
        raise
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


def confirm_and_publish_daily_group(group_value: Any, actor: dict[str, Any]) -> dict[str, Any]:
    """Server-side final check for the compact daily-card flow.

    The button is intentionally not a validation bypass: every order must be
    auto-safe (or an already confirmed manual value), the driver account must
    be publishable, and the generated PDF must match the final source hash.
    Existing generate/review/publish services remain the single write path.
    """
    _require_operations_actor(actor)
    date_value, driver_id, vehicle_id = parse_group_key(group_value)
    tenant = int(actor.get("tenant_id") or get_current_tenant_id())
    group = _find_group(date_value, driver_id, vehicle_id, tenant)
    if not group:
        raise ValueError("run_group_not_found")
    latest = group.get("latest_document") or {}
    if (
        group.get("document_status") == "published"
        and latest.get("source_hash") == _source_hash(group)
    ):
        return {"document": latest, "next_group_key": None, "idempotent": True}

    issues: list[dict[str, Any]] = []
    for index, order in enumerate(group.get("orders") or [], 1):
        status = str(order.get("daily_check_status") or "missing")
        if status not in {"auto_passed", "manual_recheck"}:
            issues.append(
                {
                    "order_id": order.get("order_id"),
                    "order_index": index,
                    "oid": order.get("oid") or "",
                    "status": status,
                    "label": order.get("daily_check_label") or "待处理",
                    "fields": order.get("daily_check_issues") or [],
                }
            )
    if issues:
        raise DailyGroupPreflightError(issues)
    blocked = _driver_account_preflight(tenant, [driver_id])
    if blocked:
        raise DriverAccountPreflightError(blocked)

    for order in group.get("orders") or []:
        payload = {
            "order_date": order.get("order_date"),
            "start_time": order.get("start_time"),
            "operations_business_area": order.get("daily_effective_business_area"),
            "order_type": order.get("order_type"),
            "pickup_location": order.get("pickup_location"),
            "dropoff_location": order.get("dropoff_location"),
            "price": order.get("daily_effective_price"),
            "pdf_edit": False,
        }
        if order.get("end_date"):
            payload["end_date"] = order.get("end_date")
        if order.get("end_time"):
            payload["end_time"] = order.get("end_time")
        confirm_order(order.get("order_id"), payload, actor)

    generated = generate_run_document(group_value, actor)
    result = review_and_publish_run_document(group_value, actor)
    result.update(
        {
            "generated_document_id": generated.get("id"),
            "source_hash": generated.get("source_hash"),
            "idempotent": False,
        }
    )
    return result


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
    if str(order.get("area_validation_status") or "") in {"confirmed", "risk_acknowledged"}:
        return False, ""
    if (
        str(order.get("run_confirmation_status") or "") == "confirmed"
        and not _missing_confirm_value("operations_business_area", order.get("operations_business_area"))
    ):
        return False, ""
    match = re.search(r"区域确认[:：]\s*([^；;\n]+)", str(order.get("fee_remark") or ""))
    return (True, match.group(1).strip()) if match else (False, "")


def _validate_group(group: dict[str, Any], require_complete: bool = True) -> list[str]:
    errors = []
    if not (group.get("driver_print_name") or group.get("driver_name")): errors.append("運転者の正式文書名が未設定です")
    if not group.get("plate_number"): errors.append("車両の完全な登録番号がありません")
    company = group.get("company") or {}
    if not company.get("company_name"): errors.append("事業者名が未設定です")
    if not group.get("orders"): errors.append("運行注文がありません")
    if not require_complete:
        return errors
    affiliation = group.get("vehicle_affiliation") or {}
    affiliation_acknowledged = bool(group.get("orders")) and all(
        str(item.get("area_validation_status") or "") in {"confirmed", "risk_acknowledged"}
        for item in group.get("orders") or []
    )
    if affiliation.get("status") == "conflict" and not affiliation_acknowledged:
        errors.append(str(affiliation.get("message") or "車両の所属営業所・許可区域を確認してください"))
    if not (group.get("vehicle_office") or group.get("driver_office")):
        errors.append("営業所が未設定です")
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

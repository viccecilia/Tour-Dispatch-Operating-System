"""Tenant-scoped fixed-tour templates and one-way materialization to orders."""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from backend.db.database import get_connection
from backend.services.dispatch_service import assign_orders, list_available_drivers, list_available_vehicles, reassign_orders
from backend.services.order_service import create_order, get_order, update_order
from backend.services.run_document_service import (
    generate_run_document,
    get_run_document_preview,
    mark_order_changed,
    mark_run_group_stale,
)
from backend.services.tenant_context import get_current_tenant_id


def _norm(value: Any) -> str:
    return re.sub(r"[\s\-－_]+", "", unicodedata.normalize("NFKC", str(value or "")).lower())


TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _actor_user_id(actor: dict[str, Any] | None) -> int | None:
    value = (actor or {}).get("id") or (actor or {}).get("user_id")
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _iso_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("fixed_tour_business_date_invalid") from exc


def _validate_time(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not TIME_PATTERN.fullmatch(text):
        raise ValueError("fixed_tour_time_invalid")
    return text


def _normalize_preset_stops(stops: Any, *, new_node_ids: bool = False) -> list[dict[str, Any]]:
    if not isinstance(stops, list) or len(stops) < 2:
        raise ValueError("fixed_tour_requires_two_stops")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(stops, 1):
        stop = raw if isinstance(raw, dict) else {"location_name": raw}
        location = str(stop.get("location_name") or stop.get("location") or "").strip()
        if not location:
            raise ValueError("fixed_tour_stop_location_required")
        try:
            day_index = int(stop.get("day_index") or 1)
        except (TypeError, ValueError) as exc:
            raise ValueError("fixed_tour_day_index_invalid") from exc
        if day_index < 1 or day_index > 31:
            raise ValueError("fixed_tour_day_index_invalid")
        arrival = _validate_time(stop.get("default_arrival_time") or stop.get("planned_arrival_time") or stop.get("arrival_time"))
        departure = _validate_time(stop.get("default_departure_time") or stop.get("planned_departure_time") or stop.get("departure_time"))
        if arrival and departure and departure < arrival:
            raise ValueError("fixed_tour_stop_time_order")
        preset_node_id = "" if new_node_ids else str(stop.get("preset_node_id") or "").strip()
        normalized.append({
            "preset_node_id": preset_node_id or f"preset-node-{uuid.uuid4()}",
            "day_index": day_index,
            "sequence_no": index,
            "stop_type": str(stop.get("stop_type") or ("pickup" if index == 1 else "dropoff" if index == len(stops) else "waypoint")),
            "location_name": location,
            "default_arrival_time": arrival,
            "default_departure_time": departure,
            "stay_minutes": stop.get("stay_minutes"),
            "note": str(stop.get("note") or "").strip() or None,
        })
    if any(normalized[index]["day_index"] < normalized[index - 1]["day_index"] for index in range(1, len(normalized))):
        raise ValueError("fixed_tour_day_order_invalid")
    return normalized


def _route_days(stops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    for day_index in sorted({int(stop.get("day_index") or 1) for stop in stops}):
        days.append({
            "day_index": day_index,
            "nodes": [stop for stop in stops if int(stop.get("day_index") or 1) == day_index],
        })
    return days


def _row(conn: Any, route_id: Any, tenant_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM fixed_tour_routes WHERE id = ? AND tenant_id = ?", (int(route_id), tenant_id)).fetchone()
    return dict(row) if row else None


def route_detail(route_id: Any, tenant_id: int | None = None) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    with get_connection() as conn:
        route = _row(conn, route_id, tenant_id)
        if not route:
            return None
        route["stops"] = [dict(x) for x in conn.execute("SELECT * FROM fixed_tour_route_stops WHERE route_id = ? AND tenant_id = ? ORDER BY day_index, sequence_no", (route["id"], tenant_id))]
        for stop in route["stops"]:
            stop["preset_node_id"] = stop.get("preset_node_id") or f"legacy-preset-node-{stop['id']}"
            stop["day_index"] = int(stop.get("day_index") or 1)
        route["days"] = _route_days(route["stops"])
        route["prices"] = [dict(x) for x in conn.execute("SELECT * FROM fixed_tour_route_prices WHERE route_id = ? AND tenant_id = ? ORDER BY vehicle_type", (route["id"], tenant_id))]
        return route


def list_routes(query: str = "", include_inactive: bool = False, tenant_id: int | None = None) -> list[dict[str, Any]]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    needle = _norm(query)
    with get_connection() as conn:
        rows = [dict(x) for x in conn.execute("SELECT * FROM fixed_tour_routes WHERE tenant_id = ? " + ("" if include_inactive else "AND status = 'active' ") + "ORDER BY updated_at DESC, id DESC", (tenant_id,))]
    items = [route_detail(x["id"], tenant_id) for x in rows]
    items = [x for x in items if x]
    if needle:
        items = [x for x in items if needle in _norm(" ".join([
            x["route_code"], x["route_name"], x.get("description") or "", x.get("route_summary") or "",
            *(s["location_name"] for s in x["stops"]),
        ]))]
    return items


def save_route(payload: dict[str, Any], tenant_id: int | None = None, route_id: Any = None, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    previous = route_detail(route_id, tenant_id) if route_id else None
    if previous:
        incoming = dict(payload)
        payload = {**previous, **incoming}
        payload["stops"] = incoming.get("stops", previous.get("stops") or [])
        payload["prices"] = incoming.get("prices", previous.get("prices") or [])
    stops = _normalize_preset_stops(payload.get("stops") or [])
    fields = ("route_code", "route_name", "status", "default_start_time", "default_end_time", "standard_duration_minutes", "operations_business_area", "default_order_type", "route_summary", "document_remark", "application_method", "applicant_name", "contact_name", "contact_phone", "description", "trip_type", "duration_days", "updated_by_user_id")
    defaults = {"status": "active", "default_order_type": "包车", "application_method": "ウェブサイト", "trip_type": "day", "duration_days": max(stop["day_index"] for stop in stops)}
    values = [payload.get(key) if payload.get(key) not in (None, "") else defaults.get(key) for key in fields]
    values[-1] = _actor_user_id(actor)
    values[fields.index("default_start_time")] = _validate_time(values[fields.index("default_start_time")])
    values[fields.index("default_end_time")] = _validate_time(values[fields.index("default_end_time")])
    values[fields.index("duration_days")] = max(int(values[fields.index("duration_days")] or 1), max(stop["day_index"] for stop in stops))
    if values[fields.index("trip_type")] not in {"day", "multi_day"}:
        raise ValueError("fixed_tour_trip_type_invalid")
    if values[fields.index("trip_type")] == "day" and values[fields.index("duration_days")] != 1:
        raise ValueError("fixed_tour_day_trip_has_multiple_days")
    if not values[0] or not values[1]:
        raise ValueError("fixed_tour_code_and_name_required")
    with get_connection() as conn:
        existing = _row(conn, route_id, tenant_id) if route_id else None
        duplicate = conn.execute(
            "SELECT id FROM fixed_tour_routes WHERE tenant_id = ? AND route_code = ?",
            (tenant_id, values[0]),
        ).fetchone()
        if duplicate and (not existing or int(duplicate["id"]) != int(existing["id"])):
            raise ValueError("fixed_tour_route_code_exists")
        if existing:
            conn.execute("UPDATE fixed_tour_routes SET " + ", ".join(f"{f} = ?" for f in fields) + ", version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?", (*values, existing["id"], tenant_id))
            target_id = existing["id"]
            conn.execute("DELETE FROM fixed_tour_route_stops WHERE route_id = ? AND tenant_id = ?", (target_id, tenant_id))
            conn.execute("DELETE FROM fixed_tour_route_prices WHERE route_id = ? AND tenant_id = ?", (target_id, tenant_id))
        else:
            insert_fields = (*fields, "created_by_user_id")
            cur = conn.execute("INSERT INTO fixed_tour_routes (tenant_id, " + ", ".join(insert_fields) + ") VALUES (?, " + ", ".join("?" for _ in insert_fields) + ")", (tenant_id, *values, _actor_user_id(actor)))
            target_id = cur.lastrowid
        for index, stop in enumerate(stops, 1):
            conn.execute("INSERT INTO fixed_tour_route_stops (tenant_id, route_id, sequence_no, stop_type, location_name, default_arrival_time, default_departure_time, stay_minutes, note, preset_node_id, day_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (tenant_id, target_id, index, stop["stop_type"], stop["location_name"], stop["default_arrival_time"], stop["default_departure_time"], stop.get("stay_minutes"), stop.get("note"), stop["preset_node_id"], stop["day_index"]))
        for price in payload.get("prices") or []:
            if price.get("vehicle_type") and price.get("price_jpy") not in (None, ""):
                conn.execute("INSERT INTO fixed_tour_route_prices (tenant_id, route_id, vehicle_type, price_jpy) VALUES (?, ?, ?, ?)", (tenant_id, target_id, price["vehicle_type"], float(price["price_jpy"])))
        conn.commit()
    return route_detail(target_id, tenant_id) or {}


def copy_route(route_id: Any, tenant_id: int | None = None, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    route = route_detail(route_id, tenant_id)
    if not route: raise ValueError("fixed_tour_route_not_found")
    route.pop("id", None); route["route_code"] = f"{route['route_code']}-COPY-{uuid.uuid4().hex[:6].upper()}"; route["route_name"] = f"{route['route_name']}（复制）"; route["status"] = "inactive"
    route["stops"] = _normalize_preset_stops(route.get("stops") or [], new_node_ids=True)
    return save_route(route, tenant_id, actor=actor)


def set_route_status(route_id: Any, status: str, tenant_id: int | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    if status not in {"active", "inactive"}: raise ValueError("fixed_tour_status_invalid")
    with get_connection() as conn:
        cur = conn.execute("UPDATE fixed_tour_routes SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?", (status, int(route_id), tenant_id)); conn.commit()
    if not cur.rowcount: raise ValueError("fixed_tour_route_not_found")
    return route_detail(route_id, tenant_id) or {}


def delete_route(route_id: Any, tenant_id: int | None = None) -> bool:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    target_id = int(route_id)
    with get_connection() as conn:
        existing = _row(conn, target_id, tenant_id)
        if not existing:
            return False
        run_count = conn.execute(
            "SELECT COUNT(*) FROM fixed_tour_runs WHERE tenant_id = ? AND route_id = ?",
            (tenant_id, target_id),
        ).fetchone()[0]
        if run_count:
            raise ValueError("fixed_tour_route_in_use")
        conn.execute(
            "DELETE FROM fixed_tour_route_stops WHERE tenant_id = ? AND route_id = ?",
            (tenant_id, target_id),
        )
        conn.execute(
            "DELETE FROM fixed_tour_route_prices WHERE tenant_id = ? AND route_id = ?",
            (tenant_id, target_id),
        )
        deleted = conn.execute(
            "DELETE FROM fixed_tour_routes WHERE tenant_id = ? AND id = ?",
            (tenant_id, target_id),
        ).rowcount
        conn.commit()
    return bool(deleted)


def _draft_row(conn: Any, draft_id: Any, tenant_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM fixed_tour_charter_drafts WHERE (id = ? OR charter_id = ?) AND tenant_id = ?",
        (int(draft_id) if str(draft_id).isdigit() else -1, str(draft_id), tenant_id),
    ).fetchone()
    return dict(row) if row else None


def charter_draft_detail(draft_id: Any, tenant_id: int | None = None) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    with get_connection() as conn:
        draft = _draft_row(conn, draft_id, tenant_id)
        if not draft:
            return None
        order = conn.execute("SELECT * FROM orders WHERE id = ? AND tenant_id = ?", (draft["order_id"], tenant_id)).fetchone()
        assignment = conn.execute(
            """SELECT a.*, d.name AS driver_name, v.plate_number, v.vehicle_type
               FROM assignments a
               JOIN drivers d ON d.id = a.driver_id AND d.tenant_id = a.tenant_id
               JOIN vehicles v ON v.id = a.vehicle_id AND v.tenant_id = a.tenant_id
               WHERE a.order_id = ? AND a.tenant_id = ? AND a.status = 'active'
               ORDER BY a.id DESC LIMIT 1""",
            (draft["order_id"], tenant_id),
        ).fetchone()
    draft["route_snapshot"] = json.loads(draft.get("route_snapshot_json") or "{}")
    draft["order"] = dict(order) if order else None
    draft["assignment"] = dict(assignment) if assignment else None
    return draft


def charter_dispatch_options(
    business_date: Any,
    draft_id: Any = None,
    route_id: Any = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return tenant-scoped resources with conservative whole-day conflict hints."""
    tenant_id = get_current_tenant_id()
    service_date = _iso_date(business_date)
    excluded_order_id = None
    request_start = ""
    request_end = ""
    if draft_id not in (None, ""):
        draft = charter_draft_detail(draft_id, tenant_id)
        if not draft:
            raise ValueError("fixed_tour_charter_draft_not_found")
        excluded_order_id = int(draft["order_id"])
        request_start = str((draft.get("order") or {}).get("start_time") or "")[:5]
        request_end = str((draft.get("order") or {}).get("end_time") or "")[:5]
    elif route_id not in (None, ""):
        route = route_detail(route_id, tenant_id)
        if not route:
            raise ValueError("fixed_tour_route_not_found")
        request_start = str(route.get("default_start_time") or "")[:5]
        request_end = str(route.get("default_end_time") or "")[:5]
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.driver_id, a.vehicle_id, o.id AS order_id, o.start_time, o.end_time, o.oid
               FROM assignments a
               JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
               WHERE a.tenant_id = ? AND a.status = 'active'
                 AND COALESCE(o.is_deleted, 0) = 0 AND o.order_date = ?
                 AND (? IS NULL OR o.id <> ?)""",
            (tenant_id, service_date, excluded_order_id, excluded_order_id),
        ).fetchall()
        usage_rows = conn.execute(
            """SELECT driver_id, vehicle_id, MAX(COALESCE(updated_at, assigned_at)) AS last_used_at
               FROM assignments WHERE tenant_id = ? GROUP BY driver_id, vehicle_id""",
            (tenant_id,),
        ).fetchall()
    driver_last_used: dict[int, str] = {}
    vehicle_last_used: dict[int, str] = {}
    for row in usage_rows:
        if row["driver_id"] is not None:
            driver_last_used[int(row["driver_id"])] = max(driver_last_used.get(int(row["driver_id"]), ""), str(row["last_used_at"] or ""))
        if row["vehicle_id"] is not None:
            vehicle_last_used[int(row["vehicle_id"])] = max(vehicle_last_used.get(int(row["vehicle_id"]), ""), str(row["last_used_at"] or ""))
    actor_office = str((actor or {}).get("office") or "").strip()
    def overlaps(item: dict[str, Any]) -> bool:
        existing_start = str(item.get("start_time") or "")[:5]
        existing_end = str(item.get("end_time") or "")[:5]
        if not all((request_start, request_end, existing_start, existing_end)):
            return False
        return request_start < existing_end and existing_start < request_end

    conflicts_by_driver: dict[int, list[dict[str, Any]]] = {}
    conflicts_by_vehicle: dict[int, list[dict[str, Any]]] = {}
    unknown_by_driver: set[int] = set()
    unknown_by_vehicle: set[int] = set()
    for raw in rows:
        item = dict(raw)
        if overlaps(item):
            conflicts_by_driver.setdefault(int(item["driver_id"]), []).append(item)
            conflicts_by_vehicle.setdefault(int(item["vehicle_id"]), []).append(item)
        elif not all((request_start, request_end, item.get("start_time"), item.get("end_time"))):
            unknown_by_driver.add(int(item["driver_id"]))
            unknown_by_vehicle.add(int(item["vehicle_id"]))
    drivers = []
    for item in list_available_drivers():
        conflicts = conflicts_by_driver.get(int(item["id"]), [])
        license_due = str(item.get("license_due_date") or item.get("license_expires_at") or "")[:10]
        health_due = str(item.get("health_check_due_date") or "")[:10]
        qualification_valid = (not license_due or license_due >= service_date) and (not health_due or health_due >= service_date)
        drivers.append({
            **item,
            "date_conflict": bool(conflicts),
            "conflicts": conflicts,
            "qualification_valid": qualification_valid,
            "manual_check_required": not bool(license_due and health_due),
            "manual_conflict_check": int(item["id"]) in unknown_by_driver,
            "same_office": bool(actor_office and str(item.get("office") or "").strip() == actor_office),
            "last_used_at": driver_last_used.get(int(item["id"]), ""),
        })
    vehicles = []
    for item in list_available_vehicles():
        conflicts = conflicts_by_vehicle.get(int(item["id"]), [])
        maintenance = str(item.get("maintenance_status") or "").lower()
        vehicle_valid = maintenance not in {"maintenance", "repair", "out_of_service", "点検中", "修理中"}
        vehicles.append({
            **item,
            "date_conflict": bool(conflicts),
            "conflicts": conflicts,
            "vehicle_valid": vehicle_valid,
            "manual_check_required": not bool(item.get("shaken_due_date")),
            "manual_conflict_check": int(item["id"]) in unknown_by_vehicle,
            "same_office": bool(actor_office and str(item.get("office") or "").strip() == actor_office),
            "last_used_at": vehicle_last_used.get(int(item["id"]), ""),
        })
    drivers.sort(key=lambda item: str(item.get("last_used_at") or ""), reverse=True)
    drivers.sort(key=lambda item: (bool(item.get("date_conflict")), not bool(item.get("same_office"))))
    vehicles.sort(key=lambda item: str(item.get("last_used_at") or ""), reverse=True)
    vehicles.sort(key=lambda item: (bool(item.get("date_conflict")), not bool(item.get("same_office"))))
    return {"business_date": service_date, "drivers": drivers, "vehicles": vehicles}


def prepare_charter_draft_workbench(
    draft_id: Any,
    payload: dict[str, Any],
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotently assign a charter draft and return its editable view model.

    This intentionally does not render a PDF.  Rendering remains an explicit
    confirmation action in the shared document workbench.
    """
    tenant_id = get_current_tenant_id()
    draft = charter_draft_detail(draft_id, tenant_id)
    if not draft:
        raise ValueError("fixed_tour_charter_draft_not_found")
    driver_id = int(payload.get("driver_id") or 0)
    vehicle_id = int(payload.get("vehicle_id") or 0)
    if not driver_id or not vehicle_id:
        raise ValueError("fixed_tour_driver_vehicle_required")
    order = draft.get("order") or {}
    if not order:
        raise ValueError("fixed_tour_charter_order_not_found")
    options = charter_dispatch_options(order.get("order_date") or draft.get("business_start_date"), draft["id"], actor=actor)
    driver = next((item for item in options["drivers"] if int(item["id"]) == driver_id), None)
    vehicle = next((item for item in options["vehicles"] if int(item["id"]) == vehicle_id), None)
    if not driver or not vehicle:
        raise ValueError("driver_or_vehicle_not_found")
    if driver.get("date_conflict") or not driver.get("qualification_valid", True):
        raise ValueError("fixed_tour_driver_unavailable")
    if vehicle.get("date_conflict") or not vehicle.get("vehicle_valid", True):
        raise ValueError("fixed_tour_vehicle_unavailable")
    if draft.get("source_preset_id"):
        route = route_detail(draft["source_preset_id"], tenant_id) or {}
        configured_types = {_norm(item.get("vehicle_type")) for item in route.get("prices") or [] if item.get("vehicle_type")}
        if configured_types and _norm(vehicle.get("vehicle_type")) not in configured_types:
            raise ValueError("fixed_tour_vehicle_type_mismatch")
    active = draft.get("assignment")
    if active:
        if int(active["driver_id"]) != driver_id or int(active["vehicle_id"]) != vehicle_id:
            raise ValueError("fixed_tour_draft_already_assigned")
        assignment_result = {
            "success": True,
            "assignment_ids": [int(active["id"])],
            "updated_order_ids": [int(order["id"])],
            "conflicts": [],
            "reused": True,
        }
    else:
        assignment_result = assign_orders(
            [order["id"]], driver_id, vehicle_id, actor=actor,
            notify_driver=False, publish_assignment=False,
        )
        if not assignment_result.get("success"):
            raise ValueError("fixed_tour_assignment_conflict")
        assignment_result["reused"] = False
    group_key = f"{str(order.get('order_date') or draft.get('business_start_date'))[:10]}:{driver_id}:{vehicle_id}"
    preview = get_run_document_preview(group_key, actor or {})
    with get_connection() as conn:
        conn.execute(
            """UPDATE fixed_tour_charter_drafts
               SET status = 'assigned_draft', updated_by_user_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND tenant_id = ?""",
            (_actor_user_id(actor), int(draft["id"]), tenant_id),
        )
        conn.commit()
    return {
        "draft": charter_draft_detail(draft["id"], tenant_id),
        "assignment": assignment_result,
        "group_key": group_key,
        "preview": preview,
    }


def generate_charter_draft_documents(
    draft_id: Any,
    payload: dict[str, Any],
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibility entrypoint: prepare the draft, then explicitly render."""
    prepared = prepare_charter_draft_workbench(draft_id, payload, actor)
    document = generate_run_document(prepared["group_key"], actor or {})
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        conn.execute(
            """UPDATE fixed_tour_charter_drafts
               SET status = 'document_draft', updated_by_user_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND tenant_id = ?""",
            (_actor_user_id(actor), int(prepared["draft"]["id"]), tenant_id),
        )
        conn.commit()
    return {**prepared, "draft": charter_draft_detail(prepared["draft"]["id"], tenant_id), "document": document}


def _draft_by_request(client_request_id: str, tenant_id: int) -> dict[str, Any] | None:
    if not client_request_id:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM fixed_tour_charter_drafts WHERE tenant_id = ? AND client_request_id = ?",
            (tenant_id, client_request_id),
        ).fetchone()
    return charter_draft_detail(row["id"], tenant_id) if row else None


def _orphan_order_by_request(client_request_id: str, tenant_id: int) -> dict[str, Any] | None:
    """Recover the order written immediately before a charter draft insert failed."""
    if not client_request_id:
        return None
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE tenant_id = ? AND order_source = 'mobile_charter_draft'
              AND COALESCE(is_deleted, 0) = 0
              AND id NOT IN (
                  SELECT order_id FROM fixed_tour_charter_drafts WHERE tenant_id = ?
              )
            ORDER BY id DESC
            """,
            (tenant_id, tenant_id),
        ).fetchall()
    for row in rows:
        try:
            snapshot = json.loads(row["remark"] or "{}").get("fixed_tour") or {}
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if str(snapshot.get("client_request_id") or "") == client_request_id:
            return dict(row)
    return None


def _discard_unreferenced_charter_order(order_id: Any, tenant_id: int) -> None:
    """Remove only a duplicate order created by a losing idempotent request."""
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM orders
            WHERE id = ? AND tenant_id = ? AND order_source = 'mobile_charter_draft'
              AND NOT EXISTS (
                  SELECT 1 FROM fixed_tour_charter_drafts
                  WHERE tenant_id = ? AND order_id = ?
              )
            """,
            (int(order_id), tenant_id, tenant_id, int(order_id)),
        )
        conn.commit()


def _draft_snapshot(
    route: dict[str, Any],
    business_start_date: str,
    *,
    source_preset_id: int | None,
    source_preset_version: int | None,
    preserve_node_ids: bool = False,
) -> dict[str, Any]:
    start_date = date.fromisoformat(_iso_date(business_start_date))
    raw_stops = route.get("stops") or [node for day in route.get("days") or [] for node in day.get("nodes") or []]
    stops = _normalize_preset_stops(raw_stops)
    raw_by_index = [item if isinstance(item, dict) else {} for item in raw_stops]
    duration_days = max(int(route.get("duration_days") or 1), max(item["day_index"] for item in stops))
    trip_type = str(route.get("trip_type") or ("multi_day" if duration_days > 1 else "day"))
    if trip_type == "day" and duration_days > 1:
        trip_type = "multi_day"
    days: list[dict[str, Any]] = []
    sequence = 1
    for day_index in range(1, duration_days + 1):
        nodes: list[dict[str, Any]] = []
        for stop_index, stop in enumerate(stops):
            if stop["day_index"] != day_index:
                continue
            raw = raw_by_index[stop_index] if stop_index < len(raw_by_index) else {}
            route_node_id = str(raw.get("route_node_id") or "").strip() if preserve_node_ids else ""
            day_date = start_date + timedelta(days=day_index - 1)
            arrival_time = stop.get("default_arrival_time")
            departure_time = stop.get("default_departure_time")
            nodes.append({
                "route_node_id": route_node_id or f"node-{uuid.uuid4()}",
                "source_preset_node_id": stop.get("preset_node_id") if source_preset_id else None,
                "sequence_number": sequence,
                "day_index": day_index,
                "node_type": stop.get("stop_type") if stop.get("stop_type") in {"pickup", "via", "dropoff", "wait", "rest"} else "via",
                "location": stop["location_name"],
                "location_name": stop["location_name"],
                "arrival_time": arrival_time,
                "departure_time": departure_time,
                "arrival_at": f"{day_date.isoformat()} {arrival_time}:00" if arrival_time else "",
                "departure_at": f"{day_date.isoformat()} {departure_time}:00" if departure_time else "",
                "time_confirmed": False,
                "note": stop.get("note") or "",
            })
            sequence += 1
        if nodes:
            days.append({"day_index": day_index, "date": (start_date + timedelta(days=day_index - 1)).isoformat(), "nodes": nodes})
    if not days:
        raise ValueError("fixed_tour_requires_two_stops")
    return {
        "route_code": route.get("route_code") or "",
        "route_name": str(route.get("route_name") or route.get("name") or "私人订制行程").strip(),
        "description": str(route.get("description") or "").strip(),
        "operations_business_area": str(route.get("operations_business_area") or "").strip(),
        "trip_type": trip_type,
        "duration_days": duration_days,
        "source_preset_id": source_preset_id,
        "source_preset_version": source_preset_version,
        "version": source_preset_version,
        "document_status": "draft",
        "time_confirmation_status": "pending",
        "stops": [node for day in days for node in day["nodes"]],
        "days": days,
    }


def _charter_order_payload(
    snapshot: dict[str, Any],
    actor: dict[str, Any] | None,
    client_request_id: str,
) -> dict[str, Any]:
    all_nodes = snapshot["stops"]
    first, last = all_nodes[0], all_nodes[-1]
    business_start_date = snapshot["days"][0]["date"]
    business_end_date = snapshot["days"][-1]["date"]
    snapshot["client_request_id"] = client_request_id
    return {
        "order_date": business_start_date,
        "end_date": business_end_date,
        "start_time": first.get("departure_time") or first.get("arrival_time"),
        "end_time": last.get("departure_time") or last.get("arrival_time"),
        "pickup_location": first["location"],
        "dropoff_location": last["location"],
        "order_type": "包车",
        "operations_business_area": snapshot.get("operations_business_area") or "",
        "order_source": "mobile_charter_draft",
        "source_channel": "dispatch_miniapp",
        "created_by_dispatcher_id": _actor_user_id(actor) or 0,
        "created_by_dispatcher": str((actor or {}).get("name") or (actor or {}).get("username") or ""),
        "remark": json.dumps({"fixed_tour": snapshot}, ensure_ascii=False),
        "dispatch_status": "unassigned",
    }


def create_charter_draft(payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    client_request_id = str(payload.get("client_request_id") or "").strip()
    if not client_request_id:
        raise ValueError("fixed_tour_client_request_id_required")
    existing = _draft_by_request(client_request_id, tenant_id)
    if existing:
        return {"created": False, "draft": existing}

    source_preset_id = int(payload.get("source_preset_id") or payload.get("route_id") or 0) or None
    if source_preset_id:
        route = route_detail(source_preset_id, tenant_id)
        if not route or route.get("status") != "active":
            raise ValueError("fixed_tour_route_not_available")
        source_version = int(route.get("version") or 1)
    else:
        route = payload.get("route") if isinstance(payload.get("route"), dict) else payload
        source_version = None
    business_start_date = _iso_date(payload.get("business_start_date") or payload.get("date"))
    snapshot = _draft_snapshot(
        route,
        business_start_date,
        source_preset_id=source_preset_id,
        source_preset_version=source_version,
    )
    order_payload = _charter_order_payload(snapshot, actor, client_request_id)
    business_end_date = snapshot["days"][-1]["date"]
    order = _orphan_order_by_request(client_request_id, tenant_id)
    order_created = not order
    if order:
        order = update_order(str(order["id"]), order_payload)
        if not order:
            raise ValueError("fixed_tour_charter_order_not_found")
    else:
        order = create_order(order_payload)
    charter_id = f"charter-{uuid.uuid4()}"
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO fixed_tour_charter_drafts (
                    tenant_id, charter_id, source_preset_id, source_preset_version, order_id,
                    status, trip_type, duration_days, business_start_date, business_end_date,
                    route_name, route_snapshot_json, client_request_id, created_by_user_id, updated_by_user_id
                ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id, charter_id, source_preset_id, source_version, order["id"],
                    snapshot["trip_type"], snapshot["duration_days"], business_start_date, business_end_date,
                    snapshot["route_name"], json.dumps(snapshot, ensure_ascii=False), client_request_id,
                    _actor_user_id(actor), _actor_user_id(actor),
                ),
            )
            conn.commit()
            draft_id = cur.lastrowid
    except sqlite3.IntegrityError:
        existing = _draft_by_request(client_request_id, tenant_id)
        if not existing:
            raise
        if order_created and int(existing["order_id"]) != int(order["id"]):
            _discard_unreferenced_charter_order(order["id"], tenant_id)
        return {"created": False, "draft": existing}
    return {"created": True, "draft": charter_draft_detail(draft_id, tenant_id)}


def update_charter_draft(draft_id: Any, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    current = charter_draft_detail(draft_id, tenant_id)
    if not current:
        raise ValueError("fixed_tour_charter_draft_not_found")
    assignment = current.get("assignment") or {}
    editable_statuses = {"draft", "assigned_draft", "document_draft"}
    if current.get("status") not in editable_statuses:
        raise ValueError("fixed_tour_charter_draft_locked")
    if assignment and (
        assignment.get("status") != "active"
        or assignment.get("execution_status") != "draft"
        or assignment.get("published_at")
    ):
        raise ValueError("fixed_tour_charter_draft_locked")
    if assignment:
        with get_connection() as conn:
            published = conn.execute(
                """
                SELECT 1 FROM driver_run_documents
                WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
                  AND status = 'published'
                LIMIT 1
                """,
                (
                    tenant_id,
                    str((current.get("order") or {}).get("order_date") or current.get("business_start_date") or "")[:10],
                    int(assignment["driver_id"]),
                    int(assignment["vehicle_id"]),
                ),
            ).fetchone()
        if published:
            raise ValueError("fixed_tour_charter_draft_locked")
    before_order = dict(current.get("order") or {})
    current_snapshot = current["route_snapshot"]
    raw_route = payload.get("route") if isinstance(payload.get("route"), dict) else payload
    merged_route = {
        **current_snapshot,
        **{key: raw_route[key] for key in ("route_name", "name", "description", "trip_type", "duration_days") if key in raw_route},
    }
    if "stops" in raw_route:
        merged_route["stops"] = raw_route["stops"]
        merged_route.pop("days", None)
    elif "days" in raw_route:
        merged_route["days"] = raw_route["days"]
        merged_route["stops"] = [node for day in raw_route["days"] for node in day.get("nodes") or []]
    business_start_date = _iso_date(payload.get("business_start_date") or current["business_start_date"])
    snapshot = _draft_snapshot(
        merged_route,
        business_start_date,
        source_preset_id=current.get("source_preset_id"),
        source_preset_version=current.get("source_preset_version"),
        preserve_node_ids=True,
    )
    snapshot["client_request_id"] = current["client_request_id"]
    all_nodes = snapshot["stops"]
    first, last = all_nodes[0], all_nodes[-1]
    business_end_date = snapshot["days"][-1]["date"]
    updated_order = update_order(str(current["order_id"]), {
        "order_date": business_start_date,
        "end_date": business_end_date,
        "start_time": first.get("departure_time") or first.get("arrival_time"),
        "end_time": last.get("departure_time") or last.get("arrival_time"),
        "pickup_location": first["location"],
        "dropoff_location": last["location"],
        "updated_by_dispatcher_id": _actor_user_id(actor) or 0,
        "updated_by_dispatcher": str((actor or {}).get("name") or (actor or {}).get("username") or ""),
        "remark": json.dumps({"fixed_tour": snapshot}, ensure_ascii=False),
    })
    if not updated_order:
        raise ValueError("fixed_tour_charter_order_not_found")
    if assignment:
        mark_order_changed(current["order_id"], before_order, updated_order, tenant_id, force=True)
    next_status = "assigned_draft" if assignment else "draft"
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE fixed_tour_charter_drafts
            SET status = ?, trip_type = ?, duration_days = ?, business_start_date = ?, business_end_date = ?,
                route_name = ?, route_snapshot_json = ?, updated_by_user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (
                next_status, snapshot["trip_type"], snapshot["duration_days"], business_start_date, business_end_date,
                snapshot["route_name"], json.dumps(snapshot, ensure_ascii=False), _actor_user_id(actor),
                current["id"], tenant_id,
            ),
        )
        conn.commit()
    return charter_draft_detail(current["id"], tenant_id) or {}


def save_preset_and_create_draft(payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    client_request_id = str(payload.get("client_request_id") or "").strip()
    if not client_request_id:
        raise ValueError("fixed_tour_client_request_id_required")
    existing = _draft_by_request(client_request_id, tenant_id)
    if existing:
        route = route_detail(existing.get("source_preset_id"), tenant_id) if existing.get("source_preset_id") else None
        return {"created": False, "route": route, "draft": existing}
    route_payload = dict(payload.get("route") or {})
    route_id = payload.get("route_id")
    if route_id and not route_payload.get("route_code"):
        current_route = route_detail(route_id, tenant_id)
        if not current_route:
            raise ValueError("fixed_tour_route_not_found")
        route_payload["route_code"] = current_route["route_code"]
    if not route_payload.get("route_code"):
        route_payload["route_code"] = f"DT-MOBILE-{uuid.uuid5(uuid.NAMESPACE_URL, f'{tenant_id}:{client_request_id}').hex[:12].upper()}"
    if not route_id:
        with get_connection() as conn:
            prior = conn.execute(
                "SELECT id FROM fixed_tour_routes WHERE tenant_id = ? AND route_code = ?",
                (tenant_id, route_payload["route_code"]),
            ).fetchone()
        route_id = prior["id"] if prior else None
    route = save_route(route_payload, tenant_id, route_id=route_id, actor=actor)
    created = create_charter_draft({
        "source_preset_id": route["id"],
        "business_start_date": payload.get("business_start_date") or payload.get("date"),
        "client_request_id": client_request_id,
    }, actor)
    return {"created": created["created"], "route": route, "draft": created["draft"]}


def materialize(payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id(); route = route_detail(payload.get("route_id"), tenant_id)
    if not route or route["status"] != "active": raise ValueError("fixed_tour_route_not_available")
    vehicle_id, driver_id, business_date = int(payload.get("vehicle_id") or 0), int(payload.get("driver_id") or 0), str(payload.get("date") or "")
    if not vehicle_id or not driver_id or not business_date: raise ValueError("fixed_tour_date_driver_vehicle_required")
    segments = payload.get("segments") or []
    for segment in segments:
        if not segment.get("pickup_location") or not segment.get("dropoff_location"):
            raise ValueError("fixed_tour_segment_locations_required")
        if segment.get("start_time") and segment.get("end_time") and str(segment["end_time"]) < str(segment["start_time"]):
            raise ValueError("segment_time_order")
    with get_connection() as conn:
        vehicle = conn.execute("SELECT * FROM vehicles WHERE id = ? AND tenant_id = ?", (vehicle_id, tenant_id)).fetchone()
        if not vehicle: raise ValueError("fixed_tour_vehicle_not_found")
        suggested_price = next((x["price_jpy"] for x in route["prices"] if _norm(x["vehicle_type"]) == _norm(vehicle["vehicle_type"])), None)
        override = payload.get("effective_price_jpy")
        if override in (None, ""):
            if suggested_price is None:
                raise ValueError("missing_route_vehicle_price")
            price = float(suggested_price)
        else:
            try:
                price = float(override)
            except (TypeError, ValueError):
                raise ValueError("fixed_tour_effective_price_invalid")
            if price < 0 or not price.is_integer():
                raise ValueError("fixed_tour_effective_price_invalid")
        existing = conn.execute("SELECT * FROM fixed_tour_runs WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ? AND route_id = ?", (tenant_id, business_date, driver_id, vehicle_id, route["id"])).fetchone()
        if existing: return {"run": dict(existing), "created": False}
    snapshot = {k: route[k] for k in route if k not in {"id", "created_at", "updated_at"}}
    snapshot["segments"] = segments
    snapshot["suggested_price_jpy"] = int(float(suggested_price)) if suggested_price is not None else None
    snapshot["effective_price_jpy"] = int(price)
    route_nodes = [stop["location_name"] for stop in route["stops"]]
    for segment in segments:
        if not segment.get("same_passenger", True):
            continue
        if segment.get("position") == "post":
            if route_nodes[-1] != segment["pickup_location"]:
                route_nodes.append(segment["pickup_location"])
            if route_nodes[-1] != segment["dropoff_location"]:
                route_nodes.append(segment["dropoff_location"])
        else:
            prefix = [segment["pickup_location"], segment["dropoff_location"]]
            route_nodes = prefix[:-1] + route_nodes if route_nodes[0] == prefix[-1] else prefix + route_nodes
    route_note = "完整路线：" + " -> ".join(route_nodes)
    order = create_order({"order_date": business_date, "end_date": business_date, "start_time": route.get("default_start_time"), "end_time": route.get("default_end_time"), "pickup_location": route_nodes[0], "dropoff_location": route_nodes[-1], "order_type": route.get("default_order_type") or "包车", "vehicle_type": vehicle["vehicle_type"], "price": int(price), "price_jpy": int(price), "operations_business_area": route.get("operations_business_area"), "fee_remark": route_note, "remark": json.dumps({"fixed_tour": snapshot}, ensure_ascii=False)})
    assigned = assign_orders([order["id"]], driver_id, vehicle_id, actor, notify_driver=False, publish_assignment=False)
    if not assigned.get("success"): raise ValueError("fixed_tour_assignment_conflict")
    segment_order_ids: dict[int, int] = {}
    for sequence, segment in enumerate(segments, 1):
        if segment.get("same_passenger", True):
            continue
        segment_order = create_order({
            "order_date": business_date, "end_date": business_date,
            "start_time": segment.get("start_time") or route.get("default_start_time"),
            "end_time": segment.get("end_time") or route.get("default_end_time"),
            "pickup_location": segment["pickup_location"], "dropoff_location": segment["dropoff_location"],
            "order_type": segment.get("type") or "接送", "vehicle_type": vehicle["vehicle_type"],
            "price": 0, "price_jpy": 0, "operations_business_area": route.get("operations_business_area"),
            "remark": json.dumps({"fixed_tour_segment": {**segment, "route_id": route["id"]}}, ensure_ascii=False),
        })
        segment_assigned = assign_orders([segment_order["id"]], driver_id, vehicle_id, actor, notify_driver=False, publish_assignment=False)
        if not segment_assigned.get("success"):
            raise ValueError("fixed_tour_segment_assignment_conflict")
        segment_order_ids[sequence] = segment_order["id"]
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO fixed_tour_runs (tenant_id, route_id, route_snapshot_json, business_date, driver_id, vehicle_id, order_id, assignment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (tenant_id, route["id"], json.dumps(snapshot, ensure_ascii=False), business_date, driver_id, vehicle_id, order["id"], assigned["assignment_ids"][0]))
        run_id = cur.lastrowid
        for sequence, segment in enumerate(segments, 1):
            segment_order_id = segment_order_ids.get(sequence)
            conn.execute("INSERT INTO fixed_tour_run_segments (tenant_id, run_id, sequence_no, segment_position, pickup_location, dropoff_location, start_time, end_time, same_passenger, order_id, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (tenant_id, run_id, sequence, segment.get("position") if segment.get("position") in {"pre", "post"} else "pre", segment["pickup_location"], segment["dropoff_location"], segment.get("start_time"), segment.get("end_time"), 1 if segment.get("same_passenger", True) else 0, segment_order_id, json.dumps({**segment, "segment_type": segment.get("type") or "custom"}, ensure_ascii=False)))
        conn.commit(); run_id = cur.lastrowid
    return {"created": True, "run": {"id": run_id, "order_id": order["id"], "assignment_id": assigned["assignment_ids"][0], "route_snapshot": snapshot}}


def update_run(run_id: Any, payload: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Update a materialized fixed-tour run and invalidate its prior PDF packet.

    A fixed route template remains immutable for historical runs.  The run keeps
    its own route/segment snapshot in both fixed-tour tables and the existing
    order remark, which is already part of the run-document source hash.
    """
    tenant_id = get_current_tenant_id()
    with get_connection() as conn:
        run_row = conn.execute("SELECT * FROM fixed_tour_runs WHERE id = ? AND tenant_id = ?", (int(run_id), tenant_id)).fetchone()
        if not run_row:
            raise ValueError("fixed_tour_run_not_found")
        run = dict(run_row)
        before_row = conn.execute("SELECT * FROM orders WHERE id = ? AND tenant_id = ?", (run["order_id"], tenant_id)).fetchone()
        assignment = conn.execute("SELECT * FROM assignments WHERE id = ? AND tenant_id = ? AND status = 'active'", (run["assignment_id"], tenant_id)).fetchone()
    if not before_row or not assignment:
        raise ValueError("fixed_tour_run_assignment_not_found")

    before = dict(before_row)
    snapshot = json.loads(run.get("route_snapshot_json") or "{}")
    stops = payload.get("stops")
    if stops is not None:
        if not isinstance(stops, list) or len(stops) < 2:
            raise ValueError("fixed_tour_requires_two_stops")
        snapshot["stops"] = stops
    segments = payload.get("segments")
    if segments is not None:
        if not isinstance(segments, list):
            raise ValueError("fixed_tour_segments_invalid")
        for segment in segments:
            if not segment.get("pickup_location") or not segment.get("dropoff_location"):
                raise ValueError("fixed_tour_segment_locations_required")
            if segment.get("start_time") and segment.get("end_time") and str(segment["end_time"]) < str(segment["start_time"]):
                raise ValueError("segment_time_order")
        snapshot["segments"] = segments

    effective_stops = snapshot.get("stops") or []
    order_changes = {key: payload[key] for key in ("order_date", "end_date", "start_time", "end_time", "pickup_location", "dropoff_location", "operations_business_area", "order_type", "price", "price_jpy") if key in payload}
    if effective_stops:
        order_changes.setdefault("pickup_location", effective_stops[0].get("location_name") or before.get("pickup_location"))
        order_changes.setdefault("dropoff_location", effective_stops[-1].get("location_name") or before.get("dropoff_location"))
    # `remark` participates in the existing document source hash.  This makes
    # a segment-only change observable by the V0.14 pipeline without changing
    # its renderer or duplicating a document state machine.
    order_changes["remark"] = json.dumps({"fixed_tour": snapshot, "segments": snapshot.get("segments", [])}, ensure_ascii=False)
    after = update_order(str(run["order_id"]), order_changes)
    if not after:
        raise ValueError("fixed_tour_order_not_found")

    old_driver_id, old_vehicle_id = int(assignment["driver_id"]), int(assignment["vehicle_id"])
    new_driver_id = int(payload.get("driver_id") or old_driver_id)
    new_vehicle_id = int(payload.get("vehicle_id") or old_vehicle_id)
    # Force covers a segment-only or remark-only change.  The shared function
    # resets confirmation, increments run_revision and stales the old packet.
    mark_order_changed(run["order_id"], before, after, tenant_id, force=True)
    assignment_id = int(assignment["id"])
    if (new_driver_id, new_vehicle_id) != (old_driver_id, old_vehicle_id):
        reassigned = reassign_orders([run["order_id"]], new_driver_id, new_vehicle_id, actor)
        if not reassigned.get("success"):
            raise ValueError("fixed_tour_assignment_conflict")
        assignment_id = int(reassigned["new_assignment_ids"][0])
        # The destination group may already have a packet, too.
        mark_run_group_stale(after.get("order_date") or run["business_date"], new_driver_id, new_vehicle_id, tenant_id)

    with get_connection() as conn:
        conn.execute(
            "UPDATE fixed_tour_runs SET route_snapshot_json = ?, business_date = ?, driver_id = ?, vehicle_id = ?, assignment_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?",
            (json.dumps(snapshot, ensure_ascii=False), after.get("order_date") or run["business_date"], new_driver_id, new_vehicle_id, assignment_id, run["id"], tenant_id),
        )
        if segments is not None:
            conn.execute("DELETE FROM fixed_tour_run_segments WHERE tenant_id = ? AND run_id = ?", (tenant_id, run["id"]))
            for sequence, segment in enumerate(segments, 1):
                conn.execute(
                    "INSERT INTO fixed_tour_run_segments (tenant_id, run_id, sequence_no, segment_position, pickup_location, dropoff_location, start_time, end_time, same_passenger, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (tenant_id, run["id"], sequence, segment.get("position") if segment.get("position") in {"pre", "post"} else "pre", segment["pickup_location"], segment["dropoff_location"], segment.get("start_time"), segment.get("end_time"), 1 if segment.get("same_passenger", True) else 0, json.dumps({**segment, "segment_type": segment.get("type") or "custom"}, ensure_ascii=False)),
                )
        conn.commit()
    return {"run": {"id": run["id"], "order_id": run["order_id"], "assignment_id": assignment_id, "route_snapshot": snapshot}, "stale": True}


def list_today_runs(business_date: str, tenant_id: int | None = None) -> list[dict[str, Any]]:
    """Return fixed-tour runs with the existing driver workflow and GPS state.

    This is intentionally a read model over assignments, driver workflow
    events, location_logs and driver_run_documents; no second execution or
    telemetry table is introduced for fixed tours.
    """
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, a.execution_status, a.status AS assignment_status,
                   d.name AS driver_name, v.plate_number, o.oid,
                   o.pickup_location, o.dropoff_location
            FROM fixed_tour_runs r
            JOIN assignments a ON a.id = r.assignment_id AND a.tenant_id = r.tenant_id
            JOIN drivers d ON d.id = r.driver_id AND d.tenant_id = r.tenant_id
            JOIN vehicles v ON v.id = r.vehicle_id AND v.tenant_id = r.tenant_id
            JOIN orders o ON o.id = r.order_id AND o.tenant_id = r.tenant_id
            WHERE r.tenant_id = ? AND r.business_date = ?
            ORDER BY o.start_time, r.id
            """,
            (tenant_id, business_date),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for raw in rows:
            run = dict(raw)
            snapshot = json.loads(run.get("route_snapshot_json") or "{}")
            segments = [dict(row) for row in conn.execute(
                "SELECT * FROM fixed_tour_run_segments WHERE tenant_id = ? AND run_id = ? AND status = 'active' ORDER BY sequence_no",
                (tenant_id, run["id"]),
            )]
            events = [dict(row) for row in conn.execute(
                """SELECT event_type, event_time, location_text FROM driver_workflow_events
                   WHERE tenant_id = ? AND driver_id = ? AND (assignment_id = ? OR order_id = ?)
                   ORDER BY event_time ASC, id ASC""",
                (tenant_id, run["driver_id"], run["assignment_id"], run["order_id"]),
            )]
            location = conn.execute(
                """SELECT latitude, longitude, location_text, reported_at, source
                   FROM location_logs WHERE tenant_id = ? AND driver_id = ?
                   ORDER BY reported_at DESC, id DESC LIMIT 1""",
                (tenant_id, run["driver_id"]),
            ).fetchone()
            document = conn.execute(
                """SELECT status, version, stale_at, updated_at FROM driver_run_documents
                   WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ?
                   ORDER BY version DESC LIMIT 1""",
                (tenant_id, business_date, run["driver_id"], run["vehicle_id"]),
            ).fetchone()
            departure = next((event for event in events if event["event_type"] in {"roll_call_out", "depart_yard"}), None)
            returned = next((event for event in reversed(events) if event["event_type"] in {"roll_call_in", "return_yard"}), None)
            result.append({
                "id": run["id"], "business_date": run["business_date"], "route_id": run["route_id"],
                "route_name": snapshot.get("route_name") or "", "route_code": snapshot.get("route_code") or "",
                "route_version": snapshot.get("version"), "driver_id": run["driver_id"], "driver_name": run.get("driver_name"),
                "vehicle_id": run["vehicle_id"], "plate_number": run.get("plate_number"), "order_id": run["order_id"],
                "oid": run.get("oid"), "order_count": 1, "execution_status": run.get("execution_status") or "assigned",
                "assignment_status": run.get("assignment_status"), "pdf_status": dict(document) if document else None,
                "pre_segments": [segment for segment in segments if segment.get("segment_position") == "pre"],
                "post_segments": [segment for segment in segments if segment.get("segment_position") == "post"],
                "roll_call_out": dict(departure) if departure else None,
                "roll_call_in": dict(returned) if returned else None,
                "latest_location": dict(location) if location else None,
            })
    return result

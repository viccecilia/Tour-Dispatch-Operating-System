"""Tenant-scoped fixed-tour templates and one-way materialization to orders."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from backend.db.database import get_connection
from backend.services.dispatch_service import assign_orders, reassign_orders
from backend.services.order_service import create_order, get_order, update_order
from backend.services.run_document_service import mark_order_changed, mark_run_group_stale
from backend.services.tenant_context import get_current_tenant_id


def _norm(value: Any) -> str:
    return re.sub(r"[\s\-－_]+", "", unicodedata.normalize("NFKC", str(value or "")).lower())


def _row(conn: Any, route_id: Any, tenant_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM fixed_tour_routes WHERE id = ? AND tenant_id = ?", (int(route_id), tenant_id)).fetchone()
    return dict(row) if row else None


def route_detail(route_id: Any, tenant_id: int | None = None) -> dict[str, Any] | None:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    with get_connection() as conn:
        route = _row(conn, route_id, tenant_id)
        if not route:
            return None
        route["stops"] = [dict(x) for x in conn.execute("SELECT * FROM fixed_tour_route_stops WHERE route_id = ? AND tenant_id = ? ORDER BY sequence_no", (route["id"], tenant_id))]
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
        items = [x for x in items if needle in _norm(" ".join([x["route_code"], x["route_name"], *(s["location_name"] for s in x["stops"])]))]
    return items


def save_route(payload: dict[str, Any], tenant_id: int | None = None, route_id: Any = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    stops = payload.get("stops") or []
    if len(stops) < 2:
        raise ValueError("fixed_tour_requires_two_stops")
    fields = ("route_code", "route_name", "status", "default_start_time", "default_end_time", "standard_duration_minutes", "operations_business_area", "default_order_type", "route_summary", "document_remark", "application_method", "applicant_name", "contact_name", "contact_phone")
    values = [payload.get(key) or ("active" if key == "status" else "包车" if key == "default_order_type" else "ウェブサイト" if key == "application_method" else None) for key in fields]
    if not values[0] or not values[1]:
        raise ValueError("fixed_tour_code_and_name_required")
    with get_connection() as conn:
        existing = _row(conn, route_id, tenant_id) if route_id else None
        if existing:
            conn.execute("UPDATE fixed_tour_routes SET " + ", ".join(f"{f} = ?" for f in fields) + ", version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?", (*values, existing["id"], tenant_id))
            target_id = existing["id"]
            conn.execute("DELETE FROM fixed_tour_route_stops WHERE route_id = ? AND tenant_id = ?", (target_id, tenant_id))
            conn.execute("DELETE FROM fixed_tour_route_prices WHERE route_id = ? AND tenant_id = ?", (target_id, tenant_id))
        else:
            cur = conn.execute("INSERT INTO fixed_tour_routes (tenant_id, " + ", ".join(fields) + ") VALUES (?, " + ", ".join("?" for _ in fields) + ")", (tenant_id, *values))
            target_id = cur.lastrowid
        for index, stop in enumerate(stops, 1):
            conn.execute("INSERT INTO fixed_tour_route_stops (tenant_id, route_id, sequence_no, stop_type, location_name, default_arrival_time, default_departure_time, stay_minutes, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (tenant_id, target_id, index, stop.get("stop_type") or ("pickup" if index == 1 else "dropoff" if index == len(stops) else "waypoint"), stop.get("location_name") or "", stop.get("default_arrival_time"), stop.get("default_departure_time"), stop.get("stay_minutes"), stop.get("note")))
        for price in payload.get("prices") or []:
            if price.get("vehicle_type") and price.get("price_jpy") not in (None, ""):
                conn.execute("INSERT INTO fixed_tour_route_prices (tenant_id, route_id, vehicle_type, price_jpy) VALUES (?, ?, ?, ?)", (tenant_id, target_id, price["vehicle_type"], float(price["price_jpy"])))
        conn.commit()
    return route_detail(target_id, tenant_id) or {}


def copy_route(route_id: Any, tenant_id: int | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    route = route_detail(route_id, tenant_id)
    if not route: raise ValueError("fixed_tour_route_not_found")
    route.pop("id", None); route["route_code"] = f"{route['route_code']}-COPY"; route["route_name"] = f"{route['route_name']}（复制）"; route["status"] = "inactive"
    return save_route(route, tenant_id)


def set_route_status(route_id: Any, status: str, tenant_id: int | None = None) -> dict[str, Any]:
    tenant_id = get_current_tenant_id() if tenant_id is None else int(tenant_id)
    if status not in {"active", "inactive"}: raise ValueError("fixed_tour_status_invalid")
    with get_connection() as conn:
        cur = conn.execute("UPDATE fixed_tour_routes SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND tenant_id = ?", (status, int(route_id), tenant_id)); conn.commit()
    if not cur.rowcount: raise ValueError("fixed_tour_route_not_found")
    return route_detail(route_id, tenant_id) or {}


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
        price = next((x["price_jpy"] for x in route["prices"] if _norm(x["vehicle_type"]) == _norm(vehicle["vehicle_type"])), None)
        if price is None: raise ValueError("missing_route_vehicle_price")
        existing = conn.execute("SELECT * FROM fixed_tour_runs WHERE tenant_id = ? AND business_date = ? AND driver_id = ? AND vehicle_id = ? AND route_id = ?", (tenant_id, business_date, driver_id, vehicle_id, route["id"])).fetchone()
        if existing: return {"run": dict(existing), "created": False}
    snapshot = {k: route[k] for k in route if k not in {"id", "created_at", "updated_at"}}
    snapshot["segments"] = segments
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
    order = create_order({"order_date": business_date, "end_date": business_date, "start_time": route.get("default_start_time"), "end_time": route.get("default_end_time"), "pickup_location": route_nodes[0], "dropoff_location": route_nodes[-1], "order_type": route.get("default_order_type") or "包车", "vehicle_type": vehicle["vehicle_type"], "price": price, "price_jpy": price, "operations_business_area": route.get("operations_business_area"), "fee_remark": route_note, "remark": json.dumps({"fixed_tour": snapshot}, ensure_ascii=False)})
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

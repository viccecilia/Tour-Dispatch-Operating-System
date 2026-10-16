"""Driver Phase 2A actual route-node read/write service.

The published plan remains authoritative for node ownership and planned values.
This module stores only driver-entered actual values and a durable idempotency/audit ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
from contextlib import closing
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from backend.db.database import get_connection


ACTUAL_FIELDS = ("actual_location", "actual_arrival_at", "actual_departure_at", "odometer_km")


class DriverRouteActualError(ValueError):
    def __init__(self, code: str, status: int = 400, details: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or {}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_day(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise DriverRouteActualError("invalid_business_date") from exc
    if parsed.isoformat() != text:
        raise DriverRouteActualError("invalid_business_date")
    return text


def _parse_timestamp(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DriverRouteActualError(f"{field}_required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DriverRouteActualError(f"invalid_{field}") from exc
    if "T" not in text and " " not in text:
        raise DriverRouteActualError(f"invalid_{field}")
    return parsed.isoformat(timespec="seconds")


def _timestamp_order_key(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    return parsed.astimezone(timezone.utc)


def _current_documents(conn: Any, tenant_id: int, driver_id: int, business_date: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.*
        FROM driver_run_documents d
        WHERE d.tenant_id = ? AND d.driver_id = ? AND d.business_date = ?
          AND d.status = 'published'
          AND d.id = (
              SELECT d2.id FROM driver_run_documents d2
              WHERE d2.tenant_id = d.tenant_id AND d2.driver_id = d.driver_id
                AND d2.vehicle_id = d.vehicle_id AND d2.business_date = d.business_date
                AND d2.status = 'published'
              ORDER BY d2.version DESC, d2.id DESC LIMIT 1
          )
        ORDER BY d.vehicle_id, d.version DESC
        """,
        (tenant_id, driver_id, business_date),
    ).fetchall()
    return [dict(row) for row in rows]


def _valid_assignments(conn: Any, document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT a.id AS assignment_id, a.order_id, a.driver_id, a.vehicle_id,
               a.status AS assignment_status, a.execution_status AS assignment_execution_status,
               a.published_at AS assignment_published_at, o.oid, o.order_date, o.end_date,
               o.execution_status AS order_execution_status
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        WHERE a.tenant_id = ? AND a.driver_id = ? AND a.vehicle_id = ?
          AND a.status = 'active' AND a.published_at IS NOT NULL
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date <= ? AND COALESCE(NULLIF(o.end_date, ''), o.order_date) >= ?
        """,
        (
            int(document["tenant_id"]), int(document["driver_id"]), int(document["vehicle_id"]),
            str(document["business_date"]), str(document["business_date"]),
        ),
    ).fetchall()
    return {int(row["order_id"]): dict(row) for row in rows}


def _actual_public(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "actual_location": None,
            "actual_arrival_at": None,
            "actual_departure_at": None,
            "odometer_km": None,
            "revision": 0,
            "source_document_version_id": None,
            "source_sha256": None,
            "entered_at": None,
            "updated_at": None,
        }
    return {
        "actual_location": row.get("actual_location"),
        "actual_arrival_at": row.get("actual_arrival_at"),
        "actual_departure_at": row.get("actual_departure_at"),
        "odometer_km": row.get("odometer_km"),
        "revision": int(row.get("revision") or 0),
        "source_document_version_id": row.get("source_document_version_id"),
        "source_sha256": row.get("source_sha256"),
        "entered_at": row.get("entered_at"),
        "updated_at": row.get("updated_at"),
    }


def get_driver_day_workbench(user: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    tenant_id = int(user.get("tenant_id") or 0)
    driver_id = int(user.get("profile_id") or 0)
    if not tenant_id or not driver_id:
        raise DriverRouteActualError("driver_profile_required", 403)
    business_date = _parse_day(params.get("date"))
    documents: list[dict[str, Any]] = []
    flat_nodes: list[dict[str, Any]] = []
    with closing(get_connection()) as conn:
        for document in _current_documents(conn, tenant_id, driver_id, business_date):
            assignments = _valid_assignments(conn, document)
            if not assignments:
                continue
            node_rows = conn.execute(
                """
                SELECT n.*, a.actual_location, a.actual_arrival_at, a.actual_departure_at,
                       a.odometer_km, a.revision, a.source_document_version_id,
                       a.source_sha256 AS actual_source_sha256, a.entered_at, a.updated_at
                FROM dispatch_route_nodes n
                LEFT JOIN dispatch_route_node_actuals a
                  ON a.tenant_id = n.tenant_id AND a.run_group_id = n.run_group_id
                 AND a.route_node_id = n.route_node_id
                WHERE n.tenant_id = ? AND n.driver_id = ? AND n.run_group_id = ?
                  AND n.document_version_id = ?
                ORDER BY n.sequence_number, n.id
                """,
                (tenant_id, driver_id, document["run_group_id"], document["document_version_id"]),
            ).fetchall()
            nodes = []
            for raw in node_rows:
                row = dict(raw)
                order_id = int(row.get("order_id") or 0)
                assignment = assignments.get(order_id) if order_id else None
                if order_id and not assignment:
                    continue
                actual_row = {
                    **row,
                    "source_sha256": row.get("actual_source_sha256"),
                } if row.get("revision") is not None else None
                node = {
                    "route_node_id": row["route_node_id"],
                    "run_group_id": row["run_group_id"],
                    "document_version_id": row["document_version_id"],
                    "document_id": document.get("document_id"),
                    "document_version": int(document.get("version") or 0),
                    "source_sha256": document.get("source_sha256") or document.get("source_hash"),
                    "driver_id": int(row["driver_id"]),
                    "vehicle_id": int(row["vehicle_id"]),
                    "business_date": row["business_date"],
                    "sequence_number": int(row["sequence_number"]),
                    "assignment_id": int(assignment["assignment_id"]) if assignment else None,
                    "order_id": order_id or None,
                    "order_oid": assignment.get("oid") if assignment else None,
                    "node_type": row["node_type"],
                    "planned_location": row.get("planned_location"),
                    "planned_arrival_at": row.get("planned_arrival_at"),
                    "planned_departure_at": row.get("planned_departure_at"),
                    "load_status": row.get("load_status"),
                    "actual": _actual_public(actual_row),
                }
                nodes.append(node)
                flat_nodes.append(node)
            if nodes:
                documents.append({
                    "document_id": document.get("document_id"),
                    "document_version_id": document.get("document_version_id"),
                    "document_version": int(document.get("version") or 0),
                    "run_group_id": document.get("run_group_id"),
                    "vehicle_id": int(document["vehicle_id"]),
                    "source_sha256": document.get("source_sha256") or document.get("source_hash"),
                    "published_at": document.get("published_at"),
                    "nodes": nodes,
                })
    return {
        "business_date": business_date,
        "driver_id": driver_id,
        "documents": documents,
        "nodes": flat_nodes,
    }


def _normalize_update(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    changes: dict[str, Any] = {}
    for field in ACTUAL_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field in {"actual_arrival_at", "actual_departure_at"}:
            changes[field] = _parse_timestamp(value, field)
        elif field == "odometer_km":
            if value is None or isinstance(value, bool):
                raise DriverRouteActualError("invalid_odometer_km")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise DriverRouteActualError("invalid_odometer_km") from exc
            if not math.isfinite(number):
                raise DriverRouteActualError("invalid_odometer_km")
            if number < 0:
                raise DriverRouteActualError("odometer_km_negative")
            changes[field] = number
        else:
            text = str(value or "").strip()
            if not text:
                raise DriverRouteActualError("actual_location_required")
            changes[field] = text
    if not changes:
        raise DriverRouteActualError("actual_fields_required")
    client_recorded_at = payload.get("client_recorded_at")
    if client_recorded_at is not None:
        client_recorded_at = _parse_timestamp(client_recorded_at, "client_recorded_at")
    return changes, client_recorded_at


def _validate_time_order(current: dict[str, Any], changes: dict[str, Any]) -> None:
    arrival = changes.get("actual_arrival_at", current.get("actual_arrival_at"))
    departure = changes.get("actual_departure_at", current.get("actual_departure_at"))
    if arrival and departure:
        if _timestamp_order_key(departure) < _timestamp_order_key(arrival):
            raise DriverRouteActualError("actual_departure_before_arrival")


def _validate_odometer(conn: Any, node: dict[str, Any], document: dict[str, Any], odometer: float) -> None:
    bounds = conn.execute(
        """
        SELECT
          MAX(CASE WHEN n.sequence_number < ? THEN a.odometer_km END) AS previous_km,
          MIN(CASE WHEN n.sequence_number > ? THEN a.odometer_km END) AS next_km
        FROM dispatch_route_nodes n
        JOIN dispatch_route_node_actuals a
          ON a.tenant_id = n.tenant_id AND a.run_group_id = n.run_group_id
         AND a.route_node_id = n.route_node_id
        WHERE n.tenant_id = ? AND n.run_group_id = ? AND n.document_version_id = ?
        """,
        (
            node["sequence_number"], node["sequence_number"], node["tenant_id"],
            node["run_group_id"], document["document_version_id"],
        ),
    ).fetchone()
    if bounds and bounds["previous_km"] is not None and odometer < float(bounds["previous_km"]):
        raise DriverRouteActualError("odometer_km_regression", details={"previous_km": bounds["previous_km"]})
    if bounds and bounds["next_km"] is not None and odometer > float(bounds["next_km"]):
        raise DriverRouteActualError("odometer_km_exceeds_next", details={"next_km": bounds["next_km"]})


def _insert_request_ledger(conn: Any, values: tuple[Any, ...]) -> None:
    """Single fault-injection seam; kept inside the same transaction as the actual upsert."""
    conn.execute(
        """
        INSERT INTO driver_route_node_actual_requests (
          tenant_id, driver_id, actor_user_id, actor_role, actor_name,
          client_request_id, request_sha256,
          run_group_id, route_node_id, source_document_version_id, source_sha256,
          expected_revision, resulting_revision, before_json, after_json, response_json,
          client_recorded_at, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        values,
    )


def save_driver_route_node_actual(user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = int(user.get("tenant_id") or 0)
    driver_id = int(user.get("profile_id") or 0)
    user_id = int(user.get("id") or 0)
    if not tenant_id or not driver_id:
        raise DriverRouteActualError("driver_profile_required", 403)
    client_request_id = str(payload.get("client_request_id") or "").strip()
    run_group_id = str(payload.get("run_group_id") or "").strip()
    route_node_id = str(payload.get("route_node_id") or "").strip()
    source_version_id = str(payload.get("source_document_version_id") or "").strip()
    if not client_request_id:
        raise DriverRouteActualError("client_request_id_required")
    if not run_group_id or not route_node_id or not source_version_id:
        raise DriverRouteActualError("route_node_source_required")
    try:
        expected_revision = int(payload.get("expected_revision"))
    except (TypeError, ValueError) as exc:
        raise DriverRouteActualError("expected_revision_required") from exc
    if expected_revision < 0:
        raise DriverRouteActualError("invalid_expected_revision")
    changes, client_recorded_at = _normalize_update(payload)
    request_contract = {
        "run_group_id": run_group_id,
        "route_node_id": route_node_id,
        "source_document_version_id": source_version_id,
        "source_sha256": str(payload.get("source_sha256") or "").strip() or None,
        "assignment_id": payload.get("assignment_id"),
        "order_id": payload.get("order_id"),
        "expected_revision": expected_revision,
        "changes": changes,
        "client_recorded_at": client_recorded_at,
    }
    request_sha256 = _sha256(request_contract)

    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = conn.execute(
                """SELECT request_sha256, response_json FROM driver_route_node_actual_requests
                   WHERE tenant_id = ? AND driver_id = ? AND client_request_id = ?""",
                (tenant_id, driver_id, client_request_id),
            ).fetchone()
            if replay:
                if replay["request_sha256"] != request_sha256:
                    raise DriverRouteActualError("client_request_id_payload_conflict", 409)
                response = json.loads(replay["response_json"])
                response["idempotent_replay"] = True
                conn.rollback()
                return response

            document_row = conn.execute(
                """
                SELECT d.* FROM driver_run_documents d
                WHERE d.tenant_id = ? AND d.driver_id = ? AND d.run_group_id = ?
                  AND d.status = 'published'
                ORDER BY d.version DESC, d.id DESC LIMIT 1
                """,
                (tenant_id, driver_id, run_group_id),
            ).fetchone()
            if not document_row:
                raise DriverRouteActualError("published_run_group_not_found", 404)
            document = dict(document_row)
            if document.get("document_version_id") != source_version_id:
                raise DriverRouteActualError(
                    "published_source_revision_conflict", 409,
                    {"current_document_version_id": document.get("document_version_id"), "current_source_sha256": document.get("source_sha256") or document.get("source_hash")},
                )
            supplied_sha = request_contract["source_sha256"]
            current_sha = document.get("source_sha256") or document.get("source_hash")
            if supplied_sha and supplied_sha != current_sha:
                raise DriverRouteActualError("published_source_hash_conflict", 409, {"current_source_sha256": current_sha})

            node_row = conn.execute(
                """
                SELECT * FROM dispatch_route_nodes
                WHERE tenant_id = ? AND driver_id = ? AND run_group_id = ?
                  AND document_version_id = ? AND route_node_id = ?
                """,
                (tenant_id, driver_id, run_group_id, source_version_id, route_node_id),
            ).fetchone()
            if not node_row:
                raise DriverRouteActualError("route_node_not_found_in_published_plan", 404)
            node = dict(node_row)
            if int(node["vehicle_id"]) != int(document["vehicle_id"]):
                raise DriverRouteActualError("route_node_vehicle_mismatch", 409)
            assignments = _valid_assignments(conn, document)
            if not assignments:
                raise DriverRouteActualError("published_assignment_not_active", 409)
            order_id = int(node.get("order_id") or 0)
            assignment = assignments.get(order_id) if order_id else None
            if order_id and not assignment:
                raise DriverRouteActualError("route_node_assignment_not_active", 409)
            if order_id:
                supplied_order_id = payload.get("order_id")
                supplied_assignment_id = payload.get("assignment_id")
                try:
                    supplied_order_id = int(supplied_order_id)
                    supplied_assignment_id = int(supplied_assignment_id)
                except (TypeError, ValueError) as exc:
                    raise DriverRouteActualError("assignment_order_binding_required") from exc
                if supplied_order_id != order_id:
                    raise DriverRouteActualError("order_id_mismatch", 403)
                if supplied_assignment_id != int(assignment["assignment_id"]):
                    raise DriverRouteActualError("assignment_id_mismatch", 403)

            current_row = conn.execute(
                """SELECT * FROM dispatch_route_node_actuals
                   WHERE tenant_id = ? AND run_group_id = ? AND route_node_id = ?""",
                (tenant_id, run_group_id, route_node_id),
            ).fetchone()
            current = dict(current_row) if current_row else {}
            current_revision = int(current.get("revision") or 0)
            if current_revision != expected_revision:
                raise DriverRouteActualError(
                    "actual_revision_conflict", 409,
                    {"current_actual": _actual_public(current if current else None)},
                )
            _validate_time_order(current, changes)
            if "odometer_km" in changes:
                _validate_odometer(conn, node, document, float(changes["odometer_km"]))

            before = _actual_public(current if current else None)
            merged = dict(current)
            merged.update(changes)
            resulting_revision = current_revision + 1
            entered_at = client_recorded_at or datetime.now().astimezone().isoformat(timespec="seconds")
            conn.execute(
                """
                INSERT INTO dispatch_route_node_actuals (
                  tenant_id, route_node_id, run_group_id, driver_id, vehicle_id, business_date,
                  actual_arrival_at, actual_departure_at, odometer_km, actual_location,
                  entered_by_user_id, entered_by, entered_at, revision,
                  source_document_version_id, source_sha256, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(tenant_id, run_group_id, route_node_id) DO UPDATE SET
                  actual_arrival_at = excluded.actual_arrival_at,
                  actual_departure_at = excluded.actual_departure_at,
                  odometer_km = excluded.odometer_km,
                  actual_location = excluded.actual_location,
                  entered_by_user_id = excluded.entered_by_user_id,
                  entered_by = excluded.entered_by,
                  entered_at = excluded.entered_at,
                  revision = excluded.revision,
                  source_document_version_id = excluded.source_document_version_id,
                  source_sha256 = excluded.source_sha256,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    tenant_id, route_node_id, run_group_id, driver_id, int(node["vehicle_id"]), node["business_date"],
                    merged.get("actual_arrival_at"), merged.get("actual_departure_at"), merged.get("odometer_km"),
                    merged.get("actual_location"), user_id or None,
                    f"driver:{user.get('username') or driver_id}", entered_at, resulting_revision,
                    source_version_id, current_sha,
                ),
            )
            saved = dict(conn.execute(
                """SELECT * FROM dispatch_route_node_actuals
                   WHERE tenant_id = ? AND run_group_id = ? AND route_node_id = ?""",
                (tenant_id, run_group_id, route_node_id),
            ).fetchone())
            after = _actual_public(saved)
            response = {
                "saved": True,
                "idempotent_replay": False,
                "run_group_id": run_group_id,
                "route_node_id": route_node_id,
                "assignment_id": int(assignment["assignment_id"]) if assignment else None,
                "order_id": order_id or None,
                "document_version_id": source_version_id,
                "source_sha256": current_sha,
                "actual": after,
            }
            _insert_request_ledger(conn, (
                tenant_id, driver_id, user_id or None, str(user.get("role") or "driver"),
                str(user.get("display_name") or user.get("username") or driver_id),
                client_request_id, request_sha256,
                run_group_id, route_node_id, source_version_id, current_sha,
                expected_revision, resulting_revision, _canonical(before), _canonical(after),
                _canonical(response), client_recorded_at,
            ))
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise

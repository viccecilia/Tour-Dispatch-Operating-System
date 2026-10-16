from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import closing
from datetime import date, datetime
from typing import Any

from backend.db.database import get_connection
from backend.services.order_number_service import build_order_oid
from backend.services.permission_service import account_scope


EDITABLE_FIELDS = {
    "business_date",
    "service_kind",
    "service_source",
    "authorization_source",
    "authorization_evidence",
    "actual_pickup_location",
    "actual_pickup_at",
    "actual_dropoff_location",
    "actual_dropoff_at",
    "odometer_km",
    "pickup_odometer_km",
    "dropoff_odometer_km",
    "note",
}
TERMINAL_STATUSES = {"approved_new_order", "approved_linked_order", "rejected"}
DRIVER_RESUBMIT_STATUSES = {"draft", "needs_information"}
REVIEW_ACTIONS = {"approve-create", "approve-link", "needs-info", "reject"}
DRIVER_SETTLEMENT_STATUSES = {"pending", "unsettled", "settled", "paid"}
SUBMIT_REQUIRED = {
    "business_date",
    "service_source",
    "authorization_source",
    "actual_pickup_location",
    "actual_pickup_at",
    "actual_dropoff_location",
    "actual_dropoff_at",
}
MONEY_FIELDS = {
    "price", "price_jpy", "price_rmb", "fare_jpy", "fee_jpy",
    "driver_salary_jpy", "driver_settlement_amount", "collection_amount_jpy",
}


class DriverProvisionalError(ValueError):
    def __init__(self, code: str, status: int = 400, details: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or {}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, *, maximum: int = 1000) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    if not result:
        return None
    if len(result) > maximum:
        raise DriverProvisionalError("field_too_long")
    return result


def _parse_date(value: Any) -> str:
    result = _text(value, maximum=10)
    if not result:
        raise DriverProvisionalError("business_date_required")
    try:
        return date.fromisoformat(result).isoformat()
    except ValueError as exc:
        raise DriverProvisionalError("invalid_business_date") from exc


def _parse_timestamp(value: Any, field: str) -> str | None:
    result = _text(value, maximum=64)
    if not result:
        return None
    try:
        datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DriverProvisionalError(f"invalid_{field}") from exc
    return result


def _parse_revision(value: Any) -> int:
    try:
        revision = int(value)
    except (TypeError, ValueError) as exc:
        raise DriverProvisionalError("expected_revision_required") from exc
    if revision < 1:
        raise DriverProvisionalError("invalid_expected_revision")
    return revision


def _parse_odometer(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DriverProvisionalError("invalid_odometer_km") from exc
    if result < 0:
        raise DriverProvisionalError("invalid_odometer_km")
    return result


def _parse_money(value: Any, field: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise DriverProvisionalError(f"invalid_{field}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DriverProvisionalError(f"invalid_{field}") from exc
    if result < 0:
        raise DriverProvisionalError(f"invalid_{field}")
    return result


def _reject_money_fields(payload: dict[str, Any]) -> None:
    if any(field in payload for field in MONEY_FIELDS):
        raise DriverProvisionalError("provisional_pricing_not_available_in_phase2b0a")


def _dropoff_precedes_pickup(pickup: datetime, dropoff: datetime) -> bool:
    try:
        return dropoff < pickup
    except TypeError as exc:
        raise DriverProvisionalError("actual_time_timezone_mismatch") from exc


def _actor(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": int(user.get("id") or 0),
        "role": str(user.get("role") or ""),
        "scope": account_scope(user),
        "name": str(user.get("display_name") or user.get("username") or user.get("id") or "unknown"),
    }


def _driver_identity(user: dict[str, Any]) -> tuple[int, int, int]:
    actor = _actor(user)
    tenant_id = int(user.get("tenant_id") or 0)
    driver_id = int(user.get("profile_id") or 0)
    if actor["role"] != "driver" or actor["scope"] != "driver" or not tenant_id or not driver_id or not actor["user_id"]:
        raise DriverProvisionalError("driver_profile_required", 403)
    return tenant_id, driver_id, actor["user_id"]


def _carrier_admin_identity(user: dict[str, Any]) -> tuple[int, int]:
    actor = _actor(user)
    tenant_id = int(user.get("tenant_id") or 0)
    if actor["role"] != "admin" or actor["scope"] != "carrier" or not tenant_id or not actor["user_id"]:
        raise DriverProvisionalError("carrier_admin_required", 403)
    return tenant_id, actor["user_id"]


def _resolve_shift(conn: Any, tenant_id: int, driver_id: int, business_date: str, requested_assignment_id: Any = None) -> tuple[int, int | None]:
    rows = conn.execute(
        """
        SELECT a.id AS assignment_id, a.vehicle_id
        FROM assignments a
        JOIN orders o ON o.id = a.order_id AND o.tenant_id = a.tenant_id
        WHERE a.tenant_id = ? AND a.driver_id = ?
          AND a.status = 'active' AND a.published_at IS NOT NULL
          AND COALESCE(o.is_deleted, 0) = 0
          AND o.order_date <= ?
          AND COALESCE(NULLIF(o.end_date, ''), o.order_date) >= ?
        ORDER BY a.id
        """,
        (tenant_id, driver_id, business_date, business_date),
    ).fetchall()
    if requested_assignment_id not in (None, ""):
        try:
            wanted = int(requested_assignment_id)
        except (TypeError, ValueError) as exc:
            raise DriverProvisionalError("invalid_source_assignment_id") from exc
        match = next((row for row in rows if int(row["assignment_id"]) == wanted), None)
        if not match:
            raise DriverProvisionalError("source_assignment_not_in_driver_shift", 403)
        return int(match["vehicle_id"]), wanted
    vehicle_ids = sorted({int(row["vehicle_id"]) for row in rows if row["vehicle_id"]})
    if not vehicle_ids:
        raise DriverProvisionalError("active_shift_vehicle_not_found", 409)
    if len(vehicle_ids) != 1:
        raise DriverProvisionalError("active_shift_vehicle_ambiguous", 409)
    assignment_id = int(rows[0]["assignment_id"]) if len(rows) == 1 else None
    return vehicle_ids[0], assignment_id


def _normalize_changes(payload: dict[str, Any], *, require_date: bool = False) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if require_date or "business_date" in payload:
        changes["business_date"] = _parse_date(payload.get("business_date"))
    for field in (
        "service_kind", "service_source", "authorization_source", "authorization_evidence",
        "actual_pickup_location", "actual_dropoff_location", "note",
    ):
        if field in payload:
            changes[field] = _text(payload.get(field), maximum=2000 if field in {"authorization_evidence", "note"} else 300)
    for field in ("actual_pickup_at", "actual_dropoff_at"):
        if field in payload:
            changes[field] = _parse_timestamp(payload.get(field), field)
    for field in ("odometer_km", "pickup_odometer_km", "dropoff_odometer_km"):
        if field in payload:
            changes[field] = _parse_odometer(payload.get(field))
    if "service_kind" not in changes and require_date:
        changes["service_kind"] = "other"
    if changes.get("actual_pickup_at") and changes.get("actual_dropoff_at"):
        pickup = datetime.fromisoformat(changes["actual_pickup_at"].replace("Z", "+00:00"))
        dropoff = datetime.fromisoformat(changes["actual_dropoff_at"].replace("Z", "+00:00"))
        if _dropoff_precedes_pickup(pickup, dropoff):
            raise DriverProvisionalError("actual_dropoff_before_pickup")
    return changes


def _validate_merged_times(row: dict[str, Any]) -> None:
    if not row.get("actual_pickup_at") or not row.get("actual_dropoff_at"):
        return
    pickup = datetime.fromisoformat(str(row["actual_pickup_at"]).replace("Z", "+00:00"))
    dropoff = datetime.fromisoformat(str(row["actual_dropoff_at"]).replace("Z", "+00:00"))
    if _dropoff_precedes_pickup(pickup, dropoff):
        raise DriverProvisionalError("actual_dropoff_before_pickup")


def _public(row: dict[str, Any], *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = dict(row)
    result["revision"] = int(result.get("revision") or 0)
    result["original_snapshot"] = json.loads(result.pop("original_snapshot_json"))
    if events is not None:
        result["events"] = events
    return result


def _event_public(row: Any) -> dict[str, Any]:
    item = dict(row)
    for source, target in (
        ("before_json", "before"), ("after_json", "after"),
        ("request_json", "request"), ("response_json", "response"),
    ):
        raw = item.pop(source, None)
        item[target] = json.loads(raw) if raw else None
    return item


def _load_task(conn: Any, task_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT * FROM driver_provisional_tasks
           WHERE provisional_task_id = ? OR display_number = ?""",
        (str(task_id), str(task_id)),
    ).fetchone()
    return dict(row) if row else None


def _assert_task_access(task: dict[str, Any], tenant_id: int, driver_id: int | None = None) -> None:
    if int(task["tenant_id"]) != tenant_id:
        raise DriverProvisionalError("provisional_task_cross_tenant_forbidden", 403)
    if driver_id is not None and int(task["driver_id"]) != driver_id:
        raise DriverProvisionalError("provisional_task_not_owned_by_driver", 403)


def _request_id(payload: dict[str, Any]) -> str:
    value = _text(payload.get("client_request_id"), maximum=160)
    if not value:
        raise DriverProvisionalError("client_request_id_required")
    return value


def _client_recorded_at(payload: dict[str, Any]) -> str | None:
    return _parse_timestamp(payload.get("client_recorded_at"), "client_recorded_at") if "client_recorded_at" in payload else None


def _replay(conn: Any, tenant_id: int, actor_user_id: int, client_request_id: str, request_sha256: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT request_sha256, response_json FROM driver_provisional_task_events
           WHERE tenant_id = ? AND actor_user_id = ? AND client_request_id = ?""",
        (tenant_id, actor_user_id, client_request_id),
    ).fetchone()
    if not row:
        return None
    if row["request_sha256"] != request_sha256:
        raise DriverProvisionalError("client_request_id_payload_conflict", 409)
    result = json.loads(row["response_json"])
    result["idempotent_replay"] = True
    return result


def _insert_event(conn: Any, *, tenant_id: int, task_id: str, user: dict[str, Any], event_type: str,
                  client_request_id: str, request_sha256: str, expected_revision: int | None,
                  resulting_revision: int, before: dict[str, Any] | None, after: dict[str, Any],
                  request: dict[str, Any], response: dict[str, Any], reason: str | None = None,
                  client_recorded_at: str | None = None) -> None:
    actor = _actor(user)
    conn.execute(
        """
        INSERT INTO driver_provisional_task_events (
          tenant_id, provisional_task_id, actor_user_id, actor_role, actor_scope, actor_name,
          event_type, client_request_id, request_sha256, expected_revision, resulting_revision,
          before_json, after_json, request_json, response_json, reason, client_recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id, task_id, actor["user_id"], actor["role"], actor["scope"], actor["name"],
            event_type, client_request_id, request_sha256, expected_revision, resulting_revision,
            _canonical(before) if before is not None else None, _canonical(after), _canonical(request),
            _canonical(response), reason, client_recorded_at,
        ),
    )


def list_driver_provisional_tasks(user: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id, driver_id, _ = _driver_identity(user)
    params = params or {}
    clauses = ["tenant_id = ?", "driver_id = ?"]
    values: list[Any] = [tenant_id, driver_id]
    if params.get("status"):
        clauses.append("status = ?")
        values.append(str(params["status"]))
    with closing(get_connection()) as conn:
        rows = conn.execute(
            f"SELECT * FROM driver_provisional_tasks WHERE {' AND '.join(clauses)} ORDER BY business_date DESC, id DESC",
            values,
        ).fetchall()
    return {"tasks": [_public(dict(row)) for row in rows]}


def get_driver_provisional_task(user: dict[str, Any], task_id: str) -> dict[str, Any]:
    tenant_id, driver_id, _ = _driver_identity(user)
    with closing(get_connection()) as conn:
        task = _load_task(conn, task_id)
        if not task:
            raise DriverProvisionalError("provisional_task_not_found", 404)
        _assert_task_access(task, tenant_id, driver_id)
        events = [_event_public(row) for row in conn.execute(
            "SELECT * FROM driver_provisional_task_events WHERE tenant_id = ? AND provisional_task_id = ? ORDER BY id",
            (tenant_id, task["provisional_task_id"]),
        ).fetchall()]
    return {"task": _public(task, events=events)}


def create_driver_provisional_task(user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id, driver_id, user_id = _driver_identity(user)
    _reject_money_fields(payload)
    client_request_id = _request_id(payload)
    normalized = _normalize_changes(payload, require_date=True)
    request_contract = {"action": "create", "driver_id": driver_id, "changes": normalized,
                        "source_assignment_id": payload.get("source_assignment_id")}
    request_sha = _sha256(request_contract)
    stable = uuid.uuid5(uuid.NAMESPACE_URL, f"tourflow:{tenant_id}:{driver_id}:{client_request_id}").hex
    task_id = f"pt-{stable}"
    display_number = f"TMP-{normalized['business_date'].replace('-', '')}-{stable[-6:].upper()}"
    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = _replay(conn, tenant_id, user_id, client_request_id, request_sha)
            if replay:
                conn.rollback()
                return replay
            vehicle_id, source_assignment_id = _resolve_shift(
                conn, tenant_id, driver_id, normalized["business_date"], payload.get("source_assignment_id")
            )
            original = {
                "provisional_task_id": task_id,
                "display_number": display_number,
                "tenant_id": tenant_id,
                "driver_id": driver_id,
                "vehicle_id": vehicle_id,
                "source_assignment_id": source_assignment_id,
                **normalized,
                "requested_vehicle_id": payload.get("vehicle_id"),
            }
            fields = [
                "business_date", "service_kind", "service_source", "authorization_source",
                "authorization_evidence", "actual_pickup_location", "actual_pickup_at",
                "actual_dropoff_location", "actual_dropoff_at", "odometer_km",
                "pickup_odometer_km", "dropoff_odometer_km", "note",
            ]
            conn.execute(
                f"""INSERT INTO driver_provisional_tasks (
                    tenant_id, provisional_task_id, display_number, driver_id, vehicle_id,
                    source_assignment_id, {', '.join(fields)}, original_snapshot_json,
                    created_by_user_id
                ) VALUES ({', '.join(['?'] * (8 + len(fields)))})""",
                [tenant_id, task_id, display_number, driver_id, vehicle_id, source_assignment_id,
                 *[normalized.get(field) for field in fields], _canonical(original), user_id],
            )
            task = dict(conn.execute(
                "SELECT * FROM driver_provisional_tasks WHERE tenant_id = ? AND provisional_task_id = ?",
                (tenant_id, task_id),
            ).fetchone())
            response = {"task": _public(task), "idempotent_replay": False}
            _insert_event(
                conn, tenant_id=tenant_id, task_id=task_id, user=user, event_type="driver_created",
                client_request_id=client_request_id, request_sha256=request_sha, expected_revision=None,
                resulting_revision=1, before=None, after=_public(task), request=request_contract,
                response=response, client_recorded_at=_client_recorded_at(payload),
            )
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise


def update_driver_provisional_task(user: dict[str, Any], task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id, driver_id, user_id = _driver_identity(user)
    _reject_money_fields(payload)
    client_request_id = _request_id(payload)
    expected_revision = _parse_revision(payload.get("expected_revision"))
    changes = _normalize_changes({key: value for key, value in payload.items() if key in EDITABLE_FIELDS})
    if not changes:
        raise DriverProvisionalError("provisional_changes_required")
    request_contract = {"action": "update", "task_id": task_id, "expected_revision": expected_revision, "changes": changes}
    request_sha = _sha256(request_contract)
    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = _replay(conn, tenant_id, user_id, client_request_id, request_sha)
            if replay:
                conn.rollback()
                return replay
            task = _load_task(conn, task_id)
            if not task:
                raise DriverProvisionalError("provisional_task_not_found", 404)
            _assert_task_access(task, tenant_id, driver_id)
            if task["status"] in TERMINAL_STATUSES:
                raise DriverProvisionalError("provisional_task_terminal", 409)
            if task["status"] not in DRIVER_RESUBMIT_STATUSES:
                raise DriverProvisionalError("provisional_task_already_pending", 409)
            if int(task["revision"]) != expected_revision:
                raise DriverProvisionalError("provisional_revision_conflict", 409, {"current_task": _public(task)})
            if "business_date" in changes and changes["business_date"] != task["business_date"]:
                vehicle_id, source_assignment_id = _resolve_shift(conn, tenant_id, driver_id, changes["business_date"], payload.get("source_assignment_id"))
                changes["vehicle_id"] = vehicle_id
                changes["source_assignment_id"] = source_assignment_id
            merged = {**task, **changes}
            _validate_merged_times(merged)
            resulting_revision = expected_revision + 1
            assignments = ", ".join(f"{field} = ?" for field in changes)
            conn.execute(
                f"UPDATE driver_provisional_tasks SET {assignments}, revision = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*[changes[field] for field in changes], resulting_revision, task["id"]],
            )
            saved = dict(conn.execute("SELECT * FROM driver_provisional_tasks WHERE id = ?", (task["id"],)).fetchone())
            response = {"task": _public(saved), "idempotent_replay": False}
            _insert_event(
                conn, tenant_id=tenant_id, task_id=saved["provisional_task_id"], user=user,
                event_type="driver_updated", client_request_id=client_request_id,
                request_sha256=request_sha, expected_revision=expected_revision,
                resulting_revision=resulting_revision, before=_public(task), after=_public(saved),
                request=request_contract, response=response, reason=_text(payload.get("reason"), maximum=500),
                client_recorded_at=_client_recorded_at(payload),
            )
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise


def submit_driver_provisional_task(user: dict[str, Any], task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id, driver_id, user_id = _driver_identity(user)
    client_request_id = _request_id(payload)
    expected_revision = _parse_revision(payload.get("expected_revision"))
    request_contract = {"action": "submit", "task_id": task_id, "expected_revision": expected_revision}
    request_sha = _sha256(request_contract)
    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = _replay(conn, tenant_id, user_id, client_request_id, request_sha)
            if replay:
                conn.rollback()
                return replay
            task = _load_task(conn, task_id)
            if not task:
                raise DriverProvisionalError("provisional_task_not_found", 404)
            _assert_task_access(task, tenant_id, driver_id)
            if task["status"] in TERMINAL_STATUSES:
                raise DriverProvisionalError("provisional_task_terminal", 409)
            if task["status"] not in DRIVER_RESUBMIT_STATUSES:
                raise DriverProvisionalError("provisional_task_already_pending", 409)
            if int(task["revision"]) != expected_revision:
                raise DriverProvisionalError("provisional_revision_conflict", 409, {"current_task": _public(task)})
            missing = sorted(field for field in SUBMIT_REQUIRED if not task.get(field))
            if missing:
                raise DriverProvisionalError("provisional_submit_incomplete", 409, {"missing_fields": missing})
            _validate_merged_times(task)
            resulting_revision = expected_revision + 1
            conn.execute(
                """UPDATE driver_provisional_tasks
                   SET status = 'pending_company_confirmation', revision = ?,
                       submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (resulting_revision, task["id"]),
            )
            saved = dict(conn.execute("SELECT * FROM driver_provisional_tasks WHERE id = ?", (task["id"],)).fetchone())
            response = {"task": _public(saved), "idempotent_replay": False}
            _insert_event(
                conn, tenant_id=tenant_id, task_id=saved["provisional_task_id"], user=user,
                event_type="driver_submitted", client_request_id=client_request_id,
                request_sha256=request_sha, expected_revision=expected_revision,
                resulting_revision=resulting_revision, before=_public(task), after=_public(saved),
                request=request_contract, response=response, client_recorded_at=_client_recorded_at(payload),
            )
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise


def list_company_provisional_tasks(user: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    tenant_id, _ = _carrier_admin_identity(user)
    params = params or {}
    clauses = ["tenant_id = ?"]
    values: list[Any] = [tenant_id]
    if params.get("status"):
        clauses.append("status = ?")
        values.append(str(params["status"]))
    with closing(get_connection()) as conn:
        rows = conn.execute(
            f"SELECT * FROM driver_provisional_tasks WHERE {' AND '.join(clauses)} ORDER BY business_date DESC, id DESC",
            values,
        ).fetchall()
    return {"tasks": [_public(dict(row)) for row in rows]}


def get_company_provisional_task(user: dict[str, Any], task_id: str) -> dict[str, Any]:
    tenant_id, _ = _carrier_admin_identity(user)
    with closing(get_connection()) as conn:
        task = _load_task(conn, task_id)
        if not task:
            raise DriverProvisionalError("provisional_task_not_found", 404)
        _assert_task_access(task, tenant_id)
        events = [_event_public(row) for row in conn.execute(
            "SELECT * FROM driver_provisional_task_events WHERE tenant_id = ? AND provisional_task_id = ? ORDER BY id",
            (tenant_id, task["provisional_task_id"]),
        ).fetchall()]
        formal_order = _linked_order_public(conn, task)
    return {"task": _public(task, events=events), "formal_order": formal_order}


def _linked_order_public(conn: Any, task: dict[str, Any]) -> dict[str, Any] | None:
    order_id = int(task.get("linked_order_id") or 0)
    if not order_id:
        return None
    row = conn.execute(
        """
        SELECT o.id AS order_id, o.oid, o.order_date, o.start_time, o.end_time,
               o.pickup_location, o.dropoff_location, o.order_type,
               COALESCE(o.price_jpy, o.price) AS price_jpy,
               o.driver_salary_jpy, o.driver_settlement_amount,
               COALESCE(NULLIF(o.driver_settlement_status, ''), 'pending') AS driver_settlement_status,
               o.execution_status, o.origin_kind, o.origin_provisional_task_id
        FROM orders o
        WHERE o.tenant_id = ? AND o.id = ? AND COALESCE(o.is_deleted, 0) = 0
        """,
        (task["tenant_id"], order_id),
    ).fetchone()
    return dict(row) if row else None


def _next_order_oid(conn: Any, tenant_id: int, order_date: str, order_id: int) -> str:
    tenant = conn.execute("SELECT slug FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    serial = order_id
    while True:
        oid = build_order_oid(
            company_code=tenant["slug"] if tenant else "D",
            order_date=order_date,
            serial=serial,
            account_role="admin",
            temporary=True,
        )
        if not conn.execute("SELECT 1 FROM orders WHERE oid = ?", (oid,)).fetchone():
            return oid
        serial += 1


def _create_formal_order(conn: Any, task: dict[str, Any], user: dict[str, Any]) -> tuple[int, int, str]:
    pickup_at = datetime.fromisoformat(str(task["actual_pickup_at"]).replace("Z", "+00:00"))
    dropoff_at = datetime.fromisoformat(str(task["actual_dropoff_at"]).replace("Z", "+00:00"))
    cursor = conn.execute(
        """
        INSERT INTO orders (
          tenant_id, order_date, end_date, start_time, end_time,
          pickup_location, dropoff_location, order_type, order_source,
          price, price_jpy, dispatch_status, execution_status, settlement_status,
          source_channel, created_by_dispatcher, created_by_dispatcher_id,
          origin_kind, origin_provisional_task_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'assigned', 'completed', 'pending',
                  NULL, ?, ?, 'driver_provisional', ?)
        """,
        (
            task["tenant_id"], task["business_date"], dropoff_at.date().isoformat(),
            pickup_at.strftime("%H:%M"), dropoff_at.strftime("%H:%M"),
            task["actual_pickup_location"], task["actual_dropoff_location"],
            task.get("service_kind") or "other", task.get("service_source"),
            str(user.get("display_name") or user.get("username") or "carrier admin"),
            int(user.get("id") or 0), task["provisional_task_id"],
        ),
    )
    order_id = int(cursor.lastrowid)
    oid = _next_order_oid(conn, int(task["tenant_id"]), str(task["business_date"]), order_id)
    conn.execute("UPDATE orders SET oid = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (oid, order_id))
    assignment = conn.execute(
        """
        INSERT INTO assignments (
          tenant_id, order_id, driver_id, vehicle_id, status, execution_status,
          assigned_at, published_by_user_id, published_by_name, published_at,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'active', 'completed', CURRENT_TIMESTAMP, NULL, NULL, NULL,
                  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (task["tenant_id"], order_id, task["driver_id"], task["vehicle_id"]),
    )
    return order_id, int(assignment.lastrowid), oid


def _resolve_existing_link(conn: Any, tenant_id: int, task: dict[str, Any], order_ref: Any, assignment_ref: Any = None) -> tuple[int, int, str]:
    order_key = str(order_ref or "").strip()
    if not order_key:
        raise DriverProvisionalError("linked_order_id_required")
    numeric = int(order_key) if order_key.isdigit() else -1
    row = conn.execute(
        "SELECT * FROM orders WHERE (id = ? OR oid = ?) AND COALESCE(is_deleted, 0) = 0",
        (numeric, order_key),
    ).fetchone()
    if not row:
        raise DriverProvisionalError("linked_order_not_found", 404)
    order = dict(row)
    if int(order["tenant_id"]) != tenant_id:
        raise DriverProvisionalError("linked_order_cross_tenant_forbidden", 403)
    if not (str(order["order_date"]) <= str(task["business_date"]) <= str(order.get("end_date") or order["order_date"])):
        raise DriverProvisionalError("linked_order_business_date_mismatch", 409)
    clauses = ["tenant_id = ?", "order_id = ?", "driver_id = ?", "vehicle_id = ?", "status = 'active'"]
    values: list[Any] = [tenant_id, order["id"], task["driver_id"], task["vehicle_id"]]
    if assignment_ref not in (None, ""):
        try:
            values.append(int(assignment_ref))
        except (TypeError, ValueError) as exc:
            raise DriverProvisionalError("invalid_linked_assignment_id") from exc
        clauses.append("id = ?")
    assignment = conn.execute(
        f"SELECT * FROM assignments WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT 1",
        values,
    ).fetchone()
    if not assignment:
        raise DriverProvisionalError("matching_assignment_required", 409)
    return int(order["id"]), int(assignment["id"]), str(order.get("oid") or order["id"])


def review_company_provisional_task(user: dict[str, Any], task_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id, user_id = _carrier_admin_identity(user)
    _reject_money_fields(payload)
    if action not in REVIEW_ACTIONS:
        raise DriverProvisionalError("invalid_provisional_review_action")
    client_request_id = _request_id(payload)
    expected_revision = _parse_revision(payload.get("expected_revision"))
    reason = _text(payload.get("reason"), maximum=1000)
    if action in {"reject", "needs-info"} and not reason:
        raise DriverProvisionalError("review_reason_required")
    request_contract = {
        "action": action,
        "task_id": task_id,
        "expected_revision": expected_revision,
        "linked_order_id": payload.get("linked_order_id"),
        "linked_assignment_id": payload.get("linked_assignment_id"),
        "reason": reason,
    }
    request_sha = _sha256(request_contract)
    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = _replay(conn, tenant_id, user_id, client_request_id, request_sha)
            if replay:
                conn.rollback()
                return replay
            task = _load_task(conn, task_id)
            if not task:
                raise DriverProvisionalError("provisional_task_not_found", 404)
            _assert_task_access(task, tenant_id)
            if int(task["revision"]) != expected_revision:
                raise DriverProvisionalError("provisional_revision_conflict", 409, {"current_task": _public(task)})
            if task["status"] != "pending_company_confirmation":
                raise DriverProvisionalError("provisional_task_not_pending", 409)

            linked_order_id = None
            linked_assignment_id = None
            linked_order_oid = None
            if action == "approve-create":
                linked_order_id, linked_assignment_id, linked_order_oid = _create_formal_order(conn, task, user)
                status = "approved_new_order"
            elif action == "approve-link":
                linked_order_id, linked_assignment_id, linked_order_oid = _resolve_existing_link(
                    conn, tenant_id, task, payload.get("linked_order_id"), payload.get("linked_assignment_id")
                )
                status = "approved_linked_order"
            elif action == "needs-info":
                status = "needs_information"
            else:
                status = "rejected"

            resulting_revision = expected_revision + 1
            conn.execute(
                """
                UPDATE driver_provisional_tasks
                SET status = ?, revision = ?, linked_order_id = ?, linked_assignment_id = ?,
                    review_action = ?, review_reason = ?, reviewed_by_user_id = ?, reviewed_by_name = ?,
                    reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status, resulting_revision, linked_order_id, linked_assignment_id, action, reason,
                    user_id, str(user.get("display_name") or user.get("username") or user_id), task["id"],
                ),
            )
            saved = dict(conn.execute("SELECT * FROM driver_provisional_tasks WHERE id = ?", (task["id"],)).fetchone())
            response = {
                "task": _public(saved),
                "formal_order": ({"order_id": linked_order_id, "assignment_id": linked_assignment_id, "oid": linked_order_oid}
                                 if linked_order_id else None),
                "side_effects": {"pdf": False, "notifications": False, "finance": False},
                "idempotent_replay": False,
            }
            _insert_event(
                conn, tenant_id=tenant_id, task_id=saved["provisional_task_id"], user=user,
                event_type=f"carrier_admin_{action.replace('-', '_')}", client_request_id=client_request_id,
                request_sha256=request_sha, expected_revision=expected_revision,
                resulting_revision=resulting_revision, before=_public(task), after=_public(saved),
                request=request_contract, response=response, reason=reason,
                client_recorded_at=_client_recorded_at(payload),
            )
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise


def price_company_provisional_task(user: dict[str, Any], task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update the one linked formal order using existing finance columns and append task history."""
    tenant_id, user_id = _carrier_admin_identity(user)
    client_request_id = _request_id(payload)
    expected_revision = _parse_revision(payload.get("expected_revision"))
    allowed = {"price_jpy", "driver_salary_jpy", "driver_settlement_amount", "driver_settlement_status"}
    supplied = {key: payload.get(key) for key in allowed if key in payload}
    if not supplied:
        raise DriverProvisionalError("provisional_pricing_fields_required")
    normalized: dict[str, Any] = {}
    for field in ("price_jpy", "driver_salary_jpy", "driver_settlement_amount"):
        if field in supplied:
            if field == "driver_settlement_amount" and supplied[field] in (None, ""):
                raise DriverProvisionalError("driver_settlement_amount_omit_when_unknown")
            normalized[field] = _parse_money(supplied[field], field)
    if "driver_settlement_status" in supplied:
        status = str(supplied["driver_settlement_status"] or "").strip()
        if status not in DRIVER_SETTLEMENT_STATUSES:
            raise DriverProvisionalError("invalid_driver_settlement_status")
        normalized["driver_settlement_status"] = status
    reason = _text(payload.get("reason"), maximum=1000)
    request_contract = {
        "action": "pricing-update",
        "task_id": task_id,
        "expected_revision": expected_revision,
        "changes": normalized,
        "reason": reason,
    }
    request_sha = _sha256(request_contract)
    with closing(get_connection()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            replay = _replay(conn, tenant_id, user_id, client_request_id, request_sha)
            if replay:
                conn.rollback()
                return replay
            task = _load_task(conn, task_id)
            if not task:
                raise DriverProvisionalError("provisional_task_not_found", 404)
            _assert_task_access(task, tenant_id)
            if int(task["revision"]) != expected_revision:
                raise DriverProvisionalError("provisional_revision_conflict", 409, {"current_task": _public(task)})
            if task["status"] not in {"approved_new_order", "approved_linked_order"}:
                raise DriverProvisionalError("provisional_task_not_approved", 409)
            before_order = _linked_order_public(conn, task)
            if not before_order:
                raise DriverProvisionalError("linked_order_not_found", 404)

            assignments: list[str] = []
            values: list[Any] = []
            if "price_jpy" in normalized:
                assignments.extend(["price = ?", "price_jpy = ?"])
                values.extend([normalized["price_jpy"], normalized["price_jpy"]])
            for field in ("driver_salary_jpy", "driver_settlement_amount", "driver_settlement_status"):
                if field in normalized:
                    assignments.append(f"{field} = ?")
                    values.append(normalized[field])
            conn.execute(
                f"UPDATE orders SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP "
                "WHERE tenant_id = ? AND id = ? AND COALESCE(is_deleted, 0) = 0",
                [*values, tenant_id, before_order["order_id"]],
            )
            after_order = _linked_order_public(conn, task)
            resulting_revision = expected_revision + 1
            conn.execute(
                "UPDATE driver_provisional_tasks SET revision = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (resulting_revision, task["id"]),
            )
            saved = dict(conn.execute("SELECT * FROM driver_provisional_tasks WHERE id = ?", (task["id"],)).fetchone())
            before_amount = before_order.get("driver_settlement_amount")
            after_amount = after_order.get("driver_settlement_amount") if after_order else None
            settled_before = str(before_order.get("driver_settlement_status") or "pending") in {"settled", "paid"}
            settled_delta = None
            if settled_before and before_amount != after_amount:
                settled_delta = float(after_amount or 0) - float(before_amount or 0)
            response = {
                "task": _public(saved),
                "formal_order": after_order,
                "settled_delta_jpy": settled_delta,
                "settlement_adjustment_required": settled_delta not in (None, 0),
                "idempotent_replay": False,
            }
            _insert_event(
                conn, tenant_id=tenant_id, task_id=saved["provisional_task_id"], user=user,
                event_type="carrier_admin_pricing_updated", client_request_id=client_request_id,
                request_sha256=request_sha, expected_revision=expected_revision,
                resulting_revision=resulting_revision,
                before={"task": _public(task), "formal_order": before_order},
                after={"task": _public(saved), "formal_order": after_order},
                request=request_contract, response=response, reason=reason,
                client_recorded_at=_client_recorded_at(payload),
            )
            conn.commit()
            return response
        except Exception:
            conn.rollback()
            raise


def get_company_provisional_finance_summary(user: dict[str, Any]) -> dict[str, Any]:
    """Read unique formal-order finance facts without creating a second ledger."""
    tenant_id, _ = _carrier_admin_identity(user)
    with closing(get_connection()) as conn:
        company = conn.execute(
            """
            WITH active_assignment AS (
              SELECT tenant_id, order_id, MAX(driver_id) AS driver_id
              FROM assignments WHERE status = 'active' GROUP BY tenant_id, order_id
            )
            SELECT COUNT(DISTINCT o.id) AS formal_order_count,
                   COUNT(DISTINCT CASE WHEN o.execution_status IN ('completed', 'returned') THEN o.id END) AS completed_order_count,
                   SUM(CASE WHEN COALESCE(o.price_jpy, o.price) IS NOT NULL THEN 1 ELSE 0 END) AS priced_order_count,
                   SUM(CASE WHEN COALESCE(o.price_jpy, o.price) IS NULL THEN 1 ELSE 0 END) AS unknown_price_count,
                   COALESCE(SUM(COALESCE(o.price_jpy, o.price)), 0) AS known_business_amount_jpy,
                   COALESCE(SUM(o.driver_salary_jpy), 0) AS driver_salary_jpy,
                   COALESCE(SUM(o.driver_settlement_amount), 0) AS driver_settlement_amount_jpy
            FROM orders o
            LEFT JOIN active_assignment a ON a.tenant_id = o.tenant_id AND a.order_id = o.id
            WHERE o.tenant_id = ? AND COALESCE(o.is_deleted, 0) = 0
            """,
            (tenant_id,),
        ).fetchone()
        driver_rows = conn.execute(
            """
            WITH active_assignment AS (
              SELECT tenant_id, order_id, MAX(driver_id) AS driver_id
              FROM assignments WHERE status = 'active' GROUP BY tenant_id, order_id
            )
            SELECT d.id AS driver_id, d.name AS driver_name,
                   COUNT(DISTINCT o.id) AS formal_order_count,
                   COUNT(DISTINCT CASE WHEN o.execution_status IN ('completed', 'returned') THEN o.id END) AS completed_order_count,
                   SUM(CASE WHEN COALESCE(o.price_jpy, o.price) IS NULL THEN 1 ELSE 0 END) AS unknown_price_count,
                   COALESCE(SUM(o.driver_salary_jpy), 0) AS driver_salary_jpy,
                   COALESCE(SUM(o.driver_settlement_amount), 0) AS driver_settlement_amount_jpy
            FROM orders o
            JOIN active_assignment a ON a.tenant_id = o.tenant_id AND a.order_id = o.id
            LEFT JOIN drivers d ON d.tenant_id = a.tenant_id AND d.id = a.driver_id
            WHERE o.tenant_id = ? AND COALESCE(o.is_deleted, 0) = 0
            GROUP BY d.id, d.name ORDER BY completed_order_count DESC, d.id
            """,
            (tenant_id,),
        ).fetchall()
    return {
        "company": dict(company) if company else {},
        "drivers": [dict(row) for row in driver_rows],
        "accounting_note": "Known formal-order amounts only; this is not a cash-receipt confirmation.",
    }

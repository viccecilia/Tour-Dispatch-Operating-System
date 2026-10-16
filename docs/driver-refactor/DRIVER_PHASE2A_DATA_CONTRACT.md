# Driver Phase 2A Data Contract

## Identity and authority

Both routes are under `/api/driver/*`. The API resolves `tenant_id` and `driver_id` only from the authenticated driver token. Client-supplied driver, tenant or vehicle values are not trusted. Admin, dispatcher and operations-manager tokens receive HTTP 403.

## GET `/api/driver/day-workbench?date=YYYY-MM-DD`

Returns only the authenticated driver's latest published document per vehicle for the requested day, provided that its assignments are still active/published and its orders are not deleted.

```json
{
  "business_date": "2026-10-20",
  "driver_id": 101,
  "documents": [{
    "document_id": "doc-...",
    "document_version_id": "docv-...",
    "document_version": 2,
    "run_group_id": "run-...",
    "vehicle_id": 201,
    "source_sha256": "...",
    "nodes": []
  }],
  "nodes": [{
    "route_node_id": "node-...",
    "run_group_id": "run-...",
    "document_version_id": "docv-...",
    "assignment_id": 301,
    "order_id": 401,
    "node_type": "pickup",
    "planned_location": "KIX",
    "planned_arrival_at": "2026-10-20T08:00:00",
    "planned_departure_at": "2026-10-20T08:00:00",
    "actual": {
      "actual_location": null,
      "actual_arrival_at": null,
      "actual_departure_at": null,
      "odometer_km": null,
      "revision": 0
    }
  }]
}
```

Planned and actual values are separate. Missing actual values remain `null`, never copied from planned values and never filled with zero.

## POST `/api/driver/route-node-actual`

Each request changes only explicitly supplied actual fields.

```json
{
  "client_request_id": "device-request-uuid",
  "run_group_id": "run-...",
  "route_node_id": "node-...",
  "source_document_version_id": "docv-...",
  "source_sha256": "...",
  "assignment_id": 301,
  "order_id": 401,
  "expected_revision": 1,
  "actual_location": "実際乗車場所",
  "actual_arrival_at": "2026-10-20T08:05:00",
  "odometer_km": 100.5,
  "client_recorded_at": "2026-10-20T08:06:00"
}
```

Actual fields: `actual_location`, `actual_arrival_at`, `actual_departure_at`, `odometer_km`. Blank strings, invalid timestamps, negative mileage and mileage outside known previous/next node bounds are rejected. Full ISO dates make cross-midnight values unambiguous.

For garage nodes, `assignment_id` and `order_id` are null; the run group must still have at least one valid published assignment. For order nodes, both binding IDs are mandatory and must match the server-side published plan.

## Idempotency and concurrency

- Same authenticated driver + same `client_request_id` + same normalized payload: stored response is returned with `idempotent_replay: true`; no actual or audit duplicate is written.
- Same request ID with a different payload: HTTP 409 `client_request_id_payload_conflict`.
- `expected_revision` must equal the current actual revision; otherwise HTTP 409 `actual_revision_conflict` with `current_actual`.
- A stale `source_document_version_id` or source SHA receives HTTP 409 and the current source identity.
- Actual upsert and request audit insert share one `BEGIN IMMEDIATE` transaction.

## Main errors

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `invalid_business_date` | Invalid GET date |
| 400 | `actual_fields_required` | No actual field supplied |
| 400 | `invalid_actual_arrival_at` / `invalid_actual_departure_at` | Invalid full timestamp |
| 400 | `actual_departure_before_arrival` | Departure earlier than arrival |
| 400 | `odometer_km_negative` / `odometer_km_regression` / `odometer_km_exceeds_next` | Invalid mileage |
| 403 | `assignment_id_mismatch` / `order_id_mismatch` | Forged binding |
| 404 | `published_run_group_not_found` / `route_node_not_found_in_published_plan` | Not in this driver's tenant/current plan |
| 409 | `published_source_revision_conflict` / `published_source_hash_conflict` | Client plan is stale |
| 409 | `actual_revision_conflict` | Concurrent actual update |
| 409 | `client_request_id_payload_conflict` | Request ID reused for different content |
| 409 | `route_node_assignment_not_active` | Assignment cancelled or order deleted |

## One-odometer boundary

Phase 2A keeps the existing one `odometer_km` value per route node. It does not invent arrival/departure dual readings. If later business rules require both readings while waiting at one physical stop, Phase 2B must use explicit stable nodes rather than overload this field.

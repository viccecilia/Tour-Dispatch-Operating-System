# Driver Phase 2B-0A provisional-task contract

## Entities and immutable history

### `driver_provisional_tasks`

The current snapshot contains:

- stable `provisional_task_id` and user-facing `TMP-YYYYMMDD-XXXXXX` display number;
- tenant, authenticated driver, server-derived vehicle and validated source assignment;
- service business date and `service_kind` (airport transfer/charter/etc.);
- service source, authorization source/evidence;
- actual pickup/drop-off place and time, a single `odometer_km` consistent with the Phase 2A one-node/one-reading decision, and note;
- workflow status, optimistic `revision`, linked formal order/assignment, submit/review facts and carrier-admin identity.

`original_snapshot_json` records the first driver submission plus the server-derived identity. A database trigger prevents replacement. Another trigger prevents physical deletion of the task.

### `driver_provisional_task_events`

Every write stores actor user/role/scope/name, event, persistent client request ID, request SHA-256, expected/result revision, before/after, normalized request, response, reason and client time. Database triggers reject update and delete, making the table append-only.

## Status machine

```text
draft
  -> pending_company_confirmation
      -> approved_new_order
      -> approved_linked_order
      -> rejected
```

`needs_information` is reserved in the schema for the later full approval workflow. B0-A intentionally exposes only approve-create, approve-link and reject. Terminal records cannot be edited and are never deleted.

## HTTP contract

Driver endpoints (driver role only):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/driver/provisional-tasks` | Create a draft, derive owner/vehicle, freeze original snapshot |
| `GET` | `/api/driver/provisional-tasks` | List own records only |
| `GET` | `/api/driver/provisional-tasks/{id}` | Read own snapshot and complete append-only history |
| `POST` | `/api/driver/provisional-tasks/{id}/update` | Partial actual-fact save using expected revision |
| `POST` | `/api/driver/provisional-tasks/{id}/submit` | Move a complete draft to company confirmation |

Shared future Web/App company endpoints (same service and database; carrier admin only):

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/company/provisional-tasks` | Same-tenant review queue |
| `GET` | `/api/company/provisional-tasks/{id}` | Same-tenant detail and history |
| `POST` | `/api/company/provisional-tasks/{id}/approve-create` | Atomically create one formal order and historical assignment, then link |
| `POST` | `/api/company/provisional-tasks/{id}/approve-link` | Link to an existing matching same-tenant order/assignment without creating another order |
| `POST` | `/api/company/provisional-tasks/{id}/reject` | Preserve the record and rejection reason without creating an order |

Every write requires `client_request_id`. Updates, submit and review also require `expected_revision`.

## Submission validation

Drafts permit staged saving. Company submission requires:

- business date;
- service source and authorization source;
- actual pickup location/time;
- actual drop-off location/time.

Mileage and evidence may be added later. Drop-off cannot precede pickup. Unknown price is never converted to zero.

## Idempotency and concurrency

- The unique ledger key is `(tenant_id, actor_user_id, client_request_id)`.
- Same request ID plus the same normalized request returns the recorded response with `idempotent_replay=true`.
- Reusing the request ID with a different payload returns `409 client_request_id_payload_conflict`.
- All writes use `BEGIN IMMEDIATE`.
- A stale revision returns `409 provisional_revision_conflict` and the current record.
- Two company administrators approving the same revision can produce only one success. The other receives a revision conflict.
- A partial unique index on `(tenant_id, origin_provisional_task_id)` provides a second database-level one-formal-order guard.

## Provisional-to-formal mapping

| Provisional | Formal order/assignment | Rule |
|---|---|---|
| `business_date` | `orders.order_date` | Approval on a later day never rewrites the service date |
| actual drop-off date | `orders.end_date` | Supports cross-midnight facts |
| actual pickup/drop-off times | `orders.start_time` / `end_time` | Time values come from approved facts |
| actual pickup/drop-off locations | order locations | No route randomization |
| `service_kind` | `orders.order_type` | Provisional source is not an order type |
| `service_source` | `orders.order_source` | Existing business source meaning retained |
| stable provisional ID | `orders.origin_kind='driver_provisional'`, `origin_provisional_task_id` | Permanent reverse source link |
| authenticated driver / derived vehicle | new historical `assignments` row | Assignment is active/completed but not published in B0-A |
| provisional linked IDs | order ID and assignment ID | Forward link retained on task |
| price | `NULL` | B0-A does not price or approve settlement |

For approve-link, the existing order is not relabeled or mutated. The task retains its forward links and its history provides reverse discovery without overwriting the original order's own source.

## Single-transaction boundary

Approve-create performs all of the following in one transaction:

1. carrier-admin and tenant check;
2. idempotency replay check;
3. pending-state and revision check;
4. formal order insert with stable source fields;
5. unpublished historical assignment insert;
6. task link/status/reviewer update;
7. append-only approval event insert;
8. commit.

Any exception rolls back all seven writes. B0-A does not call notification, PDF, run-document, pricing or finance services.

## Stable error codes

Important codes include `driver_profile_required`, `carrier_admin_required`, `provisional_task_not_owned_by_driver`, `provisional_task_cross_tenant_forbidden`, `active_shift_vehicle_not_found`, `active_shift_vehicle_ambiguous`, `client_request_id_payload_conflict`, `provisional_revision_conflict`, `provisional_submit_incomplete`, `provisional_pricing_not_available_in_phase2b0a`, `matching_assignment_required`, `linked_order_cross_tenant_forbidden`, and `provisional_task_terminal`.

# Driver Phase 2A Schema Reconciliation

## Baseline

- Worktree: `C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
- HEAD: `176d549c0baa9feb8e671efa05cdacb994108cf1`
- Migration mechanism: `backend.db.database.apply_migrations`, ordered `*.sql`, one row per file in `schema_migrations`.
- Historical SQL was not edited or replayed.
- Trial and Production were not accessed.

## Existing model versus Phase 2A need

| Concern | Existing state | Reusable | Gap | Resolution |
|---|---|---:|---|---|
| Stable plan group | `driver_run_documents.run_group_id` | Yes | None | Reuse |
| Stable route node | `dispatch_route_nodes.route_node_id` is derived independently of document version | Yes | None | Reuse |
| Published source | document version, lifecycle and source SHA already exist | Yes | None | Reuse |
| Actual values | `dispatch_route_node_actuals` already stores location, arrival, departure and one odometer reading | Yes | None | Reuse existing table |
| Actual uniqueness | unique `(tenant_id, run_group_id, route_node_id)` | Yes | None | Preserve |
| Optimistic concurrency | No revision column | No | Concurrent saves can silently overwrite | Add `revision` |
| Source binding | Actual row did not record the plan version/SHA used by the client | No | Stale plan writes were not provable | Add source version/SHA |
| Request idempotency | No durable request key or response ledger | No | Retry could create another update | Add one audit/ledger table |
| Before/after audit | Only last row state existed | No | No complete change evidence | Store before/after/response JSON, actor and two timestamps |

## New additive migration

`backend/db/migrations/20261015_driver_route_node_actuals_phase2a.sql`

- Adds three nullable/defaulted columns to the existing actual table: `revision`, `source_document_version_id`, `source_sha256`.
- Adds `driver_route_node_actual_requests` for durable request idempotency and audit.
- Unique request identity: `(tenant_id, driver_id, client_request_id)`.
- Adds an audit lookup index by tenant, run group, node and time.
- Does not alter orders, assignments, planned nodes, PDFs, expenses, reports or notifications.

## Registration and compatibility result

- Fresh isolated initialization registered the migration once.
- Two additional `apply_migrations` calls kept the registration count at `1`.
- `PRAGMA integrity_check`: `ok`.
- Existing actual values were unchanged; new rows begin at revision 1 after the first accepted save.
- Business fingerprints for `orders`, `assignments`, `driver_run_documents` and `dispatch_route_nodes` were identical before/after.

Evidence: `artifacts/driver-refactor/phase2a/phase2a-migration-rehearsal.json`.

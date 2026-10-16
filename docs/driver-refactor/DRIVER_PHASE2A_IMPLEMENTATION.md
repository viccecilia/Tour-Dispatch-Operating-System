# Driver Phase 2A Implementation

## Scope delivered

Phase 2A adds the server-side actual-node data chain only. No Phase 2B six-field WXML/WXSS editor and no Phase 2C formal daily-report PDF were added.

## Data flow

```text
authenticated driver token
  -> latest published driver_run_documents row for driver/tenant/vehicle/day
  -> matching document_version_id in dispatch_route_nodes
  -> active published assignment + non-deleted order validation
  -> stable (run_group_id, route_node_id)
  -> dispatch_route_node_actuals current state
  -> driver_route_node_actual_requests idempotency/audit history
```

`run_group_id` comes from tenant + business date + driver + vehicle. `route_node_id` comes from the run group + order + node type/occurrence (or the persisted charter node ID). It is independent of `document_version_id`, so a node that remains in the next published plan keeps its actual value. A genuinely new node has no actual value. Removed/cancelled historical rows are retained but no longer writable from the current plan.

## Changed files

| File | Purpose | SHA-256 |
|---|---|---|
| `backend/api/routes.py` | Add authenticated GET/POST route adapters and error mapping | `780bff2df067aea9b37a5056767254256c62dd0331ef96c4aa59d5f7fc00c2be` |
| `backend/services/driver_route_actual_service.py` | Published-plan read, partial actual save, validation, idempotency and concurrency | `f52e7cd0843fc24daf3905c2e68844b8c1f657111b52f0ee1d2e5df8dc77c0ac` |
| `backend/services/document_model_service.py` | Publish source/concurrency fields in the existing future contract | `a0b9e8df0a98af6d4e1e66ac68381a79b21f4dd931fe63b0cfa9496cb7cc9a6e` |
| `backend/db/migrations/20261015_driver_route_node_actuals_phase2a.sql` | Add revision/source binding and durable audit ledger | `cce48f5ad16d2c8f61ce1211cf451c6bb6f743288e7c18290f9dc4e595ac8dc0` |
| `tests/test_driver_route_actual_http.py` | Real local HTTP acceptance with isolated SQLite | `dae483945a28791434d137a18fd9f27e415259f396bb52b0b969646cb53b0d04` |
| `tests/test_driver_phase2a_migration.py` | Pre/post migration, repeat-start and rollback rehearsal | `a55f7abf26b48a350f1ff2a87f89f067dfe55a178c239c887592d690ff9f2d83` |

Hashes above record the final implementation sources; report-only edits do not affect them.

## Security decisions

- Route prefix and service both require the driver role/profile.
- Tenant and driver are taken from the verified token.
- Vehicle comes from the current published document/node.
- Order and assignment IDs are server-matched; payload mismatch is rejected.
- Current published source version/SHA is checked before update.
- Cancelled assignment, deleted order, old node and unpublished group writes are blocked.
- No update statement touches orders, assignments, planned nodes, document/PDF rows, reports, expenses or notifications.

## Existing module impact

- Existing `/api/driver/report`, `/daily-report`, task, expense, location and document routes were not changed.
- Saving actual nodes does not advance the old workflow state machine and does not generate a PDF or notification.
- Phase 1 miniapp home files were not edited in Phase 2A; their hashes remained exactly unchanged.
- Existing bottom navigation remains five tabs.

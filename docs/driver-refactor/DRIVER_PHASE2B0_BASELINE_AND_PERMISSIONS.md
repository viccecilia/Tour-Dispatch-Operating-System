# Driver Phase 2B-0A baseline and permissions

## Scope and immutable baseline

- Actual worktree: `C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
- HEAD: `176d549c0baa9feb8e671efa05cdacb994108cf1`
- Worktree state at start: detached and dirty. Phase 1, Phase 2A, authentication fixes and unrelated local work were preserved in place; no reset, clean, stash, commit or push was used.
- B0-A did not access Trial or Production and did not run against either database.
- B0-A changed only a new migration, a new provisional-task service, narrow API route wiring, new tests, evidence and these reports. `backend/api/routes.py` was already dirty from Phase 2A and was extended without removing that work.

Protected pre-existing file fingerprints remained unchanged:

| File | SHA-256 after B0-A | Meaning |
|---|---|---|
| `miniapp_yuzu/package_dispatch/pages/home/index.js` | `364407b618b1c3798f7d938e33fcbd748074775770ac0bbb69ab3ff6669e13c4` | Phase 1 home logic |
| `miniapp_yuzu/package_dispatch/pages/home/index.wxml` | `0c2a2224669869cbcf377231314a75a9b4be61165524a2a6c5a7f862b516a68d` | Phase 1 home markup |
| `miniapp_yuzu/package_dispatch/pages/home/index.wxss` | `add6722547ddccc9dd41b258d7dd0f024af8dff2464c7b8ecc6f81869be788b8` | Phase 1 home styles |
| `backend/services/driver_route_actual_service.py` | `f52e7cd0843fc24daf3905c2e68844b8c1f657111b52f0ee1d2e5df8dc77c0ac` | Phase 2A actual-node service |
| `backend/db/migrations/20261015_driver_route_node_actuals_phase2a.sql` | `cce48f5ad16d2c8f61ce1211cf451c6bb6f743288e7c18290f9dc4e595ac8dc0` | Phase 2A migration |

## Existing-chain audit and the gap proved

The following existing tables/services were inspected before adding a model:

- `orders` and `assignments`: formal company order and dispatch resource chain.
- `dispatch_route_nodes`, `dispatch_route_node_actuals`, and Phase 2A request ledger: stable published-plan actual-node chain.
- `driver_reports`, `driver_workflow_events`, `driver_expense_reports`, run-document services, notifications and finance services: existing downstream systems that must not be duplicated.
- `agency_order_change_requests`: belongs to the travel-agency change-request domain and requires an existing formal `order_id`; it cannot retain a driver-created provisional fact before a formal order exists.
- `audit_logs`: general audit rows do not enforce immutable original snapshots or persistent per-actor client request IDs.

The pre-B0 isolated schema had neither a provisional-task entity nor `orders.origin_kind` / `orders.origin_provisional_task_id`. Therefore extending the agency table or silently creating an order as the driver would violate domain, authority and traceability requirements. An independent additive provisional entity and event ledger were required.

## Enforced permission matrix

| Actor | Own provisional create/save/read/submit | Company queue/read | Approve create/link/reject | Formal order direct create |
|---|---:|---:|---:|---:|
| Driver | Yes, own tenant and own `profile_id` only | No | No | No |
| Carrier `dispatcher` | No | No in B0-A | No | Existing permissions unchanged |
| Carrier `operations_manager` | No | No in B0-A | No | Existing permissions unchanged |
| Carrier `admin` | No driver impersonation | Yes, same tenant only | Yes, same tenant only | Existing permissions unchanged |
| Platform `admin` | No | No | No | Existing platform permissions unchanged |
| Another carrier tenant | No | No | No | No cross-tenant access |

The approval check is repeated in the service layer and requires both `role == admin` and `account_scope == carrier`. A platform administrator is not accepted even if its role string is `admin`. Cross-tenant task/order references return an explicit 403.

## Server-derived ownership and vehicle

- `tenant_id`, `driver_id`, and actor user ID come from the authenticated principal.
- `vehicle_id` comes from an active, published assignment covering the business date. A client-supplied vehicle ID is retained only inside the immutable source snapshot as an audit fact and is never trusted.
- If no published shift vehicle exists, creation returns `active_shift_vehicle_not_found`.
- If the day contains multiple vehicles, the driver must provide a source assignment that is validated against the same driver, tenant and date; otherwise creation returns `active_shift_vehicle_ambiguous`.

## Existing integration points, deliberately not invoked in B0-A

| Existing chain | B0-A behavior |
|---|---|
| Phase 2A actual nodes | Preserved unchanged; provisional facts are not copied into route nodes yet |
| Run documents / PDFs | No call and no version generated |
| Driver notifications | No call; the generated historical assignment remains unpublished |
| Pricing and driver settlement | Both price fields remain `NULL`; no finance row is created |
| Revenue and completed-count reporting | Only the one approved formal order can become the counting source; provisional rows themselves are not orders |
| Existing-order linkage | Requires a same-tenant formal order and an active assignment already matching the original driver and server-derived vehicle |

## B0-A implementation fingerprints

| File | SHA-256 |
|---|---|
| `backend/api/routes.py` | `60c871e8a62c94dfe79d5f7d3de54728a1608a64d7e7dba9e51436fe1c7304f1` |
| `backend/db/migrations/20261015_driver_provisional_tasks_phase2b0a.sql` | `af2a809649b21f03cdb46cea3ca301ccc786391fd1c58ef520e1c3fe753045ce` |
| `backend/services/driver_provisional_service.py` | `ff902d8bdfd3b62612e96b2a5b077941c4089a0bd5591d638e4bf3ea5d3b9a01` |
| `tests/test_driver_phase2b0_provisional_http.py` | `5862a83719a5684d2a078abf0fc553e903d24b4edf2ff153a1d896285ed18aba` |
| `tests/test_driver_phase2b0_migration.py` | `e1f2b54b86e5b690242c38cef689b11e62f4935f50877b38f2ba37084309857d` |

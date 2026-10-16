# Driver Phase 2B-0 next gates

## B0-A completion boundary

B0-A is locally complete: baseline audit, additive model, immutable source/history, driver ownership, same-tenant carrier-admin review core, idempotency, optimistic locking, atomic conversion/link/reject, migration rehearsal, local HTTP evidence and Phase 1/2A regression are present.

The implementation intentionally stops here. It is not a complete customer-facing emergency-order feature.

## Not implemented and requiring separate authorization

### B0-B: driver and management UI

- Driver six-item entry panels and staged mobile workflow.
- Carrier-admin Web queue, detail/history and review controls.
- Carrier-admin miniapp home card and review page.
- Any bottom-navigation change.

### B0-C: pricing and settlement

- Admin price confirmation and revisions.
- Driver income/settlement attribution.
- Company revenue and completed-count aggregation using the unique formal order.
- Existing-price and unknown-price UI semantics.

### B0-D: operational change types

- Cancellation, flight delay, time/location adjustment, reassignment and no-show workflows.
- Operations-manager after-the-fact amendments to submitted daily reports.
- Running-plan incremental task insertion and stable route-node linkage.

### B0-E: document and reporting revisions

- Traceable revisions of `運行指示書`, `運送引受書`, and `乗務記録表`.
- Historical PDF retention and post-event correction labels.
- Formal daily-report PDF, download, print and device validation.

## Gates before any Trial release

1. Reconcile this migration against the actual Trial migration registry and schema using a read-only check.
2. Build a complete artifact that includes the Phase 1, Phase 2A and B0-A dependencies; do not deploy isolated route/service files.
3. Rehearse on a consistent copy of the Trial database and verify all existing migration effects.
4. Decide whether unpublished historical assignments created by approve-create should remain hidden until document/operations review, or transition through a later explicit publish step. B0-A deliberately leaves them unpublished and sends no notification.
5. Complete B0-B/B0-C product acceptance before enabling the endpoints for users.
6. Obtain explicit Trial deployment authorization; Production remains a separate gate.

## Current operational status

- Trial deployment/restart: not performed.
- Production access: not performed.
- Git commit/push: not performed.
- WeChat upload/release: not performed.
- Real PDF/document generation: not performed.
- Real notification/driver publication: not performed.
- Real finance posting: not performed.
- Existing local drafts and unrelated dirty files: preserved.

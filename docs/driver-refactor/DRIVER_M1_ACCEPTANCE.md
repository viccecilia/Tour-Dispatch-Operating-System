# Driver M1 stage acceptance

Date: 2026-10-15 (Asia/Tokyo)

Classification: IMPLEMENT -> LOCAL VERIFY

Status: M1 Gate-AUTO PASS; paused at M1 Gate-HUMAN. M2 has not started.

## Delivered closure

1. Driver miniapp can create, partially save, submit and later read a temporary task with original TMP number and append-only history. Offline state is not reported as success.
2. Existing formal-task cards contain the required fixed six-field editor backed by the Phase 2A actual-node chain. Actual nulls remain blank, both odometers are distinct and stale revisions return 409.
3. Same-tenant carrier admin has one shared approval model in Web and miniapp: queue, detail/history, create/link/reject/needs-information.
4. Pricing and driver settlement update the unique formal order. Unknown amounts remain null; aggregates count unique order IDs and do not claim cash receipt.
5. Server-side role, tenant, driver, idempotency, concurrency and rollback checks are retained.

## Local evidence

- Web pending review: `artifacts/driver-m1/web-admin-pending-review.png`
- Web needs-information history: `artifacts/driver-m1/web-admin-needs-info-history.png`
- Web approved order, pricing and aggregate: `artifacts/driver-m1/web-admin-approved-pricing.png`
- Isolated database: `artifacts/driver-m1/m1-ui-acceptance.sqlite3`
- HTTP/migration artifacts: `artifacts/driver-m1/http-tests/`

Screenshot SHA-256:

- approved/pricing: `4D33B051277CF551731B6EA6AFAA63FE81826A87DFB148E9F936F807CCD4A28F`
- pending/review: `EB7A746709A67919DA502481A4EA211457ECFC64216F0AAE46468C5348404CF2`
- needs-information/history: `72F3ABA76460ED9E6FF54A2AD4AC23EC4A860EF9F715FB8DAEC7EC2C6C6B5AF9`

## Gate results

- Targeted M0/M1/role/migration/HTTP: 25/25 PASS.
- Full discovery: 210 total, 207 PASS, 3 unchanged known fixture errors; newly introduced failures: 0.
- Web TypeScript/Vite build: PASS.
- Miniapp project-local checker: PASS, exactly 17 JS and 15 WXML files checked.
- Isolated SQLite integrity: `ok`; migration applied once; one provisional-origin formal order; no duplicate formal order or aggregate.

## Permission and accounting assertions verified

- Approval and pricing: same-tenant `admin + carrier` only.
- Denied: operations manager, dispatcher, platform admin, another tenant and another driver.
- Driver identity/profile and tenant are token-derived, not client-selected.
- Temporary tasks do not enter formal company/driver totals until linked or converted to one formal order.
- Linking an existing order does not create a second income row.
- Price and salary can remain unknown; unknown is not printed or counted as zero.
- Post-settlement amount edits retain an append-only difference record.

## Human acceptance still required

The actual localhost Web admin flow was clicked and captured. The following miniapp interactions remain unexecuted and must not be described as passed:

1. Driver creates/saves/submits a temporary task and reopens its history.
2. Driver expands a real formal task, fills the six actual fields, saves and reloads.
3. Carrier admin opens the same TMP from the App, reviews/prices it, then verifies Web/App refresh consistency.
4. Device keyboard, scrolling and weak-network/offline presentation.

Reason: WeChat DevTools restored an old default Trial login session while its automation service port was disabled. The old session was not used for M1 writes or evidence; its screenshot was removed. A locally forced API session should be established manually before those clicks.

## Risks and boundaries

- The repository remains a dirty detached worktree with pre-existing Phase 1/2A/B0-A and unrelated changes. No reset/clean/stash was used.
- `npm ci` reported existing dependency advisories; no out-of-scope automatic dependency rewrite was run.
- The Vite build emits a main-chunk size warning but succeeds.
- The three `test_daily_import_dates` errors are the unchanged baseline fixture issue (`locations` table not initialized), not an M1 regression.

## Next gate

Stop here. Start M2 only after the user explicitly replies: `验收通过，继续M2`.

No Trial write/deployment or restart, no Production access, no Git commit/push, no WeChat upload, no PDF publish and no real notification occurred in M1. WeChat DevTools did auto-restore an old default Trial session and may have emitted ordinary read-only page-load requests before it was stopped; those reads were discarded from acceptance evidence.

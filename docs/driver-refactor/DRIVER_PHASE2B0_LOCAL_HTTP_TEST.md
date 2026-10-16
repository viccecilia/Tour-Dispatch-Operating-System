# Driver Phase 2B-0A local HTTP acceptance

## Environment

- Local `ThreadingHTTPServer` using the real `ApiHandler`.
- Fresh isolated SQLite database per test.
- Two carrier tenants, three drivers, two same-tenant carrier admins, a second-tenant admin, carrier operations manager, carrier dispatcher and platform admin.
- Business date `2026-10-14`; review occurs later according to real database review time. The service date remains `2026-10-14`.
- No Trial/Production endpoint or database was used.

## Test command and result

The combined B0-A plus Phase 1/2A regression run executed 19 tests and passed all 19:

```text
python -m unittest \
  tests.test_driver_phase2b0_provisional_http \
  tests.test_driver_phase2b0_migration \
  tests.test_driver_route_actual_http \
  tests.test_driver_phase2a_migration \
  tests.test_driver_home_phase1_contract \
  tests.test_driver_api_role_isolation -v

Ran 19 tests in 19.297s
OK
```

The logged Phase 2A fault-injection stack trace is expected by that existing test; the test passed after proving rollback.

A separate full discovery run executed 204 tests: 201 passed and 3 existing
`test_daily_import_dates` cases errored because that test module does not initialize the
`locations` table before the parser queries it. Re-running that module alone reproduced
the same three `sqlite3.OperationalError: no such table: locations` errors. B0-A does not
change that test, `parser_service.py`, or `location_service.py`; this is recorded as an
existing fixture gap and is not reported as a green full-suite run.

## B0-A outcomes

| Scenario | Evidence |
|---|---|
| Driver partial create, server-derived vehicle, immutable original snapshot | 201; client vehicle ignored for authority and retained only in snapshot |
| Same request replay | 201/200 with `idempotent_replay=true` |
| Reused request ID with changed payload | 409 `client_request_id_payload_conflict` |
| Partial completion and stale save | 200 then 409 `provisional_revision_conflict` |
| Own read and event history | 200, initial plus edit events |
| Another driver | 403 `provisional_task_not_owned_by_driver` |
| Another tenant driver/admin | 403 cross-tenant errors |
| Operations manager, dispatcher, platform admin approval access | 403 `carrier_admin_required` |
| Same-tenant carrier admin approve-create | 200, one formal order and one unpublished assignment |
| Driver direct formal-order create | 403 |
| Price/PDF/notification/finance side effects | price remains `NULL`; all relevant counts unchanged |
| Premature price submission during B0-A | 400 `provisional_pricing_not_available_in_phase2b0a`; pending task unchanged |
| Approve-link existing | 200; no new formal order and existing source fields unchanged |
| Reject | 200; record and reason retained, no formal order |
| Two-admin concurrent approve-create | exactly one 200 and one 409; exactly one sourced formal order |
| Injected failure after formal insert but before event | task remained pending and formal-order count remained zero |
| Task/event delete or event update | database trigger rejected |

## Evidence files

- Main flow JSON: `artifacts/driver-refactor/phase2b0a/phase2b0a-http-test_driver_partial_save_idempotency_isolation_and_carrier_admin_approval.json`
- Main flow DB SHA-256: `6c8bce89423a3467cfb82be4e9ce7e33526010b5757eba9c0f2297211f86ad35`
- Link/reject/rollback JSON: `artifacts/driver-refactor/phase2b0a/phase2b0a-http-test_link_existing_reject_history_and_atomic_fault_rollback.json`
- Link/reject/rollback DB SHA-256: `538923971171864f6476619265a87b64f5a9fd636b68440693faca1afcbe1dfd`
- Concurrency JSON: `artifacts/driver-refactor/phase2b0a/phase2b0a-http-test_two_admin_concurrency_creates_exactly_one_formal_order.json`
- Concurrency DB SHA-256: `7f37db6c2fc3dfcbf257fbef280d2fba660932de34425e6bb40bff1b464ab14e`

All three evidence databases report `PRAGMA integrity_check=ok` and one B0-A migration registration. Enabling foreign keys on the main evidence database and checking both new tables returned no violations. Sanitized HTTP transcripts contain no passwords, tokens or session data.

## Regression boundary

- Phase 1 five-tab navigation, existing task routing and existing driver endpoints passed contract tests.
- Phase 2A real actual-node HTTP, idempotency, stable-node revisions, cross-tenant/driver isolation, cross-midnight and odometer rules passed.
- Existing driver API role-isolation tests passed.
- No miniapp files were changed in B0-A. WeChat Developer Tools and real-device interaction were not executed because UI work is explicitly outside B0-A.

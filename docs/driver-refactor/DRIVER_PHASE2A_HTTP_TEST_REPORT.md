# Driver Phase 2A HTTP Test Report

## Environment

- Server: real local `ThreadingHTTPServer` using production `ApiHandler`.
- Database: isolated SQLite created through the project `init_db` and real migration mechanism.
- Preserved acceptance DB: `artifacts/driver-refactor/phase2a/phase2a-http-acceptance.sqlite3`.
- DB SHA-256: `72f503ca11a1f7a43890af538dae15695a01120e56411112bc572b613af28411`.
- Integrity: `ok`.
- Fixture: 2 tenants, 2 drivers per tenant, 6 published documents, 74 route nodes.
- No mock HTTP response or alternate service was used. Fault injection mocked only the ledger insert seam to prove transaction rollback.

## Real HTTP cases

| Case | Result |
|---|---|
| 6 orders, 14 nodes including garage boundaries | Pass |
| 10 orders, 22 nodes | Pass |
| 11 orders, 24 nodes | Pass |
| Multi-day charter returns nodes for both dates | Pass |
| Cross-midnight arrival/departure | Pass |
| Actual location partial save and reread | Pass |
| Later time/mileage partial save preserves prior location | Pass |
| Same request ID and payload returns replay without new revision | Pass |
| Same request ID with changed payload | HTTP 409 pass |
| Stale `expected_revision` | HTTP 409 with current state pass |
| Stale published plan version/source | HTTP 409 pass |
| Stable node carries actual into version 2 | Pass |
| Version 2 new node starts with null actual | Pass |
| Cancelled assignment/deleted order blocked; prior actual retained | Pass |
| Invalid datetime, negative mileage, mileage regression | Rejected pass |
| Forged assignment/order | HTTP 403 pass |
| Forged query driver ID | Ignored; authenticated driver only pass |
| Other driver, other tenant | No data/write access pass |
| Admin on driver route | HTTP 403 pass |
| Failure between actual upsert and ledger insert | HTTP 500 and both rows rolled back pass |

Command result: `tests.test_driver_route_actual_http` — 6 test methods, all passed. `tests.test_driver_phase2a_migration` — 1 test, passed. Combined Phase2A/role/Phase1/document-model gate — 35 tests, passed.

## Old-function regression

- Full discovery: 200 tests executed; 197 passed.
- Three pre-existing `tests.test_daily_import_dates` cases failed because that test file opens an uninitialized SQLite path with no `locations` table. Phase 2A does not touch parser/location code.
- The same three cases were immediately rerun against a fresh isolated project DB created by `database.init_db(seed=True)` and all 3 passed.
- Run-document, role isolation, account, Phase 1 contract, document-model and driver daily-report targeted suites passed.
- Miniapp checker: `ok: 16 js, 14 wxml`; `node --check` for driver home passed; broken closing-tag search found no match.

## Explicitly not executed

- WeChat Developer Tools interaction and real-device input: not executed because Phase 2A has no UI implementation.
- Trial and Production HTTP: not accessed.
- Real business notification/document publication: not executed.

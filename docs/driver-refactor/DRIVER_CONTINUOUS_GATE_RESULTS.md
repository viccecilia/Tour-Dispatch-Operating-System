# Driver continuous gate results

## M0 Gate-AUTO

Status: PASS

### Source and identity

- Actual worktree and HEAD match the continuous task handoff.
- Phase 1 home and Phase 2A/B0-A service/migration/test SHA-256 values match the five attached B0-A reports.
- Existing dirty files and unrelated untracked work remain present.

### Tests

```text
python -m unittest tests.test_driver_phase2b0_provisional_http tests.test_driver_phase2b0_migration tests.test_driver_route_actual_http tests.test_driver_phase2a_migration tests.test_driver_home_phase1_contract tests.test_driver_api_role_isolation -v
Ran 19 tests in 24.139s
OK
```

```text
python -m unittest discover -s tests -v
Ran 204 tests in 191.785s
201 passed; 3 KNOWN_BASELINE errors in test_daily_import_dates (missing locations fixture table)
```

### Permission boundary found in real code

- Driver identity and `profile_id` are server-derived.
- Provisional approval requires same-tenant `role=admin` and `account_scope=carrier` in the service layer.
- Operations manager, dispatcher, platform admin, another tenant and another driver have explicit negative HTTP coverage.

### Database boundary

- Phase 2A and B0-A migrations are additive and already have isolated rehearsal tests.
- M0 did not open Trial or Production databases and did not write a real business database.

## M1 Gate-AUTO

Status: PASS; paused at Gate-HUMAN. M2 not started.

### M1.1 driver provisional task UI and own history

- Native miniapp page supports create, partial draft save, submit, detail, original TMP number and append-only audit history.
- Submitted tasks remain readable but cannot be silently rewritten. Only `draft` and `needs_information` can be edited/resubmitted.
- Offline writes remain visibly unsynced; they are not presented as server success.
- Server identity fixes the driver/profile and tenant. Cross-driver and cross-tenant reads/writes are denied.

### M1.2 six actual fields

- Existing driver task cards expose a fixed 2x3 layout: arrival place/departure time, arrival time/drop-off place, arrival odometer/drop-off odometer.
- Planned values are placeholders only; unknown actuals remain null.
- The editor reuses the Phase 2A stable route-node API, including partial save, same-request retry, stale revision 409 reload, cross-midnight values and cancelled/deleted node protection.
- Additive migration `20261015_m1_driver_provisional_dual_odometers.sql` adds only `pickup_odometer_km` and `dropoff_odometer_km`; apply/repeat/integrity/restore rehearsal passed.

### M1.3 carrier-admin review

- Web provides same-tenant queue, detail, original facts, event history, approve-create, link-existing, reject and needs-information operations.
- Miniapp carrier-admin home exposes pending count and the same review page/API.
- Service layer requires `role=admin`, `account_scope=carrier`, matching tenant and server-derived identity. Operations manager, dispatcher, platform admin, another tenant and another driver negative cases pass.
- Two-admin concurrency produces exactly one formal order; request replay is idempotent and conflicting payload/revision returns 409.

### M1.4 pricing and finance

- Carrier admin pricing updates the linked formal `orders` row (`price/price_jpy`, `driver_salary_jpy`, `driver_settlement_amount`, settlement status); no second order or ledger is created.
- Unknown amounts remain null and are counted separately; they are never filled with zero.
- Company order count, known business amount and driver amounts use the unique formal `order_id`; linking an existing order cannot add a second revenue row.
- Price changes are append-only events. A change after settlement carries an explicit settlement delta; request replay cannot count it twice.
- The UI explicitly says the aggregate is not cash-receipt confirmation.

### Automated results

```text
python -m unittest tests.test_driver_phase2b0_provisional_http tests.test_driver_phase2b0_migration tests.test_driver_route_actual_http tests.test_driver_phase2a_migration tests.test_driver_home_phase1_contract tests.test_driver_api_role_isolation tests.test_driver_m1_dual_odometer_migration tests.test_driver_m1_ui_contract -v
Ran 25 tests in 24.782s
OK
```

```text
python -m unittest discover -s tests -v
Ran 210 tests in 209.656s
207 PASS; 3 unchanged KNOWN_BASELINE errors in test_daily_import_dates (fixture lacks locations)
```

```text
npm.cmd run build
PASS: 1661 modules; dist/assets/index-ilsA-Dlb.js
Warning only: main chunk exceeds 500 kB
```

```text
node miniapp_yuzu\package_dispatch\scripts\check-dispatch-miniapp.js
[dispatch-miniapp-check] ok: 17 js, 15 wxml
```

### Isolated database fingerprint

- File: `artifacts/driver-m1/m1-ui-acceptance.sqlite3`
- SHA-256: `BDF18475E6268018BAC65A9DA149839676BDE532FCA427975B25575D07AC2163`
- `PRAGMA integrity_check`: `ok`
- M1 migration registration: exactly 1
- Tasks: 2 (`approved_new_order=1`, `needs_information=1`)
- Events: 7; orders: 2; assignments: 2
- Provisional-origin formal order: exactly 1, with 19,500 company amount and 7,500 driver salary/settlement in the isolated sample.

### Real UI evidence and remaining human checks

- PASS: actual browser login to the localhost-only API, pending review selection, needs-information action, state refresh, approval history, pricing and aggregate display.
- Screenshots: `web-admin-pending-review.png`, `web-admin-needs-info-history.png`, `web-admin-approved-pricing.png` under `artifacts/driver-m1/`.
- NOT EXECUTED: actual driver-miniapp create/save/submit and six-field clicks; actual carrier-admin miniapp review/pricing and cross-device refresh. WeChat DevTools restored an old default Trial session and its automation service port is disabled, so that session was not used as local evidence.
- The discarded DevTools screenshot was removed because it contained the restored session and did not prove local isolation.

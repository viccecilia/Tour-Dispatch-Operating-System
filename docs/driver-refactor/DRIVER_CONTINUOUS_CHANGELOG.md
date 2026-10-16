# Driver continuous changelog

## M0

- Added continuous execution, gate, change and rollback records only.
- No production code, database schema, Trial/Production state, Git history or WeChat release state changed during M0.

## M1

### M1.1

- Added native miniapp provisional-task page and driver home entry.
- Reused Phase 2B-0A task/event tables and APIs; no parallel order system.
- Added needs-information resubmission while preserving the original snapshot and event chain.

### M1.2

- Added two explicit temporary-task odometer columns through one additive migration.
- Added the fixed six-field inline editor to the existing task card and reused Phase 2A stable-node APIs.
- Added offline unsynced state, replay request-ID retention and 409 refresh behavior.

### M1.3

- Added carrier-admin-only Web page, navigation permission and API client contracts.
- Added carrier-admin miniapp pending-count card and shared review screen.
- Added needs-information review and retained approve-create/link/reject behavior.

### M1.4

- Added carrier-admin pricing endpoint and UI against the linked formal order.
- Added unique-formal-order company/driver aggregate endpoint, null amount counters and settled-delta history.
- Kept operations manager, dispatcher and platform admin outside approval/pricing permissions.

### Main M1 files

- `backend/api/routes.py`
- `backend/services/driver_provisional_service.py`
- `backend/db/migrations/20261015_m1_driver_provisional_dual_odometers.sql`
- `frontend/src/pages/ProvisionalTasksPage.tsx` and existing shell/API/type files
- `miniapp_yuzu/package_dispatch/pages/provisional/*`
- existing miniapp home/task/API files
- `tests/test_driver_m1_dual_odometer_migration.py`
- `tests/test_driver_m1_ui_contract.py`
- extended Phase 2B-0A HTTP tests
- `scripts/driver_m1_local_demo.py`

### Compatibility

- Existing five-tab driver navigation and old task/expense/document APIs remain.
- Existing Phase 1 home, Phase 2A actual rows and Phase 2B-0A originals/events are not replaced.
- No Trial/Production state, Git history, WeChat upload, PDF or notification path was changed.

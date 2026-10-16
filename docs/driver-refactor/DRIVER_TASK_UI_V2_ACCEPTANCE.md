# Driver Task Page UI V2 acceptance

Date: 2026-10-16 (Asia/Tokyo)

## Scope and workspace protection

- Workspace: `C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
- HEAD: `176d549c0baa9feb8e671efa05cdacb994108cf1`
- Checkout: detached and dirty before this task. Existing Phase 1, Phase 2A, Phase 2B-0A and M1 changes were kept in place; no reset, clean, stash, commit or push was used.
- No database schema, migration, backend authorization, finance, document renderer or approval logic was changed for UI V2.
- Trial and Production were not accessed. No service was deployed or restarted. No miniapp was uploaded and no notification or business document was published.

Files changed specifically for UI V2:

- `miniapp_yuzu/package_dispatch/pages/task/index.js`
- `miniapp_yuzu/package_dispatch/pages/task/index.wxml`
- `miniapp_yuzu/package_dispatch/pages/task/index.wxss`
- `miniapp_yuzu/package_dispatch/utils/api.js` (existing API wrappers only)
- `miniapp_yuzu/package_dispatch/pages/home/index.js` (one-shot report/task focus routing only)
- `tests/test_driver_task_ui_v2_contract.py`
- `scripts/driver_task_ui_v2_local_demo.py`

The Git diff of the five tracked miniapp files also contains pre-existing M1 work because the checkout was already dirty. It must not be interpreted as a UI-V2-only patch or rolled back wholesale.

## UI-0 through UI-5 result

### UI-0 audit

- The task page already contained the M1/Phase 2A save chain: `GET /api/driver/day-workbench?date=...` and `POST /api/driver/route-node-actual` with stable `assignment_id`, `order_id`, `run_group_id`, `route_node_id`, `client_request_id` and `expected_revision`.
- Existing point-call, evidence upload, daily-report and published run-document links were retained rather than replaced.
- Existing five driver tabs remain: Home, Task, Map, Expense and Profile.

### UI-1 page order

The real task page now renders in this order:

1. selected-business-date Hero;
2. week/month calendar;
3. outbound point call;
4. selected-date tasks;
5. inbound point call;
6. daily-report preparation/completion status;
7. existing five-tab navigation.

The Hero uses the selected date, driver/vehicle, completed task count, point-call times and daily-report status. The old duplicate middle report form/statistics block is not rendered.

### UI-2 point calls and evidence

- Successful outbound/inbound calls collapse automatically and expose the saved record for viewing.
- The original outbound sleep, inspection, lights/brakes/body/documents/alcohol checks and alcohol evidence remain.
- The original inbound cleaning, vehicle inspection, alcohol and roll-call requirements remain.
- The paper driver-report photo field and the `daily_report` attachment prerequisite were removed. The inbound alcohol image is still required.
- A missing assignment for the selected date cannot be used to submit a point call; the UI reports that no associated task exists.

### UI-3 selected-date tasks and six actual fields

- Formal tasks come from the selected-date Phase 2A workbench and are sorted by planned start time.
- A task expands in place; the fixed two-column by three-row grid remains exactly: arrival place, departure time, arrival time, drop-off place, arrival odometer and drop-off odometer.
- Drafts are isolated by business date and assignment. Incremental save, idempotency request ID, optimistic revision, 409 refresh prompt and unsynced/error state remain.
- The local HTTP fixture returned 0, 3 and 10 formal tasks without creating parallel data models:
  - `2026-10-12`: 0 tasks, 0 documents, 0 nodes;
  - `2026-10-13`: 3 tasks, 1 document, 8 nodes;
  - `2026-10-17`: 10 tasks, 1 document, 22 nodes.

### UI-4 daily report and completion truth

- Both the Home report shortcut and the task-page bottom CTA route to the same existing daily-report API and task-page report area.
- Returned plus draft report displays `已入库・日报待提交` and `整理・提出司机日报`.
- Returned plus submitted report displays `今日已完成`, the real submitted timestamp and a record view action.
- Returning to the yard does not submit the report.
- No fake PDF action exists. The page explicitly states that the formal driver daily-report PDF has not been implemented. Existing published dispatch documents remain labeled separately.

### UI-5 local acceptance

Local isolated API:

- address used during acceptance: `http://127.0.0.1:18765` / `18766`;
- database: under `artifacts/driver-task-ui-v2/` only;
- fixture driver: `UI V2 验收司机`;
- Developer Tools project: `miniapp_yuzu`, AppID `wx9636a2182beaa078`.

Four server-truth states were opened in WeChat Developer Tools by selecting dates in the same calendar:

| Date | Workflow facts | Report | UI state |
| --- | --- | --- | --- |
| 2026-10-13 | no workflow event | draft/default | 未出库 |
| 2026-10-14 | `depart_yard`, `alcohol_test_out` | draft/default | 运行中 |
| 2026-10-15 | outbound + inbound/alcohol events | draft | 已入库・日报待提交 |
| 2026-10-16 | outbound + inbound/alcohol events | submitted | 今日已完成 |

The screenshot fixture was local-only and was stopped after capture; ports 18765/18766 were not left listening. Temporary source-level localhost forcing was removed. The Developer Tools storage keeps a reversible local-test flag so hot reload does not fall through to Trial.

## Screenshots

- `artifacts/driver-task-ui-v2/04-not-departed-2026-10-13.png` — not departed.
- `artifacts/driver-task-ui-v2/03-running-2026-10-14.png` — running.
- `artifacts/driver-task-ui-v2/02-returned-report-pending-2026-10-15.png` — returned, report pending.
- `artifacts/driver-task-ui-v2/01-completed-2026-10-16.png` — completed.
- `artifacts/driver-task-ui-v2/05-running-inline-six-fields-2026-10-14.png` — expanded in-place six-field editor and fixed bottom tabs.

The completed screenshot shows compact week mode. The other state screenshots show month mode and selected-date task markers. All are captures from the actual WeChat Developer Tools simulator connected to the isolated API, not HTML mockups.

## Checks and regression

Passed:

- `node --check` for task page, Home page and dispatch API wrapper.
- Python syntax check for the local fixture.
- `node miniapp_yuzu/package_dispatch/scripts/check-dispatch-miniapp.js`: `ok: 17 js, 15 wxml`.
- Targeted unit/API suite: 29 tests passed. This includes role isolation, Phase 2A schema/service behavior, route-actual HTTP idempotency/409/rollback, Phase 2B-0 provisional protection, M1 UI contract and UI V2 contract.
- `git diff --check` reported no whitespace error (only the existing Windows LF-to-CRLF advisory for task WXML).
- Actual local HTTP reads confirmed 0/3/10 task counts and the four workflow/report state combinations above.
- Actual Developer Tools clicking confirmed calendar switching, selected-date state recovery, point-call collapse, task ordering, in-place expansion, six fields and unchanged five tabs.

Full repository suite:

- `python -m unittest discover -s tests -p "test_*.py"`
- Result: 216 tests, 213 passed and 3 errors.
- The three errors are the known unrelated `tests/test_daily_import_dates.py` fixture problem: its isolated database has no `locations` table. UI V2 did not change the parser/location service or its fixture.
- The logged `fault injection` traceback is an intentional transaction-rollback test and the corresponding test passes.

## Not executed / remaining manual acceptance

- Physical iPhone/Android test was not executed; screenshots are from the Developer Tools iPhone simulator.
- Keyboard behavior on a physical device, Android safe-area differences and real weak-network radio behavior remain device checks.
- No formal daily-report PDF exists in this phase; no generation/download/print claim is made.
- No Trial login/session or real business record was used.

## Current file hashes

- task JS: `49ffff2869cff9f228d74accc47ed6fd241e7e18b04447f7965f90962c1854f0`
- task WXML: `a7fd0e5e5ae1afeb83d439f472f0e0e8f5e675c8ba21a5c28ab57e1093525b82`
- task WXSS: `c723c1d683cd94c357e87058b6e3d0ecd743703f04dcd1f06aebc6e99906dfac`
- dispatch API wrapper: `f4115842afa4f1b8ce1b3cd23b6461ace8bf5f9f1c7a527a162c1185e4867f2a`
- Home JS: `a2fa3ea9bf9aaa156ed6e046efaced37af9f4b80912d83ef4cd37ce8f99ec41b`

## Rollback plan

Do not use `git checkout`, reset or clean because those commands would discard pre-existing Phase/M1 work. A UI-V2 rollback must be hunk-scoped:

1. remove the task-page Hero/calendar/ordered section and selected-date state adapter while retaining the earlier M1 six-field editor;
2. remove only `driverWorkflowEvents(date)` and `driverDayWorkbench(date)` wrappers if no longer referenced, leaving all pre-existing provisional-task wrappers intact;
3. remove the Home one-shot task/report focus keys while leaving the Phase 1 Home unchanged;
4. remove the UI-V2 contract and local fixture script;
5. rerun the 29-test targeted command and miniapp checker.

The isolated SQLite files and screenshots under `artifacts/driver-task-ui-v2/` are evidence only and are not runtime data. They may be archived separately, but were not deleted during this task.

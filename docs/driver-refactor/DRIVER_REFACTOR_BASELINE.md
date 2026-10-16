# Driver Refactor Baseline

## Audit identity

- Working tree: `C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
- Source HEAD: `176d549c0baa9feb8e671efa05cdacb994108cf1`
- Scope: Phase 0 audit and Phase 1 driver-home shell only.
- Existing unrelated changes at audit start are preserved: `backend/services/dispatcher_mobile_service.py`, `backend/services/wechat_auth_service.py`, `tests/test_auth_accounts.py`, and untracked `runtime/deploy/`.

## Existing miniapp structure that must remain

The dispatcher package uses the existing five-tab driver navigation from `miniapp_yuzu/package_dispatch/utils/port-nav.js`:

1. Home: `/package_dispatch/pages/home/index`
2. Task: `/package_dispatch/pages/task/index`
3. Map: `/package_dispatch/pages/map/index`
4. Expense: `/package_dispatch/pages/expense/index`
5. Profile: `/package_dispatch/pages/profile/index`

Phase 1 does not change this list, its order, or `custom-tab-bar`.

The existing task page remains the write-capable workflow surface. It already contains:

- outbound roll-call / yard departure and evidence upload;
- calendar and assignment list;
- assignment confirmation and task execution status;
- published run-document download;
- inbound roll-call / yard return and evidence upload;
- daily-report draft and submit actions.

The existing expense page continues to use the driver expense API and `driver_expense_reports`. Map and profile remain their existing pages. The new home must link to these surfaces instead of duplicating their forms.

## Existing home inputs

The driver branch of `pages/home/index.js` already reads the following services:

- `GET /api/driver/assignments`
- `GET /api/driver/workbench`
- `GET /api/driver/profile`
- `GET /api/driver/notifications?limit=30`

Phase 1 may additionally read the already-existing daily-report and run-document endpoints for summary/shortcut state. No new business endpoint or database table is required.

## Existing status chain

Assignments use `assignments.execution_status` and the existing driver service transition chain. The current visible states include `assigned`, `confirmed`, `departed`, `arrived`, `in_service`, `completed`, and `returned`. Driver reports and workflow events are written by the task page through the existing service; the home must only summarize and deep-link.

Notification receipt is read state only. Marking a driver notification read does not approve a plan or mutate an assignment.

## Phase 1 change boundary

Allowed home-shell changes:

- driver/date/vehicle/current-state summary;
- today's counts and assignment list;
- unread change reminders using existing driver notifications;
- read-only outbound, inbound, run-document, and daily-report summaries;
- shortcuts to the existing task page;
- local feature-flag fallback to the legacy driver home.

Not allowed in Phase 1:

- schema or migration execution;
- new task/report/expense/document persistence;
- bottom-navigation changes;
- removal of the legacy home, task, map, expense, or profile flows;
- Trial or Production activation.

## Reuse and deletion contract

- Reuse the current session, API client, driver services, tables, and tenant context.
- Reuse the old task page for all operational writes.
- Reuse the old notification read endpoint for receipt acknowledgement.
- Keep the old driver-home layout in WXML as the feature-flag fallback.
- Delete no old API, page, handler, table, migration, or navigation item in this phase.

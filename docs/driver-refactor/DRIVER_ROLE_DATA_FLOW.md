# Driver Role Data Flow

## Authentication and scope

1. The miniapp sends the bearer token through `miniapp_yuzu/package_dispatch/utils/api.js`.
2. `backend/api/routes.py` requires an authenticated API user for every `/api/driver/*` request.
3. The same route prefix is restricted to `role=driver`.
4. For GET requests, `driver_id()` returns the authenticated user's `profile_id` when the role is driver and ignores query/header attempts to select another driver.
5. For POST requests, the route overwrites `payload.driver_id` with the authenticated driver's `profile_id` before dispatching to a service.
6. `require_api_user()` sets the tenant context from the authenticated user's `tenant_id`.

This gives the effective driver scope:

`bearer token -> role=driver -> tenant_id -> profile_id -> own records only`

## Assignment visibility

`GET /api/driver/assignments` calls `list_driver_assignments(profile_id)`. Its SQL requires all of:

- `assignments.status = 'active'`;
- `assignments.published_at IS NOT NULL`;
- assignment tenant equals current tenant;
- order tenant equals current tenant;
- assignment driver equals authenticated `profile_id`;
- order is not deleted.

The same scoped lookup is reused before a driver report can change an assignment. A driver cannot write a report for another driver's assignment merely by changing request JSON.

## Home read flow

```text
driver session
  -> /api/driver/profile --------> drivers
  -> /api/driver/assignments ----> assignments + orders + vehicles
  -> /api/driver/workbench ------> assignments + driver_workflow_events
                                  + driver_expense_reports
  -> /api/driver/notifications --> notifications (target driver/profile)
  -> /api/driver/daily-report ---> driver_daily_reports + assignment snapshot
  -> /api/driver/run-documents --> driver_run_documents (published/visible files)
```

The Phase 1 home converts these responses into read-only cards. It does not persist a second copy.

## Existing task write flow

```text
task page
  -> POST /api/driver/report
       -> validate own published assignment
       -> driver_reports
       -> assignments.execution_status
       -> notifications/audit
  -> POST /api/driver/workflow-event
       -> driver_workflow_events (+ existing attachments)
  -> POST /api/driver/location
       -> location_logs
  -> POST /api/driver/daily-report
       -> driver_daily_reports
  -> POST /api/driver/evidence
       -> driver_evidence_uploads
```

Expense remains separate and existing:

```text
expense page -> POST /api/driver/expense -> driver_expense_reports
```

## Role isolation matrix

| Surface/API family | Driver | Dispatcher | Operations manager | Admin |
|---|---:|---:|---:|---:|
| `/api/driver/*` route prefix | own driver identity only | denied | denied | denied |
| Driver assignment/report writes | own published assignment only | denied through driver prefix | denied through driver prefix | denied through driver prefix |
| Dispatch assignment/change | denied | allowed | selected read/update routes only | allowed |
| Fleet/global location | own driver location path only | allowed | allowed | allowed |
| Finance administration | denied | denied or limited by route | denied or limited by route | allowed |
| Driver notification receipt | own notifications only | denied through driver prefix | denied through driver prefix | denied through driver prefix |

The role matrix is route-enforced, not only hidden in WXML.

## Phase 1 interaction rule

- Home cards are projections of existing records.
- “已读/已收” calls the existing notification read endpoint and means receipt only.
- Operational actions navigate to the existing task page.
- Expense actions navigate to the existing expense page.
- No home action creates an alternate order, report, notification, expense, or document record.

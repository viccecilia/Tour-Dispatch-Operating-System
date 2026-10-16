# Existing Driver API and Table Map

## Read endpoints reused by Phase 1

| Method and path | Service | Main existing sources | Driver scope |
|---|---|---|---|
| `GET /api/driver/assignments` | `list_driver_assignments` | `assignments`, `orders`, `vehicles`, `drivers` | tenant + own profile + active + published + not deleted |
| `GET /api/driver/assignments/{id}` | `get_driver_assignment` | same as above | same plus assignment id |
| `GET /api/driver/workbench` | `get_driver_workbench` | assignments, `driver_workflow_events`, `driver_expense_reports` | own profile in current tenant |
| `GET /api/driver/profile` | `get_driver_profile` | `drivers` | own profile in current tenant |
| `GET /api/driver/notifications` | `list_driver_notifications` | `notifications` | own driver target, sanitized allowed types |
| `GET /api/driver/daily-report` | `get_driver_daily_report` | `driver_daily_reports`, assignments snapshot | own profile/date/current tenant |
| `GET /api/driver/run-documents` | `list_driver_run_documents` | `driver_run_documents` and document metadata | own profile/current tenant/visible lifecycle |
| `GET /api/driver/expenses` | `list_driver_expenses` | `driver_expense_reports` | own profile/current tenant |
| `GET /api/driver/history` | `list_driver_history` | assignments, orders, evidence, expenses | own profile/current tenant |
| `GET /api/driver/income` | finance driver summary | existing settlement/assignment sources | own profile/current tenant |

## Existing write endpoints retained unchanged

| Method and path | Existing purpose | Main writes |
|---|---|---|
| `POST /api/driver/report` | assignment confirmation and execution reports | `driver_reports`, assignment execution status, audit/notifications |
| `POST /api/driver/workflow-event` | outbound/inbound checks and workflow evidence | `driver_workflow_events`, existing evidence storage |
| `POST /api/driver/location` | own location report | `location_logs` |
| `POST /api/driver/daily-report` | save/submit current driver daily report | `driver_daily_reports` |
| `POST /api/driver/expense` | submit existing driver expense | `driver_expense_reports` |
| `POST /api/driver/evidence` | upload existing task evidence | `driver_evidence_uploads` |
| `POST /api/driver/notifications/{id}/read` | receipt/read acknowledgement | `notifications.read_at/status` |
| `POST /api/driver/profile` | update allowed own profile fields | `drivers` |
| `POST /api/driver/profile-document` | upload allowed driver document | existing driver document fields/storage |

## Existing schema inventory relevant to the driver workflow

| Domain | Existing table(s) | Phase 1 use |
|---|---|---|
| Orders and assignment | `orders`, `assignments` | read-only home projection |
| Execution reports | `driver_reports`, `driver_workflow_events` | read-only summaries; writes stay on task page |
| Expenses | `driver_expense_reports` | status only; writes stay on expense page |
| Location | `location_logs` | no new home write |
| Notifications | `notifications` | unread/change reminder and existing read receipt |
| Daily report | `driver_daily_reports` | status/shortcut only |
| Run documents | `driver_run_documents` | published-document shortcut only |
| Route/document detail | `dispatch_route_nodes`, `dispatch_route_node_actuals`, `dispatch_document_receipts`, `dispatch_document_events` | no Phase 1 write |
| Vehicle inspection | `driver_daily_inspections` | future phase only; no Phase 1 write |

## No-parallel-system decision

Phase 1 adds no endpoint, table, file store, local business cache, or independent status machine. The home view model is rebuilt from current API responses on each dashboard refresh. Existing page routes remain the only mutation entry points.

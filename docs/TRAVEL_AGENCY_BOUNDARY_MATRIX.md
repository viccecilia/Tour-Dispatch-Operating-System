# Travel Agency Boundary Matrix

This document records the stage-00 product boundary for the travel-agency side without changing the existing carrier-company runtime.

## Entry Points

| Surface | Owner role | Local entry | Data scope | Must not see |
| --- | --- | --- | --- | --- |
| Travel agency portal | Travel agency customer service / guide / finance clerk | React route `#agency-portal`, API `/api/agency-portal/*` | Only orders created for the logged-in agency and its tenant | Other agencies, other tenants, carrier internal driver ledger, carrier finance margins |
| Carrier admin console | `admin` | React admin console on port `5173`, API on `18765` | Current carrier tenant | Other tenants |
| Carrier dispatcher console | `dispatcher` | Shared React console and dispatch miniapp | Current tenant dispatch/order workflow | Finance and system-control pages |
| Carrier operations console | `operations_manager` | Shared React console | Vehicles, drivers, maintenance, map, incidents, reminders in current tenant | Parser, orders, dispatch, auction, finance, analytics, system-control pages |
| Driver miniapp | `driver` | `miniapp/pages/driver/index` | Driver's own tasks and runtime data | Order sale price, agency settlement, carrier margin, other drivers |

## Role Boundary

The travel-agency side is a customer-facing surface, not a new carrier-company management role.

- Agency users submit orders, review their own order status, provide execution details, and later handle agency-side settlement or complaints.
- Carrier `admin` remains the only role that can manage accounts, finance, and system-level settings.
- Carrier `dispatcher` continues to operate order intake, parsing, dispatch, and day-to-day assignment.
- `operations_manager` continues to monitor vehicles, drivers, maintenance, incidents, reminders, and map data. It is intentionally blocked from order-entry and finance workflows.
- Driver logic stays in the driver miniapp and must stay scoped to the authenticated driver.

## Port and API Boundary

Local development keeps the existing split:

- Backend API: `http://127.0.0.1:18765`
- React admin console: `http://127.0.0.1:5173`
- Driver miniapp: `miniapp/`
- Dispatcher miniapp: `miniapp_dispatch/`

For already-published miniapps, keep one stable public API domain and hide internal service ports behind a reverse proxy. Do not introduce another public port for the travel-agency portal without a deployment decision.

## Tenant and Agency Isolation

The minimum isolation checks for this stage are:

- Carrier-side services query and write with `tenant_id`.
- Agency portal tokens contain both `agency_id` and `tenant_id`.
- Agency portal order listing filters by both `tenant_id` and `agency_id`.
- Agency-created orders set `agency_id`, `agency_name`, and `order_source = agency_portal`.
- Public agency selection exposes only portal-enabled agency identity needed for login; it must not expose carrier-internal finance or operational data.

## Current Implementation Mapping

| Capability | Current file | Boundary signal |
| --- | --- | --- |
| Agency ledger | `backend/services/agency_service.py` | Lists, creates, updates, and soft-deletes agencies inside `get_current_tenant_id()` |
| Agency portal auth | `backend/services/agency_portal_service.py` | Login uses `agency_id + portal_code`; token carries `agency_id` and `tenant_id` |
| Agency order submission | `backend/services/agency_portal_service.py` | Creates orders with `order_source = agency_portal` |
| Agency order visibility | `backend/services/agency_portal_service.py` | Lists orders with `WHERE tenant_id = ? AND agency_id = ?` |
| Carrier role gating | `frontend/src/app/App.tsx`, `frontend/src/layouts/SaasShell.tsx` | Finance/system pages remain admin-only; operations manager and dispatcher visibility stays restricted |
| API routes | `backend/api/routes.py` | `/api/agency-portal/*` is separate from carrier admin routes |

## TA-S00-R01 Acceptance

TA-S00-R01 is complete when the repository has a single readable boundary matrix and a local verification script that confirms:

- Travel-agency, carrier admin, dispatcher, operations manager, and driver surfaces are distinguishable.
- Travel-agency order visibility is not mixed with carrier company internal management.
- Tenant and agency filters are present on the agency portal service.
- Existing carrier role restrictions for finance/system/order-entry surfaces are still present.

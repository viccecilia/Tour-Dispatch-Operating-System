# Travel Agency Stage Implementation Map

This map ties the travel-agency stage files to the implementation added under the independent `travel_agency_` module. The intent is to extend the system without rewriting the existing carrier-company admin, dispatch, driver, or operations-manager workflows.

## Added Backend Module

- Service: `backend/services/travel_agency_service.py`
- API prefix: `/api/travel-agency/*`
- Tables are created lazily with the `travel_agency_` prefix.
- All business rows include `tenant_id`.
- Company-owned rows include `company_id`.
- Marketplace and guide runtime events are separated from the existing carrier dispatch runtime.

## Stage Coverage

| Stage | Coverage |
| --- | --- |
| TA-STAGE-00 | Company tenant model, master account seed, role matrix, password-change flags, WeChat binding state, order base model, and platform/company boundary. |
| TA-STAGE-01 | Web-admin support APIs for companies, accounts, guides, customers, settings-style company metadata, and audit logs. |
| TA-STAGE-02 | Customer-service APIs for order creation, text parse preview, source/customer selection, confirmation flow, filtering, and status transitions. |
| TA-STAGE-03 | Confirmed-order pool, guide assignment, vehicle request, marketplace draft publishing, carrier award writeback, and notification/audit-ready status records. |
| TA-STAGE-04 | Guide runtime data model for guide assignment, task events, node reports, evidence URLs, and profile data. |
| TA-STAGE-05 | Finance ledger, receivable/payable/profit summary, settlement transition, and CSV export. |
| TA-STAGE-06 | Marketplace draft, start price, buyout price, public listing, quote submission, award writeback, timeout/cancel responsibility note, and platform audit log. |
| TA-STAGE-07 | Local QA matrix through `scripts/verify_travel_agency_all_stages.py`; trial deploy, miniapp upload, production backup, and cloud release remain confirmation-gated. |

## API Surface

| Method | Path | Purpose | Role gate |
| --- | --- | --- | --- |
| GET | `/api/travel-agency/summary` | Module counts and role matrix | admin, dispatcher, operations_manager |
| GET/POST | `/api/travel-agency/companies` | Travel-agency company tenant ledger | admin, dispatcher |
| GET/POST | `/api/travel-agency/accounts` | Travel-agency subaccounts | admin, dispatcher |
| GET/POST | `/api/travel-agency/guides` | Guide ledger | GET includes operations_manager; POST admin/dispatcher |
| GET/POST | `/api/travel-agency/customers` | Customer/source ledger | admin, dispatcher |
| GET/POST | `/api/travel-agency/orders` | Travel-agency orders | admin, dispatcher |
| POST | `/api/travel-agency/orders/parse` | Text parse preview | admin, dispatcher |
| POST | `/api/travel-agency/orders/{id}/confirm` | Confirm order | admin, dispatcher |
| POST | `/api/travel-agency/orders/{id}/assign-guide` | Assign guide | admin, dispatcher |
| POST | `/api/travel-agency/orders/{id}/vehicle-request` | Submit vehicle demand | admin, dispatcher |
| POST | `/api/travel-agency/orders/{id}/settle` | Update settlement status | admin, dispatcher |
| GET/POST | `/api/travel-agency/marketplace` | Marketplace listing drafts | GET includes operations_manager; POST admin/dispatcher |
| POST | `/api/travel-agency/marketplace/{id}/quotes` | Carrier quote record | admin, dispatcher, operations_manager |
| POST | `/api/travel-agency/marketplace/{id}/award` | Award carrier and write back order | admin, dispatcher |
| GET/POST | `/api/travel-agency/guide-events` | Guide execution nodes and evidence URLs | admin, dispatcher, operations_manager |
| GET | `/api/travel-agency/finance/ledger` | Receivable/payable/profit ledger | admin |
| GET | `/api/travel-agency/finance/export` | CSV export | admin |
| GET | `/api/travel-agency/audit` | Travel-agency audit trail | admin |

## Local Verification

Run:

```powershell
python scripts\verify_travel_agency_all_stages.py
```

The script uses an isolated SQLite database under `runtime/test_dbs/` and does not modify production or cloud data.

## Release Boundary

The following stage items are intentionally not executed without explicit confirmation:

- Trial environment deployment.
- Miniapp upload or experience-version release.
- Cloud database migration or cleanup.
- Production backup, restore, or destructive data operations.
- Git push.

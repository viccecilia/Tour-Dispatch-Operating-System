# Pilot Release Checklist

## Freeze

- [ ] No new feature work is merged during pilot freeze.
- [ ] Only critical bug fixes are accepted.
- [ ] Runtime config is documented.
- [ ] Rollback owner is assigned.

## Data

- [ ] Trial database prepared with `scripts/prepare_trial_db.py`.
- [ ] Demo/smoke data is not used as trial data.
- [ ] Backup created before pilot start.
- [ ] Restore tested on a copy.

## Validation

- [ ] `python scripts/health_check.py`
- [ ] `python scripts/verify_orders_api.py`
- [ ] `python scripts/verify_dispatch_api.py`
- [ ] `python scripts/verify_calendar_api.py`
- [ ] `python scripts/verify_parser_api.py`
- [ ] `python scripts/verify_driver_api.py`
- [ ] `cd frontend && npm run build`

## Manual Acceptance

- [ ] Admin can login.
- [ ] Dispatcher can login.
- [ ] Driver workflow can be simulated.
- [ ] Parser creates drafts from real text.
- [ ] Orders can be edited.
- [ ] Dispatch can assign driver and vehicle.
- [ ] Calendar shows assigned orders.
- [ ] Driver reports update dashboard.
- [ ] Audit trail records changes.
- [ ] Backup/restore process is understood.

## Launch Decision

Pilot launch is allowed only when all critical validation items pass and the release owner accepts known risks.


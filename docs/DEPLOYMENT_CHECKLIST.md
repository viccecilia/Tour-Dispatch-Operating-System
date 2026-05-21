# Deployment Checklist

## Pre-Deploy

- [ ] Confirm target machine has Python and Node runtime.
- [ ] Confirm `.env` exists or environment variables are set.
- [ ] Confirm `WX_DISPATCH_DEMO_MODE=false` for trial or production.
- [ ] Confirm `WX_DISPATCH_RESET_DEMO_ON_START=false`.
- [ ] Confirm admin password and JWT secret are changed.
- [ ] Run `python scripts/check_production_config.py --strict`.
- [ ] Run `python scripts/backup_db.py`.
- [ ] Record backup file path.

## Deploy

- [ ] Stop old backend process.
- [ ] Deploy code package.
- [ ] Run `python -m compileall backend scripts`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Start backend with `python backend/main.py`.
- [ ] Confirm dashboard URL.

## Post-Deploy

- [ ] Run `python scripts/health_check.py`.
- [ ] Login as admin.
- [ ] Open Dashboard.
- [ ] Open Orders.
- [ ] Open Dispatch.
- [ ] Open Calendar.
- [ ] Open Driver Monitor.
- [ ] Open Audit Trail.
- [ ] Update a test order and confirm audit log appears.
- [ ] Create a backup after successful deployment.

## Go / No-Go

Go only if:

- health check passes
- frontend build passes
- backup is available
- audit trail records a test operation
- rollback file and rollback code are known


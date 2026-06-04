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
- [ ] For trial cloud deployment, run `python scripts/verify_trial_deploy.py`.
- [ ] Confirm hosted Web bundle points to `https://api-trial.taxi-airport.jp`, not the admin domain and not local API.
- [ ] Confirm cloud API uses `WX_DISPATCH_ENV=trial` and `runtime/trial/wx_dispatch_trial.sqlite3`.
- [ ] Confirm seeded test accounts log in against the cloud API, not only local DB.
- [ ] Confirm miniapp API base URL and cached base URL are correct before asking testers to use WeChat DevTools or phone.
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

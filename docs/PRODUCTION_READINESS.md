# Production Readiness

## Goal

This document defines the minimum production-readiness baseline for WX Dispatch before trial operation.

## Runtime Mode

Production or trial mode must use explicit environment variables:

```powershell
$env:WX_DISPATCH_DEMO_MODE='false'
$env:WX_DISPATCH_RESET_DEMO_ON_START='false'
$env:WX_DISPATCH_JWT_SECRET='<long-random-secret>'
$env:WX_DISPATCH_ADMIN_PASSWORD='<non-default-password>'
$env:WX_DISPATCH_DB='C:\wx-dispatch-runtime\wx_dispatch.sqlite3'
$env:WX_DISPATCH_LOG_DIR='C:\wx-dispatch-runtime\logs'
$env:WX_DISPATCH_BACKUP_DIR='C:\wx-dispatch-runtime\backups'
```

Then validate:

```bash
python scripts/check_production_config.py --strict
python scripts/health_check.py
```

## Startup Checklist

1. Confirm the database path is not the demo database.
2. Confirm `WX_DISPATCH_RESET_DEMO_ON_START=false`.
3. Confirm `WX_DISPATCH_DEMO_MODE=false`.
4. Confirm admin password is not `admin123`.
5. Confirm `WX_DISPATCH_JWT_SECRET` has been replaced.
6. Run `python scripts/backup_db.py` before deployment.
7. Start backend with `python backend/main.py`.
8. Run `python scripts/health_check.py`.
9. Open the React Admin Console and verify login.
10. Confirm audit logs are being written after a test order update.

## Production Smoke Test

Required checks:

- Login succeeds.
- Dashboard loads.
- Parser drafts can be listed.
- Orders API responds.
- Dispatch API responds.
- Calendar API responds.
- Driver API responds.
- Audit API responds.
- Backup script can create a SQLite backup.

## Release Gate

Do not enter trial operation if any of these are true:

- Health check fails.
- Backup cannot be created.
- Restore has not been tested on a copy.
- Demo reset is enabled.
- Default admin password is still in use.
- Audit logs are not created for order changes.


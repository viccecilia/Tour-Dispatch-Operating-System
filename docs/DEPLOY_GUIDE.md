# Deploy Guide

## Local Demo Start

Windows:

```bat
start_demo.bat
```

Mac / Linux:

```bash
sh start_demo.sh
```

Default dashboard:

```text
http://127.0.0.1:18765/dashboard
```

## Manual Start

```bash
python scripts/reset_demo_db.py
set WX_DISPATCH_PORT=18765
python backend/main.py
```

PowerShell:

```powershell
$env:WX_DISPATCH_PORT='18765'
python backend/main.py
```

## Environment Config

Copy:

```bash
cp .env.example .env
```

Key variables:

- `WX_DISPATCH_HOST`
- `WX_DISPATCH_PORT`
- `WX_DISPATCH_BASE_URL`
- `WX_DISPATCH_DB`
- `WX_DISPATCH_DEMO_MODE`
- `WX_DISPATCH_RESET_DEMO_ON_START`
- `WX_DISPATCH_LOG_LEVEL`
- `WX_DISPATCH_LOG_DIR`
- `WX_DISPATCH_BACKUP_DIR`

Production baseline:

```powershell
$env:WX_DISPATCH_DEMO_MODE='false'
$env:WX_DISPATCH_RESET_DEMO_ON_START='false'
$env:WX_DISPATCH_JWT_SECRET='<replace-with-long-random-secret>'
$env:WX_DISPATCH_ADMIN_PASSWORD='<replace-default-password>'
python scripts/check_production_config.py --strict
python backend/main.py
```

Do not run `scripts/reset_demo_db.py` against a trial or production database.

## Docker Start

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:18765/dashboard
http://127.0.0.1:5173
```

Docker uses one backend container, one React frontend container, and a SQLite runtime volume. It does not add Redis, PostgreSQL, nginx, maps, or WebSocket.

## React Admin Console

Local frontend start:

```bash
cd frontend
npm install
npm run dev
```

Default:

```text
http://127.0.0.1:5173
```

API base URL:

```text
frontend/.env
VITE_API_BASE_URL=http://127.0.0.1:18765
```

Frontend build validation:

```bash
cd frontend
npm run build
npm run lint
```

## Health Check

```bash
python scripts/health_check.py
```

Expected output:

```text
[OK] database
[OK] api
[OK] dashboard
[OK] parser
[OK] dispatch
[OK] calendar
[OK] driver
[OK] audit
```

## Backup

```bash
python scripts/backup_db.py
```

Backups are saved under:

```text
runtime/backups/
```

## Restore

```bash
python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
```

Stop the backend before restore when possible, then restart it.

## Production Readiness Docs

- `docs/PRODUCTION_READINESS.md`
- `docs/SECURITY_CHECKLIST.md`
- `docs/DB_MIGRATION_POLICY.md`
- `docs/BACKUP_RESTORE_RUNBOOK.md`
- `docs/ROLLBACK_PLAN.md`

## WeChat MiniApp Preview

Set API base URL in:

```text
miniapp/utils/api.js
```

For local developer tools:

```text
http://127.0.0.1:18765
```

For real phone preview:

```text
http://your-lan-ip:18765
```

In WeChat Developer Tools, enable:

```text
Do not verify valid domain name, web-view domain, TLS version, or HTTPS certificate
```

Also check local firewall permissions for Python or Docker.

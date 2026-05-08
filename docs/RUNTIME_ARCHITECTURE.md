# Runtime Architecture

## Overview

WX Dispatch Demo Runtime is a lightweight single-process MVP runtime:

```text
Browser / React Admin Console / MiniApp
        |
        v
Python HTTP backend
        |
        v
SQLite runtime database
```

It is designed for demos, local migration, and early trial operation.

## Components

### Backend

Entry point:

```text
backend/main.py
```

The backend exposes:

- `/dashboard`
- `/api/ping`
- `/api/auth/login`
- `/api/orders`
- `/api/parser/*`
- `/api/dispatch/*`
- `/api/calendar/*`
- `/api/driver/*`

### SQLite

Default database:

```text
runtime/wx_dispatch.sqlite3
```

Override:

```text
WX_DISPATCH_DB
```

### Dashboard

`/dashboard` is the desktop dispatch console for demo and operator review.

### React Admin Console

`frontend/` is the new Vite + React + TypeScript SaaS Admin Console. It is an independent frontend shell that consumes the existing backend APIs.

Default local URL:

```text
http://127.0.0.1:5173
```

API config:

```text
frontend/.env
VITE_API_BASE_URL=http://127.0.0.1:18765
```

Main React pages:

- Dashboard
- Parser
- Orders
- Dispatch
- Calendar
- Driver Monitor

### MiniApp

`miniapp/` uses `miniapp/utils/api.js` for API base URL configuration.

### Parser

Parser APIs create editable order drafts. Drafts are confirmed into orders manually.

### Dispatch

Dispatch APIs assign orders to drivers and vehicles and write assignments.

### Calendar

Calendar APIs read orders, assignments, drivers, and vehicles to render the schedule matrix.

### Driver

Driver APIs expose assigned orders and report execution status.

## Runtime Config

Config is centralized in:

```text
backend/config.py
```

It reads `.env` and environment variables.

Important variables:

- `WX_DISPATCH_PORT`
- `WX_DISPATCH_DB`
- `WX_DISPATCH_DEMO_MODE`
- `WX_DISPATCH_RESET_DEMO_ON_START`
- `WX_DISPATCH_LOG_LEVEL`

## Logs

Default log directory:

```text
runtime/logs/
```

Backend log:

```text
runtime/logs/backend.log
```

## Backup and Restore

Backup:

```bash
python scripts/backup_db.py
```

Restore:

```bash
python scripts/restore_db.py <backup_file>
```

## Docker Runtime

Docker runtime contains:

- one Python backend container
- one React frontend container
- one SQLite volume

It intentionally does not include:

- Redis
- PostgreSQL
- nginx
- maps
- WebSocket
- external AI services

## Demo Reset

Demo reset:

```bash
python scripts/reset_demo_db.py
```

This restores a fixed demo data set and prevents smoke data from accumulating.

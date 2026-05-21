# WX Dispatch Pilot Launch Guide

## Pilot Scope

This pilot version is for controlled trial operation by internal staff.

Included workflows:

- login and role separation
- parser draft intake
- order CRUD
- dispatch assignment
- calendar schedule view
- driver execution reporting
- vehicle and driver resource records
- finance settlement basics
- audit trail
- backup and restore

Excluded from this pilot:

- public internet exposure without TLS
- real payment
- formal WeChat login
- map routing
- WebSocket tracking
- complex accounting

## Functional Freeze

During pilot, only these changes are allowed:

- critical bug fixes
- parser rule corrections
- data repair under admin approval
- documentation fixes
- deployment/runtime fixes

Do not add new business modules during pilot unless the release owner approves.

## Prepare Trial Database

Generate a clean trial database without demo orders:

```bash
python scripts/prepare_trial_db.py --overwrite
```

Default output:

```text
runtime/trial/wx_dispatch_trial.sqlite3
```

Run backend with it:

```powershell
$env:WX_DISPATCH_DB='runtime/trial/wx_dispatch_trial.sqlite3'
$env:WX_DISPATCH_DEMO_MODE='false'
$env:WX_DISPATCH_RESET_DEMO_ON_START='false'
$env:WX_DISPATCH_JWT_SECRET='<long-random-secret>'
python backend/main.py
```

## Pilot Accounts

Default seed accounts:

- `admin / admin123`
- `dispatcher / dispatcher123`

Before real pilot, change default passwords using an admin-maintained process.

## Pilot Acceptance

The pilot can start only after:

- `python scripts/health_check.py` passes
- frontend build passes
- backup and restore are tested
- audit trail records an order update
- operators complete the training flow
- rollback plan is understood


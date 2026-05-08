# WX-DISPATCH-R009 Round Summary

## Round

- Round ID: WX-DISPATCH-R009
- Round Name: Demo Deploy & Runtime Engineering

## Summary

The MVP runtime has been upgraded from local development mode into a demo runtime that can be started, reset, checked, backed up, restored, documented, and containerized.

## Key Fixes During Validation

- Default runtime port was corrected from `8000` to `18765`.
- Verification scripts now default to `http://127.0.0.1:18765`.
- `start_demo.bat` and `start_demo.sh` now print a clearer LAN IP instruction.
- Repeated smoke tests exposed duplicate order `oid` generation after soft delete; `order_service.py` now avoids reusing an existing `oid` without changing the database schema.
- SQLite backup journal cleanup is now best-effort to avoid Windows file-lock failures.

## Required Validation Results

| Command | Result |
| --- | --- |
| `python -m compileall backend scripts` | Passed |
| `python scripts/reset_demo_db.py` | Passed |
| `python scripts/health_check.py` | Passed |
| `python scripts/verify_orders_api.py` | Passed |
| `python scripts/verify_dispatch_api.py` | Passed |
| `python scripts/verify_calendar_api.py` | Passed |
| `python scripts/verify_parser_api.py` | Passed |
| `python scripts/verify_driver_api.py` | Passed |
| `python scripts/backup_db.py` | Passed |
| `python scripts/restore_db.py runtime/backups/wx_dispatch_20260508_092517.sqlite3` | Passed |

## Docker Validation

Docker was not available on this machine:

```text
docker: The term 'docker' is not recognized
```

Docker files are present and require manual validation on a Docker-enabled machine.

## Final Runtime State

After smoke tests, `python scripts/reset_demo_db.py` was run again to restore stable demo data. `python scripts/health_check.py` passed afterward.

## Scope Boundaries

No business feature, finance system, map, WebSocket, OpenAI API, complex AI Agent, Redis, PostgreSQL, or database schema change was added.

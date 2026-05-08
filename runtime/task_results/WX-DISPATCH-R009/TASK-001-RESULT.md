# TASK-001 Result

Status: DONE

## Changes

- `.env.example` defines demo runtime variables.
- `backend/config.py` loads `.env` and environment variables.
- Default backend port is now `18765`.
- Runtime paths are centralized:
  - `WX_DISPATCH_DB`
  - `WX_DISPATCH_LOG_DIR`
  - `WX_DISPATCH_BACKUP_DIR`
- Demo switches are centralized:
  - `WX_DISPATCH_DEMO_MODE`
  - `WX_DISPATCH_RESET_DEMO_ON_START`

## Validation

- `python -m compileall backend scripts`: passed.
- `python scripts/health_check.py`: passed on `http://127.0.0.1:18765`.

## Notes

No database schema changes were made.

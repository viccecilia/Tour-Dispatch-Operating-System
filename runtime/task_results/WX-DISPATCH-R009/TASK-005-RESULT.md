# TASK-005 Result

Status: DONE

## Changes

- `scripts/backup_db.py` creates timestamped SQLite backups under `runtime/backups/`.
- `scripts/restore_db.py` restores a selected backup file.
- Backup journal cleanup is best-effort so Windows file locks do not fail a successful backup.

## Validation

Backup:

```bash
python scripts/backup_db.py
```

Result:

```text
runtime/backups/wx_dispatch_20260508_092517.sqlite3
```

Restore:

```bash
python scripts/restore_db.py runtime/backups/wx_dispatch_20260508_092517.sqlite3
```

Result: restore completed.

## Notes

Stop the backend before restore when possible.

# Backup Restore Runbook

## Backup Policy

Minimum trial policy:

- Create a backup before every deployment.
- Create a backup before every schema change.
- Create a backup before importing large real order batches.
- Keep at least 7 daily backups during trial.
- Copy important backups off the demo machine.

## Create Backup

```bash
python scripts/backup_db.py
```

The script prints the backup file path. Default directory:

```text
runtime/backups/
```

## Restore Backup

Preferred restore flow:

1. Stop backend.
2. Restore:

   ```bash
   python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
   ```

3. Restart backend.
4. Run:

   ```bash
   python scripts/health_check.py
   ```

## Restore Test

Before a real restore, test the backup by restoring it to a temporary database path:

```powershell
$env:WX_DISPATCH_DB='runtime/restore_test.sqlite3'
python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
python backend/main.py
```

Then run health check against that runtime.

## Data Safety Notes

- Restore replaces the configured SQLite database file.
- Do not restore while users are actively writing data.
- Do not use demo reset as a restore mechanism.
- Backups contain operational and contact data; treat them as sensitive.


# DB Migration Policy

## Current Strategy

WX Dispatch currently uses SQLite and idempotent schema initialization:

- `backend/db/schema.sql` creates missing tables.
- `backend/db/database.py` adds compatible missing columns.
- Existing data should not be hard-deleted by migrations.

## Migration Rules

1. Always back up before a schema change:

   ```bash
   python scripts/backup_db.py
   ```

2. Schema changes must be backward compatible when possible:

   - add nullable columns
   - add default values
   - create new tables
   - avoid destructive renames

3. Never run `scripts/reset_demo_db.py` on trial or production data.

4. Never physically delete orders, assignments, audit logs, or finance history during a migration.

5. Test migration against a copied database before applying it to the live database.

## Manual Migration Checklist

1. Stop backend.
2. Run `python scripts/backup_db.py`.
3. Copy the backup to a separate restore-test path.
4. Run the new app against the copy.
5. Run `python scripts/health_check.py`.
6. Check dashboard, orders, dispatch, calendar, finance, and audit pages.
7. If the copy passes, apply to the live runtime.

## Rollback

If a migration fails:

1. Stop backend.
2. Restore the pre-migration backup:

   ```bash
   python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
   ```

3. Restart backend.
4. Run `python scripts/health_check.py`.


# Rollback Plan

## Rollback Triggers

Rollback is required when:

- backend cannot start
- `scripts/health_check.py` fails after deployment
- login fails for admin
- order CRUD fails
- dispatch assignment fails
- calendar cannot read active assignments
- backup restore test fails
- audit trail cannot record key operations

## Code Rollback

1. Stop backend and frontend processes.
2. Return to the previous known-good code package or Git revision.
3. Confirm `.env` still points at the intended database.
4. Start backend.
5. Run:

   ```bash
   python scripts/health_check.py
   ```

6. Build frontend:

   ```bash
   cd frontend
   npm run build
   ```

## Database Rollback

If data or migration is the issue:

1. Stop backend.
2. Restore the last pre-deployment backup:

   ```bash
   python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
   ```

3. Restart backend.
4. Run health check.
5. Manually inspect dashboard, orders, dispatch, calendar, finance, and audit pages.

## Communication Checklist

- Record the rollback reason.
- Record the backup file used.
- Record the code version used after rollback.
- Record the result of health check.
- Tell operators whether data entered after the backup must be re-entered.


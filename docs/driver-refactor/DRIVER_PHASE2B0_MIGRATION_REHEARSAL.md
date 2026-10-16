# Driver Phase 2B-0A migration rehearsal and rollback

## Migration

- File: `backend/db/migrations/20261015_driver_provisional_tasks_phase2b0a.sql`
- SHA-256: `af2a809649b21f03cdb46cea3ca301ccc786391fd1c58ef520e1c3fe753045ce`
- Type: additive SQLite migration; no existing row is updated.
- Adds two nullable source columns to `orders`, two new tables, supporting indexes, uniqueness guards and immutability triggers.
- Does not alter the Phase 2A route-node actual tables.

## Isolated rehearsal procedure

1. Initialized an isolated SQLite database with all earlier migrations but without B0-A.
2. Inserted representative user, driver, vehicle, formal order/assignment, manual price `19,500`, and Phase 2A actual location/time/odometer data.
3. Ran a complete compatibility startup to establish the true pre-B0 baseline.
4. Produced a consistent closed-connection copy and SHA-256.
5. Restored the full migration directory and ran the project migration mechanism.
6. Verified schema, migration registration, `PRAGMA integrity_check`, and legacy business-data fingerprints.
7. Ran startup again and verified the migration remained registered exactly once with unchanged fingerprints.
8. Restored the pre-migration database copy into a separate rollback file and verified the old schema and legacy fingerprints.

## Results

| Check | Result |
|---|---|
| Pre-migration registrations | 12 |
| B0-A registration count | 1 |
| Pre integrity | `ok` |
| Post integrity | `ok` |
| User/driver/vehicle/order/assignment/Phase2A actual fingerprints | unchanged |
| Repeated startup | passed, no duplicate DDL |
| Recoverable pre-B0 copy | verified |
| Rollback copy integrity and old schema | verified |

Evidence:

- `artifacts/driver-refactor/phase2b0a/phase2b0a-migration-rehearsal.json`
- `artifacts/driver-refactor/phase2b0a/phase2b0a-before.sqlite3` — SHA-256 `4a86c2a7193bfd0b8b790dc1deaa28345f0a23bb1f1487a5415df0e93fe2c15c`
- `artifacts/driver-refactor/phase2b0a/phase2b0a-rehearsal.sqlite3`
- `artifacts/driver-refactor/phase2b0a/phase2b0a-rollback.sqlite3`

## Rollback design

B0-A was not deployed, so no live rollback was performed. For a future authorized release:

- Before activation, stop relevant Trial writes and make a consistent database backup.
- If activation fails before any B0-A write, restore the backup and the prior compatible backend as one coordinated rollback.
- If B0-A records already exist, do not downgrade by dropping tables or restoring an older database over newer business writes. Disable the new endpoints, preserve the tables/history, and run a forward compatibility repair.
- Never delete the migration registration to force repeat `ALTER TABLE` statements.

No Trial or Production database was read, copied, modified or restarted in this phase.

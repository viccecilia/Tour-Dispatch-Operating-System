# Driver Phase 2A Migration Rehearsal and Rollback

## Isolated rehearsal

The rehearsal built a pre-Phase2A SQLite database from `schema.sql` plus every prior registered migration, inserted representative order/assignment/actual data, made a byte-for-byte backup, then applied only `20261015_driver_route_node_actuals_phase2a.sql`.

Artifacts:

| Artifact | SHA-256 |
|---|---|
| `artifacts/driver-refactor/phase2a/phase2a-migration-pre.sqlite3` | `64e0ff542dbfb5244f10452fdb67929b91e1f4d520d2b10b9b4197f66c32e078` |
| `artifacts/driver-refactor/phase2a/phase2a-migration-post.sqlite3` | `762457ad629147a96a5d9cf11f7415711b7b00dba98d2c94561a8e9394801948` |
| `artifacts/driver-refactor/phase2a/phase2a-migration-rehearsal.json` | `c3a3ef19ddb449bd2abecbc5356f40d700f3e39ae0ca12a621bdd6fec2c53dae` |

Results:

- Pre/post `PRAGMA integrity_check`: `ok`.
- Existing actual row content unchanged.
- Orders, assignments, run documents and planned route node fingerprints identical.
- Re-running project migration discovery twice did not reapply the SQL; registration count remained one.
- Backup remained readable and retained the original actual location.

## Activation dependency (not performed)

Any future Trial activation must first read-only reconcile the live `schema_migrations` registration and actual schema. If either differs from the reviewed migration source, stop; do not insert a registration manually and do not retry duplicate `ALTER TABLE` statements.

## Rollback plan

Before a future environment migration:

1. Pause only the affected driver's actual-node write endpoint.
2. Take and hash a consistent SQLite backup.
3. Apply the migration through the project mechanism and verify schema, registration and integrity before reopening writes.
4. If activation fails before any Phase2A actual write, restore the verified backup and matching pre-Phase2A backend together.
5. If new actual writes already exist, do **not** overwrite the database with the old backup. Keep writes paused, export `dispatch_route_node_actuals` and `driver_route_node_actual_requests`, and prepare a forward-compatible recovery.

Because the migration is additive, normal code rollback may leave unused columns/table in place. Dropping them is neither necessary nor safe during incident recovery.

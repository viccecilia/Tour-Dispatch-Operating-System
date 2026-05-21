# Security Checklist

## Required Before Trial

- Change `WX_DISPATCH_ADMIN_PASSWORD`.
- Change `WX_DISPATCH_JWT_SECRET`.
- Set `WX_DISPATCH_DEMO_MODE=false`.
- Set `WX_DISPATCH_RESET_DEMO_ON_START=false`.
- Keep the SQLite file outside the source tree for real trial data.
- Restrict OS file permissions for database, logs, and backups.
- Do not expose the backend directly to the public internet without TLS and access controls.
- Confirm driver and dispatcher accounts use only the intended role.
- Confirm tenant isolation with at least two test tenants before multi-company use.
- Confirm audit logs are enabled for order, dispatch, finance, and driver-report changes.

## Operational Rules

- Do not share the admin account for daily dispatch work.
- Use dispatcher accounts for normal operation.
- Use admin only for setup, resource management, and emergency recovery.
- Keep backup files private; they contain order and contact data.
- Rotate the JWT secret if a machine or backup is exposed.

## Current MVP Security Boundary

The current runtime is trial-ready only for controlled environments. It does not yet provide:

- HTTPS termination
- external identity provider integration
- formal password reset
- row-level permission UI
- encrypted SQLite at rest
- managed secrets vault

These are production hardening items for later rounds.


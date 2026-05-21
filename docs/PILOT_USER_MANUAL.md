# Pilot User Manual

## Roles

- Admin: configuration, resources, users, backup, audit review.
- Dispatcher: parser, orders, dispatch, calendar, driver monitor.
- Driver: receives assigned jobs and submits execution reports through driver-side flow.

## Daily Dispatcher Flow

1. Check Dashboard.
2. Paste new order text in Parser.
3. Review drafts and confirm orders.
4. Open Orders and check important fields.
5. Open Dispatch.
6. Select orders, driver, and vehicle.
7. Confirm dispatch.
8. Open Calendar and confirm schedule.
9. Monitor driver execution.
10. Check Dashboard again.

## Important Rules

- Do not physically delete orders.
- Use soft delete only when hiding an incorrect order.
- Failed parser drafts must be reviewed, not ignored.
- Dispatch conflicts must be resolved manually.
- Finance status changes should be made only after confirmation.
- Audit Trail is the source for who changed what.

## What To Report During Pilot

Record these issues:

- parser fields that are often wrong
- orders that cannot be dispatched
- confusing status labels
- wrong dashboard counts
- missing finance fields
- driver workflow confusion
- calendar readability problems

## Emergency Steps

If the system behaves unexpectedly:

1. Stop new data entry.
2. Take a backup.
3. Record the time and action that caused the issue.
4. Run `python scripts/health_check.py`.
5. Contact the admin/release owner.


# Operator Training Guide

## Training Goal

Operators should be able to complete the daily chain without developer help:

```text
Parser -> Draft confirmation -> Orders -> Dispatch -> Calendar -> Driver Monitor -> Dashboard
```

## 1. Login

1. Open the React Admin Console.
2. Login as `dispatcher`.
3. Confirm the sidebar and dashboard are visible.

Pass standard:

- operator can enter the console
- API badge is online
- dashboard numbers load

## 2. Parser Intake

1. Open Parser.
2. Paste a real order text batch.
3. Generate drafts.
4. Expand uncertain rows.
5. Correct date, time, route, vehicle type, price, and remark.
6. Confirm selected drafts into orders.

Pass standard:

- original text is preserved
- failed draft is not lost
- confirmed order appears in Orders

## 3. Order Review

1. Open Orders.
2. Search by order number, agency, route, or guest.
3. Edit a test order.
4. Soft-delete only if the order should be hidden.

Pass standard:

- order can be found quickly
- edits are saved
- audit trail records the change

## 4. Dispatch

1. Open Dispatch.
2. Select unassigned orders by clicking rows.
3. Use route suggestion when needed.
4. Select driver.
5. Select vehicle.
6. Confirm dispatch.

Pass standard:

- assignment is created
- unassigned pool decreases
- assigned pool increases
- calendar shows the order
- driver side can see the assignment

## 5. Calendar

1. Open Calendar.
2. Switch 24h / 7d / 30d.
3. Filter by date.
4. Check assigned vehicles and status colors.

Pass standard:

- dispatch result appears on the selected date
- status color is understandable
- operator can find a vehicle schedule

## 6. Driver Monitor

1. Open Driver Monitor.
2. Confirm driver report status.
3. Check latest report and report time.

Pass standard:

- driver status updates are visible
- unusual status can be found

## 7. Audit Trail

1. Open Audit Trail.
2. Search the order number.
3. Confirm create/update/dispatch/finance records.
4. Run anomaly scan.

Pass standard:

- operator can trace who changed what
- scan does not modify data


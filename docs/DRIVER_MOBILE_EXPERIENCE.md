# Driver Mobile Experience

## Goal

The driver mobile page is designed around one question:

```text
What should the driver do next?
```

The page should show today's tasks, highlight the active task, and expose one primary next-step button.

## Today Task Rules

- Only today's assignments are shown by default.
- Active or in-progress assignments are listed above completed assignments.
- Completed and returned assignments are folded under a secondary section.
- Tasks are sorted by start time.

## Next Action Mapping

| Current status | Next button |
| --- | --- |
| assigned | 确认订单 |
| confirmed | 出库 |
| departed | 到达上车点 |
| arrived | 开始服务 |
| in_service | 完成订单 |
| completed | 归库 |

The backend rejects duplicate, regressive, or skipped execution reports.

## Location Reporting

Each status report can include:

- latitude
- longitude
- location_text
- note

The backend writes:

- `driver_reports`
- `location_logs`

The driver can also manually upload the current location without changing the execution status.

## Navigation

The MiniApp page provides:

- 导航到上车点
- 导航到终点

If coordinates are available, it uses `wx.openLocation`. If no coordinates exist, it shows the text address and asks the driver to use a navigation app manually.

## Weak Network Handling

When a report fails, the MiniApp caches it locally and shows a retry prompt. Pending reports can be retried manually or after the network comes back.

## Dispatch Visibility

Driver Monitor reads latest location and report status through:

- `/api/fleet/latest-locations`
- `/api/dispatch/assignments`
- `/api/driver/reports`

The first version is a coordinate list and map placeholder, not realtime tracking.


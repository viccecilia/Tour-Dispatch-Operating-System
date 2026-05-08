# TASK-002 Result

Status: DONE

## Changes

- `start_demo.bat` supports Windows one-command demo start.
- `start_demo.sh` supports Mac/Linux one-command demo start.
- Both scripts reset demo data, print dashboard URL, print MiniApp API URL, and open the dashboard when supported.

## Runtime URLs

```text
Dashboard:
http://127.0.0.1:18765/dashboard

WeChat MiniApp API:
http://你的局域网IP:18765
```

## Validation

- Backend was started manually through the same `backend/main.py` entry.
- Dashboard and `/api/ping` were verified through health checks.

## Manual Acceptance Required

- Double-click `start_demo.bat`.
- Confirm browser opens dashboard automatically.
- Confirm LAN IP prompt is clear for real device preview.

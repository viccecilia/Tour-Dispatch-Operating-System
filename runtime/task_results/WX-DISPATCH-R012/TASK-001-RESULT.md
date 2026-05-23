# TASK-001 Lightweight Polling Runtime

- 修改了什么：采用轻量 polling，不引入 WebSocket；关键页面 Query 增加 `refetchInterval`。
- 涉及文件：frontend/src/pages/DashboardPage.tsx, frontend/src/pages/DispatchPage.tsx, frontend/src/pages/CalendarPage.tsx, frontend/src/pages/DriverMonitorPage.tsx。
- 验证方式：npm.cmd run build；npm.cmd run lint。
- 是否完成：DONE。
- 风险：轮询有 4-10 秒延迟，不是毫秒级实时。

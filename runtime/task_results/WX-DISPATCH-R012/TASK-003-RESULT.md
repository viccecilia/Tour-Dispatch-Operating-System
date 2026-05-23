# TASK-003 Dispatch / Driver / Calendar Auto Refresh

- 修改了什么：dispatch 未派车池、已派车池、日历预览自动刷新；driver monitor 报备和 assignment 自动刷新；calendar 页面自动刷新。
- 涉及文件：frontend/src/pages/DispatchPage.tsx, frontend/src/pages/DriverMonitorPage.tsx, frontend/src/pages/CalendarPage.tsx。
- 验证方式：python scripts/verify_dispatch_api.py；python scripts/verify_driver_api.py；npm.cmd run build。
- 是否完成：DONE。
- 风险：轮询刷新不会打断当前选择，但如果外部状态变化，列表会在刷新周期后更新。

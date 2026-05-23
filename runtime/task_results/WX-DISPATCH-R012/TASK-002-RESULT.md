# TASK-002 Dashboard Auto Refresh

- 修改了什么：dashboard summary 每 5 秒刷新，草稿每 8 秒刷新，assignments 每 5 秒刷新。
- 涉及文件：frontend/src/pages/DashboardPage.tsx。
- 验证方式：npm.cmd run build。
- 是否完成：DONE。
- 风险：如果后台 API 401，前端会显示现有 error state，需要重新登录。

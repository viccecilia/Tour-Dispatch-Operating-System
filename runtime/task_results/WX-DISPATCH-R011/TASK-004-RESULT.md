# TASK-004 React Login State

- 修改了什么：React 前端增加登录页、登录态校验、Authorization header、退出按钮、租户信息展示。
- 涉及文件：frontend/src/app/App.tsx, frontend/src/pages/LoginPage.tsx, frontend/src/services/apiClient.ts, frontend/src/layouts/SaasShell.tsx, frontend/src/types/api.ts。
- 验证方式：浏览器清空 token 后进入登录页；admin 登录后进入 Admin Console。
- 是否完成：DONE。
- 风险：token 保存在 localStorage，适合 demo；正式生产可再升级刷新 token/更严格安全策略。

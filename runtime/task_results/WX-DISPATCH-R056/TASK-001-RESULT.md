# TASK-001：空状态高级化

## 修改了什么
- 新增统一 `ErrorPanel`、`EmptyPanel`、`SkeletonCard`、`RetryButton`。
- API 失败时显示图标、标题、说明、重试按钮、检查后端按钮、请求路径、演示数据入口。
- 将目标页面从单行红字错误改为模块化错误状态。

## 涉及文件
- `frontend/src/components/OperationalState.tsx`
- `frontend/src/pages/AnalyticsPage.tsx`
- `frontend/src/pages/AutomationPage.tsx`
- `frontend/src/pages/CopilotPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- 浏览器检查 `settings`、`analytics`、`automation`、`copilot` 页面

## 是否完成
DONE

## 风险
- 本轮未断开后端做强制离线截图验证，但页面逻辑已覆盖 API error 分支。

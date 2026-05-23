# TASK-006：统一 Web Error Component

## 修改了什么
- 新增统一组件文件：
  - `ErrorPanel`
  - `EmptyPanel`
  - `SkeletonCard`
  - `RetryButton`
- 四个目标页面复用统一组件，减少各页自行写粗糙错误提示。

## 涉及文件
- `frontend/src/components/OperationalState.tsx`
- `frontend/src/pages/AnalyticsPage.tsx`
- `frontend/src/pages/AutomationPage.tsx`
- `frontend/src/pages/CopilotPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- `python scripts/health_check.py`

## 是否完成
DONE

## 风险
- 后续其他页面还可以继续逐步迁移到统一错误组件。

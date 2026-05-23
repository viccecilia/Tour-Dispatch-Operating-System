# TASK-003：调度端安全警报展示

## 修改了什么
- Driver Monitor 页面增加安全警报 KPI。
- 增加安全警报区，显示 SOS、异常报备和长时间未移动提醒。
- 清理 Driver Monitor 页面中文显示。

## 涉及文件
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/services/apiClient.ts`
- `frontend/src/types/api.ts`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 调度端警报频率和展示优先级需要运营人工确认。

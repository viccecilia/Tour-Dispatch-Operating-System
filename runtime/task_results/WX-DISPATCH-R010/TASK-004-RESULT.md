# TASK-004 RESULT

## 修改了什么

实现 React Orders / Dispatch / Calendar 页面。Orders 使用订单 API 展示大表；Dispatch 展示未分配订单、司机、车辆、已分配订单池并支持派车动作；Calendar 展示车辆纵向、时间横向的 24h 矩阵。

## 涉及文件

- `frontend/src/pages/OrdersPage.tsx`
- `frontend/src/pages/DispatchPage.tsx`
- `frontend/src/pages/CalendarPage.tsx`
- `frontend/src/components/CalendarMatrix.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式

- `npm.cmd run build`
- `python scripts/verify_orders_api.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_calendar_api.py`
- 截图：`docs/ui_screenshots/dispatch-react.png`
- 截图：`docs/ui_screenshots/calendar-react.png`

## 是否完成

DONE

## 风险

- Calendar 本轮不做拖拽、不做地图、不做复杂 scheduler；30d/week 数据入口已接 API，当前视觉重点先完成 24h 车辆矩阵。

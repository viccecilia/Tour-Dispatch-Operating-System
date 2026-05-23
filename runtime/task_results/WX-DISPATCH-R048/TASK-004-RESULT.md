# TASK-004：dashboard 与调度端显示车辆状态

## 修改了什么
- `/api/dashboard/summary` 增加车辆状态统计：
  - `available_vehicles`
  - `outbound_vehicles`
  - `in_service_vehicles`
  - `returned_vehicles`
  - `vehicle_status`
- Dispatch 已分配订单池增加“车辆状态”列。
- Driver Monitor 增加车辆出库、服务中、已入库统计，并在司机任务行显示车辆状态 badge。
- Dashboard 首页增加车辆出库 KPI。

## 涉及文件
- `backend/services/dashboard_service.py`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DispatchPage.tsx`
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/types/api.ts`

## 验证方式
- `npm run build`
- `npm run lint`
- `python scripts/verify_dispatch_api.py`
- 验证项：`dashboard_vehicle_status` 返回车辆状态统计。

## 是否完成
DONE

## 风险
- 视觉上仍需人工检查 Dashboard KPI 的信息密度是否合适。

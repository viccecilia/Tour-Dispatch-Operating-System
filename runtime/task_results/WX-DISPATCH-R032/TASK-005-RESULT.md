# TASK-005 在线状态与地图刷新

## 修改了什么
- 后端对最新位置计算 `online_status`。
- Map 页面每 5 秒自动刷新。
- Driver Monitor 继续使用最新位置 API，并修复 queryFn 类型问题。

## 涉及文件
- `backend/services/location_service.py`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `python scripts/verify_driver_api.py`
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 没有 WebSocket，刷新粒度是 5 秒 polling。

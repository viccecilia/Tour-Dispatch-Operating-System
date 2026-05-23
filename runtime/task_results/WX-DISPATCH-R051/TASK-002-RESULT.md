# TASK-002 司机实时位置刷新与 latest location

## 修改了什么
- 扩展 `/api/fleet/latest-locations` 返回字段。
- latest location 现在包含车辆状态、派车状态、订单执行状态、结算状态、当前订单号和路线信息。
- 支持按 `vehicle_status` 过滤。

## 涉及文件
- `backend/services/location_service.py`
- `backend/api/routes.py`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/health_check.py`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 刷新方式为前端 5 秒 polling，不使用 WebSocket。

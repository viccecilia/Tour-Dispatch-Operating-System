# TASK-003：最新位置查询与车辆在线状态

## 修改了什么
- 新增 `GET /api/fleet/latest-locations`。
- 新增 `GET /api/driver/locations`。
- 最新位置返回司机、车辆、订单、坐标、位置文字、上报时间和 `online_status`。
- 15 分钟内位置视为 `online`，否则为 `stale`。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`

## 验证方式
- 位置 smoke：
  - `latest_count = 2`
  - `latest_has_driver = true`
  - `driver_log_count = 2`
  - `online_status = online`

## 是否完成
DONE

## 风险
- 在线状态基于最后上报时间，不是 WebSocket 心跳。

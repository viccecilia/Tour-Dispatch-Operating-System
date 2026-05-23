# TASK-001 location_logs 与位置服务

## 修改了什么
- 保留 `location_logs` 作为司机位置日志表。
- 新增轻量车队位置服务，提供司机最新位置、位置列表和车队位置摘要。
- `/api/fleet/latest-locations` 支持 `driver_id`、`online_status`、`limit` 查询。
- 新增 `/api/fleet/location-summary`。

## 涉及文件
- `backend/services/location_service.py`
- `backend/api/routes.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`
- 手动请求 `/api/fleet/latest-locations?limit=5`
- 手动请求 `/api/fleet/location-summary`

## 是否完成
DONE

## 风险
- 当前在线状态按最后上报时间 15 分钟内判断，后续可配置。

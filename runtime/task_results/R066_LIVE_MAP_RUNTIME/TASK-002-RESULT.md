# TASK-002 结果：Assignment Overlay

## 修改了什么
- 地图页增加“订单覆盖层”。
- 从 `/api/fleet/latest-locations` 读取 `assignment_id`、`order_id`、订单号、时间、起终点和司机车辆信息。
- 右侧展示正在执行或最新上报位置关联的派车任务。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `scripts/verify_live_map_runtime.py`

## 验证方式
- `python scripts/verify_live_map_runtime.py`
  - 验证 `assignment_overlay_visible = true`
  - 验证 `latest_has_assignment_overlay`
  - 验证 `latest_has_order_overlay`

## 是否完成
DONE

## 风险
- 如果司机端不上报 `assignment_id/order_id`，覆盖层只能显示司机位置，不能精确关联订单。

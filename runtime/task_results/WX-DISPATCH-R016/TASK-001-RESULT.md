# TASK-001：订单按时间排序

## 修改了什么
- 增强 `route_suggestion`，输出按 `order_date + start_time + pickup_location + id` 排序后的订单顺序。
- 保持调度安全原则：不把晚时间订单排到早时间订单前面。

## 涉及文件
- `backend/services/dispatch_service.py`

## 验证方式
- `python scripts/verify_dispatch_api.py`
- 额外调用 `GET /api/dispatch/route-suggestion` 验证返回多订单顺序。

## 是否完成
DONE

## 风险
- 当前只按文本时间排序，不做地图路程计算。

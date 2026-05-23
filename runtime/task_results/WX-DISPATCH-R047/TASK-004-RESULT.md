# TASK-004：Dashboard 联动统计

## 修改了什么
- `/api/dashboard/summary` 增加：
  - `assigned_unconfirmed_orders`
  - `confirmed_driver_count`
- 统计范围为今日及未来 active assignments，便于第二天订单提前确认。

## 涉及文件
- `backend/services/dashboard_service.py`
- `frontend/src/types/api.ts`

## 验证方式
- `python scripts/verify_dispatch_api.py`
- 验证项：
  - `dashboard_assigned_unconfirmed_orders_after_confirm`
  - `dashboard_confirmed_driver_count_after_confirm`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- React Dashboard 页面本轮没有大改，只补了 API 字段和 Dispatch 页面即时统计；如需要首页 KPI 展示，可下一轮专门调整。

# TASK-005 结果

状态：DONE

修改了什么：

- `/api/dashboard/summary` 接入真实订单统计。
- dashboard 首页四项指标更新为：
  - 今日订单数
  - 未分配订单数
  - 待结算订单数
  - 价格缺失订单数
- 小程序首页同步显示上述四项指标。
- 无订单时返回 0。

涉及文件：

- `backend/services/dashboard_service.py`
- `backend/api/routes.py`
- `miniapp/pages/index/index.js`
- `miniapp/pages/index/index.wxml`

验证方式：

- `python scripts/verify_orders_api.py`
- `GET /api/dashboard/summary`

是否完成：是

风险：

- “待结算”目前按 `settlement_status = 'pending'` 统计，不做财务结算计算。

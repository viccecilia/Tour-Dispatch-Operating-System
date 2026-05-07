# TASK-005 结果

状态：DONE

修改了什么：

- `/api/dashboard/summary` 增加派车统计：
  - 今日订单数
  - 未分配订单数
  - 已分配订单数
  - 待结算订单数
  - 价格缺失订单数
  - 可用司机数
  - 可用车辆数
- 后端 dashboard HTML 首页同步展示上述指标。
- 小程序首页同步展示上述指标。

涉及文件：

- `backend/services/dashboard_service.py`
- `backend/api/routes.py`
- `miniapp/pages/index/index.js`
- `miniapp/pages/index/index.wxml`

验证方式：

- `python scripts/verify_dispatch_api.py`
- `GET /api/dashboard/summary`

是否完成：是

风险：

- 可用司机/车辆按基础状态统计，不代表复杂班次排班能力。

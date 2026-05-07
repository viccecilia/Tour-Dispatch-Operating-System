# TASK-005 结果

状态：DONE

修改了什么：

- 更新 `/api/dashboard/summary` 今日派车摘要：
  - 今日订单数
  - 今日已派车数
  - 今日未派车数
  - 今日异常数
  - 今日未结算数
  - 可用车辆数
  - 可用司机数
- 后端 dashboard HTML 首页同步正常中文展示。
- 小程序首页同步显示 R004 摘要字段。

涉及文件：

- `backend/services/dashboard_service.py`
- `backend/api/routes.py`
- `miniapp/pages/index/index.js`
- `miniapp/pages/index/index.wxml`

验证方式：

- `python scripts/verify_calendar_api.py`
- `GET /api/dashboard/summary`

是否完成：是

风险：

- 今日异常数依赖 `orders.dispatch_status = 'exception'`，本轮没有新增异常录入流程。

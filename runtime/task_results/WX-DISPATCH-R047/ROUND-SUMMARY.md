# WX-DISPATCH-R047 总结

## 本轮完成内容
- 建立调度端到司机端的确认闭环：
  - 派车后 assignment 自动进入司机端。
  - 司机端新增“明日订单”显示未来已派未确认订单。
  - 司机确认接单后状态从 `assigned` 进入 `confirmed`。
  - 调度端已分配订单池能看到“未确认 / 已确认”。
  - Dashboard summary 返回已派未确认与已确认司机统计。

## 修改文件
- `backend/services/dashboard_service.py`
- `frontend/src/pages/DispatchPage.tsx`
- `frontend/src/types/api.ts`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `scripts/verify_dispatch_api.py`
- `scripts/verify_driver_api.py`

## 验证结果
- `node --check miniapp/pages/driver/index.js`：通过
- `python -m compileall backend scripts`：通过
- `python scripts/reset_demo_db.py`：通过
- `python scripts/health_check.py`：通过
- `python scripts/verify_dispatch_api.py`：通过
- `python scripts/verify_driver_api.py`：通过
- `cd frontend && npm run build`：通过
- `cd frontend && npm run lint`：通过
- 浏览器验证 `http://127.0.0.1:5173/#dispatch`：已看到“已派未确认 / 已确认司机 / 司机确认”

## 协作验收
- 需要在微信开发者工具或真机中确认：
  - 明日订单是否能在司机首页看到。
  - 点击明日订单后，底部确认接单按钮是否符合司机习惯。
  - 调度端是否在司机确认后及时显示为已确认。

## 未完成/风险
- 本轮没有新增独立“明日订单”数据库表，使用 active assignment + order_date 生成视图。
- React Dashboard 首页未新增可视 KPI，仅 API 已返回字段，Dispatch 页面已显示联动统计。
- 刷新方式仍是轮询，不是 WebSocket。

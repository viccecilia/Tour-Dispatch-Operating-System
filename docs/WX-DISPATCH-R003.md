# WX-DISPATCH-R003 派车核心链路

本轮新增轻量派车主链路：

- 未分配订单查询
- 可用司机/车辆查询
- 批量派车
- 写入 assignments
- 同步 `orders.dispatch_status`
- 取消分配
- 重新分配并保留历史 assignment
- 简单时间冲突检测
- 简单地点接龙建议

后端 API：

- `GET /api/dispatch/unassigned-orders`
- `GET /api/dispatch/drivers`
- `GET /api/dispatch/vehicles`
- `POST /api/dispatch/assign`
- `POST /api/dispatch/cancel`
- `POST /api/dispatch/reassign`
- `GET /api/dispatch/assignments`
- `GET /api/dispatch/route-suggestion`

本轮不包含派车日历、拖拽日历、司机端闭环、定位、地图和财务结算计算。

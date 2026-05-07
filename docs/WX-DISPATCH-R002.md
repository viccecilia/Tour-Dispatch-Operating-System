# WX-DISPATCH-R002 订单录入与订单大表

本轮在 R001 基础上新增订单主链路第一步：

- 手工新增订单
- 订单列表和筛选
- 订单编辑
- 订单软删除
- dashboard 订单统计

后端 API：

- `GET /api/orders`
- `POST /api/orders`
- `GET /api/orders/{id}`
- `PUT /api/orders/{id}`
- `DELETE /api/orders/{id}`

删除只设置 `is_deleted = 1`，不物理删除订单。

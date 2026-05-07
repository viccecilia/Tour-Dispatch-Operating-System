# TASK-002 结果

状态：DONE

修改了什么：

- 新增订单服务层，支持订单列表、详情、新增、编辑、软删除。
- 新增订单 API：
  - `GET /api/orders`
  - `POST /api/orders`
  - `GET /api/orders/{id}`
  - `PUT /api/orders/{id}`
  - `DELETE /api/orders/{id}`
- `GET /api/orders` 支持 `order_date`、`agency_id`、`agency_name`、`dispatch_status`、`settlement_status`、`keyword` 筛选。
- 删除只设置 `is_deleted = 1`。

涉及文件：

- `backend/services/order_service.py`
- `backend/api/routes.py`

验证方式：

- `python scripts/verify_orders_api.py`

是否完成：是

风险：

- 本轮未做鉴权中间件保护订单 API，保持 R001 的轻量 API 风格。

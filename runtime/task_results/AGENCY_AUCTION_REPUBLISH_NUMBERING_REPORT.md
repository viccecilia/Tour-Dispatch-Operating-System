# 旅行社订单大厅再发布编号验证报告

## 业务规则

- 旅行社订单本体号 `orders.oid` 生成后保持不变。
- 每一次进入订单大厅都生成新的大厅发布记录 `auction_listings`。
- 大厅发布记录新增：
  - `listing_code`：大厅发布号，格式为 `{订单号}-H{发布日期YYMMDD}-{当日发布流水3位}`。
  - `publish_round`：同一订单第几次发布。
- 自动超时无人接单时：
  - 发布记录状态为 `expired`。
  - 订单状态为 `auction_expired`。
  - 旅行社端显示为“超时撤回”。
  - 可再次发布。
- 旅行社主动撤回时：
  - 发布记录状态为 `cancelled`。
  - 订单状态为 `auction_cancelled`。
  - 旅行社端显示为“已撤回”。
  - 可再次发布。
- 再次发布不覆盖历史发布记录，不改变订单本体号。

## 修改文件

- `backend/db/schema.sql`
- `backend/services/auction_service.py`
- `backend/services/agency_portal_service.py`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`
- `frontend/src/pages/AuctionHallPage.tsx`
- `frontend/src/components/StatusBadge.tsx`

## 本地数据链验证

测试流程：

1. 创建旅行社订单。
2. 第一次发布到订单大厅。
3. 强制过期并刷新超时状态。
4. 第二次发布。
5. 主动撤回。
6. 第三次发布。

验证结果：

- 订单本体号保持不变：`oid_stable=True`。
- 超时后订单状态：`auction_expired`。
- 主动撤回后订单状态：`auction_cancelled`。
- 三次发布号：
  - `A260610-0001-TMP-H260531-001`
  - `A260610-0001-TMP-H260531-002`
  - `A260610-0001-TMP-H260531-003`
- 三次发布轮次：`1, 2, 3`。
- 历史记录保留：`expired -> cancelled -> listed`。

## 验证命令

- `python -m py_compile backend\services\auction_service.py backend\services\agency_portal_service.py backend\db\database.py backend\api\routes.py`
- `npm.cmd run build`
- 本地后端重启后 `GET http://127.0.0.1:18765/api/ping`
- 浏览器检查 `http://127.0.0.1:5173/#agency-portal`

## 浏览器验证

- 旅行社“订单大厅”可见“超时撤回”。
- 旅行社“订单大厅”可见“已撤回”。
- “我的订单”和大厅列表可见大厅发布号，例如 `A260530-0006-TMP-H260530-001`。
- 旧发布记录会非破坏性补齐发布号，不改订单号、不删除历史。

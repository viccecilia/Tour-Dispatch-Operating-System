# 旅行社订单大厅撤回与变更确认测试报告

## 范围

- 订单进入订单大厅但未被接单时，旅行社可直接撤回大厅发布。
- 订单已被接单或已派单后，旅行社不能直接撤回或直接修改关键字段。
- 旅行社可提交修改申请或撤销申请，车公司端确认后生效。
- 撤销申请计算费用策略：
  - 距订单开始时间超过 24 小时，且本月免费撤销未超过 10 单：车公司确认后免费撤销。
  - 不满足免费条件、短时或强制取消：按策略显示 50% 或 100% 费用。
  - 距开始时间 6 小时内强制取消：按全额费用处理。

## 修改文件

- `backend/services/agency_portal_service.py`
- `backend/api/routes.py`
- `backend/db/schema.sql`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`
- `frontend/src/pages/AuctionHallPage.tsx`

## 新增数据结构

- `agency_order_change_requests`
  - 保存旅行社修改/撤销申请。
  - 保存申请类型、状态、修改字段、取消费用比例、取消费用金额、免费额度使用标记、车公司确认信息。

## 接口

- `GET /api/agency-portal/change-requests`
- `POST /api/agency-portal/orders/{order_id}/withdraw`
- `POST /api/agency-portal/orders/{order_id}/change-requests`
- `GET /api/auction/change-requests?status=pending`
- `POST /api/auction/change-requests/{request_id}/review`

## 本地验证

- `python -m py_compile backend\services\agency_portal_service.py backend\api\routes.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，为既有体积警告。

## 隔离数据库链路验证

测试库：

- `runtime/test_dbs/agency_withdraw_request.sqlite3`

验证步骤：

1. 旅行社创建订单并发布到订单大厅。
2. 未接单状态下，旅行社直接撤回大厅发布。
3. 再创建订单并发布到大厅。
4. 车公司接单。
5. 旅行社尝试直接撤回，被拒绝并返回 `order_already_claimed_requires_carrier_confirmation`。
6. 旅行社提交关键字段修改申请。
7. 车公司端同意修改申请。
8. 订单关键字段更新成功。
9. 旅行社提交撤销申请。
10. 系统计算超过 24 小时且免费额度未满，费用比例为 `0%`。
11. 车公司端同意撤销申请。
12. 订单状态变为 `agency_cancelled`。

验证结果：

- 未接单大厅撤回：通过。
- 已接单禁止直接撤回：通过。
- 已接单修改需申请并由车公司确认：通过。
- 撤销申请费用策略计算：通过。
- 车公司确认后订单取消：通过。

## 浏览器验证

- `http://127.0.0.1:5173/#agency-portal`
  - 已渲染 `变更/撤回` 页签。
- `http://127.0.0.1:5173/#auction`
  - 页面需要车公司后台登录；本次未使用真实车公司账号登录验证。
  - 前端构建已验证车公司确认面板类型与渲染代码可编译。

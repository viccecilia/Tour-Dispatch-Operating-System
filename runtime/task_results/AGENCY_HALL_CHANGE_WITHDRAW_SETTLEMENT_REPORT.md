# 订单大厅我的订单 / 变更撤回 / 结算联动报告

## 需求

- 变更和撤回应放在订单大厅中。
- 订单大厅下面要有“我的订单”分类，可查看多种状态订单。
- “我的订单”要有筛选，默认进行中订单排在最上方。
- 增加费用结算：车公司跑完订单后发起付款请求，旅行社付款并上传回执，车公司确认收款后订单完成。

## 修改文件

- `frontend/src/pages/AgencyPortalPage.tsx`
  - 移除顶部独立“变更/撤回”导航入口。
  - 在订单大厅内新增“我的订单”处理区。
  - “我的订单”支持筛选：进行中、全部、发布中、已接单、流拍、待结算、已完成。
  - “我的订单”默认按进行中优先排序。
  - 未接单的大厅订单可直接撤回。
  - 已接单订单可在“我的订单”中提交修改、撤销、强制取消申请，由车公司确认。
  - 已完成收款订单禁用变更/撤回。
  - 新增“费用结算”区：旅行社查看付款请求、上传付款回执、查看已上传回执。
- `frontend/src/pages/AuctionHallPage.tsx`
  - 新增“车公司结算联动”区。
  - 车公司可对已接单 / 已成交订单发起付款请求。
  - 旅行社上传回执后，车公司可确认收款。
- `frontend/src/services/apiClient.ts`
  - 新增旅行社付款回执上传接口。
  - 新增车公司发起付款请求、确认收款接口。
- `frontend/src/types/api.ts`
  - 补充订单和大厅列表的结算联动字段。
- `frontend/src/components/StatusBadge.tsx`
  - 补充 `payment_requested`、`receipt_uploaded`、`paid` 状态展示。
- `backend/services/agency_portal_service.py`
  - 新增订单级结算字段初始化。
  - 新增车公司发起付款请求。
  - 新增旅行社上传付款回执。
  - 新增车公司确认收款，订单完成。
  - 旅行社订单列表返回结算联动字段。
- `backend/services/auction_service.py`
  - 订单大厅列表返回结算状态、付款请求、回执字段。
- `backend/api/routes.py`
  - 新增 `/api/agency-portal/orders/{id}/payment-receipt`。
  - 新增 `/api/auction/orders/{id}/payment-request`。
  - 新增 `/api/auction/orders/{id}/confirm-payment`。
- `backend/db/database.py`
- `backend/db/schema.sql`
  - 追加结算联动字段。
- `backend/services/finance_service.py`
  - 允许 `payment_requested`、`receipt_uploaded` 作为旅行社结算状态。

## 本地验证

### 编译与构建

命令：

```powershell
python -m py_compile backend\services\agency_portal_service.py backend\services\auction_service.py backend\api\routes.py backend\db\database.py backend\services\finance_service.py
npm.cmd run build
```

结果：

- Python 编译通过。
- 前端 TypeScript + Vite 构建通过。
- Vite 仍提示 chunk 超过 500 kB，这是既有体积提示，不阻断构建。

### 结算链路服务测试

测试库：

- `runtime/test_dbs/agency_hall_change_settlement.sqlite3`

测试链路：

1. 创建旅行社。
2. 创建订单。
3. 旅行社发布到订单大厅。
4. 车公司接单。
5. 旅行社在“我的订单”提交修改申请。
6. 车公司发起付款请求。
7. 旅行社上传付款回执 `receipt-test.pdf`。
8. 车公司确认收款。

结果：

- 修改申请可在旅行社侧查询。
- 付款请求后订单状态为 `payment_requested`。
- 上传回执后订单状态为 `receipt_uploaded`。
- 车公司确认后订单状态为 `paid`，执行状态为 `completed`。

### 浏览器验证

旅行社后台：

- `http://127.0.0.1:5173/#agency-portal`

验证结果：

- 订单大厅中出现“我的订单”区。
- “我的订单”出现筛选：进行中、全部、发布中、已接单、流拍、待结算、已完成。
- 点击“全部”可看到测试订单 `A260621-0001-TMP`。
- 测试订单下方出现处理区和修改 / 撤销申请记录。
- “费用结算”区显示 `receipt-test.pdf`、查看链接和已收款状态。

车公司端订单大厅：

- `http://127.0.0.1:5173/#auction-hall`

验证结果：

- 页面出现“车公司结算联动”区。
- 测试订单显示 `JP¥170,000`、`receipt-test.pdf`。
- 已确认收款订单显示“已收款完成”，发起付款请求和确认收款按钮禁用。

截图：

- `runtime/task_results/agency_hall_my_orders_settlement_browser.png`
- `runtime/task_results/carrier_payment_request_confirm_browser.png`

## 安全边界

- 未做云端部署。
- 未 Git push。
- 未上传小程序。
- 未清理或修改生产数据。
- 本轮验证使用临时本地测试库，不处理原本 `runtime/wx_dispatch.sqlite3` 的 `orders.oid` 冲突。

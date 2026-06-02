# 旅行社我的大厅订单与日历状态测试报告

## 范围

- 旅行社订单大厅新增 `我的大厅订单`。
- `我的大厅订单` 包含旅行社自己发布到大厅的订单。
- 显示发布中、已接单、流拍等大厅状态。
- 拍卖截止后无人接单时自动标记为流拍：
  - `auction_listings.status = expired`
  - `orders.dispatch_status = auction_expired`
  - `orders.execution_status = auction_expired`
- 旅行社日历显示大厅状态和拍卖截止时间。

## 修改文件

- `backend/services/auction_service.py`
- `backend/services/agency_portal_service.py`
- `frontend/src/types/api.ts`
- `frontend/src/components/StatusBadge.tsx`
- `frontend/src/pages/AgencyPortalPage.tsx`

## 本地验证

- `python -m py_compile backend\services\auction_service.py backend\services\agency_portal_service.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，为既有体积警告。

## 隔离数据库验证

测试库：

- `runtime/test_dbs/agency_my_hall_calendar.sqlite3`

验证步骤：

1. 创建旅行社。
2. 创建两条旅行社订单。
3. 发布第一条到大厅，保持 `listed`。
4. 发布第二条到大厅，并手动把 `expires_at` 调整到过去。
5. 调用大厅列表刷新逻辑。
6. 调用旅行社订单列表。

验证结果：

- 第一条订单返回 `auction_status=listed`。
- 第二条订单自动返回 `auction_status=expired`。
- 第二条订单同步返回 `dispatch_status=auction_expired`。
- 公开大厅 `listed` 列表不再包含流拍订单。
- 旅行社订单列表返回 `auction_listing_id / auction_published_at / auction_expires_at / auction_bid_count / auction_current_bid_jpy`，可供我的大厅订单和日历使用。

## 浏览器验证

- `http://127.0.0.1:5173/#agency-portal`
- 旅行社登录后：
  - `订单大厅` 页签显示 `我的大厅订单`。
  - `我的大厅订单` 显示 `发布中`、`流拍` 统计标签。
  - `日历` 页签可正常打开，并显示当天行程。

## 未执行事项

- 未进行云端部署。
- 未修改生产数据库。
- 未 Git push。
- 未上传小程序。

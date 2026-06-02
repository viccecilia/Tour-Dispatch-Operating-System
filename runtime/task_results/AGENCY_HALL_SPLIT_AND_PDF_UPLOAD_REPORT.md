# 订单大厅分区与旅行社 PDF 行程上传测试报告

## 范围

- 订单大厅按业务类型拆成：
  - 机场接送
  - 包车 / 复杂行程
- 机场接送公开摘要保持轻量字段。
- 包车订单支持旅行社上传标准 PDF 行程文件。
- PDF 不进入公开大厅字段；公开大厅只显示是否有 PDF。
- 完整 PDF URL、导游信息、游客联系方式仅在关联方完整详情里返回。

## 修改文件

- `backend/db/schema.sql`
- `backend/db/database.py`
- `backend/services/order_service.py`
- `backend/services/auction_service.py`
- `backend/services/agency_portal_service.py`
- `backend/api/routes.py`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`
- `frontend/src/pages/AuctionHallPage.tsx`

## 新增字段

- `orders.guide_name`
- `orders.guide_phone`
- `orders.guide_wechat`
- `orders.guide_line`
- `orders.guide_whatsapp`
- `orders.itinerary_pdf_url`
- `orders.itinerary_pdf_name`

## 新增接口

- `POST /api/agency-portal/orders/{order_id}/itinerary-pdf`
  - 旅行社上传 PDF 行程文件。
  - 仅接受 PDF。
  - 文件保存到 `runtime/uploads/agency_itineraries/`。
- `GET /api/auction/listings/{listing_id}/detail`
  - 关联车公司查看已接单/已成交后的完整订单详情。
  - 完整详情包含 PDF URL、导游信息、游客联系方式等。

## 本地验证

- `python -m py_compile backend\services\auction_service.py backend\services\agency_portal_service.py backend\services\order_service.py backend\api\routes.py backend\db\database.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，为既有体积警告。

## 隔离数据库验证

测试库：

- `runtime/test_dbs/agency_hall_split_pdf.sqlite3`

验证步骤：

1. 创建旅行社。
2. 创建包车订单，写入游客联系方式、导游电话、微信、Line、WhatsApp 和私密备注。
3. 上传标准 PDF 行程文件。
4. 发布包车订单到大厅，拍卖时间为 `4` 小时。
5. 创建机场接送订单并发布到大厅。
6. 查询公开大厅列表。
7. 查询关联方完整详情。

验证结果：

- 公开大厅有 2 条订单。
- 公开大厅包车订单仅显示 `has_itinerary_pdf=true`。
- 公开大厅不返回游客联系方式、导游联系方式、PDF URL、私密备注。
- 关联方详情返回 PDF URL、游客联系方式和导游联系方式。

## 浏览器验证

- `http://127.0.0.1:5173/#agency-portal`
- 登录旅行社门户后，打开 `订单大厅` 页签：
  - 已显示 `机场接送` 分区。
  - 已显示 `包车 / 复杂行程` 分区。
  - 已显示 `标准行程 PDF` 上传入口。

## 未执行事项

- 未进行云端部署。
- 未修改生产数据库。
- 未 Git push。
- 未上传小程序。

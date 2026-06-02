# 订单大厅公开字段与拍卖时长测试报告

## 范围

- 订单大厅公开列表只暴露订单基础信息。
- 公开列表可展示价格、起止日期时间、主要行程、车型、人数/行李摘要和拍卖截止时间。
- 公开列表不暴露旅行社担当电话、微信、Line、WhatsApp、导游联系人、游客联系方式、完整备注。
- 旅行社发布大厅时可选择 `1 / 2 / 4` 小时拍卖时长。

## 修改文件

- `backend/services/auction_service.py`
- `backend/services/agency_portal_service.py`
- `backend/api/routes.py`
- `backend/db/schema.sql`
- `backend/db/database.py`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`
- `frontend/src/pages/AuctionHallPage.tsx`

## 新增/扩展字段

- `orders.guide_name`
- `orders.guide_phone`
- `orders.guide_wechat`
- `orders.guide_line`
- `orders.guide_whatsapp`
- `agencies.contact_wechat`
- `agencies.contact_line`
- `agencies.contact_whatsapp`

这些字段用于成交/接单后的完整订单详情，不进入公开大厅列表。

## 接口变化

- 大厅列表 `list_auction_listings()` 改为公开摘要输出。
- `POST /api/agency-portal/orders/{order_id}/publish-auction`
  - 支持旅行社发布自己的未派订单到大厅。
  - `auction_duration_hours` 只允许 `1 / 2 / 4`。
- `GET /api/agency-portal/auction-listings?status=listed`
  - 旅行社可查看公开大厅摘要。

## 本地验证

- `python -m py_compile backend\services\auction_service.py backend\services\agency_portal_service.py backend\api\routes.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，为既有体积警告。

## 隔离数据库验证

测试库：

- `runtime/test_dbs/agency_public_hall.sqlite3`

验证步骤：

1. 创建带敏感联系方式的旅行社。
2. 创建带游客联系方式、导游电话、导游微信/Line/WhatsApp、完整备注的订单。
3. 旅行社发布该订单到公开大厅，拍卖时长选择 `2` 小时。
4. 查询旅行社公开大厅列表。
5. 检查公开列表字段。

验证结果：

- 公开列表包含：
  - 订单 ID / OID
  - 日期、开始/结束时间
  - 起点、终点
  - 订单类型、车型
  - 人数、行李数
  - 起拍价、一口价、当前价
  - 发布时间、截止时间、拍卖时长
- 公开列表不包含：
  - `guest_name`
  - `guest_contact`
  - `guide_name`
  - `guide_phone`
  - `guide_wechat`
  - `agency_name`
  - `remark`
  - `seller_company_name`
  - `buyer_company_name`
  - `note`
- `auction_duration_hours = 2` 验证通过。

## 未部署事项

- 未进行云端部署。
- 未修改生产数据库。
- 未 Git push。
- 未上传小程序。

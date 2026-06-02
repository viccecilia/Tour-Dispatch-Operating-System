# 小程序端真实格式订单联动测试报告

测试日期：2026-05-30  
测试服务：`http://127.0.0.1:18766`  
测试数据库：`runtime/test_dbs/real_order_auction_sync.sqlite3`  
测试边界：本地隔离库，不连接云端，不上传小程序，不改生产数据库。

## 1. 测试目标

验证一条真实格式订单从旅行社录入开始，到进入订单大厅，再到被车公司一口价拍下为止，数据在 Web、调度小程序、司机小程序相关接口中的联动情况。

## 2. 本次补充

为跑完整链路，补充了订单大厅成交动作：

- `POST /api/auction/listings/{id}/claim`
- 更新 `auction_listings.status = claimed`
- 写入 `buyer_tenant_id`
- 写入成交价到 `current_bid_jpy`
- 写入 `sold_at`
- 同步订单状态：`orders.dispatch_status = auction_claimed`
- 同步执行状态：`orders.execution_status = auction_claimed`
- 调度小程序 API 封装增加 `claimAuctionListing`

## 3. 测试数据

旅行社：

- 名称：`真实联动旅行社 1780145554`
- Portal code：测试脚本自动创建

订单：

- 订单号：`A260530-0001-TMP`
- 日期：2026-05-30
- 时间：09:35-11:05
- 起点：Kansai International Airport T1
- 终点：Osaka Namba Swissotel
- 类型：airport_transfer
- 车型：Hiace
- 人数：4
- 行李：5
- 客人：`REAL-LINK-Zhang-1780145554`
- 联系方式：080-1111-2222
- 旅行社报价：JPY 52,000

订单大厅：

- 起拍价：JPY 41,000
- 一口价：JPY 47,000
- 买方车公司租户：tenant 2

## 4. 数据链路结果

| 步骤 | 接口 / 端 | 结果 | 说明 |
| --- | --- | --- | --- |
| 后端健康检查 | `GET /api/ping` | 通过 | 本地服务正常 |
| 旅行社门户登录 | `POST /api/agency-portal/login` | 通过 | 获取旅行社 token |
| 旅行社订单录入 | `POST /api/agency-portal/orders` | 通过 | 创建订单 id `1` |
| 旅行社 Web 我的订单 | `GET /api/agency-portal/orders` | 通过 | 可看到新订单 |
| 管理端订单详情 | `GET /api/orders/1` | 通过 | 管理端可看到订单 |
| 调度小程序共享状态 | `GET /api/dispatch-mobile/shared-state` | 通过 | 可获取共享数据状态 |
| 调度小程序个人未派队列 | `GET /api/dispatch-mobile/unassigned-orders` | 未显示该订单 | 原因见第 6 节 |
| 发布订单大厅 | `POST /api/auction/listings` | 通过 | listing id `1` |
| 调度小程序订单大厅围观 | `GET /api/auction/listings?status=listed` | 通过 | 可看到待拍订单 |
| 车公司拍下 | `POST /api/auction/listings/1/claim` | 通过 | 状态变为 `claimed` |
| 调度小程序已成交围观 | `GET /api/auction/listings?status=claimed` | 通过 | 可看到已成交 listing |
| 待拍列表移除 | `GET /api/auction/listings?status=listed` | 通过 | 成交后不再出现在待拍列表 |
| 订单状态写回 | `GET /api/orders/1` | 通过 | `auction_claimed / auction_claimed` |
| 司机小程序任务获取 | `GET /api/driver/assignments`、`GET /api/driver/workbench` | 通过 | 接口可获取数据 |
| 司机小程序是否看到未分配大厅订单 | 司机任务接口 | 正常不可见 | 未派给司机前不应显示 |

## 5. 小程序端围观情况

### 调度小程序 `miniapp_dispatch`

正常获取到：

- 登录态：通过
- 共享状态：通过
- 订单大厅待拍列表：通过
- 订单大厅成交列表：通过
- 成交后待拍列表移除：通过

需要注意：

- `pages/auction/index` 当前主要是发布和围观订单大厅。
- 本次新增了 `claimAuctionListing` API 封装，但页面按钮层还没有做“车公司一口价拍下”的前端按钮。
- 如果要让车公司真的在小程序里点击拍下，需要再补页面按钮和权限文案。

### 司机小程序 `miniapp`

正常获取到：

- `GET /api/driver/assignments`
- `GET /api/driver/workbench`

符合预期：

- 订单进入大厅或被车公司拍下后，还没有分配给具体司机。
- 因此司机小程序不应该看到这条订单。
- 本次检测结果：司机端没有错误显示，也没有越权看到未分配订单。

### 旅行社 Web

正常获取到：

- 旅行社登录
- 订单录入
- 我的订单列表

## 6. 发现的问题 / 差异

### P1：调度小程序个人未派队列看不到旅行社 Web 录入的订单

现象：

- 旅行社 Web 录入订单后，`GET /api/dispatch-mobile/unassigned-orders?dispatcher_id=...` 没有返回该订单。

原因：

- 当前调度小程序个人未派队列按 `created_by_dispatcher_id = 当前调度员` 过滤。
- 旅行社门户订单没有 `created_by_dispatcher_id`。

影响：

- 订单可以进入订单大厅，也能在共享状态/管理端看到。
- 但调度员个人“未派订单”页看不到旅行社直接录入的订单。

建议：

- 增加一个“旅行社新订单池”或“公共未派池”入口。
- 或调整调度小程序未派队列：允许显示 `created_by_dispatcher_id IS NULL AND order_source = agency_portal` 的订单。
- 不建议直接去掉 `created_by_dispatcher_id` 过滤，否则会破坏调度员个人工作队列边界。

### P2：订单大厅成交按钮还未接入小程序页面

现象：

- 后端成交接口已经可用。
- `miniapp_dispatch/utils/api.js` 已有 `claimAuctionListing`。
- `miniapp_dispatch/pages/auction/index` 页面还没有“拍下/一口价接单”按钮。

建议：

- 在订单大厅列表行增加按钮：一口价拍下。
- 点击后调用 `claimAuctionListing(listingId, { buyer_tenant_id, claim_price_jpy })`。
- 成功后刷新待拍列表和已成交列表。

## 7. 验证输出摘要

关键输出：

```json
{
  "ok": true,
  "created_order": {
    "id": 1,
    "oid": "A260530-0001-TMP",
    "dispatch_status_initial": "unassigned"
  },
  "auction": {
    "listing_id": 1,
    "listed_visible_in_dispatch_miniapp": true,
    "claim_status": "claimed",
    "buyer_tenant_id": 2,
    "claimed_visible_in_dispatch_miniapp": true,
    "no_longer_in_listed_after_claim": true,
    "order_dispatch_status_after_claim": "auction_claimed"
  },
  "miniapp_watch": {
    "agency_web_orders_visible": true,
    "dispatch_mobile_shared_state_ok": true,
    "dispatch_mobile_personal_unassigned_visible": false,
    "dispatch_mobile_auction_list_visible": true,
    "driver_miniapp_fetch_ok": true,
    "driver_miniapp_order_visible_before_assignment": false
  }
}
```

## 8. 结论

真实格式订单链路在本地隔离环境中跑通：

- 旅行社录入订单：正常。
- 旅行社订单列表：正常。
- 订单发布到大厅：正常。
- 调度小程序订单大厅围观：正常。
- 车公司拍下：正常。
- 成交状态写回订单：正常。
- 成交后待拍列表移除：正常。
- 司机小程序不越权看到未分配订单：正常。

唯一需要补的业务入口是：调度小程序个人未派队列目前看不到旅行社直接录入的订单。建议新增公共订单池或旅行社新订单池，而不是直接破坏调度员个人队列过滤。

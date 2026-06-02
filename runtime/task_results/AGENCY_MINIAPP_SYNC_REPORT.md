# 旅行社小程序端同步报告

## 范围
- 新增独立小程序目录：`miniapp_agency/`
- 不改动车公司小程序目录：`miniapp_dispatch/`
- 不改动司机端/旧通用小程序目录：`miniapp/`
- 未执行云端部署、未上传小程序、未修改生产数据、未 Git push

## 新增页面
- `pages/index/index`：旅行社登录、接口环境切换、订单统计、快捷入口
- `pages/orders/index`：机场接送批量解析、包车批量解析、单条包车解析、解析预览、批量导入
- `pages/hall/index`：订单大厅、我的订单筛选、发布大厅、未接单撤回、已接单变更/撤销申请、付款回执上传、申请记录
- `pages/tracking/index`：订单跟踪、司机/车辆信息、地图位置、标准行程 PDF 上传和查看
- `pages/calendar/index`：旅行社日历，按日期展示发布中、已接单、待结算、已完成等状态

## 接口联动
- `GET /api/agency-portal/agencies`
- `POST /api/agency-portal/login`
- `GET /api/agency-portal/orders`
- `POST /api/agency-portal/orders/parse`
- `POST /api/agency-portal/orders`
- `GET /api/agency-portal/auction-listings?status=listed`
- `POST /api/agency-portal/orders/{id}/publish-auction`
- `POST /api/agency-portal/orders/{id}/withdraw`
- `GET /api/agency-portal/change-requests`
- `POST /api/agency-portal/orders/{id}/change-requests`
- `POST /api/agency-portal/orders/{id}/itinerary-pdf`
- `POST /api/agency-portal/orders/{id}/payment-receipt`

## 本地验证
- `node --check miniapp_agency\\utils\\api.js`：通过
- `node --check miniapp_agency\\pages\\index\\index.js`：通过
- `node --check miniapp_agency\\pages\\orders\\index.js`：通过
- `node --check miniapp_agency\\pages\\hall\\index.js`：通过
- `node --check miniapp_agency\\pages\\tracking\\index.js`：通过
- `node --check miniapp_agency\\pages\\calendar\\index.js`：通过
- `Get-ChildItem miniapp_agency -Recurse -Filter *.json | ConvertFrom-Json`：通过
- `rg "miniapp_dispatch|dispatch-mobile|/api/auction/" miniapp_agency`：无匹配，旅行社端未引用车公司端接口

## 注意
- 当前只新增旅行社小程序源码，尚未绑定真实旅行社小程序 AppID。
- 小程序上传、云端域名配置和线上体验版发布需要单独确认后执行。

# 柚子调度统一小程序

当前目录是统一入口小程序的迁移目标，用于把旅行社端和车公司端合并到一个微信小程序入口中。

## 当前阶段

- 阶段：Phase 3，原旅行社端和车公司端业务页已迁入统一入口小程序。
- 已完成：入口选择、统一登录、登录态桥接、角色路由、车公司业务分包、旅行社业务分包、原业务页路径迁移、包内 API 隔离和页面注册检查。
- 待联调：微信开发者工具真机预览、真实登录态切换、两个端口之间的订单链路回归、微信上传前云端 API/DB 目标检查。

## 迁移原则

- 不直接覆盖 `miniapp_agency` 和 `miniapp_dispatch`。
- 先迁移公共能力：API、session、角色路由、入口和登录。
- 已按模块迁移：旅行社入单、订单大厅、订单跟踪、日历、设置；车公司派车、订单大厅、地图、费用、司机任务、订单导入、搜索、司机车辆信息。
- 每迁移一个模块，必须做端口权限、API 地址、数据库目标、订单链路和角色可见性检查。

## 角色导航

- 车公司管理：首页、派车、订单大厅、地图、财务、我的。
- 车公司调度：首页、派车、地图、我的。
- 车公司运行管理：首页、车辆、地图、我的。
- 司机：首页、任务、地图、费用、我的。
- 旅行社管理：首页、入单、大厅、跟踪、日历、我的。
- 旅行社客服：首页、入单、跟踪、日历、我的。
- 旅行社导游：首页、任务、日历、我的。

## 本地打开

微信开发者工具打开：

```text
C:\PycharmProjects\pythonProject01\Tour Dispatch Operating System\miniapp_yuzu
```

## 当前验证

```powershell
node --check miniapp_yuzu\app.js
node --check miniapp_yuzu\utils\api.js
node --check miniapp_yuzu\utils\session.js
node --check miniapp_yuzu\utils\role-router.js
node --check miniapp_yuzu\utils\port-nav.js
node --check miniapp_yuzu\pages\entry\index.js
node --check miniapp_yuzu\pages\login\index.js
node --check miniapp_yuzu\package_dispatch\pages\home\index.js
node --check miniapp_yuzu\package_agency\pages\home\index.js
```

当前已扩展为递归检查：

```powershell
Get-ChildItem miniapp_yuzu -Recurse -Filter *.js | % { node --check $_.FullName }
Get-ChildItem miniapp_yuzu -Recurse -Filter *.json | % { Get-Content $_.FullName -Raw | ConvertFrom-Json }
```

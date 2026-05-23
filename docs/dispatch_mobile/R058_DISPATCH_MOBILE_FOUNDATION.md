# R058 Dispatch Mobile Foundation

## Scope

本轮新增独立调度移动端 `miniapp_dispatch/`，用于调度员在没有电脑时完成轻量订单导入、快速派车、查看司机位置和个人上下文。

## Runtime

- 登录：`POST /api/dispatch-mobile/login`
- 上下文：`GET /api/dispatch-mobile/context`
- 移动首页：`GET /api/dispatch-mobile/dashboard`
- 共享库状态：`GET /api/dispatch-mobile/shared-state`
- 移动解析：`POST /api/dispatch-mobile/parser/text`

## Dispatcher Context

移动端登录后写入本地 `dispatcher_session`，包含：

- `dispatcher_id`
- `dispatcher_code`
- `dispatcher_name`
- `dispatcher_role`

移动端创建草稿、确认草稿入库时，会写入：

- `created_by_dispatcher`
- `created_by_dispatcher_id`
- `created_by_dispatcher_code`
- `updated_by_dispatcher`
- `updated_by_dispatcher_id`
- `updated_by_dispatcher_code`

## Miniapp Tabs

- 首页：Runtime Dashboard
- 导入：微信订单录入
- 派车：快速派车
- 地图：司机位置
- 我的：Dispatcher Profile

## Shared Database

移动端、Web 后台共用同一个 SQLite runtime DB：

- `orders`
- `order_drafts`
- `assignments`
- `notifications`

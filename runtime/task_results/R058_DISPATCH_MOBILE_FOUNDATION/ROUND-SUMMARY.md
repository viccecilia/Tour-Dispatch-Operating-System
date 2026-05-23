# R058_DISPATCH_MOBILE_FOUNDATION

## 修改了什么

- 新增独立 `miniapp_dispatch/` 调度移动端骨架。
- 新增调度移动端登录、上下文、Dashboard、共享库状态和移动解析 API。
- 为 `orders` 与 `order_drafts` 增加调度员创建/更新上下文字段。
- 新增验证脚本：
  - `scripts/verify_dispatch_mobile_runtime.py`
  - `scripts/verify_shared_orders_sync.py`
- 新增说明文档：
  - `docs/dispatch_mobile/R058_DISPATCH_MOBILE_FOUNDATION.md`

## Dispatcher Runtime 状态

- 调度员可用 `admin / admin123` 登录移动端。
- 登录后写入 `dispatcher_session`。
- 移动端 5 Tab 已建立：首页、导入、派车、地图、我的。
- 订单草稿和确认入库订单可写入调度员上下文。

## Shared DB 验证

- `orders`、`order_drafts`、`assignments`、`notifications` 与 Web Runtime 共库。
- `verify_shared_orders_sync.py` 已校验 API 统计与数据库直读统计一致。

实际验证结果：

- `python -m compileall backend scripts`：通过。
- `python scripts/reset_demo_db.py`：通过，重置后 40 单今日订单、10 单未派车、30 条 active assignments、15 个司机、15 台车。
- `python scripts/verify_dispatch_mobile_runtime.py`：通过，移动调度登录成功，写入草稿和订单 dispatcher context。
- `python scripts/verify_shared_orders_sync.py`：通过，API 与 SQLite 直读统计一致。
- `python scripts/health_check.py`：通过。
- `node --check miniapp_dispatch/...`：通过。

## 未完成风险

- `miniapp_dispatch/` 仍是 Lite Runtime 骨架，视觉和交互未进入精修。
- 地图页读取司机位置，但不做复杂轨迹和调度热力图。
- 登录使用现有 JWT 与 admin/dispatcher 角色，未单独做微信绑定。

## 下一轮建议

- R059：移动调度订单导入与草稿纠错体验。
- R060：移动调度快速派车交互升级。
- R061：移动调度与司机端确认回执联动。

# R059 MOBILE ORDER IMPORT RUNTIME

## 修改了什么

- 升级 `miniapp_dispatch/pages/import/`：
  - 大文本输入框支持微信 / LINE 多订单粘贴。
  - 草稿卡片支持展开详情。
  - 草稿支持原地编辑日期、时间、地点、车型、价格、旅行社和备注。
  - 草稿支持风险高亮：缺少时间、缺少车型、地点异常、重复订单、可疑价格。
  - 草稿确认后进入 `orders`。
- 后端补充移动导入来源：
  - `source_channel = mobile_dispatch`
  - `created_by_dispatcher`
  - `updated_by_dispatcher`
- 新增/扩展移动调度草稿更新 API：
  - `PUT /api/dispatch-mobile/drafts/{id}`
- 扩展验证：
  - `scripts/verify_dispatch_mobile_runtime.py` 校验移动解析、草稿纠错、确认入库、调度员上下文和移动来源。

## Dispatcher Runtime 状态

- 手机端可执行：粘贴文本 -> 批量解析 -> 草稿风险检查 -> 展开修改 -> 确认入库。
- 调度员身份会写入草稿和正式订单。
- Web 后台可通过同库看到移动端生成的草稿和订单。

## Shared DB 验证

- `orders`、`order_drafts`、`assignments`、`notifications` API 统计与 SQLite 直读统计一致。
- 并行运行验证时曾因一个脚本正在新增草稿/通知，另一个脚本同时读取产生瞬时计数差；顺序补跑后通过。

## 验证结果

- `python -m compileall backend scripts`：通过。
- `node --check miniapp_dispatch/utils/api.js`：通过。
- `node --check miniapp_dispatch/pages/import/index.js`：通过。
- `python scripts/reset_demo_db.py`：通过。
- `python scripts/verify_dispatch_mobile_runtime.py`：通过。
- `python scripts/verify_shared_orders_sync.py`：顺序补跑通过。
- `python scripts/health_check.py`：通过。

## 未完成风险

- 移动导入页已可用，但还没有接入旅行社下拉选择。
- 风险高亮目前是轻量规则，不是完整重复订单引擎。
- 小程序真机上还需要人工验证输入体验、展开编辑和确认入库流程。

## 下一轮建议

- R060：移动快速派车 Runtime，重点做手机端选订单、选司机、选车辆、批量派车和冲突提示。

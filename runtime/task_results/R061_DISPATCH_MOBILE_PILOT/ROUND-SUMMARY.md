# R061 DISPATCH MOBILE PILOT

## 修改了什么

- 移动调度首页升级为 Pilot Dashboard：
  - 今日订单
  - 未派车
  - 在线司机
  - 异常订单
  - 待确认
  - 待确认草稿
- 新增 Fleet Status Runtime：
  - 在线
  - 工作中
  - 即将结束
  - 离线
- 新增移动调度提醒入口：
  - 新订单
  - 司机完成/报备类提醒
  - 财务/运营异常提醒
- 新增移动调度审计表：
  - `dispatch_mobile_audit_logs`
- 移动端关键操作写入审计：
  - 移动解析
  - 草稿确认入库
  - 移动派车
- 移动端未派车订单池改为按 `created_by_dispatcher_id` 隔离。
- 新增验证脚本：
  - `scripts/verify_dispatch_mobile_pilot.py`

## Dispatcher Runtime 状态

- 调度员登录后，首页显示自己的移动试运行 Dashboard。
- 移动端只显示当前调度员创建/所属的未派车订单。
- 派车后仍然同步 Web 后台、司机端通知和 `assignments`。

## Shared DB 验证

- 移动端与 Web 继续共用：
  - `orders`
  - `order_drafts`
  - `assignments`
  - `notifications`
- `verify_shared_orders_sync.py` 顺序补跑后通过。

## Real Device Pilot Validation

真机连续测试项已在 Runtime 层准备：

- 录单
- 派车
- 接单
- 地图
- 返回前台
- 弱网

其中真机操作本身仍需人工在微信开发者工具或手机预览中执行。

## 验证结果

- `python -m compileall backend scripts`：通过。
- `node --check miniapp_dispatch/pages/index/index.js`：通过。
- `node --check miniapp_dispatch/pages/dispatch/index.js`：通过。
- `node --check miniapp_dispatch/utils/api.js`：通过。
- `python scripts/reset_demo_db.py`：通过。
- `python scripts/verify_dispatch_mobile_pilot.py`：通过。
- `python scripts/verify_mobile_quick_dispatch.py`：通过。
- `python scripts/health_check.py`：通过。
- `python scripts/verify_shared_orders_sync.py`：顺序补跑通过。

## 未完成风险

- Fleet Status 的 `ending_soon` 目前是占位统计，后续需要按当前时间和订单结束时间计算。
- 在线司机依赖 `location_logs`，如果司机端未上报位置，在线数会是 0。
- 真机 Pilot 的返回前台、弱网体验还需要人工验证。

## 下一轮建议

- R062：移动调度 Pilot 真机修复与手感优化，重点修复真机端录单、派车、提醒、返回前台和弱网场景。

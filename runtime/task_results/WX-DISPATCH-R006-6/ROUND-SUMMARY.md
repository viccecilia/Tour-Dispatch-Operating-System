# WX-DISPATCH-R006-6 轮次总结

## Round Name

演示数据冻结与真机启动修复

## 完成内容

- 新增一键重置演示库脚本。
- 固定 demo 数据集，避免 smoke/demo 数据无限累加。
- 修复小程序 API 地址集中配置。
- 补充启动指南。
- 补充老板演示脚本。
- 补充小程序真机验收清单。
- 完成订单、派车、日历、解析、司机端回归验证。
- 回归后重新重置数据库，保持演示库稳定。

## 固定演示数据

重置后数据：

- 今日订单：40
- 今日已派车：30
- 今日未派车：10
- 服务中：5
- 已完成：2
- 已归库：3
- 司机：10
- 车辆：8
- 旅行社：5
- 草稿：5，其中 3 个 parsed，2 个 failed

## 验证结果

通过：

- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/verify_orders_api.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_calendar_api.py`
- `python scripts/verify_parser_api.py`
- `python scripts/verify_driver_api.py`

本机 8000 被其他服务占用，回归脚本通过 `WX_DISPATCH_BASE_URL=http://127.0.0.1:18765` 指向本项目后端。

## 最终 dashboard 稳定数据

- today_orders: 40
- today_assigned_orders: 30
- today_unassigned_orders: 10
- today_pending_settlement_orders: 35
- unassigned_orders: 10
- assigned_orders: 30
- available_drivers: 10
- available_vehicles: 8
- pending_drafts: 5
- today_parsed_drafts: 3
- failed_drafts: 2
- today_in_service_orders: 5
- today_completed_orders: 2
- today_returned_orders: 3

## 风险

- 真机预览仍需要人工确认局域网 IP、防火墙、微信开发者工具域名校验设置。
- 当前仍是本地 SQLite MVP，不是多人并发生产部署。
- 8000 端口在本机被其他服务占用；演示时建议使用 18765 或先释放 8000。

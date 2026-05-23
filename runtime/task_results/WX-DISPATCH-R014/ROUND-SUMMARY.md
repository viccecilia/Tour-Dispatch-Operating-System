# WX-DISPATCH-R014：Vehicle & Driver Resource System

## 本轮结果
- 车辆台账支持新增、编辑、搜索、车检到期、保险到期、维修状态。
- 司机台账支持新增、编辑、搜索、驾照到期、体检到期。
- 新增资源提醒中心，显示已过期、即将到期、维修状态。
- 新增资源提醒 API：`GET /api/resources/reminders`。
- Dashboard summary 增加资源提醒统计。
- 前端 dashboard 增加资源提醒 KPI。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/verify_resources_api.py`：通过。
- `npm.cmd run build`：通过。
- `npm.cmd run lint`：通过。
- 浏览器检查车辆页：提醒中心、车辆台账、司机台账均可见。

## 风险
- 到期提醒当前固定为 30 天内提醒。
- 本轮未做复杂审批流、附件、证件照片、批量导入。
- 资源验证脚本会写入测试资源，演示前建议重置 demo 数据。

## 下一轮建议
- 增加资源批量导入和 Excel 模板。
- 增加车辆/司机停用原因和历史记录。
- 把资源提醒接入系统顶部通知。

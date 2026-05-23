# WX-DISPATCH-R039：Driver Safety & Incident Runtime

## 修改了什么
- 建立司机异常与安全机制。
- 小程序司机端增加 SOS 和异常报备入口。
- 后端新增司机安全事件接口，写入 `incidents` 并通知调度端。
- 新增安全警报查询，包含高优先级异常和长时间未移动提醒。
- React Driver Monitor 增加安全警报区。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `node --check miniapp/pages/driver/index.js`：通过。
- `python scripts/health_check.py`：通过。
- `python scripts/verify_driver_api.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- `cd frontend && npm.cmd run lint`：通过。
- 验证脚本结果包含：
  - `sos_incident_success: true`
  - `sos_incident_type: accident`
  - `safety_alert_visible: true`

## 协作验收
- 需要人工确认：
  - SOS 按钮是否够明显但不容易误触。
  - 异常分类是否符合司机习惯。
  - 长时间未移动 30 分钟阈值是否合理。
  - 调度端安全警报是否足够醒目。

## 未完成/风险
- 不做复杂安防系统。
- 不接短信、电话、LINE 等外部警报。
- 长时间未移动提醒是查询时计算，不是后台实时推送。

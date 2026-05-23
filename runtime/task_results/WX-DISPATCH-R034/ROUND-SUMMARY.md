# WX-DISPATCH-R034：Driver Notification & Messaging

## 修改了什么
- 建立司机通知中心基础能力。
- 派车后司机可收到新订单通知。
- 司机查询通知时会同步生成即将开始和延误风险提醒。
- 司机端小程序增加通知展示与已读操作。
- 验证脚本覆盖通知生成和已读状态。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `node --check miniapp/pages/driver/index.js`：通过。
- `python scripts/health_check.py`：通过。
- `python scripts/verify_driver_api.py`：通过，验证新订单通知存在，标记已读后状态为 `read`。

## 未完成/风险
- 未接真实短信、LINE、微信模板消息。
- 即将开始和延误提醒为查询时轻量同步，不是后台定时推送。
- 小程序通知 UI 仍需人工真机验收。

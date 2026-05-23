# WX-DISPATCH-R050：Notification Runtime

## 本轮完成内容
- 建立系统内运营提醒 runtime。
- 自动生成未确认订单、未出库、未到达、未上传照片、未提交费用、未入库提醒。
- 司机端提醒接口会同步生成司机相关提醒。
- React Console 新增“运营提醒中心”页面。
- 通知支持单条已读和全部已读。

## 验证结果
- `python -m compileall backend scripts`：通过
- `python scripts/reset_demo_db.py`：通过
- `python scripts/health_check.py`：通过
- `python scripts/verify_driver_api.py`：通过
- `npm.cmd run build`：通过
- `npm.cmd run lint`：通过
- 额外 API 检查：`/api/notifications/summary` 生成未确认、未出库、未入库、未提交费用等提醒；已读接口返回 `read`。

## 协作验收
- 需要人工确认提醒频率是否过高。
- 需要人工确认优先级是否符合运营习惯。
- 需要人工确认哪些提醒应该只给调度，哪些也要给司机。

## 风险
- 不接短信、LINE、WhatsApp、微信订阅消息。
- 当前提醒使用轻量状态规则，不做复杂排班或 SLA 策略。
- 已读通知不会因为同一 source 再次自动重建。

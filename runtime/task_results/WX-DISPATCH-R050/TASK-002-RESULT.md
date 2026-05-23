# TASK-002：司机端提醒同步

## 修改了什么
- 司机获取 `/api/driver/notifications` 时会同步运营提醒。
- 司机端可看到与自己相关的未确认、未出库、费用未提交等提醒。

## 涉及文件
- `backend/services/notification_service.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
- DONE

## 风险
- 小程序只消费现有提醒列表；未接微信订阅消息或真实推送。

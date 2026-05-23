# TASK-002：司机通知 API 与已读状态

## 修改了什么
- 新增司机通知列表接口。
- 新增司机通知标记已读接口。
- 通知按 `driver_id` 隔离，司机只能处理自己的通知。

## 涉及文件
- `backend/api/routes.py`
- `backend/services/notification_service.py`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 本轮未接短信、LINE、微信模板消息，只做系统内通知。

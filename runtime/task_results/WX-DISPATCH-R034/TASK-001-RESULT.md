# TASK-001：司机通知生成

## 修改了什么
- 扩展司机通知服务，支持新订单通知、即将开始提醒、延误风险提醒。
- 派车成功时同步给司机生成 `new_order` 通知。

## 涉及文件
- `backend/services/notification_service.py`
- `backend/services/dispatch_service.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 即将开始和延误提醒目前通过司机通知查询时轻量同步生成，不是后台定时任务。

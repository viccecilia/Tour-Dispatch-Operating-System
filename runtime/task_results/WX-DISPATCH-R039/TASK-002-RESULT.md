# TASK-002：长时间未移动提醒

## 修改了什么
- 新增司机安全警报查询。
- 对执行中、已出库、已到达、服务中的任务，如果最新位置超过 30 分钟未更新，会生成查询侧提醒。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 当前是查询时计算提醒，不是后台定时推送。

# TASK-001 结果

状态：DONE

修改了什么：

- 新增 `backend/services/calendar_service.py`。
- 从 `orders`、`assignments`、`drivers`、`vehicles` 读取日历数据。
- 只读取 `assignments.status = 'active'` 且 `orders.is_deleted = 0` 的有效派车记录。
- 输出统一日历 item 字段，包括订单、司机、车辆、颜色、标题和副标题。
- 增加颜色图例和月汇总数据。

涉及文件：

- `backend/services/calendar_service.py`

验证方式：

- `python -m compileall backend`
- `python scripts/verify_calendar_api.py`

是否完成：是

风险：

- 日历服务为只读展示，不处理拖拽调整和复杂排班规则。

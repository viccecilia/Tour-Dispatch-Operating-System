# TASK-004：已读状态

## 修改了什么
- 复用并验证现有已读接口：
  - `POST /api/notifications/{id}/read`
  - `POST /api/notifications/read-all`
  - `POST /api/driver/notifications/{id}/read`
- 通知页面支持单条已读和全部已读。

## 涉及文件
- `backend/api/routes.py`
- `frontend/src/pages/NotificationsPage.tsx`

## 验证方式
- 额外 API 验证：标记通知已读后返回 `status = read`
- `python scripts/verify_driver_api.py`

## 是否完成
- DONE

## 风险
- 已读后同一 `source_id` 不会重复生成，若需要周期性重复提醒，需要下一轮增加提醒周期策略。

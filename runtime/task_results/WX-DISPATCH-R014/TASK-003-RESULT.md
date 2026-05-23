# TASK-003：到期提醒与维修状态

## 修改了什么
- 新增资源提醒计算：30 天内到期、已过期、日期异常、维修状态。
- 新增 `GET /api/resources/reminders`。
- Dashboard summary 返回资源提醒数量。

## 涉及文件
- `backend/services/resource_service.py`
- `backend/api/routes.py`
- `backend/services/dashboard_service.py`
- `frontend/src/pages/DashboardPage.tsx`

## 验证方式
- `python scripts/verify_resources_api.py`

## 是否完成
DONE

## 风险
- 30 天阈值是当前默认规则，需要运营确认是否改成 7/15/30/60 天多级提醒。

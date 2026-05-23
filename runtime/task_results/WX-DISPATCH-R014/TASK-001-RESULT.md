# TASK-001：车辆台账

## 修改了什么
- 车辆资源增加车检到期、保险到期、维修状态字段。
- 车辆列表返回提醒信息与 alert_level。
- 前端车辆台账支持新增、编辑、搜索、状态展示。

## 涉及文件
- `backend/services/resource_service.py`
- `backend/db/schema.sql`
- `frontend/src/pages/VehiclesPage.tsx`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_resources_api.py`
- `npm.cmd run build`

## 是否完成
DONE

## 风险
- 当前不做审批流，车辆信息保存后直接生效。

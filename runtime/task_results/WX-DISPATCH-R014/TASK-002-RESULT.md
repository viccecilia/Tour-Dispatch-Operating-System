# TASK-002：司机台账

## 修改了什么
- 司机资源增加驾照到期、体检到期字段。
- 司机列表返回提醒信息与 alert_level。
- 前端司机台账支持新增、编辑、搜索、状态展示。

## 涉及文件
- `backend/services/resource_service.py`
- `backend/db/schema.sql`
- `frontend/src/pages/VehiclesPage.tsx`

## 验证方式
- `python scripts/verify_resources_api.py`
- `npm.cmd run build`

## 是否完成
DONE

## 风险
- 司机资质附件、照片、证件扫描件不在本轮范围。

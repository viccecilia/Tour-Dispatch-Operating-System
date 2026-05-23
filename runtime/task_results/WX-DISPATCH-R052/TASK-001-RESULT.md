# TASK-001 照片 timeline / assignment evidence

## 修改了什么
- 新增 assignment 维度执行证据链聚合能力。
- 将司机报备、工作流事件、照片证据、费用小票合并为统一 timeline。
- 证据链 summary 返回照片数、报备数、费用数、可下载文件数。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `frontend/src/types/api.ts`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 本轮不做复杂审核，只做证据展示与下载入口。

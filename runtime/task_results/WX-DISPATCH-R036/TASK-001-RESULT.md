# TASK-001：司机照片上传后端

## 修改了什么
- 新增 `driver_evidence_uploads` 上传记录表。
- 新增司机照片上传服务，支持 base64 图片保存到 `runtime/uploads/driver_evidence/`。
- 新增司机照片查询服务。
- 上传后会尝试把最近相关 `driver_reports.photo_url` 补上照片 URL。

## 涉及文件
- `backend/db/schema.sql`
- `backend/db/database.py`
- `backend/services/driver_service.py`
- `backend/api/routes.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 当前是本地文件存储，不是对象存储；迁移服务器时要一起迁移 `runtime/uploads/`。

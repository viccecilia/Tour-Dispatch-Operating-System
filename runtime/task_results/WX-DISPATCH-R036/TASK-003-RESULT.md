# TASK-003：上传记录查询与图片访问

## 修改了什么
- 新增 `GET /api/driver/evidence` 查询司机照片上传记录。
- 新增 `POST /api/driver/evidence` 上传照片。
- 后端支持访问 `/uploads/driver_evidence/...` 本地图片文件。

## 涉及文件
- `backend/api/routes.py`
- `backend/services/driver_service.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 检查 `runtime/uploads/driver_evidence/` 存在测试图片。

## 是否完成
DONE

## 风险
- 当前未做缩略图生成和图片压缩服务，依赖小程序端选择压缩图。

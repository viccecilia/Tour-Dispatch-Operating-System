# TASK-002 小票记录 / evidence download

## 修改了什么
- 司机费用记录进入证据链 timeline。
- `receipt_photo_url` 会作为可下载证据返回。
- 司机上传照片的 `file_url` 会进入 download files。

## 涉及文件
- `backend/services/driver_service.py`
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/pages/OrdersPage.tsx`

## 验证方式
- `python scripts/verify_driver_api.py` 验证：
  - `assignment_evidence_photo_count = 3`
  - `assignment_evidence_expense_count = 2`
  - `evidence_download_files_visible = true`

## 是否完成
DONE

## 风险
- 下载入口使用当前后端 `/uploads/...` 静态文件服务；真实云存储不在本轮范围。

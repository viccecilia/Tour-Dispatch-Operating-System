# WX-DISPATCH-R036：Driver Media & Evidence Upload

## 修改了什么
- 建立司机照片与证据上传能力。
- 新增照片上传记录表 `driver_evidence_uploads`。
- 新增上传 API 和查询 API。
- 图片保存到 `runtime/uploads/driver_evidence/`。
- 小程序司机端增加接客照片、完成照片、车况照片入口。
- 验证脚本覆盖图片上传和记录查询。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `node --check miniapp/pages/driver/index.js`：通过。
- `python scripts/health_check.py`：通过。
- `python scripts/verify_driver_api.py`：通过。
- 验证结果包含：
  - `evidence_upload_success: true`
  - `evidence_upload_type: pickup`
  - `evidence_visible: true`

## 协作验收
- 需要在微信开发者工具或真机确认：
  - 拍照/相册选择是否顺手。
  - 三类照片按钮是否够清楚。
  - 上传后记录是否能预览。

## 未完成/风险
- 不做视频上传。
- 不做复杂审核系统。
- 当前是本地文件存储，正式部署前需要规划备份或对象存储。
